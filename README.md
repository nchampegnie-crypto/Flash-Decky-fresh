# FlashDecky (Fresh v1.0.0)

A clean, minimal Streamlit app that turns a list of terms & definitions into
**8-up printable index cards** with dashed cut lines and duplex-safe backs
(mirrored for long-edge by default).

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Features
- Paste list or type inline (simple formats: `term - definition`, `term: definition`,
  `term — definition`, or dictionary style like `abhor (v.) to hate…`).  
- Quick **Review & edit** table before export.
- **8 cards per page** (US Letter), dashed guides, white layout.
- **Duplex** options (long- or short-edge, mirrored backs).
- **Footer text** per card (e.g., subject • lesson).

No external OCR or images in this fresh baseline (keeps it stable).

