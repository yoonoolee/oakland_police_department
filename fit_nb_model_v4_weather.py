"""
V4: adds weather (temperature, precipitation) on top of V2 (seasonal +
holiday, 2024+ training data only -- V3's trend term was dropped, see memory
opd_demand_forecasting_scope, it overshot on extrapolation and made things
worse).

Motivation: the V2 long-horizon evaluation found a systematic hour-of-day
bias (over-predicting daytime, under-predicting nighttime) on an
April-June 2026 holdout. Hypothesis is this is a seasonal/weather effect
(e.g. warmer, longer days shifting activity from daytime to evening) rather
than a secular trend -- weather is a more principled way to capture that
than a coarse month dummy.

Weather source: Open-Meteo historical archive API for Oakland, cached at
Data/Our Data/weather_oakland_2024_2026.parquet (see fetch_weather_data.py).
Includes temp_c (with a quadratic term, since both very cold and very hot
could plausibly push calls up) and precip_mm.

Evaluated on the same 13-week holdout as V2/V3 for direct comparison,
checking both overall MAE/RMSE and whether the hour-of-day bias shrinks.
"""

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

CALLS_PARQUET = "../Data/Our Data/harmonized_calls_2021_2026.parquet"
WEATHER_PARQUET = "../Data/Our Data/weather_oakland_2024_2026.parquet"
OUTPUT_BIAS_PLOT = "../Outputs/v4_hour_of_day_bias.png"

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

    weather = pd.read_parquet(WEATHER_PARQUET)
    data = data.merge(weather, on="hour", how="left")
    print(f"Weather join: {data['temp_c'].isna().sum()} rows missing weather (should be 0)")
    data["temp_c2"] = data["temp_c"] ** 2

    cutoff = data["hour"].max() - pd.Timedelta(weeks=HOLDOUT_WEEKS) + pd.Timedelta(hours=1)
    train = data[data["hour"] < cutoff].copy()
    test = data[data["hour"] >= cutoff].copy()

    print(f"Train: {len(train):,} hours, {train['hour'].min()} to {train['hour'].max()}")
    print(f"Test:  {len(test):,} hours, {test['hour'].min()} to {test['hour'].max()}")

    formula_v2 = "calls ~ C(hour_of_day) * C(day_of_week) + C(hour_of_day) * is_holiday"
    formula_v4 = formula_v2 + " + temp_c + temp_c2 + precip_mm"

    print("\n=== V2 (seasonal + holiday, 2024+, no weather) ===")
    v2_model = smf.negativebinomial(formula_v2, data=train).fit(disp=0, maxiter=200, method="bfgs")
    v2_pred = v2_model.predict(test)
    evaluate(test["calls"].values, v2_pred.values, "V2")

    print("\n=== V4 (+ weather: temp_c, temp_c^2, precip_mm) ===")
    v4_model = smf.negativebinomial(formula_v4, data=train).fit(disp=0, maxiter=200, method="bfgs")
    print("Converged:", v4_model.mle_retvals.get("converged"))
    print(v4_model.summary().tables[1])
    v4_pred = v4_model.predict(test)
    evaluate(test["calls"].values, v4_pred.values, "V4")

    test["v2_pred"] = v2_pred
    test["v4_pred"] = v4_pred
    bias_v2 = test.groupby("hour_of_day").apply(lambda g: (g["v2_pred"] - g["calls"]).mean(), include_groups=False)
    bias_v4 = test.groupby("hour_of_day").apply(lambda g: (g["v4_pred"] - g["calls"]).mean(), include_groups=False)

    print("\nMean bias by hour-of-day (predicted - actual):")
    comp = pd.DataFrame({"V2_bias": bias_v2, "V4_bias": bias_v4})
    print(comp.round(2).to_string())
    print(f"\nMean |bias| across hours: V2={comp['V2_bias'].abs().mean():.2f}  V4={comp['V4_bias'].abs().mean():.2f}")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    width = 0.4
    ax.bar(comp.index - width / 2, comp["V2_bias"], width, label="V2 (no weather)")
    ax.bar(comp.index + width / 2, comp["V4_bias"], width, label="V4 (+ weather)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Prediction bias by hour-of-day: V2 vs V4 (13-week holdout)")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Bias (calls)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_BIAS_PLOT, dpi=150)
    print(f"\nSaved {OUTPUT_BIAS_PLOT}")


if __name__ == "__main__":
    main()
