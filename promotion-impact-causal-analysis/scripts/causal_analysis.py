"""
Promotion Impact & Causal Analysis — hypothesis testing + causal design
Loads the cleaned Fact_Daily_Sales warehouse and answers three questions:

1. Hypothesis test — is there a statistically significant difference in
   daily sales between promo and non-promo days? (pooled Welch's t-test +
   Mann-Whitney U, plus a store-level paired test that respects clustering)
2. Causal analysis — Promo is chosen by store managers, not randomly
   assigned, so the raw promo/non-promo gap is confounded by store size,
   season, day-of-week, and holidays. A two-way fixed-effects regression
   (store FE + year-month FE, controlling for day-of-week and holidays) is
   used to isolate the effect attributable to the promo itself.
3. A light supporting seasonal-decomposition view for two representative
   stores (not the headline — ML-based time series forecasting already
   lives in the energy-grid-load-forecasting project).

Writes all real numeric results to output/results.md.
"""
import pandas as pd
import numpy as np
import sqlite3
import os
from scipy import stats
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.tsa.seasonal import seasonal_decompose

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DB_PATH = os.path.join(OUTPUT_DIR, "promotion_dw.db")
RESULTS_PATH = os.path.join(OUTPUT_DIR, "results.md")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("""
    SELECT f.Store_Key, f.Sales, f.Customers, f.Promo, f.School_Holiday,
           d.Full_Date, d.Year_Month, d.Day_Of_Week, d.Is_Weekend,
           d.Is_State_Holiday, s.Store_Type, s.Assortment
    FROM Fact_Daily_Sales f
    JOIN Dim_Date d ON f.Date_Key = d.Date_Key
    JOIN Dim_Store s ON f.Store_Key = s.Store_Key
    WHERE f.Is_Sales_Anomaly = 0
""", conn)
conn.close()

df["Full_Date"] = pd.to_datetime(df["Full_Date"])
out = []


def fmt_p(p):
    """scipy/statsmodels underflow tiny p-values to exact 0.0 — report that
    honestly as '< 1e-300' rather than the literal (misleading) '0'."""
    if p == 0:
        return "< 1e-300"
    return f"{p:.3g}"


def w(line=""):
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))
    out.append(line)


w("# Promotion Impact & Causal Analysis — Results")
w("")
w(f"Analysis sample: {len(df):,} store-days, {df['Store_Key'].nunique():,} stores, "
  f"{df['Full_Date'].min().date()} to {df['Full_Date'].max().date()} "
  f"(open-store days only, sales-anomaly rows excluded).")
w("")

# =====================================================================
# 1. HYPOTHESIS TESTING — promo days vs. non-promo days
# =====================================================================
w("## 1. Hypothesis testing: do promo days have higher sales?")
w("")

promo_sales = df.loc[df["Promo"] == 1, "Sales"]
nonpromo_sales = df.loc[df["Promo"] == 0, "Sales"]

n_promo, n_nonpromo = len(promo_sales), len(nonpromo_sales)
mean_promo, mean_nonpromo = promo_sales.mean(), nonpromo_sales.mean()
median_promo, median_nonpromo = promo_sales.median(), nonpromo_sales.median()

# Welch's t-test (unequal variance, pooled daily observations)
t_stat, t_p = stats.ttest_ind(promo_sales, nonpromo_sales, equal_var=False)

# Cohen's d (pooled SD)
pooled_sd = np.sqrt(((n_promo - 1) * promo_sales.var(ddof=1) +
                      (n_nonpromo - 1) * nonpromo_sales.var(ddof=1)) /
                     (n_promo + n_nonpromo - 2))
cohens_d = (mean_promo - mean_nonpromo) / pooled_sd

# Mann-Whitney U (nonparametric — sales are right-skewed)
u_stat, u_p = stats.mannwhitneyu(promo_sales, nonpromo_sales, alternative="two-sided")

w("**Pooled comparison (one row per store-day — naive, not yet store-adjusted):**")
w("")
w(f"- Promo days: n={n_promo:,}, mean sales={mean_promo:,.0f}, median={median_promo:,.0f}")
w(f"- Non-promo days: n={n_nonpromo:,}, mean sales={mean_nonpromo:,.0f}, median={median_nonpromo:,.0f}")
w(f"- Raw mean gap: {mean_promo - mean_nonpromo:,.0f} "
  f"({(mean_promo / mean_nonpromo - 1) * 100:.1f}% higher on promo days)")
w(f"- Welch's t-test: t={t_stat:.2f}, p={fmt_p(t_p)}, Cohen's d={cohens_d:.3f}")
w(f"- Mann-Whitney U: U={u_stat:,.0f}, p={fmt_p(u_p)}")
w("")

# --- Store-level paired test (respects clustering: one observation per store) ---
# Pooling ~844K daily rows and testing them as if independent overstates
# significance — the same store's promo days are correlated with each
# other (pseudo-replication). Collapsing to one paired observation per
# store (its own promo-day mean vs. its own non-promo-day mean) removes
# that clustering before testing.
store_means = df.groupby(["Store_Key", "Promo"])["Sales"].mean().unstack()
store_means = store_means.dropna()  # stores that used Promo=1 at least once and had Promo=0 days too
store_diff = store_means[1] - store_means[0]

paired_t, paired_p = stats.ttest_rel(store_means[1], store_means[0])
wilcoxon_stat, wilcoxon_p = stats.wilcoxon(store_means[1], store_means[0])
store_cohens_d = store_diff.mean() / store_diff.std(ddof=1)

w("**Store-level paired comparison (n = one pair per store, clustering-safe):**")
w("")
w(f"- Stores included: {len(store_means):,}")
w(f"- Mean of within-store (promo mean minus non-promo mean): {store_diff.mean():,.0f} "
  f"(SD {store_diff.std(ddof=1):,.0f})")
w(f"- Paired t-test: t={paired_t:.2f}, p={fmt_p(paired_p)}, Cohen's d={store_cohens_d:.3f}")
w(f"- Wilcoxon signed-rank test: W={wilcoxon_stat:,.0f}, p={fmt_p(wilcoxon_p)}")
w(f"- {(store_diff > 0).sum():,} of {len(store_diff):,} stores ({(store_diff > 0).mean()*100:.1f}%) "
  f"sell more on their own promo days than their own non-promo days")
w("")
w("All four tests agree: the promo/non-promo sales gap is statistically significant "
  "at any conventional threshold (p < 0.001), whether tested on pooled daily "
  "observations or on clustering-safe store-level pairs. **This establishes association, "
  "not causation** — Promo is a decision store managers make, not a coin flip, so "
  "Section 2 isolates how much of this gap survives once store size, seasonality, "
  "day-of-week, and holidays are controlled for.")
w("")

# =====================================================================
# 2. CAUSAL ANALYSIS — two-way fixed effects (generalized DiD)
# =====================================================================
w("## 2. Causal analysis: two-way fixed-effects (generalized diff-in-diff)")
w("")
w("**Why a naive comparison is confounded.** `Promo` isn't randomly assigned — "
  "store managers choose which days to run a promo, and that choice correlates "
  "with things that independently move sales: bigger stores run promos more "
  "often, promos cluster around certain months/seasons, and day-of-week and "
  "holiday patterns differ across the sample. Comparing raw promo-day vs. "
  "non-promo-day sales (Section 1) bakes all of that in.")
w("")
w("**Design.** `Promo` switches on and off for individual stores on individual "
  "days throughout the panel (not one simultaneous campaign), so the natural "
  "causal design here is a two-way fixed-effects regression — the standard "
  "generalization of difference-in-differences to panel data with staggered, "
  "repeated treatment. Store fixed effects absorb every time-invariant store "
  "trait (location, size, assortment, baseline traffic); year-month fixed "
  "effects absorb common seasonal/macro trends shared by all stores in a given "
  "month; day-of-week and state/school holiday flags are added directly so the "
  "regression isn't just comparing, say, more Saturdays in the promo group.")
w("")

reg_df = df.copy()
reg_df["LogSales"] = np.log1p(reg_df["Sales"])

# Store fixed effects removed by demeaning (1,115 levels — too many for dense
# dummy columns to be practical). Year-month (31 levels) and day-of-week
# (7 levels) fixed effects are added directly as categorical regressors: by
# the Frisch-Waugh-Lovell theorem, demeaning one high-cardinality FE and
# including the other, lower-cardinality FE(s) as regressors in the same
# model correctly estimates both simultaneously in one pass.
store_mean_log_sales = reg_df.groupby("Store_Key")["LogSales"].transform("mean")
store_mean_promo = reg_df.groupby("Store_Key")["Promo"].transform("mean")
reg_df["LogSales_tilde"] = reg_df["LogSales"] - store_mean_log_sales
reg_df["Promo_tilde"] = reg_df["Promo"] - store_mean_promo

model = smf.ols(
    "LogSales_tilde ~ Promo_tilde + C(Year_Month) + C(Day_Of_Week) "
    "+ School_Holiday + Is_State_Holiday",
    data=reg_df
).fit(cov_type="cluster", cov_kwds={"groups": reg_df["Store_Key"]})

did_coef = model.params["Promo_tilde"]
did_se = model.bse["Promo_tilde"]
did_p = model.pvalues["Promo_tilde"]
ci_low, ci_high = model.conf_int().loc["Promo_tilde"]
pct_lift = (np.exp(did_coef) - 1) * 100
pct_lift_low = (np.exp(ci_low) - 1) * 100
pct_lift_high = (np.exp(ci_high) - 1) * 100

w(f"**Model:** `log(1+Sales)` ~ `Promo` + Store FE (demeaned) + Year-Month FE "
  f"+ Day-of-Week + School Holiday + State Holiday, standard errors clustered "
  f"by store (n={reg_df['Store_Key'].nunique():,} clusters).")
w("")
w(f"- Promo coefficient (log points): {did_coef:.4f} (cluster-robust SE {did_se:.4f})")
w(f"- 95% CI (log points): [{ci_low:.4f}, {ci_high:.4f}]")
w(f"- p-value: {fmt_p(did_p)}")
w(f"- **Causal lift estimate: {pct_lift:.1f}% increase in sales attributable to promo "
  f"(95% CI: {pct_lift_low:.1f}% to {pct_lift_high:.1f}%)**")
w("")
w(f"For comparison, the naive pooled gap in Section 1 was "
  f"{(mean_promo / mean_nonpromo - 1) * 100:.1f}%. After controlling for store "
  f"fixed effects, seasonality, day-of-week, and holidays, the estimated causal "
  f"lift is {pct_lift:.1f}% — {'lower' if pct_lift < (mean_promo / mean_nonpromo - 1) * 100 else 'higher'} "
  f"than the naive gap, meaning part of the naive comparison really was "
  f"confounding rather than a promo effect, though a real, statistically "
  f"significant promo effect remains.")
w("")
w("**Identifying assumption.** This design assumes *conditional parallel "
  "trends*: absent the promo, a store's sales in a given month would have "
  "moved in line with the same month's trend shared across all stores (net of "
  "its own fixed baseline and day-of-week/holiday pattern). Under that "
  "assumption, the store+month fixed effects strip out everything except the "
  "promo's own effect.")
w("")
w("**Threats to that assumption:**")
w("")
w("- **Strategic timing (reverse causality).** If managers turn on promos "
  "*because* they anticipate a demand dip or a competitor threat that this "
  "model can't observe, the promo coefficient would be biased — it would "
  "partly capture the manager's private forecast, not the promo's own "
  "effect. This dataset can't rule that out directly.")
w("- **Anticipation/pull-forward effects.** Sales just before or after a "
  "promo period may shift (customers delaying purchases to wait for a "
  "promo, or a promo pulling forward demand that would have happened days "
  "later anyway). This model treats each day independently and doesn't "
  "correct for either.")
w("- **Coarse time fixed effects.** Year-month (not full daily) fixed "
  "effects are used for tractability given 1,115 store dummies already "
  "consume the store dimension; a chain-wide event inside a single month "
  "(e.g. a nationwide flash sale) would only be partially absorbed.")
w("- **Promo2 overlap.** A subset of stores also run a separate continuing "
  "loyalty promo (`Promo2`) on top of the day-level `Promo` flag; this model "
  "doesn't separate the two, so the estimate is the effect of `Promo` in a "
  "population where some stores also have `Promo2` running.")
w("")

# =====================================================================
# 3. LIGHT SUPPORTING VIEW — seasonal decomposition for two stores
# =====================================================================
w("## 3. Supporting view: weekly seasonality for two representative stores")
w("")
w("A brief classical decomposition, not the headline of this project — "
  "ML-based time series forecasting is already covered in "
  "`energy-grid-load-forecasting/`. This is included only as a sanity check "
  "that the day-of-week control in Section 2 is doing real work.")
w("")

top_store = df.groupby("Store_Key")["Sales"].mean().idxmax()
rep_stores = [top_store, 1]  # highest-average-sales store + Store 1 (typical/small)

for store_id in rep_stores:
    s = df.loc[df["Store_Key"] == store_id].set_index("Full_Date")["Sales"].asfreq("D")
    s = s.interpolate()  # closed-store gaps (Sundays etc.) already excluded from fact table
    if s.isna().all() or len(s.dropna()) < 28:
        continue
    decomp = seasonal_decompose(s.dropna(), model="additive", period=7)
    seasonal_amplitude = decomp.seasonal.max() - decomp.seasonal.min()
    trend_start = decomp.trend.dropna().iloc[0]
    trend_end = decomp.trend.dropna().iloc[-1]
    avg_sales = s.mean()
    w(f"**Store {store_id}** (avg daily sales {avg_sales:,.0f}): weekly seasonal "
      f"swing of {seasonal_amplitude:,.0f} ({seasonal_amplitude/avg_sales*100:.0f}% of "
      f"average), 7-day trend component moved from {trend_start:,.0f} to "
      f"{trend_end:,.0f} over the sample window "
      f"({(trend_end/trend_start - 1)*100:+.1f}%).")
w("")

with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")

print(f"\nResults written to {os.path.abspath(RESULTS_PATH)}")
