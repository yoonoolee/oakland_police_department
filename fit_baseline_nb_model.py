"""
V1 baseline: forecast total 911 calls per hour using a Negative Binomial GLM
on hour-of-day x day-of-week seasonality (a saturated 168-cell seasonal model).

Also fits a plain Poisson model for comparison, since the CAD data shows real
overdispersion (variance ~2.3x the mean even within fixed hour/day-of-week
cells) which Poisson can't represent but NB can.

Also compares two training windows (full 2021-2026 history vs. 2024+ only) to
start answering the open question of how much history the model actually
needs (see memory: opd_demand_forecasting_scope).

Evaluation: the last 7 days (168 hours) of available data are held out as a
test set, mimicking the real forecast task (predict the next 7 days' hourly
counts). "Today" = max event_time in the data, per project convention.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

CALLS_PARQUET = "../Data/Our Data/harmonized_calls_2021_2026.parquet"
OUTPUT_PLOT = "../Outputs/baseline_nb_model_test_week.png"

TEST_HOURS = 7 * 24


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
    return out


def evaluate(y_true, y_pred, label):
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    print(f"  [{label}] MAE={mae:.2f}  RMSE={rmse:.2f}")
    return mae, rmse


def main():
    data = build_hourly_counts()
    print(f"Hourly series: {len(data):,} hours, "
          f"{data['hour'].min()} to {data['hour'].max()}")

    test = data.iloc[-TEST_HOURS:].copy()
    train_full = data.iloc[:-TEST_HOURS].copy()
    train_recent = train_full[train_full["hour"] >= "2024-01-01"].copy()

    print(f"\nTest window (held out, = 'next 7 days'): "
          f"{test['hour'].min()} to {test['hour'].max()}")
    print(f"Train (full history): {len(train_full):,} hours from {train_full['hour'].min()}")
    print(f"Train (2024+ only):   {len(train_recent):,} hours from {train_recent['hour'].min()}")

    formula = "calls ~ C(hour_of_day) * C(day_of_week)"

    results = {}
    for label, train in [("full_history", train_full), ("2024_plus", train_recent)]:
        print(f"\n=== Training window: {label} ({len(train):,} hours) ===")

        poisson_model = smf.poisson(formula, data=train).fit(disp=0)
        pred_poisson = poisson_model.predict(test)
        evaluate(test["calls"].values, pred_poisson.values, f"{label} / Poisson")

        nb_model = smf.negativebinomial(formula, data=train).fit(disp=0)
        pred_nb = nb_model.predict(test)
        mae, rmse = evaluate(test["calls"].values, pred_nb.values, f"{label} / NegBinomial")

        print(f"  NB estimated alpha (dispersion): {nb_model.params['alpha']:.4f}")
        print(f"  NB AIC: {nb_model.aic:.1f}   Poisson AIC: {poisson_model.aic:.1f}")

        results[label] = dict(model=nb_model, pred=pred_nb, mae=mae, rmse=rmse)

    best_label = min(results, key=lambda k: results[k]["mae"])
    print(f"\nBest training window on held-out week (by MAE): '{best_label}'")

    # Plot actual vs. predicted (both NB models) for the held-out test week.
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(test["hour"], test["calls"], label="Actual", color="black", linewidth=1.5)
    for label, style in [("full_history", "--"), ("2024_plus", ":")]:
        ax.plot(test["hour"], results[label]["pred"], style,
                label=f"NB predicted ({label})", linewidth=1.5)
    ax.set_title("Baseline NB model: actual vs. predicted calls/hour (held-out test week)")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Calls")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_PLOT, dpi=150)
    print(f"\nSaved plot to {OUTPUT_PLOT}")


if __name__ == "__main__":
    main()
