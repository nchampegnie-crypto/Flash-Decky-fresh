
import re
import io
from dataclasses import dataclass
from typing import List, Tuple

import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

# ============== Styling ==============
with open("styles.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="FlashDecky – fresh", layout="wide")

st.title("FlashDecky – fresh start")

st.markdown("Paste your list below (one item per line).\
 Accepts `term - definition`, `term: definition`, `term — definition`, \
 or dictionary-like `abhor (v.) to hate, detest …`.")


# ============== Parser ==============
_sep = r"[:\-–—]"  # colon, hyphen, en/em dash

def _normalize(s: str) -> str:
    s = s.replace("—", "—")  # keep em dash as is (visual); regex handles
    return re.sub(r"[ \t]+", " ", s).strip()

def looks_like_new_item(line: str) -> bool:
    line = line.strip()
    if not line: 
        return False
    # bullets or numbered
    if re.match(r"^(\d+[\)\.]\s+|[-*•]\s+)", line):
        return True
    # starts like "term - def" or "term: def"
    if re.match(r"^[A-Za-z][\w'\-]*(?:\s+[A-Za-z][\w'\-]*)*\s+(?:%s|\()" % _sep, line):
        return True
    return False

def coalesce_lines(text: str) -> List[str]:
    parts = []
    current = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if looks_like_new_item(line):
            if current.strip():
                parts.append(current.strip())
            current = line
        else:
            if line.strip():
                if current:
                    current += " " + line.strip()
                else:
                    current = line.strip()
    if current.strip():
        parts.append(current.strip())
    # Also split on blank-blank as separate items
    final = []
    for chunk in "\n\n".join(parts).split("\n\n"):
        if chunk.strip():
            final.append(chunk.strip())
    return final

def parse_item(line: str) -> Tuple[str, str]:
    line = line.strip()
    # remove bullets / numbering
    line = re.sub(r"^(\d+[\)\.\-]*\s+|[-*•]\s+)", "", line).strip()

    # dictionary form: take first word as term if followed by '(' or space + punctuation part-of-speech
    m = re.match(r"^(?P<term>[A-Za-z][\w'\-]*)\s*(\([^)]*\))?\s*(?P<rest>.*)$", line)
    if m:
        term = m.group("term").strip()
        rest = m.group("rest").strip()
        # If explicit separator appears early, respect it
        m2 = re.match(r"^(?P<lhs>.+?)\s*(%s)\s*(?P<rhs>.+)$" % _sep, line)
        if m2:
            term_clean = _normalize(m2.group("lhs"))
            defn = _normalize(m2.group("rhs"))
            return term_clean, defn
        # Otherwise treat "rest" as definition
        if rest:
            return _normalize(term), _normalize(rest)
    # Fallback: split on first separator
    m3 = re.match(r"^(?P<lhs>.+?)\s*(%s)\s*(?P<rhs>.+)$" % _sep, line)
    if m3:
        return _normalize(m3.group("lhs")), _normalize(m3.group("rhs"))
    # last resort: first token is term, rest definition
    toks = line.split(" ", 1)
    if len(toks) == 2:
        return _normalize(toks[0]), _normalize(toks[1])
    return _normalize(line), ""

def parse_text_block(text: str) -> List[Tuple[str, str]]:
    items = []
    for chunk in coalesce_lines(text):
        term, definition = parse_item(chunk)
        if term:
            items.append((term, definition))
    return items


# ============== Inputs ==============
default_text = "1. munch - to chew food loudly and completely\n2) bellowed — to have shouted in a loud deep voice"

src_tab = st.tabs(["Paste text"])[0]
with src_tab:
    pasted = st.text_area("Your list", value=default_text, height=200, key="pasted_txt")

if st.button("Next: Review & edit", type="primary"):
    st.session_state["parsed_items"] = parse_text_block(pasted)

items = st.session_state.get("parsed_items", parse_text_block(default_text))

st.header("2) Review & edit")
df = pd.DataFrame(items, columns=["Front of Flash Card (term)", "Back of Flash Card (definition)"])
edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="edit_grid")
st.caption("Click a cell to edit. Add/remove rows if needed.")


# ============== PDF generation ==============
st.header("3) Download PDF")

with st.expander("Print alignment", expanded=False):
    duplex = st.selectbox("Duplex mode", ["Long-edge (mirrored back)", "Long-edge (no mirror)", "Short-edge (mirrored back)", "Short-edge (no mirror)"], index=0)
    back_offset_x = st.number_input("Back page offset X (mm)", value=0.0, step=0.25)
    back_offset_y = st.number_input("Back page offset Y (mm)", value=0.0, step=0.25)
    show_mark = st.checkbox("Show tiny corner marker", value=False)

st.subheader("Card footer (subject • lesson)")
include_footer = st.checkbox("Include footer text on cards", value=True)
colA, colB = st.columns(2)
with colA:
    subj = st.text_input("Subject", value="")
with colB:
    less = st.text_input("Lesson", value="")
footer_template = st.text_input("Footer template", value="{subject} • {lesson}")

def build_pdf(data: List[Tuple[str,str]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter  # 612 x 792 points

    margin = 36  # 0.5in
    cols, rows = 2, 4  # 8-up
    grid_w, grid_h = W - 2*margin, H - 2*margin
    card_w, card_h = grid_w/cols, grid_h/rows

    def draw_grid_guides():
        c.setDash(3,3)
        c.setStrokeColor(colors.lightgrey)
        for i in range(1, cols):
            x = margin + i*card_w
            c.line(x, margin, x, H-margin)
        for j in range(1, rows):
            y = margin + j*card_h
            c.line(margin, y, W-margin, y)
        c.rect(margin, margin, grid_w, grid_h)
        c.setDash()  # solid again

    def draw_card_text(x, y, term, small, align="center"):
        # center box
        tx = c.beginText()
        tx.setTextOrigin(x + card_w/2, y + card_h/2 + 6)
        tx.setFont("Helvetica-Bold", 16)
        # multi-line center: wrap term if too long
        max_chars = 26
        lines = []
        t = term
        while len(t) > max_chars:
            cut = t.rfind(" ", 0, max_chars)
            if cut <= 0: cut = max_chars
            lines.append(t[:cut])
            t = t[cut:].lstrip()
        lines.append(t)
        # adjust vertical offset
        yoff = 10*(len(lines)-1)
        for i, ln in enumerate(lines):
            width = c.stringWidth(ln, "Helvetica-Bold", 16)
            c.drawString(x + (card_w - width)/2, y + card_h/2 + (len(lines)-1-i)*14, ln)
        # footer
        if include_footer and (subj or less):
            ft = footer_template.format(subject=subj, lesson=less).strip()
            if ft:
                c.setFont("Helvetica", 8.5)
                c.setFillColor(colors.grey)
                c.drawRightString(x + card_w - 4, y + 6, ft)
                c.setFillColor(colors.black)

    def draw_card_back(x, y, definition):
        # definition centered-ish
        c.setFont("Helvetica", 12)
        # wrap definition
        max_width = card_w - 18
        words = definition.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if c.stringWidth(test, "Helvetica", 12) <= max_width:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        # print lines centered
        baseline = y + card_h/2 + (len(lines)*7)
        for i, ln in enumerate(lines):
            w = c.stringWidth(ln, "Helvetica", 12)
            c.drawString(x + (card_w - w)/2, baseline - i*14, ln)

        if include_footer and (subj or less):
            ft = footer_template.format(subject=subj, lesson=less).strip()
            if ft:
                c.setFont("Helvetica", 8.5)
                c.setFillColor(colors.grey)
                c.drawRightString(x + card_w - 4, y + 6, ft)
                c.setFillColor(colors.black)

    # Build pages
    # chunk data into 8 per sheet
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    for sheet_items in chunks(data, cols*rows):
        # FRONT
        draw_grid_guides()
        for idx, (term, definition) in enumerate(sheet_items):
            col = idx % cols
            row = rows - 1 - (idx // cols)  # origin bottom-left; we want row 0 at top
            x = margin + col*card_w
            y = margin + row*card_h
            draw_card_text(x, y, term, small=False)
        c.showPage()

        # BACK
        draw_grid_guides()
        # Determine mirroring
        mirror_x = "mirrored" in duplex
        short_edge = duplex.startswith("Short-edge")
        for idx, (term, definition) in enumerate(sheet_items):
            col = idx % cols
            row_index = rows - 1 - (idx // cols)
            if mirror_x:
                col = (cols-1) - col
            if short_edge:
                row_index = (rows-1) - row_index
            x = margin + col*card_w + back_offset_x*mm
            y = margin + row_index*card_h + back_offset_y*mm
            draw_card_back(x, y, definition)
        if show_mark:
            c.setFillColor(colors.red)
            c.circle(W-6, H-6, 2, fill=1)
            c.setFillColor(colors.black)
        c.showPage()

    c.save()
    return buf.getvalue()


if st.button("Generate PDF", type="primary"):
    # get edited rows
    rows = []
    for _,r in edited.iterrows():
        t = str(r.iloc[0]).strip()
        d = str(r.iloc[1]).strip()
        if t:
            rows.append((t,d))
    if not rows:
        st.error("Add at least one card.")
    else:
        pdf_bytes = build_pdf(rows)
        st.download_button("Download PDF", data=pdf_bytes, file_name="flashdecky_cards.pdf", mime="application/pdf")

