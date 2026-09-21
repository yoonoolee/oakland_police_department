"""Compile 'Number of officers assigned to patrol' by Area from OPD staffing reports to City Council
for the current 6-Area boundaries (Mar 2022 onward). Values were read from each report's 'Police Beat
Patrol Data' table and cross-checked so the Areas sum to the printed citywide total.
Writes Data/Our Data/opd_patrol_officers_by_area.csv (source PDFs are in Data/Our Data/OPD Reports/).

The 2016-2021 five-Area era (35 snapshots incl. a 2016-19 per-watch split) was compiled in commit
21d3e04 and dropped afterwards because the beats were reassigned when OPD went to 6 Areas."""
import pandas as pd
from box_utils import BOX_ROOT

OUT = BOX_ROOT / "OPD & TAN - Core Workspace" / "02 Oakland Police Dept (OPD)" / "Data" / "Our Data"

SRC = {  # as_of -> (document, url)
    "2022-03-31": ("City informational memo 2022-04-15 (Q1 2022), Table 8", "https://cao-94612.s3.amazonaws.com/documents/OPD-Qtrly-Staffing-Informational-Memo-1st-Quarter-2022.pdf"),
    "2022-09-30": ("City informational memo 2022-11-07 (Q3 2022), Table 9", "https://www.oaklandca.gov/files/assets/city/v/1/city-administrator/documents/informational-memos/2022/2022_q3_opd_qtrlystaffingmemo-final-and-signed.pdf"),
    "2022-12-31": ("City informational memo 2023-02-01 (Q4 2022), Table 9", "https://cao-94612.s3.amazonaws.com/documents/2022_Q4_OPD_QtrlyStaffingMemo_2023-03-01-051307_wewh.pdf"),
    "2023-03-31": ("Legistar 23-0309 (Q1 2023), Table 9", "https://oakland.legistar1.com/oakland/attachments/4fa6200c-82a6-4115-973a-a6cf1f9cf3fc.pdf"),
    "2023-09-30": ("Legistar 23-0838 (biannual), Table 10", "https://oakland.legistar1.com/oakland/attachments/9ec88be6-94de-4aab-aa32-4dd24c7b0522.pdf"),
    "2023-12-31": ("Legistar 23-0838 supplemental 2024-02-01, Table 10", "https://oakland.legistar1.com/oakland/attachments/9d587885-da40-4f3f-b52a-151be37b3a44.pdf"),
    "2024-03-15": ("Legistar 23-0838 supplemental 2024-03-29 (memo dated 2024-03-15; as-of date not stated)", "https://oakland.legistar1.com/oakland/attachments/e494a05e-76c6-4564-98e8-1cad609f3c52.pdf"),
    "2024-06-30": ("Legistar 25-0068 (biannual), Table 10", "https://oakland.legistar1.com/oakland/attachments/b2602b0e-b8bd-43ef-a1e1-98ad7476ec16.pdf"),
    "2025-06-17": ("Legistar 25-0852 (biannual), Table 5 (table dated 2025-06-17)", "https://oakland.legistar1.com/oakland/attachments/0ff05a1c-925e-42e4-91ac-4e64e45e61b0.pdf"),
    "2026-02-28": ("Legistar 26-0503 (biannual), Table 7", "https://oakland.legistar1.com/oakland/attachments/71da75fc-f2b9-4442-a205-d1a197c29d3d.pdf"),
}
# Areas 1-6 (beats 1-7, 8-13, 14-19, 20-25, 26-30, 31-35): officers assigned to patrol
COUNTS = {
    "2022-03-31": [53, 46, 46, 52, 48, 42],
    "2022-09-30": [57, 45, 44, 51, 51, 49],
    "2022-12-31": [59, 50, 48, 53, 51, 55],
    "2023-03-31": [59, 50, 48, 58, 48, 52],
    "2023-09-30": [56, 54, 49, 59, 51, 58],
    "2023-12-31": [55, 53, 48, 58, 52, 57],
    "2024-03-15": [59, 49, 47, 51, 51, 53],
    "2024-06-30": [59, 49, 47, 50, 51, 53],
    "2025-06-17": [62, 53, 56, 54, 51, 49],
    "2026-02-28": [66, 54, 51, 55, 57, 49],
}
BEATS = {1: "1-7", 2: "8-13", 3: "14-19", 4: "20-25", 5: "26-30", 6: "31-35"}
NOTES = {
    "2024-03-15": "Supplemental memo; as-of date not stated. Memo notes totals are permanent positions and exclude officers on leave or loaned out.",
    "2025-06-17": "Report covers Dec 31, 2024 levels but its patrol table is dated June 17, 2025.",
}

rows = [dict(as_of=asof, area=i, beats=BEATS[i], officers_assigned_to_patrol=n, citywide_total=sum(areas),
             source=SRC[asof][0], source_url=SRC[asof][1], note=NOTES.get(asof, ""))
        for asof, areas in COUNTS.items() for i, n in enumerate(areas, 1)]
df = pd.DataFrame(rows).sort_values(["as_of", "area"]).reset_index(drop=True)
df.to_csv(OUT / "opd_patrol_officers_by_area.csv", index=False)
print(df.groupby("as_of")["officers_assigned_to_patrol"].sum().to_string())
print(len(df), "rows ->", OUT / "opd_patrol_officers_by_area.csv")
