"""Load transcribed papers with images for benchmark use (requires pydantic_ai)."""

import re

from litxbench.core.utils import get_paper_dir


def load_transcribed_paper(doi: str) -> list:
    """Load a transcribed paper and interleave text with images.

    Returns:
        List alternating between text strings and BinaryContent image objects
    """
    from pydantic_ai import BinaryContent

    transcribed_dir = get_paper_dir(doi)
    paper_md_path = transcribed_dir / "paper.md"
    markdown_text = paper_md_path.read_text(encoding="utf-8")

    pattern = r"!\[([^\]]*)\]\(([^\)]+)\)"
    matches = list(re.finditer(pattern, markdown_text))

    if not matches:
        return [markdown_text]

    result: list = []
    start_idx = 0

    for match in matches:
        text_before = markdown_text[start_idx : match.start()].strip()
        if text_before:
            result.append(text_before)

        image_filename = match.group(2)
        image_path = transcribed_dir / image_filename
        image_bytes = image_path.read_bytes()
        result.append(BinaryContent(data=image_bytes, media_type="image/jpeg"))

        start_idx = match.end()
        while start_idx < len(markdown_text) and markdown_text[start_idx] in "\n\r":
            start_idx += 1

    text_after = markdown_text[start_idx:].strip()
    if text_after:
        result.append(text_after)

    return result
