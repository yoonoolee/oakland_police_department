"""Compile 'Number of officers assigned to patrol' by Area from every OPD staffing report found
(Legistar 2016-2026 + city informational memos 2020-2023). Values were read from each report's
'Patrol Data' / 'Police Beat Patrol Data' table and cross-checked so Areas sum to the reported total.
Writes two CSVs: by Area (all snapshots) and by Area x Watch (only reported 2016-2018)."""
import pandas as pd

L = "https://oakland.legistar.com/LegislationDetail.aspx?ID={}&GUID={}"
SRC = {  # as_of -> (document, url)
    "2016-04-30": ("Legistar 15-1207, Table 18", "https://oakland.legistar1.com/oakland/attachments/25321eba-511f-4ff7-8fca-b444127d3228.pdf"),
    "2016-07-31": ("Legistar 16-49, Table 18",   "https://oakland.legistar1.com/oakland/attachments/fc34ddd8-b51d-4685-84f1-b9fe1364a238.pdf"),
    "2016-08-31": ("Legistar 16-0323, Table 18", "https://oakland.legistar1.com/oakland/attachments/63b8efd3-ab59-4200-a2bc-3cc80c80000e.pdf"),
    "2016-09-30": ("Legistar 16-0481, Table 18", "https://oakland.legistar1.com/oakland/attachments/10eecd1d-1052-4a31-a09c-2d76bb6646af.pdf"),
    "2016-11-30": ("Legistar 16-0613, Table 18", "https://oakland.legistar1.com/oakland/attachments/239a1f5a-b16b-4410-bfd0-27c88048e866.pdf"),
    "2016-12-31": ("Legistar 16-0741, Table 18", "https://oakland.legistar1.com/oakland/attachments/304a4ec0-abfa-4d7a-829b-873747b04f9f.pdf"),
    "2017-02-28": ("Legistar 16-0808, Table 18 (report says 'as of February 28, 2016' - typo)", "https://oakland.legistar1.com/oakland/attachments/3d8bd06c-4733-4883-9950-7512f4a9d6df.pdf"),
    "2017-03-31": ("Legistar 16-1125, Table 18", "https://oakland.legistar1.com/oakland/attachments/8f9ab535-f4b2-498e-bbfa-e291e08761fb.pdf"),
    "2017-05-31": ("Legistar 16-1365, Table 18", "https://oakland.legistar1.com/oakland/attachments/c6e9fa42-de02-4849-bad0-66551153289e.pdf"),
    "2017-08-31": ("Legistar 17-0229, Table 18", "https://oakland.legistar1.com/oakland/attachments/3323a8bf-570f-49f7-ad48-351d27740040.pdf"),
    "2017-10-31": ("Legistar 17-0480, Table 18", "https://oakland.legistar1.com/oakland/attachments/88a3ab29-da39-44d2-a547-473e4808e9ae.pdf"),
    "2017-11-30": ("Legistar 17-0480 supplemental 2018-01-12, Table 18", "https://oakland.legistar1.com/oakland/attachments/5a94791d-f787-4209-ac5b-2790ae7231f7.pdf"),
    "2017-12-31": ("Legistar 17-0480 supplemental 2018-02-02, Table 18", "https://oakland.legistar1.com/oakland/attachments/92485f44-b5e7-4ec3-8754-69dc7da90330.pdf"),
    "2018-01-31": ("Legistar 17-0363, Table 18", "https://oakland.legistar1.com/oakland/attachments/0b7d2a43-8dcb-42b9-bfaa-4780ad25bad7.pdf"),
    "2018-03-31": ("Legistar 18-0506, Table 15", "https://oakland.legistar1.com/oakland/attachments/69b83942-b880-4c38-b8e6-efd25a18fb3d.pdf"),
    "2018-04-30": ("Legistar 18-0506 supplemental 2018-06-15, Table 17", "https://oakland.legistar1.com/oakland/attachments/1d157751-82f7-4e20-a14f-e7fc5ccadf25.pdf"),
    "2018-07-31": ("Legistar 18-0870, Table 17", "https://oakland.legistar1.com/oakland/attachments/715ad5ea-093b-46b3-a440-150459c5968a.pdf"),
    "2018-08-31": ("Legistar 18-0870 supplemental 2018-10-12, Table 17", "https://oakland.legistar1.com/oakland/attachments/b078cda6-2b5e-43ec-836b-bfa1d56e329a.pdf"),
    "2018-10-31": ("Legistar 18-1164, Table 18", "https://oakland.legistar1.com/oakland/attachments/9dd1cc5a-97df-4bab-ac4b-bd11709648bc.pdf"),
    "2019-03-31": ("Legistar 18-1739, Table 19", "https://oakland.legistar1.com/oakland/attachments/c9ffb1e2-0827-4119-94db-83571fab936f.pdf"),
    "2019-06-30": ("Legistar 18-1164 supplemental 2019-09-13, Table 19", "https://oakland.legistar1.com/oakland/attachments/1d732e1e-6341-4b1f-b273-0a182273f9e6.pdf"),
    "2019-09-30": ("Legistar 20-0017, Table 16", "https://oakland.legistar1.com/oakland/attachments/47e7e15d-02dc-4618-96f0-de9e71b9a836.pdf"),
    "2020-06-30": ("City informational memo 2020-10-07 (Q2 2020), Table 13", "https://cao-94612.s3.amazonaws.com/documents/OPD-Quarterly-Staffing-Informational-Memo.pdf"),
    "2021-06-30": ("City informational memo 2021-09-13 (Q2 2021), Table 14", "https://cao-94612.s3.amazonaws.com/documents/OPD-QtrlyStaffingMemo.pdf"),
    "2021-09-30": ("City informational memo 2021-10-14 (Q3 2021), Table 14", "https://www.oaklandca.gov/files/assets/city/v/1/city-administrator/documents/informational-memos/2021/opd-3rd-quarter-staffing-report.pdf"),
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

# 5-Area era (Area beats: 1: 1-7, 2: 8-14, 3: 15-22, 4: 23-28, 5: 29-35).
# Per Area: (first_watch, early_tac, second_watch, late_tac, third_watch, total_reported); None = not published.
FIVE = {
    "2016-04-30": [(15,None,18,8,17,58),(14,None,16,None,15,45),(15,None,16,None,16,47),(18,None,16,None,18,52),(16,None,16,7,16,55)],
    "2016-07-31": [(16,None,18,9,17,60),(16,None,16,None,16,48),(15,None,16,None,16,47),(17,None,16,None,18,51),(16,None,23,8,17,64)],
    "2016-08-31": [(16,None,18,9,18,61),(16,None,16,None,16,48),(15,None,16,None,16,47),(17,None,16,None,18,51),(16,None,23,8,17,64)],
    "2016-09-30": [(16,None,18,8,20,62),(18,None,16,None,16,50),(17,None,16,None,16,49),(17,None,17,None,19,53),(16,None,24,8,16,64)],
    "2016-11-30": [(17,None,19,8,18,62),(19,None,16,None,16,51),(17,None,16,None,17,50),(19,None,18,None,18,55),(16,None,24,8,16,64)],
    "2016-12-31": [(17,None,19,8,18,62),(19,None,16,None,16,51),(16,None,16,None,17,49),(18,None,17,None,17,52),(16,None,24,8,16,64)],
    "2017-02-28": [(17,None,16,8,17,58),(16,None,17,None,16,49),(14,None,16,8,15,53),(15,None,14,8,15,52),(14,None,23,8,16,61)],
    "2017-03-31": [(17,None,16,7,17,57),(16,None,17,None,16,49),(14,None,16,7,16,53),(15,None,15,8,15,53),(15,None,23,8,16,62)],
    "2017-05-31": [(16,None,15,7,16,54),(16,None,17,None,16,49),(16,None,16,4,16,52),(14,None,16,8,15,53),(17,None,23,6,17,63)],
    "2017-08-31": [(15,None,16,10,15,56),(15,None,16,None,16,47),(14,None,15,None,16,45),(14,None,14,8,15,51),(15,None,21,5,16,57)],
    "2017-10-31": [(15,None,16,8,16,55),(17,None,16,None,16,49),(16,None,16,None,17,49),(14,None,17,8,15,54),(16,None,22,5,16,59)],  # report prints Area 3 total as 45; watches sum to 49 and 49 is needed for the 266 total
    "2017-11-30": [(15,None,16,8,16,55),(17,None,16,None,16,49),(16,None,16,None,17,49),(14,None,17,6,15,52),(16,None,22,5,16,59)],
    "2017-12-31": [(15,None,16,8,16,55),(17,None,16,None,16,49),(16,None,16,None,17,49),(13,None,17,6,15,51),(16,None,22,5,16,59)],
    "2018-01-31": [(17,None,18,7,19,61),(15,None,15,None,15,45),(14,None,16,None,16,46),(17,None,15,None,16,48),(16,8,15,8,16,63)],
    "2018-03-31": [(16,None,18,7,19,60),(15,None,15,None,15,45),(14,None,16,None,15,45),(17,None,15,None,16,48),(16,8,15,8,15,62)],
    "2018-04-30": [(15,None,18,6,19,58),(16,None,15,None,14,45),(14,None,16,None,14,44),(17,None,15,None,16,48),(16,8,16,7,15,62)],
    "2018-07-31": [(16,None,17,6,19,58),(16,None,15,None,16,47),(15,None,16,None,16,47),(13,None,16,None,16,45),(16,8,16,6,15,61)],
    "2018-08-31": [(16,None,17,6,19,58),(15,None,14,None,16,45),(15,None,16,None,16,47),(13,None,16,None,16,45),(16,7,16,6,15,60)],
    "2018-10-31": [(16,None,17,6,18,57),(14,None,15,None,17,46),(16,None,16,None,16,48),(13,None,16,None,16,45),(16,7,15,6,17,61)],
    "2019-03-31": [(16,None,17,8,18,59),(16,None,16,None,16,48),(16,None,16,None,16,48),(15,None,16,None,17,48),(16,5,17,8,16,57)],  # Area 5 watches sum to 62; report total 57 (needed for the 260 total)
    "2019-06-30": [(None,None,None,None,None,64),(None,None,None,None,None,49),(None,None,None,None,None,47),(None,None,None,None,None,47),(None,None,None,None,None,65)],
    "2019-09-30": [(None,None,None,None,None,65),(None,None,None,None,None,48),(None,None,None,None,None,49),(None,None,None,None,None,49),(None,None,None,None,None,63)],
    "2020-06-30": [(None,None,None,None,None,67),(None,None,None,None,None,50),(None,None,None,None,None,49),(None,None,None,None,None,49),(None,None,None,None,None,68)],
    "2021-06-30": [(None,None,None,None,None,61),(None,None,None,None,None,65),(None,None,None,None,None,62),(None,None,None,None,None,62),(None,None,None,None,None,69)],
    "2021-09-30": [(None,None,None,None,None,59),(None,None,None,None,None,64),(None,None,None,None,None,58),(None,None,None,None,None,55),(None,None,None,None,None,69)],
}
FIVE_BEATS = {1: "1-7", 2: "8-14", 3: "15-22", 4: "23-28", 5: "29-35"}

# 6-Area era (Area beats: 1: 1-7, 2: 8-13, 3: 14-19, 4: 20-25, 5: 26-30, 6: 31-35). Totals only.
SIX = {
    "2022-03-31": [53,46,46,52,48,42],
    "2022-09-30": [57,45,44,51,51,49],
    "2022-12-31": [59,50,48,53,51,55],
    "2023-03-31": [59,50,48,58,48,52],
    "2023-09-30": [56,54,49,59,51,58],
    "2023-12-31": [55,53,48,58,52,57],
    "2024-03-15": [59,49,47,51,51,53],
    "2024-06-30": [59,49,47,50,51,53],
    "2025-06-17": [62,53,56,54,51,49],
    "2026-02-28": [66,54,51,55,57,49],
}
SIX_BEATS = {1: "1-7", 2: "8-13", 3: "14-19", 4: "20-25", 5: "26-30", 6: "31-35"}
NOTES = {
    "2017-02-28": "Report header says 'as of February 28, 2016' (typo for 2017; report introduced Feb 2017).",
    "2017-10-31": "Report prints Area 3 total as 45; its watch counts sum to 49, and 49 is required for the printed citywide total of 266.",
    "2019-03-31": "Area 5 watch counts sum to 62 but report total is 57 (57 is required for the printed citywide total of 260).",
    "2024-03-15": "Supplemental memo; as-of date not stated. Memo notes totals are permanent positions and exclude officers on leave or loaned out.",
    "2025-06-17": "Report covers Dec 31, 2024 levels but its patrol table is dated June 17, 2025.",
}

rows, wrows = [], []
for asof, areas in FIVE.items():
    total = sum(a[5] for a in areas)
    for i, a in enumerate(areas, 1):
        rows.append(dict(as_of=asof, area_regime="5 Areas (2016-2021)", area=i, beats=FIVE_BEATS[i],
                         officers_assigned_to_patrol=a[5], citywide_total=total,
                         source=SRC[asof][0], source_url=SRC[asof][1], note=NOTES.get(asof, "")))
        if a[0] is not None:
            wrows.append(dict(as_of=asof, area=i, first_watch=a[0], early_tac=a[1], second_watch=a[2], late_tac=a[3],
                              third_watch=a[4], total_reported=a[5], watch_sum=sum(x for x in a[:5] if x is not None),
                              source=SRC[asof][0], source_url=SRC[asof][1], note=NOTES.get(asof, "")))
for asof, areas in SIX.items():
    total = sum(areas)
    for i, n in enumerate(areas, 1):
        rows.append(dict(as_of=asof, area_regime="6 Areas (2022-)", area=i, beats=SIX_BEATS[i],
                         officers_assigned_to_patrol=n, citywide_total=total,
                         source=SRC[asof][0], source_url=SRC[asof][1], note=NOTES.get(asof, "")))

by_area = pd.DataFrame(rows).sort_values(["as_of", "area"]).reset_index(drop=True)
by_watch = pd.DataFrame(wrows).sort_values(["as_of", "area"]).reset_index(drop=True)
by_area.to_csv("opd_patrol_officers_by_area.csv", index=False)
by_watch.to_csv("opd_patrol_officers_by_area_watch.csv", index=False)
print(by_area.groupby("as_of")["officers_assigned_to_patrol"].sum().to_string())
print(len(by_area), "area rows;", len(by_watch), "area x watch rows")
