# OPD 911 demand & response analysis (INFO 285)

Berkeley INFO 285 project with the Oakland Police Department. Two strands: **call-demand
forecasting** and **beat travel-time / response-time analysis**. Client questions center on how
demand varies over time and across beats, and whether OPD's beat boundaries still fit its workload.

## Data lives in Box, not the repo

`box_utils.py` auto-detects the Box Drive mount — import `BOX_ROOT` from it, never hardcode a path.

```python
from box_utils import BOX_ROOT
OPD  = BOX_ROOT / "OPD & TAN - Core Workspace" / "02 Oakland Police Dept (OPD)"
DATA = OPD / "Data" / "Our Data"
```

Key files in `Data/Our Data/`:

| File | What |
|---|---|
| `2021-2026current.xlsx` | Raw CAD call log, 2.28M rows, 6 sheets (one per year), ~204MB. **Don't open directly** — read the DATA GUIDE next to it. |
| `harmonized_calls_2021_2026.parquet` | The xlsx harmonized to one long table (14 cols). **Use this for modeling.** |
| `opd_patrol_officers_by_area.csv` | Officers assigned to patrol per Area per report date (6-Area era only). |
| `OPD Reports/` | Source PDFs: OPD staffing reports, PFM staffing study, CPSM report, the watch-schedule memo. |
| `Audit REPORT OPD 911 response times.pdf` | 2025 City Auditor 911 audit (+ GUIDE). |

Each dataset has a `- DATA GUIDE.md` beside it. **Read the guide before using a dataset** — they
document schema drift, null rates and known traps that are easy to get wrong.

## CAD data traps

- **Column names change every year.** No consistent header across sheets; the guide has the canonical mapping.
- **CAD system cutover 2024-08-01** (`P1CAD/OLDCAD` flag in the 2024 sheet). Don't compare incident-type volumes across it without checking whether the category's volume was conserved.
- **No unit/officer ID column** in any year — only "first unit" timestamps. You cannot tell which unit responded, so supply-side analysis must come from staffing reports, not CAD.
- `CallSource` mixes public 911 calls with officer-initiated activity (traffic stops etc.). Filter these out for public-demand models or you conflate demand with staffing.
- Arrival-time null rate is 46–64%/yr. Priority is int in 2021–23, str in 2024–26. Priority 5/6 are undocumented.
- Modeling convention: treat "today" as the max timestamp in the data (currently **2026-06-30**), not the calendar date.

## How OPD actually dispatches (matters for modeling)

From the Oct 2025 City Auditor audit:

- 35 beats grouped into **6 Patrol Areas**; 2 bureaus — **BFO 1 = Areas 1–3 (West)**, **BFO 2 = Areas 4–6 (East)**. BFO is geographic, not seniority.
- Dispatchers draw from the **Patrol Area**, not the beat: the beat's officer first, then any free unit in that Area, then nearby Areas.
- **P1** = any unit citywide, no approval. **P2** = confined to the Area unless command staff of *both* Areas approve a cross-dispatch — otherwise the call queues (median P2 response 2+ hrs). So calibrate P1 and P2 separately.
- Dispatch **cannot see officer locations**. No closest-unit dispatch; GPS/ARL is installed but never activated.
- Audit Rec 9 asks OPD to redraw beat boundaries using call volume — that's essentially this project's framing.

### Watch schedule

Areas 1, 3, 5 run early; Areas 2, 4, 6 run late (OPD memo *Patrol Staffing and Structure*, 1 Jul 2023):

| Area | 1st Watch | 2nd Watch | 3rd Watch |
|---|---|---|---|
| 1, 3, 5 | 0600–1600 | 1400–0200 | 2100–0700 |
| 2, 4, 6 | 0700–1700 | 1400–0200 | 2200–0800 |

Each watch splits into **A/B sides** that alternate days, so only one side works any given day
(~half the watch's headcount). Critically: officers spend the **first and last hour of every shift
in the station**, so effective beat coverage is 2h shorter than scheduled — this drives the P1
response-time spikes at 6–7am and 2pm.

## Repo

- `box_utils.py` — Box path helper. Import `BOX_ROOT` from here.
- `build_harmonized_calls_table.py` — xlsx → harmonized parquet.
- `build_patrol_staffing_table.py` — staffing-report PDFs → `opd_patrol_officers_by_area.csv`.
- `fetch_weather_data.py`, `fit_nb_model_v*.py`, `evaluate_v2_long_horizon.py` — demand forecasting (negative binomial, v1→v4 adding holidays, trend, weather).
- `beat_travel_times_osrm.ipynb` — main analysis notebook: OSRM beat travel times, CAD calibration, response-time maps, then §11 watch schedule and §12 officers-by-Area.
- `opd_demand_eda.ipynb`, `opd_demand_forecast_models.ipynb` — demand EDA and models.

Notebook figures are committed **with outputs embedded** so they render without a Box mount.

## Open threads

1. **Post-2023 watch schedule.** The 1 Jul 2023 memo is the only published Area-by-Area grid. PFM (Sept 2024) corroborates it indirectly. Checked and found nothing: CPAB packets Sep 2026 and May 2025, OPD staffing reports 2024–26. Archived CPAB meeting pages 404 and packet filenames vary by year, so a WebSearch sweep of 2024–2026 CPAB packets is still owed.
2. **Data to request from OPD** — the highest-value ask: **unit-level CAD from Aug 2024 on** (unit ID + per-unit dispatch/enroute/arrive/clear, plus unit log-on/log-off). PFM and CPSM both received unit-level CAD for 2019–2023, so there's precedent. Also worth asking for: current **DGO I-7** (unit-ID decoder), patrol shift schedules, and what "assigned to patrol" counts (it exceeds budgeted slots, likely including officers on leave).
3. Ask OPD what **Priority 5 and 6** mean, and about the 2024 hang-up-category volume drop.

## Conventions

- Prefer editing the existing notebook over new scripts; keep the numbered-section structure (`# 11)`, `# 12)`).
- Cite sources inline in analysis cells (report name + page) — this work feeds a client memo.
- Charts: validated categorical palette, direct labels on lines, source note in the figure caption.
