# Lab 5 – Generating and testing random variables

Run the simulation and its regression tests from the repository root with Python 3.10 or newer. Both use the standard library.

```sh
python3 -B lab5.py --samples 5000 --seed 42
python3 -B -m unittest -v
```

## Generators

Each function returns one draw. Pass a single `random.Random` instance through successive calls to reproduce a sequence.

| Function | Construction |
| --- | --- |
| `lognormal(mu, sigma, rng)` | Generate a standard normal $Z$ with the Box–Muller transform and return $\exp(\mu+\sigma Z)$. The parameters are the mean and standard deviation on the log scale. |
| `compound_poisson(event_mean, jump_rate, rng)` | Simulate unit-rate Poisson arrivals up to time $\lambda=$ `event_mean`. Add an independent exponential jump of rate $\beta=$ `jump_rate` per arrival. Each jump has mean $1/\beta$. With probability $e^{-\lambda}$ there are no arrivals and the sum is zero. |
| `beta22(rng)` | Take the median of three independent uniform draws on $[0,1)$. Its CDF at $x$ is the probability that at least two draws are at most $x$, giving $3x^2(1-x)+x^3=3x^2-2x^3$ for $0\le x\le1$. |

## Statistical validation

Both tests use the same Beta(2, 2) sample and a 5% significance level per test.

1. **Goodness of fit.** The two-sided Kolmogorov–Smirnov distance $D$ measures the largest gap between the empirical CDF and $F(x)=3x^2-2x^3$ on $[0,1]$. Under independent draws from this CDF, the Dvoretzky–Kiefer–Wolfowitz inequality gives a conservative cutoff. Reject the target distribution when $D>\sqrt{\log(2/\alpha)/(2n)}$.
2. **Independence of consecutive draws.** In the original sample order, label each draw according to whether it is below 0.5 or at least 0.5. A *run* is a consecutive block of one label. Under independent, identically distributed draws, all orderings of the labels are equally likely given their counts $L$ and $H$. The expected run count is $1+2LH/n$. Shuffle the labels 999 times and count the shuffled results at least as far from that expectation as the observed count. The two-sided Monte Carlo p-value is $(1+\text{count})/1000$. Reject at $p\le0.05$. Few runs indicate clustering and many runs indicate alternation. Dependence that preserves the pattern of threshold crossings can go undetected.

The simulation prints both decisions. Exit code 0 means neither test rejected its null hypothesis, 1 means a test rejected, and 2 indicates invalid input or an inconclusive runs test. Different seeds can yield a rejection even for a correct generator.

The regression suite checks generator moments, parameter boundaries, and the compound Poisson probability of zero. Its validation controls include uniform quantiles, a sorted Beta sample with the original empirical CDF, and an alternating sequence.

## Lab 6 – Modelling a commercial and entertainment complex

The second simulation follows visitors from arrival by car to departure through the payment gates. It compares three capacity changes and measures how scarce tables block ordering counters. [Model, results, and run instructions](lab6/README.md)
