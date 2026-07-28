"""Generate the quality-cost Pareto plot from the combined benchmark summary."""

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RED = "#D62728"
BLUE = "#1F77B4"
GREEN = "#2CA02C"

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent.parent
DEFAULT_SUMMARY = PAPER_DIR / "combined_results" / "zero_shot_summary_with_ci.csv"
DEFAULT_PDF = PAPER_DIR / "pareto_front.pdf"
DEFAULT_PNG = REPO_ROOT / "docs" / "_static" / "pareto_front.png"


@dataclass(frozen=True)
class ModelPoint:
    name: str
    f1: float
    cost: float
    color: str
    marker: str


@dataclass(frozen=True)
class PlotStyle:
    summary_name: str
    plot_name: str
    color: str
    marker: str
    cost_override: float | None = None


PLOT_STYLES: tuple[PlotStyle, ...] = (
    PlotStyle("Gemini CLI (Gemini-3.1 Pro Preview)", "Gemini CLI (Gemini-3.1 Pro Preview)", GREEN, "s"),
    PlotStyle("Gemini 3.1 Pro", "Gemini 3.1 Pro", BLUE, "s"),
    PlotStyle("Gemini 3 Flash", "Gemini 3 Flash", RED, "s"),
    PlotStyle("Claude Code (Opus 4.6)", "Claude Code (Opus 4.6)", GREEN, "o"),
    PlotStyle("Claude Opus 4.6", "Claude Opus 4.6", BLUE, "o"),
    PlotStyle("Claude Haiku 4.5", "Claude Haiku 4.5", RED, "o"),
    PlotStyle("Codex (GPT 5.2 Codex High)", "Codex (GPT 5.2 Codex High)", GREEN, "^"),
    PlotStyle("GPT 5.2 High", "GPT 5.2 High", BLUE, "^"),
    PlotStyle("GPT 5 Mini Medium", "GPT 5 Mini Med.", RED, "^"),
    # KnowMat2 does not report token usage in the combined result files.
    PlotStyle("KnowMat2", "KnowMat2", GREEN, "p", cost_override=19.40),
)


def _parse_summary_number(value: str) -> float:
    """Parse either a plain number or the mean from a ``mean +/- CI`` value."""
    return float(value.split("+/-", 1)[0].strip())


def load_model_points(summary_path: Path = DEFAULT_SUMMARY) -> tuple[ModelPoint, ...]:
    """Load plot points from the generated zero-shot summary."""
    with summary_path.open(newline="", encoding="utf-8") as file:
        summaries = {row["method"]: row for row in csv.DictReader(file, delimiter="\t")}

    points: list[ModelPoint] = []
    for style in PLOT_STYLES:
        row = summaries.get(style.summary_name)
        if row is None:
            continue
        cost = style.cost_override if style.cost_override is not None else float(row["cost_usd"])
        if cost <= 0:
            continue
        points.append(
            ModelPoint(
                name=style.plot_name,
                f1=_parse_summary_number(row["overall_f1"]),
                cost=cost,
                color=style.color,
                marker=style.marker,
            )
        )
    return tuple(points)


def pareto_front(points: tuple[ModelPoint, ...]) -> tuple[ModelPoint, ...]:
    sorted_points = sorted(points, key=lambda point: point.cost)
    pareto_points = []
    best_f1 = float("-inf")
    for point in sorted_points:
        if point.f1 > best_f1:
            pareto_points.append(point)
            best_f1 = point.f1
    return tuple(pareto_points)


def upper_convex_front(points: tuple[ModelPoint, ...]) -> tuple[ModelPoint, ...]:
    front: list[ModelPoint] = []

    def slope(left: ModelPoint, right: ModelPoint) -> float:
        x_left = math.log10(left.cost)
        x_right = math.log10(right.cost)
        return (right.f1 - left.f1) / (x_right - x_left)

    for point in pareto_front(points):
        while len(front) >= 2 and slope(front[-2], front[-1]) <= slope(front[-1], point):
            front.pop()
        front.append(point)
    return tuple(front)


def clean_text(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def generate_pareto_plot(
    summary_path: Path = DEFAULT_SUMMARY,
    pdf_path: Path = DEFAULT_PDF,
    png_path: Path = DEFAULT_PNG,
) -> tuple[ModelPoint, ...]:
    """Generate PDF and PNG Pareto plots and return the plotted points."""
    models = load_model_points(summary_path)
    if not models:
        raise ValueError(f"No plottable model rows found in {summary_path}")

    convex_front = upper_convex_front(models)
    front_cost = [point.cost for point in convex_front]
    front_f1 = [point.f1 for point in convex_front]

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 18,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "axes.linewidth": 2.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.size": 12,
            "ytick.major.size": 6,
            "xtick.major.width": 2.6,
            "ytick.major.width": 1.8,
            "xtick.minor.size": 7,
            "ytick.minor.size": 4,
            "xtick.minor.width": 1.8,
            "ytick.minor.width": 1.2,
        }
    )

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_box_aspect(1)
    ax.plot(front_cost, front_f1, color="#B22222", linewidth=3.2, linestyle="--", zorder=2)

    for point in models:
        ax.scatter(
            point.cost,
            point.f1,
            color=point.color,
            s=280,
            zorder=3,
            marker=point.marker,
            edgecolors="white",
            linewidths=0.6,
        )

    ax.set_xscale("log")
    ax.set_xlim(min(point.cost for point in models) * 0.75, max(point.cost for point in models) * 1.3)
    ax.set_ylim(min(point.f1 for point in models) - 0.015, max(point.f1 for point in models) + 0.02)
    ax.set_xlabel("Cost (USD)", fontsize=24)
    ax.set_ylabel("F1", fontsize=24)
    ax.tick_params(labelsize=22)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:g}"))
    legend_handles = [
        Line2D(
            [0],
            [0],
            marker=point.marker,
            linestyle="None",
            markerfacecolor=point.color,
            markeredgecolor="white",
            markeredgewidth=0.6,
            markersize=11,
            label=clean_text(point.name),
        )
        for point in models
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower left",
        bbox_to_anchor=(-0.01, 0.065),
        fontsize=21.5,
        frameon=False,
        ncol=2,
        columnspacing=0.45,
        handletextpad=0.0,
    )

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=1200)
    plt.close(fig)
    return models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    args = parser.parse_args()
    models = generate_pareto_plot(args.summary, args.pdf, args.png)
    print(f"Generated Pareto plot for {len(models)} models:")
    print(f"  {args.pdf}")
    print(f"  {args.png}")


if __name__ == "__main__":
    main()
