import os
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")


def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarc master dataset-ul si istoricul de rezultate --")
master = read_csv("dataset_04_master_live.csv")
results = read_csv("results.csv")
races = read_csv("races.csv")

print("-- 2. pregatesc informatia cronologica si filtrez doar 2014+ --")
race_info = races.loc[:, ["raceId", "year", "round"]].copy()
race_info = race_info[race_info["year"] >= 2014].copy()

# -------------------------------------------------
# a) momentum pilot (media punctelor pe ultimele n curse, fara leakage)
# -------------------------------------------------
print("-- 3. calculez momentum-ul pilotului (3 si 6 curse) --")

pilot_points = results.loc[:, ["raceId", "driverId", "points"]].merge(
    race_info, on="raceId", how="inner"
)

pilot_points = pilot_points.sort_values(by=["driverId", "year", "round"]).copy()

pilot_points["pilot_momentum_3"] = (
    pilot_points.groupby("driverId")["points"]
    .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
)

pilot_points["pilot_momentum_6"] = (
    pilot_points.groupby("driverId")["points"]
    .transform(lambda x: x.shift(1).rolling(window=6, min_periods=1).mean())
)

pilot_points[["pilot_momentum_3", "pilot_momentum_6"]] = (
    pilot_points[["pilot_momentum_3", "pilot_momentum_6"]].fillna(0)
)

pilot_momentum_final = pilot_points.loc[:, [
    "raceId", "driverId", "pilot_momentum_3", "pilot_momentum_6"
]].drop_duplicates(subset=["raceId", "driverId"])

# -------------------------------------------------
# b) momentum echipa (pe cursa, nu pe rand de pilot; fara leakage)
# -------------------------------------------------
print("-- 3.1 calculez momentum-ul echipei (3 si 6 curse) --")

team_points = results.loc[:, ["raceId", "constructorId", "points"]].merge(
    race_info, on="raceId", how="inner"
)

# agregare: punctele echipei pe cursa = suma ambilor piloti
team_race = (
    team_points.groupby(["constructorId", "raceId", "year", "round"], as_index=False)
    .agg(team_points_race=("points", "sum"))
)

team_race = team_race.sort_values(by=["constructorId", "year", "round"]).copy()

team_race["team_momentum_3"] = (
    team_race.groupby("constructorId")["team_points_race"]
    .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
)

team_race["team_momentum_6"] = (
    team_race.groupby("constructorId")["team_points_race"]
    .transform(lambda x: x.shift(1).rolling(window=6, min_periods=1).mean())
)

team_race[["team_momentum_3", "team_momentum_6"]] = (
    team_race[["team_momentum_3", "team_momentum_6"]].fillna(0)
)

team_momentum_final = team_race.loc[:, [
    "raceId", "constructorId", "team_momentum_3", "team_momentum_6"
]].drop_duplicates(subset=["raceId", "constructorId"])

print("-- 4. lipesc momentum-ul in master (idempotent) --")
# daca rerulam scriptul, scot coloanele vechi ca sa evit _x/_y
momentum_cols = ["pilot_momentum_3", "pilot_momentum_6", "team_momentum_3", "team_momentum_6"]
master = master.drop(columns=[c for c in momentum_cols if c in master.columns], errors="ignore")

out = master.merge(pilot_momentum_final, on=["raceId", "driverId"], how="left")
out = out.merge(team_momentum_final, on=["raceId", "constructorId"], how="left")
out[momentum_cols] = out[momentum_cols].fillna(0)

print("-- 5. salvez master dataset-ul actualizat --")
save_path = os.path.join(data_folder, "dataset_04_master_live.csv")
out.to_csv(save_path, index=False)

print("gata! atributele de momentum (pilot + echipa) au fost adaugate fara leakage.")
print(f"fisier salvat: {save_path}")