"""
Evaluates the V2 (seasonal + holiday) NB model over a longer holdout than the
1-week test used during development -- to get an honest read on "how good is
this baseline, generally" rather than one week's luck.

Single train/test split (no weekly retraining): train on everything before
the holdout window, fit once, predict every hour across the whole holdout in
one pass. This mirrors what fit_nb_model_v2_holidays.py already did, just
with a ~13-week holdout instead of 1 week, and richer diagnostics:
  - overall MAE/RMSE/MAPE
  - MAE/RMSE by week within the holdout (is error stable over time?)
  - mean bias by hour-of-day (does it systematically over/under-predict at
    certain times of day?)
  - full-span actual-vs-predicted plot
"""

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

CALLS_PARQUET = "../Data/Our Data/harmonized_calls_2021_2026.parquet"
OUTPUT_PLOT = "../Outputs/v2_long_horizon_eval.png"
OUTPUT_BIAS_PLOT = "../Outputs/v2_hour_of_day_bias.png"

HOLDOUT_WEEKS = 13


def build_hourly_counts():
    df = pd.read_parquet(CALLS_PARQUET, columns=["event_time"])
    counts = df["event_time"].dt.floor("h").value_counts().sort_index()
    full_index = pd.date_range(counts.index.min(), counts.index.max(), freq="h")
    hourly = counts.reindex(full_index, fill_value=0)
    hourly.index.name = "hour"
    hourly.name = "calls"
    out = hourly.reset_index()
    out["hour_of_day"] = out["hour"].dt.hour
    out["day_of_week"] = out["hour"].dt.dayofweek

    start, end = out["hour"].min(), out["hour"].max()
    federal = set(USFederalHolidayCalendar().holidays(start=start, end=end).date)
    years = range(start.year, end.year + 1)
    fixed_dates = set()
    for y in years:
        fixed_dates.update([
            pd.Timestamp(y, 7, 4).date(),
            pd.Timestamp(y, 10, 31).date(),
            pd.Timestamp(y, 12, 31).date(),
        ])
    holiday_dates = federal | fixed_dates
    out["is_holiday"] = out["hour"].dt.date.isin(holiday_dates).astype(int)
    return out


def main():
    data = build_hourly_counts()

    cutoff = data["hour"].max() - pd.Timedelta(weeks=HOLDOUT_WEEKS) + pd.Timedelta(hours=1)
    train = data[data["hour"] < cutoff].copy()
    test = data[data["hour"] >= cutoff].copy()

    print(f"Train: {len(train):,} hours, {train['hour'].min()} to {train['hour'].max()}")
    print(f"Test:  {len(test):,} hours, {test['hour'].min()} to {test['hour'].max()} "
          f"(~{HOLDOUT_WEEKS} weeks)")

    formula_v2 = "calls ~ C(hour_of_day) * C(day_of_week) + C(hour_of_day) * is_holiday"
    model = smf.negativebinomial(formula_v2, data=train).fit(disp=0)
    test["pred"] = model.predict(test)

    err = test["calls"] - test["pred"]
    mae = err.abs().mean()
    rmse = np.sqrt((err ** 2).mean())
    mape = (err.abs() / test["calls"].replace(0, np.nan)).mean() * 100
    print(f"\nOverall over {HOLDOUT_WEEKS} weeks: MAE={mae:.2f}  RMSE={rmse:.2f}  "
          f"MAPE={mape:.1f}%  (mean actual={test['calls'].mean():.1f} calls/hr)")

    # Weekly breakdown -- is accuracy stable across the holdout?
    test["week"] = test["hour"].dt.to_period("W")
    weekly = test.groupby("week").apply(
        lambda g: pd.Series({
            "mae": (g["calls"] - g["pred"]).abs().mean(),
            "rmse": np.sqrt(((g["calls"] - g["pred"]) ** 2).mean()),
            "mean_actual": g["calls"].mean(),
            "holiday_hours": g["is_holiday"].sum(),
        }),
        include_groups=False,
    )
    print("\nWeekly breakdown:")
    print(weekly.round(2).to_string())

    # Bias by hour-of-day -- systematic over/under-prediction at certain times?
    bias = test.groupby("hour_of_day").apply(
        lambda g: (g["pred"] - g["calls"]).mean(), include_groups=False
    )
    print("\nMean bias by hour-of-day (predicted - actual; positive = over-predicting):")
    print(bias.round(2).to_string())

    # Full-span plot
    fig, ax = plt.subplots(figsize=(16, 4.5))
    ax.plot(test["hour"], test["calls"], label="Actual", color="black", linewidth=0.8)
    ax.plot(test["hour"], test["pred"], label="V2 predicted", color="tab:orange",
            linewidth=0.8, alpha=0.85)
    ax.set_title(f"V2 model: actual vs. predicted calls/hour over {HOLDOUT_WEEKS}-week holdout")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Calls")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_PLOT, dpi=150)
    print(f"\nSaved {OUTPUT_PLOT}")

    # Bias-by-hour-of-day plot
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(bias.index, bias.values, color="tab:blue")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_title("Mean prediction bias by hour-of-day (predicted - actual)")
    ax2.set_xlabel("Hour of day")
    ax2.set_ylabel("Bias (calls)")
    fig2.tight_layout()
    fig2.savefig(OUTPUT_BIAS_PLOT, dpi=150)
    print(f"Saved {OUTPUT_BIAS_PLOT}")


if __name__ == "__main__":
    main()
