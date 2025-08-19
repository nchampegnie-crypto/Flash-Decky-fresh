from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import List, Tuple

try:
    pdfmetrics.registerFont(TTFont("Inter", "Inter-Regular.ttf"))
    BASE_FONT = "Inter"
except:
    BASE_FONT = "Helvetica"

def _draw_dashed_grid(c, x0, y0, col_w, row_h):
    c.saveState()
    c.setDash(4, 4)
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.6)
    for i in range(3):
        x = x0 + i * col_w
        c.line(x, y0, x, y0 + 4 * row_h)
    for j in range(5):
        y = y0 + j * row_h
        c.line(x0, y, x0 + 2 * col_w, y)
    c.restoreState()

def _fit_text(c, text, x, y, w, h, max_font=14, min_font=8, footer=None):
    from reportlab.platypus import Paragraph, Frame
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    for fs in range(max_font, min_font-1, -1):
        style = ParagraphStyle("card", fontName=BASE_FONT, fontSize=fs, leading=fs*1.18,
                               textColor=colors.black, alignment=TA_LEFT)
        p = Paragraph(text.replace("\n","<br/>"), style)
        f = Frame(x+8, y+8, w-16, h-20, showBoundary=0)
        ok = f.addFromList([p], c)
        if ok == []:
            break
    if footer:
        c.setFont(BASE_FONT, 8)
        c.setFillColor(colors.grey)
        c.drawRightString(x+w-6, y+6, footer)

def build_pdf(path: str, fronts: List[Tuple[str,str]], backs: List[Tuple[str,str]],
              duplex_mode: str = "Long-edge (not mirrored)",
              back_offset_x: float = 0.0, back_offset_y: float = 0.0):
    page_w, page_h = letter
    margin = 0.5 * inch
    grid_w = page_w - 2*margin
    grid_h = page_h - 2*margin
    col_w = grid_w / 2.0
    row_h = grid_h / 4.0
    c = canvas.Canvas(path, pagesize=letter)

    def draw_grid(items, is_front=True):
        x0, y0 = margin, margin
        _draw_dashed_grid(c, x0, y0, col_w, row_h)
        idx = 0
        for r in range(4):
            for col in range(2):
                x = x0 + col * col_w
                y = y0 + (3 - r) * row_h
                if idx < len(items):
                    text, footer = items[idx]
                    _fit_text(c, text, x, y, col_w, row_h, max_font=18 if is_front else 14, footer=footer)
                idx += 1
        c.showPage()

    n = max(len(fronts), len(backs))
    per_page = 8
    for start in range(0, n, per_page):
        f_items = fronts[start:start+per_page]
        b_items = backs[start:start+per_page]

        # Front side
        draw_grid(f_items, is_front=True)

        # Back side
        if duplex_mode == "Short-edge":
            c.saveState()
            c.translate(page_w/2.0, page_h/2.0)
            c.rotate(180)
            c.translate(-page_w/2.0, -page_h/2.0)
        c.translate(back_offset_x, back_offset_y)
        draw_grid(b_items, is_front=False)

    c.save()
