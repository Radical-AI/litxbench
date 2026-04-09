"""Transcribe PDFs to markdown using Mistral OCR 3."""

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image


@dataclass
class PaperResult:
    """Result from OCR processing a PDF."""

    pdf_path: Path
    ocr_text: str  # Markdown with native image references
    images: list[Image.Image]  # PIL images
    image_filenames: list[str]  # Original Mistral filenames (e.g., "img-0.jpeg")


def mistral_ocr_with_images(pdf_path: Path) -> PaperResult:
    """Transcribe a PDF using Mistral OCR 3.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        PaperResult with markdown text, images, and filenames
    """
    from mistralai.client import Mistral
    from PIL import Image

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set")

    client = Mistral(api_key=api_key)

    print(f"Uploading {pdf_path.name}...")
    uploaded = client.files.upload(
        file={"file_name": pdf_path.name, "content": open(pdf_path, "rb")},
        purpose="ocr",
    )

    print("Processing with Mistral OCR 3...")
    ocr_response = client.ocr.process(
        model="mistral-ocr-2512",
        document={"file_id": uploaded.id},
        include_image_base64=True,
    )

    markdown_parts = []
    all_images = []
    image_filenames = []

    for page in ocr_response.pages:
        if hasattr(page, "images") and page.images:
            for img_data in page.images:
                image_id = img_data.id if hasattr(img_data, "id") else f"img-{len(all_images)}.png"
                image_filenames.append(image_id)

                b64_string = img_data.image_base64
                if b64_string.startswith("data:"):
                    b64_string = b64_string.split(",", 1)[1]

                img_bytes = base64.b64decode(b64_string)
                all_images.append(Image.open(BytesIO(img_bytes)))

        markdown_parts.append(page.markdown)

    print(f"Extracted {len(all_images)} images from {len(ocr_response.pages)} pages")

    return PaperResult(
        pdf_path=pdf_path,
        ocr_text="\n\n".join(markdown_parts),
        images=all_images,
        image_filenames=image_filenames,
    )
