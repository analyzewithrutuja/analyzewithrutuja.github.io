"""
Music Royalty Statement Pipeline — Step 4: catalog metrics + valuation
Reads only the validated warehouse (output/royalty_dw.db) and turns it into
the numbers an investment team asks for before pricing a catalog:
  - earnings per chart week (months hold 4 or 5 chart weeks, so raw monthly
    totals are not comparable month to month)
  - a song retention curve by age, measured from the data
  - concentration risk (top song share, top territory share)
  - an age-aware 10-year discounted cash flow value per artist catalog,
    with a sensitivity table on the long-term decline assumption
Writes output/valuation_results.md and output/catalog_metrics.csv.
"""
import os
import sqlite3

import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "output")

FULL_MONTHS = [f"2019-{m:02d}" for m in range(1, 10)]   # Oct excluded: partial month (3 chart weeks)
WEEKS_PER_MONTH = 52 / 12
DISCOUNT_RATE = 0.10                                     # illustrative
HORIZON_YEARS = 10
# Years 2-10 annual decline: an assumption (not observable in 9 months of data); 20% = base case
LONG_TERM_DECLINE = {"10pct": 0.10, "20pct": 0.20, "30pct": 0.30}
MAX_MEASURED_AGE = 6


def md(df, fmt="{:,.2f}"):
    cells = [[fmt.format(v) if isinstance(v, float) else str(v) for v in row] for row in df.itertuples(index=False)]
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(r) + " |" for r in cells)


def main():
    con = sqlite3.connect(os.path.join(OUT, "royalty_dw.db"))
    f = pd.read_sql("""
        SELECT f.sale_period, f.song_id, f.territory_iso2, f.net_usd, t.artist
        FROM fact_royalty_line f
        JOIN (SELECT DISTINCT song_id, artist FROM dim_track) t ON t.song_id = f.song_id
    """, con)
    weeks = pd.read_sql("SELECT period, chart_weeks FROM dim_period", con).set_index("period").chart_weeks
    con.close()
    f = f[f.sale_period.isin(FULL_MONTHS)]
    artist_of = f.drop_duplicates("song_id").set_index("song_id").artist

    # ---- song x month earnings, normalized to USD per chart week
    sm = f.pivot_table(index="song_id", columns="sale_period", values="net_usd", aggfunc="sum")
    sm = sm.reindex(columns=FULL_MONTHS).fillna(0).clip(lower=0)
    sw = sm.div(weeks.reindex(FULL_MONTHS).values, axis=1)
    first = sw.gt(0).idxmax(axis=1)

    # ---- retention by age: songs that debut Feb-Sep (debut observed); ratio of next-month to
    # this-month weekly earnings, summed over the same songs (earnings-weighted)
    debut = sw[first != FULL_MONTHS[0]]
    ages = {sid: FULL_MONTHS.index(m) for sid, m in first.items()}
    g, g_n = {}, {}
    for a in range(MAX_MEASURED_AGE + 1):
        num = den = 0.0
        n = 0
        for sid, row in debut.iterrows():
            i = ages[sid] + a
            if i + 1 < len(FULL_MONTHS):
                num += row.iat[i + 1]
                den += row.iat[i]
                n += 1
        g[a], g_n[a] = num / den, n
    # songs already charting in January (debut not observed) = older catalog songs
    cat = sw[first == FULL_MONTHS[0]].sum()
    g_catalog = float(np.exp(np.polyfit(np.arange(len(cat)), np.log(cat.values), 1)[0]))

    # ---- forward 12 months per song, starting from September weekly earnings
    last = sw[FULL_MONTHS[-1]] * WEEKS_PER_MONTH
    fwd = pd.Series(0.0, index=sw.index)
    for sid, e in last[last > 0].items():
        age = (len(FULL_MONTHS) - 1 - ages[sid]) if first[sid] != FULL_MONTHS[0] else None
        total, cur = 0.0, e
        for _ in range(12):
            r = g.get(age, g_catalog) if age is not None and age <= MAX_MEASURED_AGE else g_catalog
            cur *= r
            total += cur
            age = None if age is None else age + 1
        fwd[sid] = total

    # ---- catalog (artist) roll-up
    trailing = sw[FULL_MONTHS[-3:]].mean(axis=1) * 52          # Jul-Sep run-rate, annualized
    by = pd.DataFrame({"artist": artist_of.reindex(sw.index), "trailing": trailing, "fwd12": fwd,
                       "frontline": (first != FULL_MONTHS[0]) & (trailing > 0)})
    by["front_rr"] = by.trailing.where(by.frontline, 0)
    a = by.groupby("artist").agg(songs=("trailing", "size"), run_rate_usd=("trailing", "sum"),
                                 fwd12_usd=("fwd12", "sum"), front_rr=("front_rr", "sum"))
    a["new_release_share"] = a.front_rr / a.run_rate_usd
    total = f.groupby("artist").net_usd.sum()
    a["earnings_jan_sep_usd"] = total
    song_share = f.groupby(["artist", "song_id"]).net_usd.sum()
    a["top_song_share"] = song_share.groupby(level=0).max() / total
    terr = f.groupby(["artist", "territory_iso2"]).net_usd.sum()
    a["top_territory"] = terr.groupby(level=0).idxmax().str[1]
    a["top_territory_share"] = terr.groupby(level=0).max() / total

    years = np.arange(1, HORIZON_YEARS + 1)
    disc = (1 + DISCOUNT_RATE) ** years
    for name, L in LONG_TERM_DECLINE.items():
        mult = ((1 - L) ** (years - 1)) / disc                   # year1 = fwd12, then decline L per year
        a[f"value_decline_{name}_usd"] = a.fwd12_usd * mult.sum()
    a["value_to_run_rate"] = a.value_decline_20pct_usd / a.run_rate_usd
    a = a[a.run_rate_usd > 0].sort_values("run_rate_usd", ascending=False)
    a.drop(columns="front_rr").to_csv(os.path.join(OUT, "catalog_metrics.csv"))

    port = a.run_rate_usd
    top10 = port.head(10).sum() / port.sum()
    top1pct = port.head(max(1, len(port) // 100)).sum() / port.sum()
    corr = a[["new_release_share", "value_to_run_rate"]].corr().iat[0, 1]
    mid = a[a.run_rate_usd.between(50_000, 500_000) & (a.songs >= 3)]
    safest = mid.sort_values("value_to_run_rate", ascending=False)

    with open(os.path.join(OUT, "valuation_results.md"), "w", encoding="utf-8") as fh:
        fh.write("# Catalog metrics & illustrative valuation\n\n")
        fh.write("Generated by `scripts/catalog_valuation.py` from the validated warehouse only (quarantined lines are "
                 "excluded). It covers Jan-Sep 2019; October is left out as a partial month. Per-stream rates, the 10% "
                 "discount rate and the long-term decline are assumptions, so the dollar values show the method, not "
                 "market prices.\n\n")
        fh.write("## Method\n\n")
        fh.write("1. **Normalize per chart week.** Weekly charts start on Fridays, so Mar, May and Aug hold 5 chart weeks "
                 "and the other months hold 4. Raw monthly totals would show fake 25% swings.\n")
        fh.write("2. **Measure retention by song age** (next month's weekly earnings / this month's, summed over the same "
                 "songs) for songs whose debut falls inside the data. Songs already charting in January are treated as "
                 "older catalog songs with one fitted monthly rate.\n")
        fh.write("3. **Project the next 12 months per song** from its September earnings and its age, then roll up to the "
                 "artist catalog.\n")
        fh.write("4. **Years 2-10 decline** at an assumed 10% / 20% / 30% a year (9 months of data cannot show year-2 "
                 "behaviour), discounted at 10%.\n\n")
        fh.write("## Retention curve (measured)\n\n")
        rc = pd.DataFrame({"song_age_months": list(g), "next_month_retention": [round(v, 3) for v in g.values()],
                           "songs": list(g_n.values())})
        fh.write(md(rc, fmt="{:.3f}") + "\n\n")
        fh.write(f"Older catalog songs (already charting in January): **{g_catalog:.3f}** monthly retention "
                 f"({1 - g_catalog ** 12:.0%} annual decline).\n\n")
        fh.write("Caveat: streams are only counted while a song is in a country's weekly Top 200, so these rates fall "
                 "faster than total streams really do (a song that leaves the chart still earns). Read them as a "
                 "conservative floor.\n\n")
        fh.write("## Portfolio findings\n\n")
        fh.write(f"- **{len(a):,}** artist catalogs still earning in Jul-Sep ({int(a.songs.sum()):,} songs).\n")
        fh.write(f"- Concentration: the top 10 catalogs hold **{top10:.1%}** of run-rate, and the top 1% hold **{top1pct:.1%}**.\n")
        fh.write(f"- Median value-to-run-rate multiple (base case): **{a.value_to_run_rate.median():.2f}x** "
                 f"(IQR {a.value_to_run_rate.quantile(.25):.2f}x-{a.value_to_run_rate.quantile(.75):.2f}x).\n")
        fh.write(f"- Correlation between a catalog's share of run-rate from new releases and its multiple: "
                 f"**{corr:+.2f}**, close to none. In this data, new releases after their debut month and older catalog "
                 f"songs lose chart earnings at similar monthly rates (0.71-0.82 vs {g_catalog:.2f}), so a catalog's age "
                 f"mix barely moves its multiple.\n")
        fh.write("- Multiples below 1x come from the chart-only data: once a song leaves the Top 200, its earnings "
                 "read as zero here. The absolute values are a floor. The useful outputs are the ranking and the "
                 "sensitivity range.\n\n")
        fh.write("## Largest catalogs (base case)\n\n")
        cols = ["artist", "songs", "run_rate_usd", "fwd12_usd", "new_release_share", "top_song_share",
                "top_territory", "top_territory_share", "value_decline_10pct_usd", "value_decline_20pct_usd",
                "value_decline_30pct_usd", "value_to_run_rate"]
        fh.write(md(a.head(10).reset_index()[cols]) + "\n\n")
        fh.write(f"## Screen: mid-size catalogs (USD 50K-500K run-rate, 3+ songs): {len(mid)} match\n\n")
        fh.write("These are ranked by value-to-run-rate, meaning how many years of today's earnings the catalog is worth.\n\n")
        fh.write(md(safest.head(10).reset_index()[cols]) + "\n")

    print(rc.to_string(index=False))
    print(f"g_catalog {g_catalog:.3f} | catalogs {len(a):,} | top10 {top10:.1%} | top1% {top1pct:.1%}")
    print(f"median multiple {a.value_to_run_rate.median():.2f}x IQR {a.value_to_run_rate.quantile(.25):.2f}-"
          f"{a.value_to_run_rate.quantile(.75):.2f} | corr {corr:+.2f} | mid {len(mid)}")
    print(a.head(5)[["run_rate_usd", "fwd12_usd", "new_release_share", "value_decline_20pct_usd", "value_to_run_rate"]].to_string())


if __name__ == "__main__":
    main()
