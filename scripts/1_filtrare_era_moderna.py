import os
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")


def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarc datele --")
lap_times = read_csv("lap_times.csv")
results = read_csv("results.csv")
races = read_csv("races.csv")

# datele de dinainte de 2014 sunt mai putin relevante (schimbari majore de regulamente/era)
print("-- 2. filtrez doar era moderna (2014 - prezent), ca sa evit concept drift --")
modern_races = races.loc[races["year"] >= 2014, ["raceId", "year"]].copy()

# pastrez doar cursele moderne
results_modern = results.merge(modern_races, on="raceId", how="inner")
lap_times_modern = lap_times.merge(modern_races, on="raceId", how="inner")

print("-- 3. definirea castigatorului cursei --")
target = results_modern.loc[:, ["raceId", "driverId", "constructorId", "positionOrder"]].copy()
target["is_winner"] = (target["positionOrder"] == 1).astype(int)
target = target.drop(columns=["positionOrder"])

print("-- 4. construirea datasetului: 1 rand = 1 tur pentru un pilot --")
live_laps = lap_times_modern.merge(target, on=["raceId", "driverId"], how="inner")

print("-- 5. calculez informatii despre cursa: tururi ramase si progres --")
# aflu cate tururi are fiecare cursa (maximul din lap)
total_laps = (
    live_laps.groupby("raceId", as_index=False)["lap"]
    .max()
    .rename(columns={"lap": "total_laps_race"})
)

live_laps = live_laps.merge(total_laps, on="raceId", how="left")

# pastrez denumirile initiale ale feature-urilor (ca sa fie compatibile cu restul pipeline-ului)
live_laps["laps_remaining"] = live_laps["total_laps_race"] - live_laps["lap"]
live_laps["race_progress"] = live_laps["lap"] / live_laps["total_laps_race"]
live_laps["laps_remaining_ratio"] = live_laps["laps_remaining"] / live_laps["total_laps_race"]

print("-- 6. curatare si salvare --")
cols_to_drop = [c for c in ["time", "total_laps_race"] if c in live_laps.columns]
live_laps = live_laps.drop(columns=cols_to_drop)

live_laps = live_laps.sort_values(by=["year", "raceId", "lap", "position"])

save_path = os.path.join(data_folder, "dataset_01_live_modern.csv")
live_laps.to_csv(save_path, index=False)

print(f"salvare in: {save_path}")
print(f"randuri: {live_laps.shape[0]} (fiecare rand este un tur).")