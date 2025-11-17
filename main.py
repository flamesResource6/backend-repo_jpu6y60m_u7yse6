import os
import io
import urllib.parse
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Wallpapers API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Curated set of 4K-friendly wallpapers (Unsplash sources)
WALLPAPERS = [
    {
        "id": "w1",
        "title": "Peaks at Dawn",
        "src": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=3840&q=80&auto=format&fit=crop",
    },
    {
        "id": "w2",
        "title": "Forest Mist",
        "src": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=3840&q=80&auto=format&fit=crop",
    },
    {
        "id": "w3",
        "title": "Desert Dunes",
        "src": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=3840&q=80&auto=format&fit=crop",
    },
    {
        "id": "w4",
        "title": "Starry Night",
        "src": "https://images.unsplash.com/photo-1444703686981-a3abbc4d4fe3?w=3840&q=80&auto=format&fit=crop",
    },
    {
        "id": "w5",
        "title": "Aurora Sky",
        "src": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=3840&q=80&auto=format&fit=crop",
    },
]


@app.get("/health")
@app.get("/")
def health():
    return {"status": "ok", "message": "Wallpapers backend running"}


@app.get("/api/wallpapers")
def list_wallpapers():
    """Return a catalog of available wallpapers. Frontend should request watermarked images via /api/watermark?url=..."""
    return {"items": WALLPAPERS}


def _load_image_from_url(url: str) -> Image.Image:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid URL scheme")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch source image")
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to load image from URL")


def _apply_watermark(img: Image.Image, text: str = "made by afthab") -> Image.Image:
    width, height = img.size
    base = img.copy()
    watermark_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    font_size = max(24, width // 40)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text_padding = max(12, font_size // 3)

    # Text size and position
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    x = width - text_w - text_padding
    y = height - text_h - text_padding

    # Background rectangle
    bg_padding_x = text_padding // 2
    bg_padding_y = text_padding // 3
    rect_coords = (
        x - bg_padding_x,
        y - bg_padding_y,
        x + text_w + bg_padding_x,
        y + text_h + bg_padding_y,
    )
    draw.rectangle(rect_coords, fill=(0, 0, 0, 90))

    # Text with subtle shadow
    shadow_offset = max(1, font_size // 20)
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 220))

    watermarked = Image.alpha_composite(base, watermark_layer)
    return watermarked.convert("RGB")


@app.get("/api/watermark")
def watermark_image(url: str = Query(..., description="Source image URL"), text: Optional[str] = Query(None)):
    """Fetch an image from a URL, apply a subtle watermark, and stream back as JPEG."""
    img = _load_image_from_url(url)
    wm_text = text if text else "made by afthab"
    out = _apply_watermark(img, wm_text)

    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=90, optimize=True)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/jpeg")


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
