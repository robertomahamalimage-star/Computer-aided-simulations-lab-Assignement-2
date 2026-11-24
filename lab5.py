"""Lab 5 random variate generators and statistical checks. Run with python3 lab5.py."""

import argparse
import math
from collections.abc import Sequence
from itertools import pairwise
from random import Random
from statistics import fmean


def _unit_exponential(rng: Random) -> float:
    """Inverse exponential CDF for a uniform draw in [0, 1)."""
    return -math.log1p(-rng.random())


def lognormal(mu: float, sigma: float, rng: Random) -> float:
    """Draw exp(mu + sigma * Z) using a Box–Muller standard normal Z."""
    if not math.isfinite(mu) or not math.isfinite(sigma) or sigma < 0:
        raise ValueError("mu must be finite and sigma must be finite and nonnegative")
    radius = math.sqrt(2 * _unit_exponential(rng))
    z = radius * math.cos(math.tau * rng.random())
    return math.exp(mu + sigma * z)


def compound_poisson(event_mean: float, jump_rate: float, rng: Random) -> float:
    """Sum exponential jumps over a Poisson(event_mean) number of events."""
    if not math.isfinite(event_mean) or event_mean < 0:
        raise ValueError("event_mean must be finite and nonnegative")
    if not math.isfinite(jump_rate) or jump_rate <= 0:
        raise ValueError("jump_rate must be finite and positive")

    # A unit-rate Poisson process has Poisson(event_mean) arrivals by this time.
    arrival = _unit_exponential(rng)
    total = 0.0
    while arrival < event_mean:
        total += _unit_exponential(rng) / jump_rate
        arrival += _unit_exponential(rng)
    return total


def beta22(rng: Random) -> float:
    """The second order statistic of three independent uniforms is Beta(2, 2)."""
    return sorted((rng.random(), rng.random(), rng.random()))[1]


def beta22_goodness_of_fit(samples: Sequence[float], alpha: float = 0.05) -> tuple[float, float]:
    """Return the two-sided KS distance and its finite-sample DKW rejection cutoff."""
    n = len(samples)
    if n == 0 or not 0 < alpha < 1:
        raise ValueError("provide a nonempty sample and an alpha between 0 and 1")
    distance = 0.0
    for rank, x in enumerate(sorted(samples), start=1):
        if not math.isfinite(x):
            raise ValueError("samples must be finite")
        u = min(1.0, max(0.0, x))
        cdf = u * u * (3 - 2 * u)
        # Compare F(x) to the empirical CDF immediately before and after the jump.
        distance = max(distance, cdf - (rank - 1) / n, rank / n - cdf)
    cutoff = math.sqrt(math.log(2 / alpha) / (2 * n))
    return distance, cutoff


def _count_runs(labels: Sequence[bool]) -> int:
    return 1 + sum(left != right for left, right in pairwise(labels))


def beta22_independence(
    samples: Sequence[float], rng: Random, permutations: int = 999
) -> tuple[int, float]:
    """Return the observed run count and a two-sided permutation p-value."""
    if permutations < 1 or not all(math.isfinite(x) for x in samples):
        raise ValueError("provide finite samples and at least one permutation")
    labels = [x >= 0.5 for x in samples]
    high = sum(labels)
    low = len(labels) - high
    if min(high, low) == 0:
        raise ValueError("the runs test needs observations on both sides of the split at 0.5")

    observed = _count_runs(labels)
    expected = 1 + 2 * high * low / len(labels)
    deviation = abs(observed - expected)
    extreme = 0
    for _ in range(permutations):
        rng.shuffle(labels)
        if abs(_count_runs(labels) - expected) >= deviation:
            extreme += 1
    return observed, (extreme + 1) / (permutations + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5000, help="draws per generator")
    parser.add_argument("--seed", type=int, default=42, help="random seed for the whole run")
    args = parser.parse_args()
    if args.samples < 2:
        parser.error("--samples must be at least 2")

    rng = Random(args.seed)
    n = args.samples
    print(f"{n} draws per generator, seed {args.seed}")
    log_mean = fmean(lognormal(0, 1, rng) for _ in range(n))
    jump_mean = fmean(compound_poisson(2, 3, rng) for _ in range(n))
    print(f"Log-normal(0, 1) sample mean {log_mean:.4f} (theory {math.exp(0.5):.4f})")
    print(f"Compound Poisson(2), exponential rate 3, sample mean {jump_mean:.4f} (theory {2/3:.4f})")

    samples = [beta22(rng) for _ in range(n)]
    alpha = 0.05
    distance, cutoff = beta22_goodness_of_fit(samples, alpha)
    fit_rejected = distance > cutoff
    fit_decision = "reject" if fit_rejected else "fail to reject"
    print(f"Beta(2, 2) fit (KS D = {distance:.5f}, cutoff = {cutoff:.5f}) — {fit_decision} at 5%")
    try:
        runs, p_value = beta22_independence(samples, rng)
    except ValueError as error:
        print(f"Beta(2, 2) independence test is inconclusive ({error})")
        return 2
    order_rejected = p_value <= alpha
    order_decision = "reject" if order_rejected else "fail to reject"
    print(f"Beta(2, 2) independence ({runs} runs, permutation p = {p_value:.3f}) "
          f"— {order_decision} at 5%")
    return int(fit_rejected or order_rejected)


if __name__ == "__main__":
    raise SystemExit(main())
