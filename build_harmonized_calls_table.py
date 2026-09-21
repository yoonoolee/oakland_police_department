"""
Builds one harmonized long-format events table from '2021-2026current.xlsx'.

The source workbook has one sheet per year with a different column schema each
time (see '../Data/Our Data/2021-2026current - DATA GUIDE.md' section 2 for the
full mapping). This script maps every sheet's columns onto one canonical schema,
concatenates all years, and writes the result to a single parquet file for reuse
by downstream modeling scripts (no need to re-read the 200MB xlsx each time).

V1 scope decisions (see memory: opd_demand_forecasting_scope):
- No dedup of duplicate incident numbers — each row is a distinct call-taker
  event and should be counted separately.
- No CallSource filtering — officer/field/MDT-initiated rows are kept in for V1.
- Only cleanup: rows with a null call-received timestamp are dropped (a small
  corrupted batch, ~1,673 rows, all in the 2023 sheet).
"""

import openpyxl
import pandas as pd

SOURCE = "../Data/Our Data/2021-2026current.xlsx"
OUTPUT = "../Data/Our Data/harmonized_calls_2021_2026.parquet"

# Per-sheet column index map -> canonical field name.
# Index positions taken from the header row of each sheet (0-based).
SHEET_CONFIG = {
    "2021": {
        "agency": 0, "event_number": 1, "address": 2, "beat": 3,
        "call_source": 4, "priority": 5, "event_time": 6,
        "dispatch_time": 7, "arrival_time": 8,
        "incident_type_code": 9, "incident_type_desc": 10,
        "disposition_code": None, "disposition_text": 11,
    },
    "2022": {
        "agency": 0, "event_number": 1, "address": 2, "beat": 3,
        "call_source": 4, "priority": 5, "event_time": 6,
        "dispatch_time": 7, "arrival_time": 8,
        "incident_type_code": 9, "incident_type_desc": 10,
        "disposition_code": None, "disposition_text": 11,
    },
    "2023": {
        "agency": 0, "event_number": 1, "address": 2, "beat": 3,
        "call_source": 4, "priority": 5, "event_time": 6,
        "dispatch_time": 7, "arrival_time": 8,
        "incident_type_code": 9, "incident_type_desc": 10,
        "disposition_code": 11, "disposition_text": 12,
        "max_col": 14,  # sheet has 367 cols but only 14 are real; skip the rest
    },
    "2024 CFS": {
        "agency": 0, "event_number": 1, "address": 3, "beat": 4,
        "call_source": 5, "priority": 6, "event_time": 8,
        "dispatch_time": 9, "arrival_time": 10,
        "incident_type_code": 11, "incident_type_desc": 12,
        "disposition_code": 13, "disposition_text": 14,
    },
    "2025 CFS": {
        "agency": 0, "event_number": 1, "address": 2, "beat": 3,
        "call_source": 4, "priority": 5, "event_time": 6,
        "dispatch_time": 7, "arrival_time": 8,
        "incident_type_code": 9, "incident_type_desc": 10,
        "disposition_code": 11, "disposition_text": 12,
    },
    "2026 ": {
        "agency": 0, "event_number": 1, "address": 4, "beat": 5,
        "call_source": 15, "priority": 2, "event_time": 6,
        "dispatch_time": 16, "arrival_time": 20,
        "incident_type_code": 8, "incident_type_desc": 9,
        "disposition_code": 10, "disposition_text": 11,
    },
}

CANONICAL_FIELDS = [
    "agency", "event_number", "address", "beat", "call_source", "priority",
    "event_time", "dispatch_time", "arrival_time",
    "incident_type_code", "incident_type_desc",
    "disposition_code", "disposition_text",
]


def load_sheet(wb, sheet_name, cfg):
    ws = wb[sheet_name]
    max_col = cfg.get("max_col", max(v for v in cfg.values() if isinstance(v, int)) + 1)
    rows = []
    for row in ws.iter_rows(min_row=2, max_col=max_col, values_only=True):
        record = {
            field: (row[idx] if idx is not None else None)
            for field, idx in cfg.items()
            if field in CANONICAL_FIELDS
        }
        record["source_sheet"] = sheet_name
        rows.append(record)
    return pd.DataFrame(rows, columns=CANONICAL_FIELDS + ["source_sheet"])


def main():
    wb = openpyxl.load_workbook(SOURCE, read_only=True)
    frames = []
    for sheet_name, cfg in SHEET_CONFIG.items():
        print(f"Loading sheet '{sheet_name}'...")
        df = load_sheet(wb, sheet_name, cfg)
        print(f"  {len(df):,} rows")
        frames.append(df)

    full = pd.concat(frames, ignore_index=True)

    # Uniform types: several text columns mix str/int/etc. across years
    # (e.g. numeric-looking addresses, beat codes). Force to plain strings,
    # preserving nulls, so parquet doesn't choke on mixed-type object columns.
    text_cols = [
        "agency", "event_number", "address", "beat", "call_source", "priority",
        "incident_type_code", "incident_type_desc",
        "disposition_code", "disposition_text",
    ]
    for col in text_cols:
        full[col] = full[col].apply(lambda x: str(x) if x is not None else None)

    # Parse timestamps (already python datetimes from openpyxl in most cases,
    # but coerce defensively in case of stray strings/typos).
    for col in ["event_time", "dispatch_time", "arrival_time"]:
        full[col] = pd.to_datetime(full[col], errors="coerce")

    n_before = len(full)
    full = full[full["event_time"].notna()].reset_index(drop=True)
    n_dropped = n_before - len(full)
    print(f"\nDropped {n_dropped:,} rows with missing event_time.")

    full = full.sort_values("event_time").reset_index(drop=True)

    print(f"\nFinal table: {len(full):,} rows, {len(full.columns)} columns")
    print("Date range:", full["event_time"].min(), "to", full["event_time"].max())
    print("\nRows per source sheet:")
    print(full["source_sheet"].value_counts())

    full.to_parquet(OUTPUT, index=False)
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()
