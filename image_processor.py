import io

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

MAX_DIMENSION = 2400
ANALYSIS_DIMENSION = 1024  # smaller size for fast Claude vision calls


def enhance_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))

    # Fix EXIF rotation (phone photos are often rotated)
    img = ImageOps.exif_transpose(img)

    # Normalize to RGB
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if very large (saves memory and speeds up Claude vision)
    if max(img.size) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.LANCZOS,
        )

    # Auto-contrast: stretch histogram with 1% cutoff on each end
    img = ImageOps.autocontrast(img, cutoff=1)

    # Brightness: subtle lift so shadows don't crush
    img = ImageEnhance.Brightness(img).enhance(1.06)

    # Contrast punch
    img = ImageEnhance.Contrast(img).enhance(1.18)

    # Color saturation — makes paint and interior pop
    img = ImageEnhance.Color(img).enhance(1.22)

    # Sharpness — crisp edges on body lines
    img = ImageEnhance.Sharpness(img).enhance(1.50)

    # Unsharp mask for fine detail (grille, wheels, trim)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=65, threshold=3))

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def resize_for_analysis(image_bytes: bytes) -> bytes:
    """Shrink and normalize an image for fast Claude vision analysis (no enhancement)."""
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)

    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > ANALYSIS_DIMENSION:
        ratio = ANALYSIS_DIMENSION / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.LANCZOS,
        )

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=82)
    return output.getvalue()
