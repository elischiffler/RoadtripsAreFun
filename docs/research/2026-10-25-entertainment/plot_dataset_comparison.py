"""Plot verified before/after means, with fixed scales and no significance claim."""

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

source = Path(sys.argv[1])
data = json.loads(source.read_text())
trips = ["short-1d", "medium-2d", "long-3d", "coast-5d"]
rows = {r["scenario"]: r for r in data["scenario_comparison"]}


def display(value, *, signed=False):
    rounded = Decimal(str(round(float(value), 12))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{rounded:+.1f}" if signed else f"{rounded:.1f}"


before = np.array(
    [
        [100 * rows[f"{t}:entertainment:{n}"]["prior_selected_mean"] for n in (1, 2, 3)]
        for t in trips
    ]
)
after = np.array(
    [
        [100 * rows[f"{t}:entertainment:{n}"]["new_selected_mean"] for n in (1, 2, 3)]
        for t in trips
    ]
)
fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.4), layout="constrained")
labels = ["Short / 1 day", "Medium / 2 days", "Long / 3 days", "Coast / 5 days"]
for ax, matrix, title, delta in zip(
    axes,
    (before, after, after - before),
    ("Original dataset", "Enriched dataset", "Change (points)"),
    (False, False, True),
    strict=True,
):
    im = ax.imshow(
        matrix,
        cmap="PuOr" if delta else "YlGnBu",
        vmin=-10 if delta else 0,
        vmax=10 if delta else 100,
    )
    ax.set_title(title)
    ax.set_xticks(range(3), ["1", "2", "3"])
    ax.set_xlabel("Stops per day")
    ax.set_yticks(range(4), labels if ax is axes[0] else [""] * 4)
    for i in range(4):
        for j in range(3):
            ax.text(
                j,
                i,
                display(matrix[i, j], signed=delta),
                ha="center",
                va="center",
                color="white"
                if (abs(matrix[i, j]) > 6 if delta else matrix[i, j] > 55)
                else "#222222",
            )
    fig.colorbar(im, ax=ax, shrink=0.8)
fig.suptitle(
    "Entertainment: selected-place mean utility\nSame solver settings and permanent ratings; 30 seeds per cell",
    fontsize=13,
)
for extension in ("png", "svg"):
    fig.savefig(source.parent / f"entertainment-before-after.{extension}", dpi=240)
plt.close(fig)
