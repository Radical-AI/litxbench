import re
from collections.abc import Sequence
from pathlib import Path

# core/utils.py lives at <package_root>/core/utils.py in both dev and installed layouts.
# Dev:  src/litxbench/core/utils.py  →  parent.parent = src/litxbench/
# PyPI: site-packages/litxbench/core/utils.py  →  parent.parent = site-packages/litxbench/
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_LITXALLOY_DIR = _PACKAGE_ROOT / "litxalloy"
_PROJECT_ROOT = _PACKAGE_ROOT.parent.parent  # only meaningful in dev (reaches repo root)


def dict_to_csv_string(d: dict[str, float | int], keys: Sequence[str] | None = None) -> str:
    """Return comma-separated values from a dict for pasting into Google Sheets.

    If *keys* is given, output values in that order; otherwise use dict order.
    """
    if keys is not None:
        values = [d[k] for k in keys]
    else:
        values = list(d.values())
    return ",".join(str(v) for v in values)


def doi_to_name(doi: str) -> str:
    """Convert a DOI to a universal name usable as filename and Python module name.
    `/` → `__`, `.` → `_`, `-` → `_`, prefixed with `doi_`.
    """
    return "doi_" + doi.replace("/", "__").replace(".", "_").replace("-", "_")


def resolve_doi_path(doi_name: str) -> str:
    return str(_LITXALLOY_DIR / "pdfs" / f"{doi_name}.pdf")


def resolve_path(path: str | Path) -> str:
    """Resolve a path relative to the project root (dev scripts only)."""
    target_path = path if isinstance(path, Path) else Path(path)
    return str(_PROJECT_ROOT / target_path)


def get_paper_dir(doi: str) -> Path:
    """Return the path to the transcribed paper directory for a given DOI name.

    Args:
        doi: DOI name in module form, e.g. "doi_10_3390__e21020122"

    Returns:
        Path to the directory containing paper.md and image files
    """
    return _LITXALLOY_DIR / "transcribed" / doi


def load_transcribed_paper_text_only(doi: str) -> str:
    """Load a transcribed paper as plain text, stripping image references."""
    transcribed_dir = get_paper_dir(doi)
    paper_md_path = transcribed_dir / "paper.md"
    markdown_text = paper_md_path.read_text(encoding="utf-8")

    pattern = r"!\[([^\]]*)\]\(([^\)]+)\)\n?"
    return re.sub(pattern, "", markdown_text)
