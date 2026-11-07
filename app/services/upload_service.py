"""Validate, re-encode, and privately store supported crop image uploads."""

from __future__ import annotations

import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage


ALLOWED_EXTENSIONS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
MAX_IMAGE_PIXELS = 20_000_000


class UploadValidationError(ValueError):
    """Raised when an uploaded file is not a supported, valid crop image."""


def save_crop_image(
    uploaded_file: FileStorage,
    upload_folder: str | Path,
) -> str:
    """Validate an upload, store a clean image, and return its generated filename."""
    original_name = uploaded_file.filename or ""
    extension = Path(original_name).suffix.lower()
    expected_format = ALLOWED_EXTENSIONS.get(extension)
    if expected_format is None:
        raise UploadValidationError("Choose a JPG, JPEG, PNG, or WEBP image.")

    image_bytes = _reencode_image(uploaded_file, expected_format)

    target_directory = Path(upload_folder)
    target_directory.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{uuid4().hex}{extension}"
    (target_directory / safe_filename).write_bytes(image_bytes)
    return safe_filename


def _reencode_image(uploaded_file: FileStorage, expected_format: str) -> bytes:
    """Validate decoded pixels and return a clean encoding without source metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            uploaded_file.stream.seek(0)
            with Image.open(uploaded_file.stream) as source_image:
                detected_format = source_image.format
                width, height = source_image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise UploadValidationError(
                        "The image dimensions are invalid or exceed the 20-megapixel limit."
                    )
                if detected_format != expected_format:
                    raise UploadValidationError(
                        "The file extension does not match the image content."
                    )
                source_image.load()
                oriented_image = ImageOps.exif_transpose(source_image)
                mode = (
                    "RGB"
                    if detected_format == "JPEG"
                    else "RGBA"
                    if "A" in oriented_image.getbands()
                    else "RGB"
                )
                clean_image = oriented_image.convert(mode)
                output = BytesIO()
                save_options: dict[str, int | bool | str] = {
                    "format": detected_format,
                }
                if detected_format in {"JPEG", "WEBP"}:
                    save_options["quality"] = 90
                if detected_format == "PNG":
                    save_options["optimize"] = True
                clean_image.save(output, **save_options)
    except UploadValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise UploadValidationError(
            "The uploaded file is not a valid, readable image."
        ) from error
    return output.getvalue()
