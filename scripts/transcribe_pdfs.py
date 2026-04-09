"""Transcribe PDFs to markdown using Mistral OCR 3.

This script processes PDFs and extracts both text and images using Mistral's OCR API.
Output uses Mistral's native markdown format with images as ![img-0.jpeg](img-0.jpeg).
"""

import glob
from pathlib import Path

from litxbench.core.utils import resolve_path
from scripts.paper.benchmarks.helpers.transcribe import mistral_ocr_with_images


def main():
    """Transcribe all PDFs in the dataset directory."""
    pdf_paths = glob.glob(resolve_path("datasets/litxalloy/pdfs/*"))

    for pdf_path in pdf_paths:
        # Create output directory
        output_dir = Path(resolve_path(f"datasets/litxalloy/transcribed/{Path(pdf_path).stem}"))
        output_dir.mkdir(parents=True, exist_ok=True)
        paper_md_path = output_dir / "paper.md"

        if paper_md_path.exists():
            print(f"Skipping: {Path(pdf_path).name} (already transcribed)")
            continue

        # Transcribe
        print(f"\n{'=' * 60}")
        print(f"Processing: {Path(pdf_path).name}")
        print(f"{'=' * 60}")

        result = mistral_ocr_with_images(Path(pdf_path))

        # Save markdown
        paper_md_path.write_text(result.ocr_text, encoding="utf-8")
        print(f"Saved markdown to {paper_md_path}")

        # Save images (Mistral outputs JPEG)
        for image, filename in zip(result.images, result.image_filenames):
            image_path = output_dir / filename
            image.save(image_path, format="JPEG")
            print(f"Saved image to {image_path}")

        print(f"Completed: {Path(pdf_path).name}\n")


if __name__ == "__main__":
    main()
