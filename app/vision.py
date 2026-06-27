"""
Drawing -> outline (OpenCV).

Given a side-view photo, scan, or screenshot, find the dominant silhouette and
return it split into an UPPER chain (roofline) and a LOWER chain (sill), already
shaped like the frontend's topProfile / bottomProfile (x in 0..1, value in px).

Honest scope: this *suggests* an outline to trace against. It does not read
dimension annotations off the page — the user still sets scale in the UI (two
clicks + a known length). Auto-reading hand-drawn dimensions reliably is a
research problem, not a checkbox, and pretending otherwise would waste the
friend's filament on wrong-sized parts.
"""
from __future__ import annotations
from typing import Dict, List


class VisionUnavailable(RuntimeError):
    pass


def _imports():
    try:
        import cv2
        import numpy as np
        return cv2, np
    except Exception as e:  # pragma: no cover
        raise VisionUnavailable(
            "OpenCV/numpy not importable. `pip install opencv-python-headless numpy`. "
            "Original error: " + repr(e)
        )


def extract_outline(image_bytes: bytes, simplify: float = 0.004) -> Dict:
    cv2, np = _imports()

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes.")
    h, w = img.shape[:2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive: works for both dark-lines-on-white drawings and photos.
    edges = cv2.Canny(gray, 60, 160)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        # fallback: Otsu threshold then contour
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No outline found. Try a cleaner line drawing or higher contrast.")

    cnt = max(contours, key=cv2.contourArea)
    eps = simplify * cv2.arcLength(cnt, True)
    cnt = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2)

    xs = cnt[:, 0]
    x_min, x_max = int(xs.min()), int(xs.max())
    span = max(1, x_max - x_min)

    # Split outline into upper/lower by walking x and keeping, per x-bucket, the
    # topmost and bottommost y. (Image y grows downward, so "top" = min y.)
    buckets: Dict[int, List[int]] = {}
    for x, y in cnt:
        buckets.setdefault(int(x), []).append(int(y))
    top, bot = [], []
    for x in sorted(buckets):
        ys = buckets[x]
        xf = (x - x_min) / span
        top.append([round(xf, 4), int(min(ys))])     # roofline (in px, y-down)
        bot.append([round(xf, 4), int(max(ys))])      # sill line (in px, y-down)

    return {
        "image": {"width": w, "height": h},
        "bbox": {"x": x_min, "y": int(cnt[:, 1].min()),
                 "w": span, "h": int(cnt[:, 1].max() - cnt[:, 1].min())},
        "outline_px": cnt.tolist(),
        # ready to drop into the UI once the user sets scale:
        "topProfile_px": top,
        "bottomProfile_px": bot,
        "note": "Values are pixels (y grows downward). Set scale in the UI to convert to mm.",
    }
