import asyncio
import base64
import io
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

from image_processor import enhance_image
from text_generator import generate_listing

_executor = ThreadPoolExecutor(max_workers=4)
_results: dict = {}  # {uuid: {car_info, images: [bytes], listing_text}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _executor.shutdown(wait=False)


app = FastAPI(title="CarAd Pro", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process(
    request: Request,
    year: str = Form(...),
    make: str = Form(...),
    model: str = Form(...),
    trim: str = Form(""),
    vin: str = Form(""),
    mileage: str = Form(""),
    price: str = Form(""),
    exterior_color: str = Form(""),
    interior_color: str = Form(""),
    condition: str = Form(""),
    transmission: str = Form(""),
    drivetrain: str = Form(""),
    engine: str = Form(""),
    features: str = Form(""),
    notes: str = Form(""),
    images: List[UploadFile] = File(default=[]),
):
    car_info = {
        "year": year,
        "make": make,
        "model": model,
        "trim": trim,
        "vin": vin,
        "mileage": mileage,
        "price": price,
        "exterior_color": exterior_color,
        "interior_color": interior_color,
        "condition": condition,
        "transmission": transmission,
        "drivetrain": drivetrain,
        "engine": engine,
        "features": features,
        "notes": notes,
    }

    loop = asyncio.get_event_loop()
    enhanced_images: list[bytes] = []

    async def _process_one(upload: UploadFile) -> Optional[bytes]:
        if not upload.filename:
            return None
        try:
            raw = await upload.read()
            if not raw:
                return None
            return await loop.run_in_executor(_executor, enhance_image, raw)
        except Exception:
            return None

    tasks = [_process_one(img) for img in images]
    raw_results = await asyncio.gather(*tasks)
    enhanced_images = [r for r in raw_results if r is not None]

    b64_for_claude = [base64.b64encode(img).decode() for img in enhanced_images[:4]]

    try:
        listing_text = await generate_listing(car_info, b64_for_claude)
    except Exception as e:
        listing_text = f"*(Listing generation failed: {e}. Please check your ANTHROPIC_API_KEY.)*"

    result_id = str(uuid.uuid4())
    _results[result_id] = {
        "car_info": car_info,
        "images": enhanced_images,
        "listing_text": listing_text,
    }

    return RedirectResponse(url=f"/result/{result_id}", status_code=303)


@app.get("/result/{result_id}", response_class=HTMLResponse)
async def result_page(request: Request, result_id: str):
    data = _results.get(result_id)
    if not data:
        raise HTTPException(status_code=404, detail="Result not found or expired.")
    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "result_id": result_id,
            "car_info": data["car_info"],
            "image_count": len(data["images"]),
            "listing_text": data["listing_text"],
        },
    )


@app.get("/image/{result_id}/{index}")
async def serve_image(result_id: str, index: int):
    data = _results.get(result_id)
    if not data or index < 0 or index >= len(data["images"]):
        raise HTTPException(status_code=404)
    return StreamingResponse(
        io.BytesIO(data["images"][index]),
        media_type="image/jpeg",
        headers={"Cache-Control": "max-age=3600"},
    )


@app.get("/download/{result_id}/{index}")
async def download_image(result_id: str, index: int):
    data = _results.get(result_id)
    if not data or index < 0 or index >= len(data["images"]):
        raise HTTPException(status_code=404)
    return StreamingResponse(
        io.BytesIO(data["images"][index]),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="enhanced-photo-{index + 1}.jpg"'
        },
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
