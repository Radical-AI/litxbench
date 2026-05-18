import math
import re
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RED = "#D62728"  # red
BLUE = "#1F77B4"  # blue
GREEN = "#2CA02C"  # green


@dataclass(frozen=True)
class ModelPoint:
    name: str
    f1: float
    cost: float
    color: str
    marker: str


models: tuple[ModelPoint, ...] = (
    ModelPoint("Gemini CLI (Gemini-3.1 Pro Preview)", 0.7958, 6.45507, GREEN, "s"),
    ModelPoint("Gemini 3.1 Pro", 0.7708, 4.17163, BLUE, "s"),
    ModelPoint("Gemini 3 Flash", 0.7376, 1.73078, RED, "s"),
    ModelPoint("Claude Code (Opus 4.6)", 0.7766, 26.1145, GREEN, "o"),
    ModelPoint("Claude Opus 4.6", 0.7231, 5.37406, BLUE, "o"),
    ModelPoint("Claude Haiku 4.5", 0.6510, 1.7177, RED, "o"),
    ModelPoint("Codex (GPT 5.2 Codex High)", 0.7268, 4.17361, GREEN, "^"),
    ModelPoint("GPT 5.2 High", 0.7273, 4.99104, BLUE, "^"),
    ModelPoint("GPT 5 Mini Med.", 0.6764, 3.46597, RED, "^"),
    ModelPoint("KnowMat2", 0.4288, 19.40, GREEN, "p"),
)


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

LINE_C = "#B22222"


def clean_text(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


fig, ax = plt.subplots(figsize=(8, 8))
ax.set_box_aspect(1)

ax.plot(front_cost, front_f1, color=LINE_C, linewidth=3.2, linestyle="--", zorder=2, label="Convex Pareto front")

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
# ax.set_title("Quality-Cost Pareto for Experiment Extraction", fontsize=24, fontweight="bold", pad=14)
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

plt.tight_layout()
plt.savefig("pareto_front.pdf", bbox_inches="tight")  # vector output
plt.savefig("pareto_front.png", bbox_inches="tight", dpi=1200)  # high-res raster
plt.show()
