"""
V2: adds a holiday feature on top of the V1 baseline (fit_baseline_nb_model.py),
which only used hour-of-day x day-of-week seasonality.

Holiday set = US federal holidays (as observed, from pandas' calendar) UNION
the actual calendar dates of July 4th, Oct 31st (Halloween), and Dec 31st (New
Year's Eve) every year. The union matters because the *observed* federal
holiday (a day off work) can fall on a different date than the actual
celebration that drives call volume -- e.g. July 4, 2021 was a Sunday, so the
observed federal holiday was Monday July 5, but the fireworks activity (and
presumably the ShotSpotter/Priority-1 calls flagged in the audit report,
Appendix D) happens on the actual date, July 4th, regardless of the observed
day off. Same logic for New Year's Eve (Dec 31) vs. New Year's Day (Jan 1).

Model: calls ~ C(hour_of_day)*C(day_of_week) + C(hour_of_day)*is_holiday
(keeps the V1 seasonal structure, adds a holiday-specific hourly profile).

Evaluation: leave-one-week-out on three test weeks -- the standard "most
recent week" (no holiday in it, so this is a regression sanity check) plus a
week containing July 4th and a week containing New Year's Eve/Day (both from
2025, so they're not in the future-facing final week), comparing V1 vs V2 on
each, both overall and specifically on the holiday hours within the window.
"""

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
import statsmodels.formula.api as smf

CALLS_PARQUET = "../Data/Our Data/harmonized_calls_2021_2026.parquet"

TEST_WEEKS = {
    "recent_week": ("2026-06-24", "2026-07-01"),   # last week in the data
    "july4_2025":  ("2025-06-30", "2025-07-07"),
    "nye_2025":    ("2025-12-29", "2026-01-05"),
}


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
    print(f"    [{label}] MAE={mae:.2f}  RMSE={rmse:.2f}")
    return mae, rmse


def main():
    data = build_hourly_counts()
    n_holiday_hours = data["is_holiday"].sum()
    print(f"Hourly series: {len(data):,} hours; {n_holiday_hours:,} flagged as holiday hours "
          f"({n_holiday_hours / len(data):.1%})")

    formula_v1 = "calls ~ C(hour_of_day) * C(day_of_week)"
    formula_v2 = "calls ~ C(hour_of_day) * C(day_of_week) + C(hour_of_day) * is_holiday"

    for week_name, (start, end) in TEST_WEEKS.items():
        mask = (data["hour"] >= start) & (data["hour"] < end)
        test = data[mask].copy()
        train = data[~mask].copy()
        holiday_hours_in_test = test["is_holiday"].sum()

        print(f"\n=== Test week: {week_name} ({start} to {end}) "
              f"-- {holiday_hours_in_test} holiday hours in this window ===")

        for label, formula in [("V1 (no holiday)", formula_v1), ("V2 (+ holiday)", formula_v2)]:
            model = smf.negativebinomial(formula, data=train).fit(disp=0)
            pred = model.predict(test)
            evaluate(test["calls"].values, pred.values, f"{label} / overall")
            if holiday_hours_in_test > 0:
                hol_mask = test["is_holiday"] == 1
                evaluate(test.loc[hol_mask, "calls"].values, pred.loc[hol_mask].values,
                          f"{label} / holiday-hours-only")


if __name__ == "__main__":
    main()
