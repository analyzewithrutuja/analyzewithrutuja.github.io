"""
Music Royalty Statement Pipeline — Step 1: build distributor statements
Input:  real Spotify weekly Top-200 chart data by country (streams per
        track, 63 countries, Jan-Oct 2019) from github.com/kiewic/spotify-charts
Output: monthly royalty statements from 3 distributors, each in its own
        format (CSV/USD, Excel/EUR, semicolon-CSV/GBP), plus a ground-truth
        manifest of every data issue deliberately injected into them.

The STREAM COUNTS are real. The STATEMENTS are synthetic: real royalty
statements are private, so each distributor's file layout, per-stream rates,
FX rates, fees, and errors are illustrative assumptions documented below.
The ETL step (etl_pipeline.py) never reads the manifest — it has to find
the issues on its own; evaluate_checks.py then scores it against the manifest.
"""
import os
import hashlib
import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(BASE, "data", "raw", "spotify-charts.csv")
STMT_DIR = os.path.join(BASE, "data", "statements")
REF_DIR = os.path.join(BASE, "data", "reference")
rng = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
# country -> (ISO2, ISO3, rate tier)
COUNTRIES = {
    "Argentina": ("AR", "ARG", 3), "Australia": ("AU", "AUS", 2), "Austria": ("AT", "AUT", 2),
    "Belgium": ("BE", "BEL", 2), "Bolivia": ("BO", "BOL", 3), "Brazil": ("BR", "BRA", 3),
    "Bulgaria": ("BG", "BGR", 3), "Canada": ("CA", "CAN", 2), "Chile": ("CL", "CHL", 3),
    "Colombia": ("CO", "COL", 3), "Costa Rica": ("CR", "CRI", 3), "Cyprus": ("CY", "CYP", 2),
    "Czech Republic": ("CZ", "CZE", 3), "Denmark": ("DK", "DNK", 1), "Dominican Republic": ("DO", "DOM", 3),
    "Ecuador": ("EC", "ECU", 3), "El Salvador": ("SV", "SLV", 3), "Estonia": ("EE", "EST", 3),
    "Finland": ("FI", "FIN", 1), "France": ("FR", "FRA", 2), "Germany": ("DE", "DEU", 2),
    "Greece": ("GR", "GRC", 3), "Guatemala": ("GT", "GTM", 3), "Honduras": ("HN", "HND", 3),
    "Hong Kong": ("HK", "HKG", 2), "Hungary": ("HU", "HUN", 3), "Iceland": ("IS", "ISL", 1),
    "India": ("IN", "IND", 4), "Indonesia": ("ID", "IDN", 4), "Ireland": ("IE", "IRL", 2),
    "Israel": ("IL", "ISR", 2), "Italy": ("IT", "ITA", 2), "Japan": ("JP", "JPN", 2),
    "Latvia": ("LV", "LVA", 3), "Lithuania": ("LT", "LTU", 3), "Luxembourg": ("LU", "LUX", 1),
    "Malaysia": ("MY", "MYS", 4), "Malta": ("MT", "MLT", 2), "Mexico": ("MX", "MEX", 3),
    "Netherlands": ("NL", "NLD", 2), "New Zealand": ("NZ", "NZL", 2), "Nicaragua": ("NI", "NIC", 3),
    "Norway": ("NO", "NOR", 1), "Panama": ("PA", "PAN", 3), "Paraguay": ("PY", "PRY", 3),
    "Peru": ("PE", "PER", 3), "Philippines": ("PH", "PHL", 4), "Poland": ("PL", "POL", 3),
    "Portugal": ("PT", "PRT", 3), "Romania": ("RO", "ROU", 3), "Singapore": ("SG", "SGP", 2),
    "Slovakia": ("SK", "SVK", 3), "South Africa": ("ZA", "ZAF", 4), "Spain": ("ES", "ESP", 2),
    "Sweden": ("SE", "SWE", 1), "Switzerland": ("CH", "CHE", 1), "Taiwan": ("TW", "TWN", 4),
    "Thailand": ("TH", "THA", 4), "Turkey": ("TR", "TUR", 4), "United Kingdom": ("GB", "GBR", 1),
    "United States": ("US", "USA", 1), "Uruguay": ("UY", "URY", 3), "Vietnam": ("VN", "VNM", 4),
}
# Illustrative per-stream payout (USD) by market tier — NOT real contract rates.
TIER_RATE_USD = {1: 0.0045, 2: 0.0035, 3: 0.0012, 4: 0.0006}
# Approximate 2019 monthly-average FX (USD per 1 unit of currency) — illustrative.
FX = pd.DataFrame({
    "month": [f"2019-{m:02d}" for m in range(1, 11)],
    "EUR": [1.142, 1.135, 1.130, 1.124, 1.119, 1.129, 1.122, 1.113, 1.100, 1.105],
    "GBP": [1.291, 1.303, 1.318, 1.304, 1.286, 1.265, 1.244, 1.216, 1.233, 1.260],
})
C_FEE_PCT = 0.09  # Distributor C withholds a 9% distribution fee on each line

manifest = []  # ground truth of injected issues


def log_issue(distributor, file, issue, n, detail=""):
    manifest.append(dict(distributor=distributor, file=file, issue=issue, rows_affected=n, detail=detail))


def main():
    os.makedirs(REF_DIR, exist_ok=True)
    for d in ("distributor_a", "distributor_b", "distributor_c"):
        os.makedirs(os.path.join(STMT_DIR, d), exist_ok=True)

    raw = pd.read_csv(RAW)
    raw["track_id"] = raw["URL"].str.rsplit("/", n=1).str[-1]
    raw["month"] = raw["Week"].str[:7]  # chart week start date -> reporting month

    # The source chart itself is missing artist/title on a few rows; statements are
    # built from what the chart actually reported, so those gaps flow through.
    # Master catalog (what the rights holder knows about its own tracks) uses the
    # most common non-null title/artist per track ID.
    master = (raw.dropna(subset=["Track Name", "Artist"])
                 .groupby("track_id")
                 .agg(title=("Track Name", lambda s: s.mode().iat[0]),
                      artist=("Artist", lambda s: s.mode().iat[0]))
                 .reset_index())

    # Each artist's catalog is administered by exactly one distributor (stable hash split 50/30/20).
    def assign(artist):
        h = int(hashlib.md5(artist.encode("utf-8")).hexdigest(), 16) % 100
        return "A" if h < 50 else ("B" if h < 80 else "C")
    master["distributor"] = master["artist"].map(assign)
    master.to_csv(os.path.join(REF_DIR, "master_catalog.csv"), index=False)

    terr = pd.DataFrame([(k, v[0], v[1], v[2], TIER_RATE_USD[v[2]]) for k, v in COUNTRIES.items()],
                        columns=["territory", "iso2", "iso3", "tier", "rate_usd"])
    terr.to_csv(os.path.join(REF_DIR, "territories.csv"), index=False)
    FX.to_csv(os.path.join(REF_DIR, "fx_rates.csv"), index=False)

    # Monthly statement lines = streams per track x territory x month
    lines = (raw.groupby(["month", "track_id", "Country"], as_index=False)
                .agg(streams=("Streams", "sum"),
                     title=("Track Name", "first"),
                     artist=("Artist", "first")))
    lines = lines.merge(master[["track_id", "distributor"]], on="track_id")
    lines = lines.merge(terr.rename(columns={"territory": "Country"}), on="Country")
    lines["earn_usd"] = lines["streams"] * lines["rate_usd"]
    lines = lines.merge(FX, on="month")

    months = sorted(lines["month"].unique())
    prev_a = None

    # ------------------------------------------------------------------ A
    # CSV, USD, ISO2 country, has track ID. One file per month.
    for m in months:
        df = lines[(lines.distributor == "A") & (lines.month == m)].copy()
        out = pd.DataFrame({
            "Reporting Date": pd.Period(m).end_time.strftime("%Y-%m-%d"),
            "Sale Month": m,
            "Store": "Spotify",
            "Artist": df["artist"],
            "Title": df["title"],
            "Track ID": df["track_id"],
            "Quantity": df["streams"],
            "Country of Sale": df["iso2"],
            "Earnings (USD)": df["earn_usd"].round(6),
        })
        fname = f"A_{m}.csv"
        # Injection: re-sent duplicate lines (~0.3%)
        dup = out.sample(frac=0.003, random_state=int(m[-2:]))
        out = pd.concat([out, dup])
        log_issue("A", fname, "duplicate_line", len(dup))
        # Injection: decimal-shift earnings errors (x100) on a few lines
        idx = rng.choice(out.index[:len(out) - len(dup)], size=3, replace=False)
        out.loc[idx, "Earnings (USD)"] = out.loc[idx, "Earnings (USD)"] * 100
        log_issue("A", fname, "rate_outlier", 3, "earnings x100 decimal shift")
        # Injection: reversal of lines paid on the PREVIOUS statement (valid, but must be flagged)
        clean_a = out.iloc[:len(out) - len(dup)]
        if m >= "2019-03":
            rev = prev_a.sample(n=5, random_state=int(m[-2:]) + 100).copy()
            rev["Reporting Date"] = out["Reporting Date"].iat[0]
            rev["Quantity"] = -rev["Quantity"]
            rev["Earnings (USD)"] = -rev["Earnings (USD)"]
            out = pd.concat([out, rev])
            log_issue("A", fname, "negative_adjustment", 5, "prior-month reversal")
        prev_a = clean_a.drop(idx, errors="ignore")
        out = out.sample(frac=1, random_state=1)
        out.to_csv(os.path.join(STMT_DIR, "distributor_a", fname), index=False)

    # ------------------------------------------------------------------ B
    # Excel, EUR, full country name, NO track ID, US date format, 2-row preamble + TOTAL footer.
    for m in months:
        df = lines[(lines.distributor == "B") & (lines.month == m)].copy()
        per = pd.Period(m)
        out = pd.DataFrame({
            "Posted Date": (per.end_time + pd.Timedelta(days=15)).strftime("%m/%d/%Y"),
            "Song Title": df["title"],
            "Artist Name": df["artist"],
            "Territory": df["Country"],
            "Units": df["streams"],
            "Rate (EUR)": (df["rate_usd"] / df["EUR"]).round(8),
            "Total Earned (EUR)": (df["earn_usd"] / df["EUR"]).round(4),
        })
        fname = f"B_{m}.xlsx"
        footer_total = out["Total Earned (EUR)"].sum()
        # Injection: footer total that does not reconcile to its lines
        if m == "2019-07":
            footer_total += 1250.00
            log_issue("B", fname, "footer_mismatch", 0, "footer overstated by EUR 1,250.00")
        # Injection: title/artist formatting drift (casing, whitespace) that breaks naive joins
        drift = out.sample(frac=0.02, random_state=int(m[-2:]) + 7).index
        out.loc[drift, "Song Title"] = out.loc[drift, "Song Title"].str.upper() + "  "
        log_issue("B", fname, "name_format_drift", len(drift), "UPPER CASE + trailing spaces")
        write_b(out, fname, per, footer_total)
        # Injection: the whole March statement delivered twice under a new filename
        if m == "2019-03":
            write_b(out, "B_2019-03_resend.xlsx", per, footer_total)
            log_issue("B", "B_2019-03_resend.xlsx", "duplicate_statement", len(out))

    # ------------------------------------------------------------------ C
    # Semicolon CSV, GBP, ISO3 territory, gross/fee/net columns, lowercase headers.
    for m in months:
        fname = f"C_{m}.csv"
        # Injection: June statement never delivered
        if m == "2019-06":
            n_missing = int(((lines.distributor == "C") & (lines.month == m)).sum())
            log_issue("C", fname, "missing_statement", n_missing, "file not delivered")
            continue
        df = lines[(lines.distributor == "C") & (lines.month == m)].copy()
        per = pd.Period(m)
        gross = (df["earn_usd"] / df["GBP"]).round(4)
        out = pd.DataFrame({
            "period_start": per.start_time.strftime("%d.%m.%Y"),
            "period_end": per.end_time.strftime("%d.%m.%Y"),
            "track_ref": "spotify:track:" + df["track_id"],
            "track": df["title"],
            "artist": df["artist"],
            "territory_code": df["iso3"],
            "streams": df["streams"],
            "gross_gbp": gross,
            "fee_pct": C_FEE_PCT,
            "net_gbp": (gross * (1 - C_FEE_PCT)).round(4),
        })
        # Injection: territory code left blank on a few lines
        blank = out.sample(n=4, random_state=int(m[-2:]) + 3).index
        out.loc[blank, "territory_code"] = ""
        log_issue("C", fname, "missing_territory", 4)
        # Injection: chargeback lines (negative) for the same month
        cb = out.drop(blank).sample(n=3, random_state=int(m[-2:]) + 9).copy()
        for col in ("streams", "gross_gbp", "net_gbp"):
            cb[col] = -cb[col]
        out = pd.concat([out, cb])
        log_issue("C", fname, "negative_adjustment", 3, "chargeback")
        out.to_csv(os.path.join(STMT_DIR, "distributor_c", fname), sep=";", index=False)

    pd.DataFrame(manifest).to_csv(os.path.join(REF_DIR, "injection_manifest.csv"), index=False)
    print(f"Chart rows read: {len(raw):,} | tracks in master catalog: {len(master):,}")
    print(f"True statement lines generated (before injections): {len(lines):,}")
    print(lines.groupby("distributor").size().to_string())
    print(f"Injected issues logged: {len(manifest)} entries -> data/reference/injection_manifest.csv")


def write_b(out, fname, per, footer_total):
    path = os.path.join(STMT_DIR, "distributor_b", fname)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.DataFrame([["Royalty Statement - Distributor B"],
                      [f"Period: {per.start_time:%m/%d/%Y} - {per.end_time:%m/%d/%Y}"]]
                     ).to_excel(xw, index=False, header=False, startrow=0)
        out.to_excel(xw, index=False, startrow=3)
        pd.DataFrame([["TOTAL", "", "", "", "", "", round(footer_total, 2)]]
                     ).to_excel(xw, index=False, header=False, startrow=4 + len(out))


if __name__ == "__main__":
    main()
