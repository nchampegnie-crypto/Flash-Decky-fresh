import re
from typing import List, Tuple

SEP_PATTERNS = [
    r"\t",                    # tab
    r"(?<!\():(?![^()]*\))",  # colon not inside parentheses
    r"\s—\s|\s–\s|\s-\s",     # spaced em/en dash or hyphen
]

NEWROW = re.compile(r"^\s*((\d+)[\.\)]\s+|[-*•]\s+)")
DICT_STYLE = re.compile(r"^\s*([^\(\n\r]+)\s*\([^)]+\)\s*(.+)$")

def smart_split(line: str) -> Tuple[str, str]:
    # Dictionary style "term (pos.) definition"
    m = DICT_STYLE.match(line.strip())
    if m:
        term = m.group(1).strip()
        definition = m.group(2).strip()
        return term, definition

    for pat in SEP_PATTERNS:
        m = re.search(pat, line)
        if m:
            idx = m.start()
            term = line[:idx].strip()
            definition = line[m.end():].strip()
            if term and definition:
                return term, definition
    # Fallback: single word term? else treat entire line as term
    return line.strip(), ""

def parse_text_to_rows(text: str) -> List[Tuple[str,str]]:
    """
    Robust parsing:
    - Starts a new row if line begins with number.) or bullet.
    - Otherwise, tries to split term/definition using separators.
    - Continuation lines append to the last definition if they don't look like new rows.
    """
    lines = [l.rstrip() for l in text.splitlines()]
    rows: List[Tuple[str,str]] = []
    buf_term = None
    buf_def = ""

    def flush():
        nonlocal buf_term, buf_def
        if buf_term is not None:
            rows.append((buf_term.strip(), buf_def.strip()))
            buf_term, buf_def = None, ""

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if NEWROW.match(line):
            line2 = NEWROW.sub("", line).strip()
            term, definition = smart_split(line2) if line2 else ("", "")
            flush()
            buf_term = term or line2
            buf_def = definition
        else:
            term, definition = smart_split(line)
            if definition:
                flush()
                buf_term = term
                buf_def = definition
            else:
                if buf_term is None:
                    buf_term = term
                else:
                    sep = " " if buf_def and not buf_def.endswith("-") else ""
                    buf_def = (buf_def + sep + line).strip()
    flush()
    rows = [(t, d) for (t, d) in rows if t or d]
    return rows
