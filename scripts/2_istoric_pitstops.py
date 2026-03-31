import os
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")


def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarcare dataset --")
live_laps = read_csv("dataset_01_live_modern.csv")
pit_stops = read_csv("pit_stops.csv")
results = read_csv("results.csv")
races = read_csv("races.csv")

print("-- 2. completare pit_stops cu echipa pilotului (constructorId) --")
driver_team_map = results.loc[:, ["raceId", "driverId", "constructorId"]].drop_duplicates()
pit_stops = pit_stops.merge(driver_team_map, on=["raceId", "driverId"], how="inner")

print("-- 3. curatare durata opririi la boxe (in secunde) --")
pit_stops["pit_duration_sec"] = pd.to_numeric(pit_stops["milliseconds"], errors="coerce") / 1000.0

pit_stops = pit_stops[(pit_stops["pit_duration_sec"] > 15) & (pit_stops["pit_duration_sec"] < 40)].copy()

print("-- 4. adaugare cronologie reala (year, round) si sortare corecta --")
pit_stops = pit_stops.merge(races.loc[:, ["raceId", "year", "round"]], on="raceId", how="left")

sort_cols = ["constructorId", "year", "round"]
for col in ["lap", "stop"]:
    if col in pit_stops.columns:
        sort_cols.append(col)

pit_stops = pit_stops.sort_values(by=sort_cols).copy()

print("-- 5. calculare istoric pit pe echipa --")
pit_stops["istoric_pit_echipa_sec"] = (
    pit_stops.groupby("constructorId")["pit_duration_sec"]
    .rolling(window=5, min_periods=1)
    .mean()
    .reset_index(level=0, drop=True)
)

# pentru fiecare cursa, retin ultima valoare disponibila (dupa sortare)
team_pit_eff = (
    pit_stops.groupby(["raceId", "constructorId"], as_index=False)["istoric_pit_echipa_sec"]
    .last()
)

print("-- 6. shift cu o cursa in urma pentru fiecare echipa --") #pentru a nu avea leakeage
team_pit_eff["istoric_pit_echipa_sec"] = (
    team_pit_eff.groupby("constructorId")["istoric_pit_echipa_sec"]
    .shift(1)
)

team_pit_eff["istoric_pit_echipa_sec"] = team_pit_eff["istoric_pit_echipa_sec"].fillna(24.0)

print("-- 7. lipire feature in dataset --")
live_laps = live_laps.merge(team_pit_eff, on=["raceId", "constructorId"], how="left")
live_laps["istoric_pit_echipa_sec"] = live_laps["istoric_pit_echipa_sec"].fillna(24.0)

print("-- 8. salvare --")
save_path = os.path.join(data_folder, "dataset_02_istoric_pitstops.csv")
live_laps.to_csv(save_path, index=False)

print(f"salvare in: {save_path}")
print(f"datasetul are acum {live_laps.shape[1]} coloane (include istoric_pit_echipa_sec).")