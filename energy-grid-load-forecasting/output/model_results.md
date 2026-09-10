# Load Forecasting Model Results — PJME Zone

Train: 2002-01-08 to 2017-08-03 (136,487 hours)

Test (held out, most recent year): 2017-08-04 to 2018-08-03 (8,737 hours)

| Model | MAPE | RMSE (MW) | R2 |
|---|---|---|---|
| Linear Regression | 6.04% | 2549 | 0.8222 |
| Random Forest | 4.81% | 2062 | 0.8837 |
| XGBoost | 4.36% | 1842 | 0.9072 |

Best model: **XGBoost** (4.36% MAPE)

Features: hour-of-day, day-of-week, weekend flag, month, season (one-hot), 24-hour lag, 168-hour (1-week) lag, trailing 24-hour rolling average.

Split is time-based (final year held out), not random shuffling, since random splits leak future information into lag features for a temporal forecasting problem.
