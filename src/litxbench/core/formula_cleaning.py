"""Shared utilities for cleaning chemical formula strings."""

import re

# Unicode subscript digits -> ASCII
UNICODE_SUBSCRIPTS = str.maketrans(
    {
        "\u2080": "0",
        "\u2081": "1",
        "\u2082": "2",
        "\u2083": "3",
        "\u2084": "4",
        "\u2085": "5",
        "\u2086": "6",
        "\u2087": "7",
        "\u2088": "8",
        "\u2089": "9",
        "\u2024": ".",
    }
)

# LaTeX subscript notation: _{...} -> contents
LATEX_SUB_RE = re.compile(r"_\{([^}]*)\}")


def strip_latex_and_subscripts(name: str) -> str:
    """Strip LaTeX subscript braces and convert unicode subscript digits.

    ``Al_{65}`` -> ``Al65``, ``Fe₂O₃`` -> ``Fe2O3``.
    """
    name = LATEX_SUB_RE.sub(r"\1", name)
    name = name.replace("{", "").replace("}", "").replace("_", "")
    name = name.translate(UNICODE_SUBSCRIPTS)
    return name
