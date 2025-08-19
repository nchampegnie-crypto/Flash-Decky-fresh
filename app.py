import io, re, csv
from typing import List, Tuple
import streamlit as st
import pandas as pd

from parse_utils import parse_text_to_rows
from pdf_utils import build_pdf
from ocr_utils import ocr_image_to_text, OcrError

st.set_page_config(page_title="FlashDecky", page_icon="⚡", layout="wide")

# Session defaults
st.session_state.setdefault("step", 1)
st.session_state.setdefault("raw_text", "")
st.session_state.setdefault("rows", [])
st.session_state.setdefault("subject", "")
st.session_state.setdefault("lesson", "")
st.session_state.setdefault("footer_tpl", "{subject} • {lesson}")

# Sidebar Progress
st.sidebar.title("Progress")
steps = ["Upload/Paste", "Review & Edit", "Download PDF"]
for i, name in enumerate(steps, start=1):
    marker = "➡️ " if st.session_state["step"] == i else ("✅ " if st.session_state["step"] > i else "○ ")
    st.sidebar.write(f"{marker} {i}) {name}")
if st.sidebar.button("Reset"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

st.title("⚡ FlashDecky")
st.caption("Turn any list into 8-per-page, duplex-ready flash cards.")

# Step 1
if st.session_state["step"] == 1:
    st.header("1) Upload or paste your list")
    tab1, tab2, tab3 = st.tabs(["Paste text", "Upload file (CSV/XLSX)", "Paste table / OCR screenshot"])

    with tab1:
        st.subheader("Paste free-form text")
        st.session_state["raw_text"] = st.text_area(
            "Your list",
            value=st.session_state.get("raw_text",""),
            height=220,
            placeholder="1) term — definition\n2) another term: definition\n• third term - definition"
        )
        if st.button("Submit pasted text"):
            rows = parse_text_to_rows(st.session_state["raw_text"])
            if not rows:
                st.warning("Could not find any term/definition pairs. Try a different format.")
            else:
                st.session_state["rows"] = rows
                st.session_state["step"] = 2
                st.rerun()

    with tab2:
        st.subheader("Upload CSV or Excel")
        up = st.file_uploader("Choose file", type=["csv","xlsx"])
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    df = pd.read_csv(up)
                else:
                    df = pd.read_excel(up)
                st.dataframe(df.head(20))
                cols = list(df.columns)
                c1, c2 = st.columns(2)
                with c1:
                    front_col = st.selectbox("Front of card (term)", cols, index=0 if cols else None, key="front_col")
                with c2:
                    back_col = st.selectbox("Back of card (definition)", cols, index=1 if len(cols)>1 else 0, key="back_col")
                if st.button("Use these columns"):
                    rows = [(str(a).strip(), str(b).strip()) for a,b in zip(df[front_col], df[back_col]) if (str(a).strip() or str(b).strip())]
                    if not rows:
                        st.warning("No non-empty rows found.")
                    else:
                        st.session_state["rows"] = rows
                        st.session_state["step"] = 2
                        st.rerun()
            except Exception as e:
                st.error(f"Could not read file: {e}")

    with tab3:
        st.subheader("Paste two-column table (TSV) or upload screenshot (OCR)")
        pasted = st.text_area("Paste table (tab-separated)", height=160, placeholder="term<TAB>definition\nterm<TAB>definition")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("Use pasted table"):
                rows = []
                try:
                    for line in pasted.splitlines():
                        if not line.strip(): continue
                        if "\t" in line:
                            a,b = line.split("\t",1)
                        else:
                            parts = [p.strip() for p in re.split(r",", line, maxsplit=1)]
                            if len(parts)==2: a,b = parts
                            else: a,b = line.strip(), ""
                        rows.append((a.strip(), b.strip()))
                except Exception as e:
                    st.error(f"Could not parse table: {e}")
                    rows = []
                if not rows:
                    st.warning("No rows found. Make sure there is a tab or a comma between term and definition.")
                else:
                    st.session_state["rows"] = rows
                    st.session_state["step"] = 2
                    st.rerun()
        with c2:
            img = st.file_uploader("Upload screenshot (PNG/JPG)", type=["png","jpg","jpeg"], key="ocr_img")
            if st.button("Extract text from image") and img is not None:
                with st.spinner("Running OCR…"):
                    api_key = st.secrets.get("OCR_SPACE_API_KEY", None) if hasattr(st, "secrets") else None
                    try:
                        text, meta = ocr_image_to_text(img.read(), api_key)
                        if not text:
                            st.info("OCR disabled or returned empty text. Paste your list manually above.")
                        else:
                            st.session_state["raw_text"] = text
                            rows = parse_text_to_rows(text)
                            if not rows:
                                st.info("OCR succeeded, but parsing failed. The extracted text was added to the Paste tab; please edit/submit from there.")
                            else:
                                st.session_state["rows"] = rows
                                st.session_state["step"] = 2
                                st.success("OCR extracted & parsed successfully!")
                                st.rerun()
                    except OcrError as e:
                        st.error(f"OCR failed: {e}")
                    except Exception as e:
                        st.error("Unexpected OCR error. Try a clearer/smaller image.")

# Step 2
if st.session_state["step"] == 2:
    st.header("2) Review & Edit")
    df = pd.DataFrame(st.session_state["rows"], columns=["Front of Flash Card (term)", "Back of Flash Card (definition)"])
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="editor")
    if st.button("Continue to PDF"):
        rows = []
        for _, r in edited.iterrows():
            t = str(r.iloc[0]).strip()
            d = str(r.iloc[1]).strip()
            if t or d: rows.append((t,d))
        if not rows:
            st.warning("Please keep at least one row.")
        else:
            st.session_state["rows"] = rows
            st.session_state["step"] = 3
            st.rerun()

# Step 3
if st.session_state["step"] == 3:
    st.header("3) Download PDF")
    st.subheader("Card footer (subject • lesson)")
    use_footer = st.checkbox("Include footer text on cards", value=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state["subject"] = st.text_input("Subject", value=st.session_state.get("subject",""))
    with c2:
        st.session_state["lesson"] = st.text_input("Lesson / Unit", value=st.session_state.get("lesson",""))
    st.session_state["footer_tpl"] = st.text_input("Footer template", value=st.session_state.get("footer_tpl","{subject} • {lesson}"))

    with st.expander("Print alignment"):
        duplex = st.selectbox("Duplex mode", ["Long-edge (not mirrored)", "Short-edge"])
        x_mm = st.number_input("Back page offset X (mm)", value=0.0, step=0.1)
        y_mm = st.number_input("Back page offset Y (mm)", value=0.0, step=0.1)

    def mm_to_pt(mm: float) -> float: return mm * 72.0 / 25.4
    subject = st.session_state.get("subject","").strip()
    lesson = st.session_state.get("lesson","").strip()
    tpl = st.session_state.get("footer_tpl","{subject} • {lesson}")
    rows = st.session_state.get("rows", [])

    fronts, backs = [], []
    for idx, (term, definition) in enumerate(rows, start=1):
        footer = tpl.format(subject=subject, lesson=lesson, unit=lesson, index=idx, page=(1 + (idx-1)//8)) if use_footer else ""
        fronts.append((term or "", footer))
        backs.append((definition or "", footer))

    out_path = "flashdecky_cards.pdf"
    if st.button("Generate PDF"):
        try:
            build_pdf(out_path, fronts=fronts, backs=backs, duplex_mode=duplex,
                      back_offset_x=mm_to_pt(x_mm), back_offset_y=mm_to_pt(y_mm))
            with open(out_path, "rb") as f:
                st.download_button("Download PDF", f, file_name="flashdecky_cards.pdf", mime="application/pdf")
            st.success("PDF generated. Use your printer's duplex option and the selected binding setting.")
        except Exception as e:
            st.error(f"Failed to build PDF: {e}")
