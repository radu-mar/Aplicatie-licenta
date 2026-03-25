import os
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")



def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarc baza live (pasul 3) si results --")
live_laps = read_csv("dataset_03_istoric_abandon.csv")
results = read_csv("results.csv")

print("-- 2. adaug grid (pozitia de start) si calculez pozitii castigate --")
# grid-ul ajuta mult mai ales in primele tururi; il lipesc pe cheile raceId+driverId
grid_info = results.loc[:, ["raceId", "driverId", "grid"]]
live_laps = live_laps.merge(grid_info, on=["raceId", "driverId"], how="left")

# flag pentru start din pit lane / grid invalid (de regula grid=0)
live_laps["started_from_pitlane"] = (live_laps["grid"] <= 0).astype(int)

# pozitii castigate fata de start (daca grid e invalid, pun 0 ca sa evit valori ciudate)
live_laps["positions_gained"] = (live_laps["grid"] - live_laps["position"]).where(live_laps["grid"] > 0, 0)

print("-- 3. calculez timpul total de cursa si pace relativ pe fiecare tur --")
# ordonare corecta: cursa -> pilot -> tur
live_laps = live_laps.sort_values(by=["raceId", "driverId", "lap"]).copy()

# transform milisecundele in secunde
live_laps["lap_time_sec"] = live_laps["milliseconds"] / 1000.0

# pace relativ: diferenta fata de cel mai rapid tur din acel lap (in acea cursa)
leader_lap_time = live_laps.groupby(["raceId", "lap"])["lap_time_sec"].transform("min")
live_laps["delta_leader_lap"] = live_laps["lap_time_sec"] - leader_lap_time

# timp total acumulat (tur cu tur) pentru fiecare pilot
live_laps["timp_total_cursa_sec"] = live_laps.groupby(["raceId", "driverId"])["lap_time_sec"].cumsum()

print("-- 4. calculez timpul liderului pe fiecare tur --")
# in fiecare (raceId, lap), liderul este pilotul cu timpul total minim pana atunci
leader_time = (
    live_laps.groupby(["raceId", "lap"], as_index=False)["timp_total_cursa_sec"]
    .min()
    .rename(columns={"timp_total_cursa_sec": "timp_lider_sec"})
)

print("-- 5. calculez gap-ul fata de lider + trend --")
live_laps = live_laps.merge(leader_time, on=["raceId", "lap"], how="left")

# gap absolut (secunde)
live_laps["gap_to_leader_sec"] = live_laps["timp_total_cursa_sec"] - live_laps["timp_lider_sec"]

# gap normalizat (gap / numarul de tururi rulate pana acum)
live_laps["gap_ratio"] = live_laps["gap_to_leader_sec"] / (live_laps["lap"] + 1)

# trend gap: daca scade, pilotul se apropie de lider; daca creste, se indeparteaza
live_laps["gap_prev"] = live_laps.groupby(["raceId", "driverId"])["gap_to_leader_sec"].shift(1)
live_laps["gap_trend"] = (live_laps["gap_prev"] - live_laps["gap_to_leader_sec"]).fillna(0)

# nota: pilotii lapped pot avea gap-uri foarte mari; las valorile asa, modelul le poate interpreta

print("-- 6. curatenie: scot calculele intermediare --")
cols_to_drop = ["milliseconds", "timp_lider_sec", "timp_total_cursa_sec", "gap_prev"]
cols_to_drop = [c for c in cols_to_drop if c in live_laps.columns]
live_laps = live_laps.drop(columns=cols_to_drop)

print("-- 7. sortez si salvez master dataset-ul --")
live_laps = live_laps.sort_values(by=["year", "raceId", "lap", "position"])

save_path = os.path.join(data_folder, "dataset_04_master_live.csv")
live_laps.to_csv(save_path, index=False)

print("gata! master dataset-ul a fost salvat.")
print(f"fisier: {save_path}")
print(f"coloane finale: {list(live_laps.columns)}")