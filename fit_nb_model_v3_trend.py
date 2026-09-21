"""
V3: drops 2021-2023 (per project decision -- V1/V2 testing showed no accuracy
benefit from the older years, and the CAD system itself changed in 2024) and
adds a trend term on top of V2 (seasonal + holiday).

The V2 long-horizon evaluation showed a systematic, hour-specific bias:
over-predicting daytime hours by 2-5.5 calls/hr and under-predicting
nighttime hours by 2-4 calls/hr, consistently across a 13-week holdout. That
means daytime volume has been trending down (or nighttime up) relative to
the historical average, and a *flat* trend term wouldn't fix this since the
direction differs by hour. So trend is interacted with hour-of-day, letting
each hour have its own slope over time.

trend = days since the start of the (2024+) training data (continuous).

Formula: calls ~ C(hour_of_day)*C(day_of_week) + C(hour_of_day)*is_holiday
                + C(hour_of_day)*trend

Evaluated on the same 13-week holdout as the V2 long-horizon check, for a
direct before/after comparison, including whether the hour-of-day bias
pattern actually goes away.
"""

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

CALLS_PARQUET = "../Data/Our Data/harmonized_calls_2021_2026.parquet"
OUTPUT_BIAS_PLOT = "../Outputs/v3_hour_of_day_bias.png"

TRAIN_START = "2024-01-01"
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


def evaluate(y_true, y_pred, label):
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    print(f"  [{label}] MAE={mae:.2f}  RMSE={rmse:.2f}")
    return mae, rmse


def main():
    data = build_hourly_counts()
    data = data[data["hour"] >= TRAIN_START].reset_index(drop=True)

    trend_origin = data["hour"].min()
    data["trend"] = (data["hour"] - trend_origin).dt.total_seconds() / 86400  # days

    cutoff = data["hour"].max() - pd.Timedelta(weeks=HOLDOUT_WEEKS) + pd.Timedelta(hours=1)
    train = data[data["hour"] < cutoff].copy()
    test = data[data["hour"] >= cutoff].copy()

    print(f"Train (2024+ only): {len(train):,} hours, {train['hour'].min()} to {train['hour'].max()}")
    print(f"Test:  {len(test):,} hours, {test['hour'].min()} to {test['hour'].max()}")

    formula_v2 = "calls ~ C(hour_of_day) * C(day_of_week) + C(hour_of_day) * is_holiday"
    formula_v3 = formula_v2 + " + C(hour_of_day) * trend"

    print("\n=== V2 (2024+ training data, no trend) ===")
    v2_model = smf.negativebinomial(formula_v2, data=train).fit(disp=0, maxiter=200, method="bfgs")
    v2_pred = v2_model.predict(test)
    evaluate(test["calls"].values, v2_pred.values, "V2 / 2024+")

    print("\n=== V3 (2024+ training data, + trend x hour_of_day) ===")
    v3_model = smf.negativebinomial(formula_v3, data=train).fit(disp=0, maxiter=200, method="bfgs")
    print("Converged:", v3_model.mle_retvals.get("converged"))
    v3_pred = v3_model.predict(test)
    evaluate(test["calls"].values, v3_pred.values, "V3 / 2024+ + trend")

    test["v2_pred"] = v2_pred
    test["v3_pred"] = v3_pred
    bias_v2 = test.groupby("hour_of_day").apply(lambda g: (g["v2_pred"] - g["calls"]).mean(), include_groups=False)
    bias_v3 = test.groupby("hour_of_day").apply(lambda g: (g["v3_pred"] - g["calls"]).mean(), include_groups=False)

    print("\nMean bias by hour-of-day (predicted - actual):")
    comp = pd.DataFrame({"V2_bias": bias_v2, "V3_bias": bias_v3})
    print(comp.round(2).to_string())

    fig, ax = plt.subplots(figsize=(9, 4.5))
    width = 0.4
    ax.bar(comp.index - width / 2, comp["V2_bias"], width, label="V2 (no trend)")
    ax.bar(comp.index + width / 2, comp["V3_bias"], width, label="V3 (+ trend)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Prediction bias by hour-of-day: V2 vs V3 (13-week holdout)")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Bias (calls)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_BIAS_PLOT, dpi=150)
    print(f"\nSaved {OUTPUT_BIAS_PLOT}")


if __name__ == "__main__":
    main()
