"""Transcribe a PDF with Mistral OCR and extract experiments with Gemini 3 Flash.
This file is needed by the UI for transcription.

Usage:
    uv run paper/scripts/transcribe_and_extract.py <pdf_path> [--output-dir <dir>]

Prints JSON-lines progress messages to stdout for consumption by the UI.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from litxbench.litxalloy.models import Experiment
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import execute_experiments_code
from scripts.paper.benchmarks.helpers.extraction_runner import create_default_agent
from scripts.paper.benchmarks.helpers.prompts import (
    PromptConfig,
    available_names,
    composition_helpers,
    example_experiment_shape,
    field_instructions,
    scope_rules,
)
from scripts.paper.benchmarks.helpers.retry_loop import (
    PYTHON_RETRY_MESSAGES,
    RetryableError,
    run_extraction_loop,
)
from scripts.paper.benchmarks.helpers.transcribe import PaperResult, mistral_ocr_with_images


def emit(event: str, **kwargs):
    """Emit a JSON-lines progress event to stdout."""
    print(json.dumps({"event": event, **kwargs}), flush=True)


def save_ocr_results(result: PaperResult, output_dir: Path) -> str:
    """Save OCR markdown and images to output_dir. Returns the markdown text."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_md_path = output_dir / "paper.md"
    paper_md_path.write_text(result.ocr_text, encoding="utf-8")

    for image, filename in zip(result.images, result.image_filenames):
        image_path = output_dir / filename
        image.save(image_path, format="JPEG")

    return result.ocr_text


async def extract_experiments(paper_text: str, model_name: str = "gemini-3-flash") -> list[Experiment]:
    """Run the zero-shot extraction pipeline on transcribed paper text."""
    extraction_agent = create_default_agent(model_name)
    pc = PromptConfig()

    sections = [
        "Extract experiments from this paper.\n\n"
        + scope_rules()
        + "\n\n"
        + "Return a Python fenced code block (```python ... ```) containing a single expression that evaluates to a `list[Experiment]`.\n\n"
        + "Use this exact shape:\n\n"
        + example_experiment_shape(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions
        )
        + "\n\n"
        + field_instructions(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions
        )
        + "\n\n"
        + available_names(
            include_composition_helpers=pc.include_composition_helpers,
            include_normalize_function=pc.include_normalize_function,
            include_descriptions=pc.include_descriptions_instructions,
        ),
    ]
    if pc.include_composition_helpers:
        sections.append(composition_helpers())
    prompt_suffix = "\n\n".join(sections)
    prompt: list[str] = [prompt_suffix, paper_text]

    def process_response(code: str) -> list[Experiment]:
        try:
            experiments = execute_experiments_code(code, pc)
        except Exception as exc:
            raise RetryableError(
                f"The generated Python expression failed at runtime. Fix it and try again.\nExecution error:\n{exc}"
            ) from exc
        if not isinstance(experiments, list) or not all(isinstance(e, Experiment) for e in experiments):
            raise RetryableError(
                "Output must evaluate to a list[Experiment]. Every list item must be an Experiment object."
            )
        return experiments

    result = await run_extraction_loop(
        agent=extraction_agent,
        initial_prompt=prompt,
        process_response=process_response,
        extract_block=extract_python_code_block,
        retry_messages=PYTHON_RETRY_MESSAGES,
        max_retries=10,
        span_name="transcribe_and_extract",
        doi="uploaded_pdf",
    )

    return result.value


def experiments_to_json(experiments: list[Experiment], doi: str = "uploaded_pdf") -> list[dict]:
    """Serialize experiments to JSON-compatible dicts using the same graph format as the UI."""
    from scripts.ast_to_graph import experiment_to_graph

    return [experiment_to_graph(exp, doi, i) for i, exp in enumerate(experiments)]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe PDF and extract experiments")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save OCR results")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        emit("error", message=f"PDF not found: {pdf_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else pdf_path.parent / f"{pdf_path.stem}_transcribed"

    # Step 1: OCR
    emit("status", step="ocr", message=f"Starting Mistral OCR on {pdf_path.name}...")
    start = time.monotonic()
    try:
        ocr_result = mistral_ocr_with_images(pdf_path)
    except Exception as exc:
        emit("error", step="ocr", message=str(exc))
        sys.exit(1)

    paper_text = save_ocr_results(ocr_result, output_dir)
    ocr_elapsed = time.monotonic() - start
    emit(
        "status",
        step="ocr",
        message=f"OCR complete: {len(ocr_result.images)} images, {len(paper_text)} chars ({ocr_elapsed:.1f}s)",
    )

    # Step 2: Extraction with Gemini 3 Flash
    emit("status", step="extraction", message="Starting experiment extraction with Gemini 3 Flash...")
    start = time.monotonic()
    try:
        experiments = await extract_experiments(paper_text)
    except Exception as exc:
        emit("error", step="extraction", message=str(exc))
        sys.exit(1)

    extraction_elapsed = time.monotonic() - start
    emit(
        "status",
        step="extraction",
        message=f"Extraction complete: {len(experiments)} experiments ({extraction_elapsed:.1f}s)",
    )

    # Step 3: Output results
    result_json = experiments_to_json(experiments)
    emit("result", experiments=result_json, ocr_output_dir=str(output_dir))


if __name__ == "__main__":
    asyncio.run(main())
