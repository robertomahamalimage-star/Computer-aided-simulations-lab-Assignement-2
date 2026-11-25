"""Run paired mall capacity scenarios and print a Markdown results table."""

import argparse
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from random import Random
from statistics import fmean, quantiles

from .model import HOURLY_RATES, Capacities, Metrics, generate_day, simulate


BASE = Capacities()
SCENARIOS = {
    "Baseline": BASE,
    "More parking": replace(BASE, parking=108),
    "More counters": replace(BASE, order=6),
    "More tables": replace(BASE, tables=24),
}
METRICS = {
    "arrivals": "Offered arrivals per day",
    "departures": "Completed visits per day",
    "loss_pct": "Turned away (% of arrivals)",
    "sojourn_min": "Total sojourn (min/visitor)",
    "outside_wait_min": "Exterior wait (min/visitor)",
    "order_wait_min": "Queue before ordering (min/diner)",
    "table_wait_min": "Holding a counter after ordering (min/diner)",
    "parking_full_pct": "Parking full (% of open time)",
    "lot_full_on_arrival_pct": "Find parking full (% of arrivals)",
    "tables_full_pct": "Tables full (% of open time)",
    "orders_blocked_pct": "Find tables full (% of completed orders)",
    "counter_blocked_pct": "Blocked counter time (% of installed counter-minutes)",
    "parking_util_pct": "Parking utilization (%)",
    "retail_util_pct": "Supermarket utilization (%)",
    "shop_a_util_pct": "Shop A utilization (%)",
    "shop_b_util_pct": "Shop B utilization (%)",
    "order_util_pct": "Counter utilization, including blocking (%)",
    "tables_util_pct": "Table utilization (%)",
    "gate_util_pct": "Payment gate utilization (%)",
}
CONTRASTS = {
    "loss_pct": "Turned away (percentage points)",
    "sojourn_min": "Total sojourn (min/visitor)",
    "order_wait_min": "Queue before ordering (min/diner)",
    "table_wait_min": "Holding a counter after ordering (min/diner)",
    "counter_blocked_pct": "Blocked counter time (percentage points)",
}
BOOTSTRAPS = 2000


def run_scenarios(days: int, seed: int) -> dict[str, list[Metrics]]:
    if days < 1:
        raise ValueError("at least one day is required")
    day_seeds = Random(seed)
    results: dict[str, list[Metrics]] = {name: [] for name in SCENARIOS}
    for _ in range(days):
        plans = generate_day(Random(day_seeds.getrandbits(128)))
        for name, capacity in SCENARIOS.items():
            results[name].append(simulate(plans, capacity, 60 * len(HOURLY_RATES)))
    return results


@dataclass(frozen=True)
class Estimate:
    mean: float | None
    lower: float | None
    upper: float | None

    def display(self) -> str:
        if self.mean is None:
            return "undefined"
        if self.lower is None:
            return f"{self.mean:.2f} (CI unavailable)"
        return f"{self.mean:.2f} [{self.lower:.2f}, {self.upper:.2f}]"


def mean_ci(observations: Iterable[float | None]) -> Estimate:
    """Percentile bootstrap interval for the mean across independently generated days."""
    values = [x for x in observations if x is not None]
    if not values:
        return Estimate(None, None, None)
    mean = fmean(values)
    if len(values) < 2:
        return Estimate(mean, None, None)
    if min(values) == max(values):
        return Estimate(mean, mean, mean)
    # A fixed resampling seed makes reported bounds repeatable across runs.
    rng = Random(1983)
    boot = [fmean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAPS)]
    cutoffs = quantiles(boot, n=40, method="inclusive")
    return Estimate(mean, cutoffs[0], cutoffs[-1])


def paired_change(scenario: list[Metrics], baseline: list[Metrics], metric: str) -> Estimate:
    changes = []
    for day, base_day in zip(scenario, baseline, strict=True):
        value, reference = day[metric], base_day[metric]
        if value is not None and reference is not None:
            changes.append(value - reference)
    return mean_ci(changes)


def print_table(labels: Iterable[str], rows: Iterable[list[str]]):
    header = ["Metric", *labels]
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=60, help="independent simulated days per scenario")
    parser.add_argument("--seed", type=int, default=2026, help="master seed for visitor demand")
    parser.add_argument("--plot", type=Path, help="also save a scenario comparison figure (requires Matplotlib)")
    args = parser.parse_args()
    if args.days < 2:
        parser.error("use at least two days to estimate confidence intervals")
    results = run_scenarios(args.days, args.seed)
    print("# Mall scenario results\n")
    print(f"{args.days} independent days per scenario, demand seed {args.seed}. "
          f"Cells show the mean [95% day-bootstrap interval] with {BOOTSTRAPS:,} resamples.\n")
    estimates = {
        metric: {name: mean_ci(day[metric] for day in days) for name, days in results.items()}
        for metric in METRICS
    }
    rows = [
        [label, *(estimate.display() for estimate in estimates[metric].values())]
        for metric, label in METRICS.items()
    ]
    print_table(results, rows)

    print("\n## Paired change from baseline\n")
    print("Each change uses the same day's visitors in both configurations.\n")
    alternatives = [name for name in results if name != "Baseline"]
    rows = []
    for metric, label in CONTRASTS.items():
        cells = [paired_change(results[name], results["Baseline"], metric).display() for name in alternatives]
        rows.append([label, *cells])
    print_table(alternatives, rows)

    if args.plot:
        from .plot import plot_comparison

        plot_comparison(estimates, args.plot, args.days)


if __name__ == "__main__":
    main()
