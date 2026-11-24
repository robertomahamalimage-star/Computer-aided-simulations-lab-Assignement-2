import math
import unittest
from random import Random
from statistics import fmean, pvariance

from lab5 import beta22, beta22_goodness_of_fit, beta22_independence, compound_poisson, lognormal


class GeneratorTests(unittest.TestCase):
    def test_lognormal_on_log_scale(self):
        rng = Random(17)
        logs = [math.log(lognormal(-0.4, 0.7, rng)) for _ in range(12000)]
        self.assertAlmostEqual(fmean(logs), -0.4, delta=0.03)
        self.assertAlmostEqual(pvariance(logs), 0.7**2, delta=0.04)

    def test_compound_poisson_mass_at_zero_and_moments(self):
        rng = Random(18)
        event_mean, jump_rate = 1.5, 2.0
        draws = [compound_poisson(event_mean, jump_rate, rng) for _ in range(12000)]
        self.assertGreaterEqual(min(draws), 0.0)
        self.assertAlmostEqual(draws.count(0.0) / len(draws), math.exp(-event_mean), delta=0.02)
        self.assertAlmostEqual(fmean(draws), event_mean / jump_rate, delta=0.04)
        self.assertAlmostEqual(pvariance(draws), 2 * event_mean / jump_rate**2, delta=0.08)

    def test_beta_support_and_moments(self):
        rng = Random(19)
        draws = [beta22(rng) for _ in range(12000)]
        self.assertGreaterEqual(min(draws), 0.0)
        self.assertLessEqual(max(draws), 1.0)
        self.assertAlmostEqual(fmean(draws), 0.5, delta=0.01)
        self.assertAlmostEqual(pvariance(draws), 1 / 20, delta=0.003)

    def test_parameter_boundaries(self):
        rng = Random(20)
        self.assertEqual(lognormal(1, 0, rng), math.exp(1))
        self.assertEqual(compound_poisson(0, 2, rng), 0.0)
        with self.assertRaises(ValueError):
            lognormal(0, -1, rng)
        with self.assertRaises(ValueError):
            compound_poisson(-1, 2, rng)
        with self.assertRaises(ValueError):
            compound_poisson(2, 0, rng)


class ValidationTests(unittest.TestCase):
    def test_ks_includes_both_sides_of_each_jump(self):
        for value in (0.25, 0.75):
            with self.subTest(value=value):
                distance, _ = beta22_goodness_of_fit([value])
                self.assertEqual(distance, 0.84375)

    def test_fit_rejects_uniform_quantiles(self):
        uniform = [(i + 0.5) / 1000 for i in range(1000)]
        distance, cutoff = beta22_goodness_of_fit(uniform)
        self.assertGreater(distance, cutoff)

    def test_runs_detects_reordering_with_identical_marginal_fit(self):
        rng = Random(21)
        draws = [beta22(rng) for _ in range(1000)]
        ordered = sorted(draws)
        self.assertEqual(beta22_goodness_of_fit(draws), beta22_goodness_of_fit(ordered))
        runs, p_value = beta22_independence(ordered, rng, permutations=199)
        self.assertEqual(runs, 2)
        self.assertLessEqual(p_value, 0.05)

    def test_runs_detects_alternation(self):
        runs, p_value = beta22_independence([0.1, 0.9] * 100, Random(22), permutations=199)
        self.assertEqual(runs, 200)
        self.assertLessEqual(p_value, 0.05)

    def test_runs_requires_both_categories(self):
        with self.assertRaises(ValueError):
            beta22_independence([0.1, 0.2, 0.3], Random(23))


if __name__ == "__main__":
    unittest.main()
