"""Shared MPEA dataset utilities used by compare_mpea.py and find_mpea_errors.py."""

import urllib.request
from pathlib import Path

from litxbench.core.utils import resolve_path

MPEA_CSV_URL = "https://raw.githubusercontent.com/CitrineInformatics/MPEA_dataset/master/MPEA_dataset.csv"
MPEA_CSV_PATH = Path(resolve_path("scripts/paper/MPEA_dataset.csv"))
MPEA_DOI_COL = "REFERENCE: doi"


def download_mpea_csv() -> Path:
    """Download the MPEA CSV if not already cached locally."""
    if MPEA_CSV_PATH.exists():
        return MPEA_CSV_PATH
    MPEA_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MPEA dataset to {MPEA_CSV_PATH} ...")
    urllib.request.urlretrieve(MPEA_CSV_URL, MPEA_CSV_PATH)
    print("Done.")
    return MPEA_CSV_PATH
