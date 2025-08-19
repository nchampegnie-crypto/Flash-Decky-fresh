from __future__ import annotations
import io, time, requests
from typing import Optional, Tuple
from PIL import Image

OCR_ENDPOINT = "https://api.ocr.space/parse/image"

class OcrError(Exception):
    pass

def _prep_image_for_ocr(file_bytes: bytes, max_side: int = 2000) -> bytes:
    im = Image.open(io.BytesIO(file_bytes))
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()

def ocr_image_to_text(file_bytes: bytes, api_key: Optional[str], language: str = "eng",
                      timeout: float = 30.0, max_retries: int = 2, backoff: float = 1.5):
    if not api_key:
        return "", {"note": "OCR disabled: missing OCR_SPACE_API_KEY"}

    prepared = _prep_image_for_ocr(file_bytes)
    files = {"file": ("upload.png", prepared, "image/png")}
    data = {"language": language, "OCREngine": 2, "isTable": True, "scale": True, "isCreateSearchablePdf": False}
    headers = {"apikey": api_key}

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(OCR_ENDPOINT, files=files, data=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            js = resp.json()
            if js.get("IsErroredOnProcessing"):
                msg = js.get("ErrorMessage") or js.get("ErrorMessageDetails") or "Unknown OCR error"
                raise OcrError(str(msg))
            results = js.get("ParsedResults") or []
            text = "\n".join((r.get("ParsedText") or "").strip() for r in results).strip()
            return text, {"provider": "ocr.space", "raw": js}
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                import time as _t; _t.sleep(backoff ** attempt)
            else:
                raise OcrError(str(e)) from e
    raise OcrError(str(last_err) if last_err else "Unknown OCR failure")
