"""Optional figure for the capacity experiment."""

from matplotlib.figure import Figure


def plot_comparison(estimates, path, days):
    panels = [
        ("sojourn_min", "Total visit time", "Minutes per visitor"),
        ("loss_pct", "Visitors turned away", "Percent of arrivals"),
        ("order_wait_min", "Queue before ordering", "Minutes per diner"),
    ]
    fig = Figure(figsize=(10.3, 3.2))
    axes = fig.subplots(1, 3, sharey=True)
    names = list(estimates["sojourn_min"])
    for ax, (metric, title, unit) in zip(axes, panels):
        for row, name in enumerate(names):
            estimate = estimates[metric][name]
            if estimate.mean is None:
                continue
            color = "#354150" if name == "Baseline" else "#00746f"
            if estimate.lower is not None:
                ax.hlines(row, estimate.lower, estimate.upper, color=color, linewidth=2)
                ax.plot([estimate.lower, estimate.upper], [row, row], "|", color=color)
            ax.plot(estimate.mean, row, "o", color=color, markersize=6)
        ax.set_title(title, fontsize=12, loc="left")
        ax.set_xlabel(unit, fontsize=10)
        ax.set_xlim(left=0)
        ax.set_ylim(len(names) - 0.5, -0.5)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#dbe1e3", linewidth=0.8)
        ax.tick_params(length=0, pad=5, labelsize=9)
        for spine in ax.spines.values():
            spine.set_visible(False)

    axes[0].set_yticks(range(len(names)), names)
    fig.subplots_adjust(left=0.14, right=0.98, bottom=0.28, top=0.86, wspace=0.24)
    fig.text(0.14, 0.06, f"Mean daily values with 95% bootstrap intervals across {days} simulated Saturdays.",
             fontsize=9, color="#354150")
    fig.savefig(path, dpi=180, facecolor="white")
