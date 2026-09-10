"""
Energy Grid Load Forecasting — next-day peak demand forecasting model
Trains and compares Linear Regression, Random Forest, and XGBoost on the
PJME zone (largest, most complete series in the warehouse) using calendar
and lag features, evaluated with a time-based (not random) train/test split
since load forecasting is a temporal problem.
"""
import pandas as pd
import numpy as np
import sqlite3
import os
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
import xgboost as xgb

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DB_PATH = os.path.join(OUTPUT_DIR, "energy_dw.db")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("""
    SELECT d.Full_Date, f.Hour_Of_Day, d.Day_Of_Week, d.Is_Weekend, d.Season, f.Demand_MW
    FROM Fact_Hourly_Demand f
    JOIN Dim_Date d ON f.Date_Key = d.Date_Key
    JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
    WHERE z.Zone_Code = 'PJME'
    ORDER BY d.Full_Date, f.Hour_Of_Day
""", conn)
conn.close()

df["Datetime"] = pd.to_datetime(df["Full_Date"]) + pd.to_timedelta(df["Hour_Of_Day"], unit="h")
df = df.sort_values("Datetime").reset_index(drop=True)

# Feature engineering
df["Lag_24h"] = df["Demand_MW"].shift(24)
df["Lag_168h"] = df["Demand_MW"].shift(168)
df["Rolling_24h_Avg"] = df["Demand_MW"].shift(1).rolling(24).mean()
df["Month"] = df["Datetime"].dt.month
season_dummies = pd.get_dummies(df["Season"], prefix="Season")
df = pd.concat([df, season_dummies], axis=1)
df = df.dropna().reset_index(drop=True)

feature_cols = (["Hour_Of_Day", "Day_Of_Week", "Is_Weekend", "Month",
                  "Lag_24h", "Lag_168h", "Rolling_24h_Avg"]
                 + list(season_dummies.columns))
X = df[feature_cols]
y = df["Demand_MW"]

# Time-based split: last full year (2017-08-04 to 2018-08-03) held out as test
split_date = pd.Timestamp("2017-08-04")
train_mask = df["Datetime"] < split_date
X_train, X_test = X[train_mask], X[~train_mask]
y_train, y_test = y[train_mask], y[~train_mask]

models = {
    "Linear Regression": LinearRegression(),
    "Random Forest": RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1),
    "XGBoost": xgb.XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, random_state=42),
}

results = []
for name, model in models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mape = mean_absolute_percentage_error(y_test, preds) * 100
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    results.append((name, mape, rmse, r2))
    print(f"{name:20} MAPE={mape:.2f}%  RMSE={rmse:.0f} MW  R2={r2:.4f}")

best = min(results, key=lambda r: r[1])

with open(os.path.join(OUTPUT_DIR, "model_results.md"), "w") as f:
    f.write("# Load Forecasting Model Results — PJME Zone\n\n")
    f.write(f"Train: {df[train_mask]['Datetime'].min().date()} to {df[train_mask]['Datetime'].max().date()} "
            f"({train_mask.sum():,} hours)\n\n")
    f.write(f"Test (held out, most recent year): {df[~train_mask]['Datetime'].min().date()} to "
            f"{df[~train_mask]['Datetime'].max().date()} ({(~train_mask).sum():,} hours)\n\n")
    f.write("| Model | MAPE | RMSE (MW) | R2 |\n|---|---|---|---|\n")
    for name, mape, rmse, r2 in results:
        f.write(f"| {name} | {mape:.2f}% | {rmse:.0f} | {r2:.4f} |\n")
    f.write(f"\nBest model: **{best[0]}** ({best[1]:.2f}% MAPE)\n")
    f.write("\nFeatures: hour-of-day, day-of-week, weekend flag, month, season "
            "(one-hot), 24-hour lag, 168-hour (1-week) lag, trailing 24-hour rolling average.\n")
    f.write("\nSplit is time-based (final year held out), not random shuffling, "
            "since random splits leak future information into lag features for a "
            "temporal forecasting problem.\n")

print(f"\nBest: {best[0]} ({best[1]:.2f}% MAPE)")
