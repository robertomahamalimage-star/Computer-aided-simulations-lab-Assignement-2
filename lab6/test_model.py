import math
import unittest
from random import Random
from statistics import fmean, stdev

from .__main__ import METRICS, mean_ci, paired_change, run_scenarios
from .model import AREAS, Capacities, Stop, Visit, generate_day, simulate


def visit(arrival, *services, meal=0):
    return Visit(arrival, tuple(Stop(area, 0, duration) for area, duration in services), meal)


class MallTests(unittest.TestCase):
    def test_blocked_counter_holds_up_next_order(self):
        visits = [visit(0, ("order", 1), ("gate", 1), meal=5) for _ in range(3)]
        result = simulate(visits, Capacities(parking=3, order=1, tables=1, gate=1), horizon=10)
        # Seats transfer at 1, 6, 11. Departures at 7, 12, 17 include the drain.
        self.assertEqual(result["departures"], 3)
        self.assertEqual(result["sojourn_min"], 12)
        self.assertAlmostEqual(result["order_wait_min"], 7 / 3)
        self.assertAlmostEqual(result["table_wait_min"], 8 / 3)
        self.assertAlmostEqual(result["orders_blocked_pct"], 200 / 3)
        # Only minutes 0 through 10 contribute to the time averages.
        self.assertEqual(result["counter_blocked_pct"], 70)
        self.assertEqual(result["order_util_pct"], 100)
        self.assertEqual(result["tables_full_pct"], 90)
        self.assertEqual(result["parking_full_pct"], 70)
        self.assertEqual(result["parking_util_pct"], 90)
        self.assertEqual(result["gate_util_pct"], 10)

    def test_finished_orders_get_tables_in_fifo_order(self):
        visits = [visit(0, ("order", prep), ("gate", 0), meal=meal)
                  for prep, meal in [(1, 9), (2, 1), (3, 10)]]
        result = simulate(visits, Capacities(order=3, tables=1), horizon=30)
        # Departure times are 10, 11 and 21. Serving the last blocked diner first changes the mean.
        self.assertEqual(result["sojourn_min"], 14)
        self.assertAlmostEqual(result["table_wait_min"], 16 / 3)

    def test_parking_fifo_loss_payment_and_drain(self):
        visits = [visit(t, ("gate", duration)) for t, duration in [(0, 5), (1, 1), (2, 1), (5, 1)]]
        metrics = simulate(visits, Capacities(parking=1, outside=1, gate=1), horizon=6)
        self.assertEqual(metrics["arrivals"], 4)
        self.assertEqual(metrics["departures"], 3)
        self.assertEqual(metrics["loss_pct"], 25)
        self.assertEqual(metrics["lot_full_on_arrival_pct"], 75)
        self.assertAlmostEqual(metrics["outside_wait_min"], 5 / 3)
        self.assertEqual(metrics["sojourn_min"], 4)
        self.assertEqual(metrics["parking_full_pct"], 100)

    def test_gate_release_precedes_a_simultaneous_arrival(self):
        visits = [visit(0, ("gate", 3)), visit(3, ("gate", 1))]
        metrics = simulate(visits, Capacities(parking=1, outside=0), horizon=5)
        self.assertEqual(metrics["loss_pct"], 0)
        self.assertEqual(metrics["parking_util_pct"], 80)

    def test_uncongested_visits_equal_sum_of_planned_durations(self):
        plans = generate_day(Random(42), (30, 70))
        capacity = Capacities(**{name: len(plans) + 1 for name in AREAS})
        metrics = simulate(plans, capacity, horizon=120)
        expected = fmean(p.meal + sum(s.walk + s.service for s in p.stops) for p in plans)
        self.assertAlmostEqual(metrics["sojourn_min"], expected)
        self.assertEqual(metrics["departures"], len(plans))
        for metric in ("loss_pct", "outside_wait_min", "order_wait_min", "table_wait_min"):
            self.assertEqual(metrics[metric], 0)

    def test_empty_day_and_invalid_inputs(self):
        result = simulate(generate_day(Random(4), (0,)))
        self.assertEqual(result["arrivals"], 0)
        self.assertIsNone(result["sojourn_min"])
        self.assertIsNone(result["loss_pct"])
        self.assertEqual(result["parking_full_pct"], 0)
        with self.assertRaises(ValueError):
            Capacities(tables=0)
        with self.assertRaises(ValueError):
            simulate([visit(60, ("gate", 1))], horizon=60)

    def test_hourly_arrival_counts_against_poisson_expectations(self):
        rates = (0, 4, 20, 0)
        totals = [0] * len(rates)
        rng = Random(83)
        for _ in range(300):
            for plan in generate_day(rng, rates):
                totals[int(plan.arrival // 60)] += 1
        for rate, observed in zip(rates, totals):
            expected = rate * 300
            self.assertLessEqual(abs(observed - expected), 5 * math.sqrt(expected))

    def test_single_stall_against_transient_two_state_ctmc(self):
        # M/M/1/1 loss system, initially empty. A customer goes directly to payment.
        capacity = Capacities(parking=1, outside=0, gate=1)
        arrival_rate, payment_rate, horizon = 0.4, 0.6, 60
        rng = Random(129)
        full_fractions = []
        for _ in range(240):
            visits = []
            time = rng.expovariate(arrival_rate)
            while time < horizon:
                visits.append(visit(time, ("gate", rng.expovariate(payment_rate))))
                time += rng.expovariate(arrival_rate)
            full_fractions.append(simulate(visits, capacity, horizon)["parking_full_pct"] / 100)
        rate = arrival_rate + payment_rate
        expected = arrival_rate / rate * (1 - (1 - math.exp(-rate * horizon)) / (rate * horizon))
        standard_error = stdev(full_fractions) / math.sqrt(len(full_fractions))
        self.assertAlmostEqual(fmean(full_fractions), expected, delta=5 * standard_error)

    def test_scenarios_share_demand_and_report_every_metric(self):
        results = run_scenarios(2, 27)
        for scenario in results.values():
            for day, baseline in zip(scenario, results["Baseline"], strict=True):
                self.assertEqual(day["arrivals"], baseline["arrivals"])
                self.assertEqual(set(day), set(METRICS))
                self.assertLessEqual(day["counter_blocked_pct"], day["order_util_pct"])

    def test_paired_intervals_resample_differences_by_day(self):
        baseline = [{"x": 10}, {"x": 100}, {"x": 1000}]
        alternative = [{"x": 14}, {"x": 104}, {"x": 1004}]
        estimate = paired_change(alternative, baseline, "x")
        self.assertEqual((estimate.lower, estimate.mean, estimate.upper), (4, 4, 4))
        self.assertIsNone(mean_ci([None, None]).mean)
        self.assertIsNone(mean_ci([None, 7]).lower)
