# Promotion Impact & Causal Analysis — Results

Analysis sample: 844,338 store-days, 1,115 stores, 2013-01-01 to 2015-07-31 (open-store days only, sales-anomaly rows excluded).

## 1. Hypothesis testing: do promo days have higher sales?

**Pooled comparison (one row per store-day — naive, not yet store-adjusted):**

- Promo days: n=376,875, mean sales=8,229, median=7,650
- Non-promo days: n=467,463, mean sales=5,930, median=5,459
- Raw mean gap: 2,299 (38.8% higher on promo days)
- Welch's t-test: t=356.69, p=< 1e-300, Cohen's d=0.797
- Mann-Whitney U: U=131,101,145,046, p=< 1e-300

**Store-level paired comparison (n = one pair per store, clustering-safe):**

- Stores included: 1,115
- Mean of within-store (promo mean minus non-promo mean): 2,299 (SD 1,024)
- Paired t-test: t=74.98, p=< 1e-300, Cohen's d=2.245
- Wilcoxon signed-rank test: W=6, p=5.98e-184
- 1,114 of 1,115 stores (99.9%) sell more on their own promo days than their own non-promo days

All four tests agree: the promo/non-promo sales gap is statistically significant at any conventional threshold (p < 0.001), whether tested on pooled daily observations or on clustering-safe store-level pairs. **This establishes association, not causation** — Promo is a decision store managers make, not a coin flip, so Section 2 isolates how much of this gap survives once store size, seasonality, day-of-week, and holidays are controlled for.

## 2. Causal analysis: two-way fixed-effects (generalized diff-in-diff)

**Why a naive comparison is confounded.** `Promo` isn't randomly assigned — store managers choose which days to run a promo, and that choice correlates with things that independently move sales: bigger stores run promos more often, promos cluster around certain months/seasons, and day-of-week and holiday patterns differ across the sample. Comparing raw promo-day vs. non-promo-day sales (Section 1) bakes all of that in.

**Design.** `Promo` switches on and off for individual stores on individual days throughout the panel (not one simultaneous campaign), so the natural causal design here is a two-way fixed-effects regression — the standard generalization of difference-in-differences to panel data with staggered, repeated treatment. Store fixed effects absorb every time-invariant store trait (location, size, assortment, baseline traffic); year-month fixed effects absorb common seasonal/macro trends shared by all stores in a given month; day-of-week and state/school holiday flags are added directly so the regression isn't just comparing, say, more Saturdays in the promo group.

**Model:** `log(1+Sales)` ~ `Promo` + Store FE (demeaned) + Year-Month FE + Day-of-Week + School Holiday + State Holiday, standard errors clustered by store (n=1,115 clusters).

- Promo coefficient (log points): 0.3312 (cluster-robust SE 0.0026)
- 95% CI (log points): [0.3260, 0.3364]
- p-value: < 1e-300
- **Causal lift estimate: 39.3% increase in sales attributable to promo (95% CI: 38.5% to 40.0%)**

For comparison, the naive pooled gap in Section 1 was 38.8%. After controlling for store fixed effects, seasonality, day-of-week, and holidays, the estimated causal lift is 39.3% — higher than the naive gap, meaning part of the naive comparison really was confounding rather than a promo effect, though a real, statistically significant promo effect remains.

**Identifying assumption.** This design assumes *conditional parallel trends*: absent the promo, a store's sales in a given month would have moved in line with the same month's trend shared across all stores (net of its own fixed baseline and day-of-week/holiday pattern). Under that assumption, the store+month fixed effects strip out everything except the promo's own effect.

**Threats to that assumption:**

- **Strategic timing (reverse causality).** If managers turn on promos *because* they anticipate a demand dip or a competitor threat that this model can't observe, the promo coefficient would be biased — it would partly capture the manager's private forecast, not the promo's own effect. This dataset can't rule that out directly.
- **Anticipation/pull-forward effects.** Sales just before or after a promo period may shift (customers delaying purchases to wait for a promo, or a promo pulling forward demand that would have happened days later anyway). This model treats each day independently and doesn't correct for either.
- **Coarse time fixed effects.** Year-month (not full daily) fixed effects are used for tractability given 1,115 store dummies already consume the store dimension; a chain-wide event inside a single month (e.g. a nationwide flash sale) would only be partially absorbed.
- **Promo2 overlap.** A subset of stores also run a separate continuing loyalty promo (`Promo2`) on top of the day-level `Promo` flag; this model doesn't separate the two, so the estimate is the effect of `Promo` in a population where some stores also have `Promo2` running.

## 3. Supporting view: weekly seasonality for two representative stores

A brief classical decomposition, not the headline of this project — ML-based time series forecasting is already covered in `energy-grid-load-forecasting/`. This is included only as a sanity check that the day-of-week control in Section 2 is doing real work.

**Store 817** (avg daily sales 21,464): weekly seasonal swing of 10,296 (48% of average), 7-day trend component moved from 24,323 to 20,901 over the sample window (-14.1%).
**Store 1** (avg daily sales 4,816): weekly seasonal swing of 645 (13% of average), 7-day trend component moved from 5,455 to 5,111 over the sample window (-6.3%).

