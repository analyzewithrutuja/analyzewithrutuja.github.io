"""
Music Royalty Statement Pipeline — Step 2: ETL + validation
Extract:   every statement file from 3 distributors (CSV/USD, Excel/EUR,
           semicolon-CSV/GBP), each with its own layout and conventions
Transform: map to one standard schema, convert to USD, match every line to
           the master catalog, and run 9 data-quality checks
Load:      star-schema SQLite warehouse + statement register + exceptions table

Nothing here reads data/reference/injection_manifest.csv — every issue has to
be found from the statements themselves.
"""
import glob
import hashlib
import os
import re
import sqlite3
import time

import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..")
STMT_DIR = os.path.join(BASE, "data", "statements")
REF_DIR = os.path.join(BASE, "data", "reference")
OUT_DIR = os.path.join(BASE, "output")
SQL_DIR = os.path.join(BASE, "sql")
DB_PATH = os.path.join(OUT_DIR, "royalty_dw.db")

EXPECTED_PERIODS = [f"2019-{m:02d}" for m in range(1, 11)]
RATE_OUTLIER_RATIO = 5.0        # effective rate > 5x or < 1/5 of peer median
VOLUME_DROP_RATIO = 0.80        # statement streams < 80% of trailing-3 median
FOOTER_TOLERANCE = 1.00         # currency units

STD_COLS = ["statement_file", "distributor", "statement_period", "sale_period", "line_no",
            "track_id", "title_raw", "artist_raw", "territory_iso2", "streams",
            "currency", "gross_local", "net_local"]

exceptions = []
log_lines = []


def log(msg):
    print(msg)
    log_lines.append(msg)


def exc(check, severity, file, n, detail):
    exceptions.append(dict(check_name=check, severity=severity, statement_file=file,
                           rows_affected=int(n), detail=detail))


def norm(s):
    """Normalization key for title/artist matching: casefold, trim, collapse spaces."""
    return s.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.casefold()


# ---------------------------------------------------------------------------
# Extract: one reader per distributor layout
# ---------------------------------------------------------------------------
def read_a(path, terr):
    df = pd.read_csv(path, dtype={"Track ID": str})
    return pd.DataFrame({
        "statement_period": df["Reporting Date"].str[:7],
        "sale_period": df["Sale Month"],
        "track_id": df["Track ID"],
        "title_raw": df["Title"], "artist_raw": df["Artist"],
        "territory_iso2": df["Country of Sale"],
        "streams": df["Quantity"],
        "currency": "USD",
        "gross_local": df["Earnings (USD)"], "net_local": df["Earnings (USD)"],
    }), None


def read_b(path, terr):
    pre = pd.read_excel(path, header=None, nrows=2)
    m = re.search(r"Period: (\d{2})/\d{2}/(\d{4})", str(pre.iat[1, 0]))
    period = f"{m.group(2)}-{m.group(1)}"
    df = pd.read_excel(path, header=3)
    is_total = df["Posted Date"].astype(str).str.upper().eq("TOTAL")
    footer = float(df.loc[is_total, "Total Earned (EUR)"].iat[0]) if is_total.any() else None
    df = df[~is_total]
    name_to_iso2 = dict(zip(terr["territory"], terr["iso2"]))
    return pd.DataFrame({
        "statement_period": period,
        "sale_period": period,
        "track_id": None,                      # Distributor B does not send track IDs
        "title_raw": df["Song Title"], "artist_raw": df["Artist Name"],
        "territory_iso2": df["Territory"].map(name_to_iso2),
        "streams": df["Units"],
        "currency": "EUR",
        "gross_local": df["Total Earned (EUR)"], "net_local": df["Total Earned (EUR)"],
    }), footer


def read_c(path, terr):
    df = pd.read_csv(path, sep=";", dtype={"territory_code": str}, keep_default_na=False)
    iso3_to_iso2 = dict(zip(terr["iso3"], terr["iso2"]))
    period = pd.to_datetime(df["period_start"], format="%d.%m.%Y").dt.strftime("%Y-%m")
    return pd.DataFrame({
        "statement_period": period,
        "sale_period": period,
        "track_id": df["track_ref"].str.replace("spotify:track:", "", regex=False),
        "title_raw": df["track"].replace("", np.nan), "artist_raw": df["artist"].replace("", np.nan),
        "territory_iso2": df["territory_code"].map(iso3_to_iso2),
        "streams": df["streams"],
        "currency": "GBP",
        "gross_local": df["gross_gbp"], "net_local": df["net_gbp"],
    }), None


READERS = {"A": ("distributor_a/*.csv", read_a),
           "B": ("distributor_b/*.xlsx", read_b),
           "C": ("distributor_c/*.csv", read_c)}


def main():
    t_start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    terr = pd.read_csv(os.path.join(REF_DIR, "territories.csv"), keep_default_na=False)
    fx = pd.read_csv(os.path.join(REF_DIR, "fx_rates.csv"))
    master = pd.read_csv(os.path.join(REF_DIR, "master_catalog.csv"))
    log("=== Music Royalty Statement Pipeline — ETL run ===")

    # ---------------- Extract + per-statement register
    frames, register = [], []
    for dist, (pattern, reader) in READERS.items():
        for path in sorted(glob.glob(os.path.join(STMT_DIR, pattern))):
            t0 = time.time()
            fname = os.path.basename(path)
            df, footer = reader(path, terr)
            df.insert(0, "statement_file", fname)
            df.insert(1, "distributor", dist)
            df["line_no"] = np.arange(1, len(df) + 1)
            # content fingerprint: independent of file name / file bytes
            fp_cols = ["sale_period", "track_id", "title_raw", "artist_raw", "territory_iso2", "streams", "net_local"]
            line_fp = pd.util.hash_pandas_object(df[fp_cols].astype(str), index=False)
            content_fp = hashlib.md5(np.sort(line_fp.values).tobytes()).hexdigest()
            register.append(dict(statement_file=fname, distributor=dist,
                                 statement_period=df["statement_period"].iat[0],
                                 currency=df["currency"].iat[0], rows_in=len(df),
                                 footer_total_local=footer, content_fp=content_fp,
                                 read_seconds=round(time.time() - t0, 3)))
            frames.append(df[STD_COLS])
    lines = pd.concat(frames, ignore_index=True)
    reg = pd.DataFrame(register)
    log(f"[Extract] {len(reg)} statement files, {len(lines):,} raw lines "
        f"({', '.join(f'{d}={n:,}' for d, n in lines.groupby('distributor').size().items())})")
    lines["quarantine_reason"] = None

    # ---------------- Check 1: duplicate statement delivered twice (same content, new file name)
    dup_stmt = reg[reg.duplicated(["distributor", "statement_period", "content_fp"], keep="first")]
    for _, r in dup_stmt.iterrows():
        orig = reg[(reg.content_fp == r.content_fp) & (reg.statement_file != r.statement_file)].statement_file.iat[0]
        exc("duplicate_statement", "HIGH", r.statement_file, r.rows_in,
            f"identical content to {orig}; whole file rejected")
    lines = lines[~lines.statement_file.isin(dup_stmt.statement_file)]
    log(f"[Check 1] duplicate statements rejected: {len(dup_stmt)} "
        f"({int(dup_stmt.rows_in.sum()):,} lines) {list(dup_stmt.statement_file)}")

    # ---------------- Check 2: missing statement periods per distributor
    for dist in READERS:
        have = set(reg[(reg.distributor == dist) & ~reg.statement_file.isin(dup_stmt.statement_file)].statement_period)
        for p in EXPECTED_PERIODS:
            if p not in have:
                exc("missing_statement", "HIGH", f"{dist}_{p}", 0,
                    f"no statement received from distributor {dist} for {p}")
                log(f"[Check 2] MISSING statement: distributor {dist}, period {p}")

    # ---------------- Check 3: exact duplicate lines within a statement
    key = ["statement_file", "sale_period", "track_id", "title_raw", "artist_raw", "territory_iso2", "streams", "net_local"]
    dmask = lines.duplicated(key, keep="first")
    for f, n in lines[dmask].groupby("statement_file").size().items():
        exc("duplicate_line", "MEDIUM", f, n, "exact duplicate line removed")
    lines = lines[~dmask]
    log(f"[Check 3] duplicate lines removed: {int(dmask.sum()):,}")

    # ---------------- Check 4: footer total reconciliation (Distributor B)
    line_totals = lines.groupby("statement_file")["net_local"].sum()
    for _, r in reg[reg.footer_total_local.notna()].iterrows():
        if r.statement_file in dup_stmt.statement_file.values:
            continue
        diff = r.footer_total_local - line_totals[r.statement_file]
        if abs(diff) > FOOTER_TOLERANCE:
            exc("footer_mismatch", "HIGH", r.statement_file, 0,
                f"footer {r.footer_total_local:,.2f} vs sum of lines {line_totals[r.statement_file]:,.2f} "
                f"({r.currency} {diff:+,.2f})")
            log(f"[Check 4] FOOTER MISMATCH {r.statement_file}: {r.currency} {diff:+,.2f}")

    # ---------------- Check 5: missing territory -> quarantine (cannot be rated or taxed)
    m = lines.territory_iso2.isna() | (lines.territory_iso2 == "")
    for f, n in lines[m].groupby("statement_file").size().items():
        exc("missing_territory", "MEDIUM", f, n, "territory code blank; line quarantined")
    lines.loc[m, "quarantine_reason"] = "missing_territory"
    log(f"[Check 5] lines with missing territory quarantined: {int(m.sum())}")

    # ---------------- Check 6: match every line to the master catalog
    # The same recording often exists under several Spotify track IDs (single vs. album vs.
    # market-specific releases). Without an ISRC, a title+artist line from Distributor B cannot
    # be pinned to one ID, so every line is also rolled up to a song-level ID (smallest track ID
    # sharing the normalized title+artist) and valuation runs at song level.
    master["k"] = norm(master.title) + "|" + norm(master.artist)
    master["song_id"] = master.groupby("k").track_id.transform("min")
    ids_per_song = master.groupby("k").track_id.nunique()
    song_by_k = master.drop_duplicates("k").set_index("k").song_id
    need = lines.track_id.isna()
    k = norm(lines.loc[need, "title_raw"]) + "|" + norm(lines.loc[need, "artist_raw"])
    lines["song_id"] = lines.track_id.map(master.set_index("track_id").song_id)
    lines.loc[need, "song_id"] = k.map(song_by_k).values
    single = need & k.reindex(lines.index).isin(ids_per_song[ids_per_song == 1].index)
    lines.loc[single, "track_id"] = lines.loc[single, "song_id"]
    multi = need & lines.song_id.notna() & ~single
    unmatched = lines.song_id.isna() & lines.quarantine_reason.isna()
    lines.loc[unmatched, "quarantine_reason"] = "unmatched_track"
    b_lines = int((lines.distributor == "B").sum())
    b_matched = int(((lines.distributor == "B") & lines.song_id.notna()).sum())
    cat_title = lines.song_id.map(master.drop_duplicates("song_id").set_index("song_id").title)
    drift = (lines.distributor == "B") & lines.song_id.notna() & (norm(lines.title_raw) == norm(cat_title))         & (lines.title_raw != cat_title)
    for f, n in lines[multi].groupby("statement_file").size().items():
        exc("multi_id_song_rollup", "LOW", f, n, "title+artist maps to several Spotify IDs of one song; rolled up to song_id")
    for f, n in lines[unmatched].groupby("statement_file").size().items():
        exc("unmatched_track", "MEDIUM", f, n, "no catalog match (title/artist missing in source)")
    for f, n in lines[drift].groupby("statement_file").size().items():
        exc("name_format_drift", "LOW", f, n, "title casing/whitespace differs from catalog; matched after normalization")
    log(f"[Check 6] master catalog: {master.track_id.nunique():,} track IDs -> {master.song_id.nunique():,} songs "
        f"({int((ids_per_song > 1).sum()):,} songs released under 2+ IDs)")
    log(f"[Check 6] Distributor B title+artist matching: {b_matched:,}/{b_lines:,} lines matched "
        f"({b_matched / b_lines:.2%}); {int(multi.sum()):,} rolled up from multi-ID songs, unmatched={int(unmatched.sum())}, "
        f"format-drift lines recovered by normalization={int(drift.sum())}")

    # ---------------- Convert to USD
    fx_long = fx.melt(id_vars="month", var_name="currency", value_name="usd_per_unit")
    fx_long = pd.concat([fx_long, pd.DataFrame({"month": EXPECTED_PERIODS, "currency": "USD", "usd_per_unit": 1.0})])
    lines = lines.merge(fx_long, left_on=["statement_period", "currency"], right_on=["month", "currency"], how="left")
    lines["gross_usd"] = lines.gross_local * lines.usd_per_unit
    lines["net_usd"] = lines.net_local * lines.usd_per_unit
    lines["is_adjustment"] = (lines.streams < 0) | (lines.net_usd < 0)

    # ---------------- Check 7: negative adjustments (valid, but must be tied back to an original line)
    adj = lines[lines.is_adjustment]
    orig = lines[~lines.is_adjustment]
    tie_key = ["distributor", "sale_period", "track_id", "territory_iso2", "abs_streams"]
    tie = (adj.assign(abs_streams=adj.streams.abs())[tie_key]
              .merge(orig.assign(abs_streams=orig.streams)[tie_key].drop_duplicates(),
                     on=tie_key, how="left", indicator=True))
    matched_adj = int((tie._merge == "both").sum())
    for f, n in adj.groupby("statement_file").size().items():
        exc("negative_adjustment", "LOW", f, n, "reversal/chargeback line; kept and tagged is_adjustment")
    log(f"[Check 7] negative adjustments: {len(adj)} lines, USD {adj.net_usd.sum():,.2f}; "
        f"{matched_adj}/{len(adj)} tied to an original line")

    # ---------------- Check 8: effective per-stream rate outliers vs peer median
    ok = lines.quarantine_reason.isna() & ~lines.is_adjustment & (lines.streams > 0)
    lines["eff_rate"] = np.where(ok, lines.gross_usd / lines.streams.where(lines.streams != 0), np.nan)
    peer = lines[ok].groupby(["distributor", "statement_period", "territory_iso2"]).eff_rate.median().rename("peer_rate")
    lines = lines.join(peer, on=["distributor", "statement_period", "territory_iso2"])
    ratio = lines.eff_rate / lines.peer_rate
    out = ok & ((ratio > RATE_OUTLIER_RATIO) | (ratio < 1 / RATE_OUTLIER_RATIO))
    lines.loc[out, "quarantine_reason"] = "rate_outlier"
    for f, g in lines[out].groupby("statement_file"):
        exc("rate_outlier", "HIGH", f, len(g),
            f"effective rate {g.eff_rate.iloc[0]:.5f} vs peer median {g.peer_rate.iloc[0]:.5f} "
            f"(~{ratio[g.index].median():.0f}x, likely decimal shift)")
    implied = (lines.loc[out, "streams"] * lines.loc[out, "peer_rate"]).sum()
    log(f"[Check 8] rate outliers quarantined: {int(out.sum())} lines reporting USD {lines.loc[out, 'gross_usd'].sum():,.2f} "
        f"vs USD {implied:,.2f} at the peer rate (overstatement of USD {lines.loc[out, 'gross_usd'].sum() - implied:,.2f} blocked)")

    # ---------------- Check 9: statement volume drop vs trailing 3 statements
    vol = (lines[~lines.is_adjustment].groupby(["distributor", "statement_period"]).streams.sum().reset_index()
           .sort_values(["distributor", "statement_period"]))
    vol["trail_med"] = vol.groupby("distributor").streams.transform(lambda s: s.shift(1).rolling(3, min_periods=2).median())
    drops = vol[vol.streams < VOLUME_DROP_RATIO * vol.trail_med]
    for _, r in drops.iterrows():
        exc("volume_drop", "MEDIUM", f"{r.distributor}_{r.statement_period}", 0,
            f"streams {r.streams:,.0f} = {r.streams / r.trail_med:.0%} of trailing-3 median; check for partial period")
        log(f"[Check 9] VOLUME DROP distributor {r.distributor} {r.statement_period}: "
            f"{r.streams / r.trail_med:.0%} of trailing median")

    # ---------------- Load
    clean = lines[lines.quarantine_reason.isna()].copy()
    quarantine = lines[lines.quarantine_reason.notna()].copy()
    exc_df = pd.DataFrame(exceptions)

    reg["rows_loaded"] = reg.statement_file.map(clean.groupby("statement_file").size()).fillna(0).astype(int)
    reg["rows_quarantined"] = reg.statement_file.map(quarantine.groupby("statement_file").size()).fillna(0).astype(int)
    high = set(exc_df[exc_df.severity == "HIGH"].statement_file)
    reg["status"] = np.where(reg.statement_file.isin(dup_stmt.statement_file), "REJECTED",
                     np.where(reg.statement_file.isin(high), "REVIEW", "AUTO-PASS"))

    con = sqlite3.connect(DB_PATH)
    with open(os.path.join(SQL_DIR, "01_schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    master[["track_id", "song_id", "title", "artist", "distributor"]].to_sql("dim_track", con, if_exists="append", index=False)
    terr.rename(columns={"territory": "territory_name"}).to_sql("dim_territory", con, if_exists="append", index=False)
    pd.DataFrame({"distributor": ["A", "B", "C"], "file_format": ["CSV", "Excel", "Semicolon CSV"],
                  "currency": ["USD", "EUR", "GBP"], "sends_track_id": [1, 0, 1]}
                 ).to_sql("dim_distributor", con, if_exists="append", index=False)
    # Weekly charts start on Fridays, so a month holds 4 or 5 chart weeks (Oct 2019 only 3 in this data).
    # Stored on dim_period so monthly earnings can be compared per chart week.
    fridays = pd.Series(pd.date_range("2019-01-04", "2019-10-18", freq="7D").strftime("%Y-%m")).value_counts()
    pd.DataFrame({"period": EXPECTED_PERIODS, "year": 2019, "month": range(1, 11),
                  "quarter": [(m - 1) // 3 + 1 for m in range(1, 11)],
                  "chart_weeks": [int(fridays.get(p, 0)) for p in EXPECTED_PERIODS]}
                 ).to_sql("dim_period", con, if_exists="append", index=False)
    fact_cols = ["statement_file", "distributor", "statement_period", "sale_period", "track_id", "song_id",
                 "territory_iso2", "streams", "currency", "gross_local", "net_local", "gross_usd", "net_usd", "is_adjustment"]
    clean[fact_cols].to_sql("fact_royalty_line", con, if_exists="append", index=False)
    quarantine[STD_COLS + ["song_id", "quarantine_reason"]].to_sql("quarantine_line", con, if_exists="append", index=False)
    reg.drop(columns=["content_fp"]).to_sql("statement_register", con, if_exists="append", index=False)
    exc_df.to_sql("validation_exception", con, if_exists="append", index=False)
    con.commit()
    con.close()

    # ---------------- Operational metrics
    elapsed = time.time() - t_start
    raw_total = int(reg.rows_in.sum())
    log("")
    log("=== Operational metrics ===")
    log(f"statement files processed        : {len(reg)}")
    log(f"  AUTO-PASS / REVIEW / REJECTED  : {(reg.status == 'AUTO-PASS').sum()} / "
        f"{(reg.status == 'REVIEW').sum()} / {(reg.status == 'REJECTED').sum()}")
    log(f"raw lines in                     : {raw_total:,}")
    log(f"lines loaded to fact table       : {len(clean):,}")
    log(f"lines quarantined for review     : {len(quarantine):,} "
        f"({quarantine.quarantine_reason.value_counts().to_dict()})")
    log(f"line-level auto-pass rate        : {len(clean) / raw_total:.2%}")
    log(f"net USD loaded                   : {clean.net_usd.sum():,.2f}")
    log(f"net USD held in quarantine       : {quarantine.net_usd.sum():,.2f}")
    log(f"exceptions raised                : {len(exc_df)} ({exc_df.check_name.value_counts().to_dict()})")
    log(f"end-to-end runtime               : {elapsed:.1f}s ({raw_total / elapsed:,.0f} lines/sec)")
    log(f"[Load] SQLite warehouse written to output/royalty_dw.db")

    exc_df.to_csv(os.path.join(OUT_DIR, "validation_exceptions.csv"), index=False)
    reg.drop(columns=["content_fp"]).to_csv(os.path.join(OUT_DIR, "statement_register.csv"), index=False)
    with open(os.path.join(OUT_DIR, "etl_run_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
