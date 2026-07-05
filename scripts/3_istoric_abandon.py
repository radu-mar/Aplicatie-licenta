import os
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")



def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarcare dataset --")
live_laps = read_csv("dataset_02_istoric_pitstops.csv")
results = read_csv("results.csv")
status = read_csv("status.csv")
races = read_csv("races.csv")

print("-- 2. unire results cu status + info despre cursa si filtrare era moderna (2014+) --")
results = results.merge(status, on="statusId", how="left")
results = results.merge(races.loc[:, ["raceId", "year", "round", "circuitId"]], on="raceId", how="left")
results = results[results["year"] >= 2014].copy()

print("-- 3. definire accident vs defectiune tehnica --")
accidente = ["Accident", "Collision", "Spun off", "Collision damage", "Fatal accident"]
defectiuni = ["Engine", "Gearbox", "Transmission", "Hydraulics", "Electrical",
             "Suspension", "Brakes", "Overheating", "Power Unit"]

# defectiuni = [
#     "Engine", "Gearbox", "Transmission", "Clutch", "Hydraulics",
#     "Electrical", "Electronics", "Suspension", "Brakes", "Differential",
#     "Overheating", "Mechanical", "Radiator", "Driveshaft",
#     "Fuel pressure", "Water pressure", "Oil pressure", "Oil leak",
#     "Water leak", "Fuel pump", "Pneumatics", "Fuel system",
#     "Power loss", "Drivetrain", "Ignition", "Battery", "Alternator",
#     "Turbo", "Power Unit", "ERS", "Cooling system", "Throttle",
#     "Steering", "Exhaust", "Engine fire", "Engine misfire"
# ]

results["is_accident"] = results["status"].isin(accidente).astype(int)
results["is_mechanical"] = results["status"].isin(defectiuni).astype(int)

print("-- 4. calculez istoric pilot / echipa / circuit --")

#istoric pilot: accidente anterioare + rata
results = results.sort_values(by=["driverId", "year", "round"]).copy()

results["istoric_accidente_pilot"] = (
    results.groupby("driverId")["is_accident"].cumsum() - results["is_accident"]
)

results["starturi_pilot"] = results.groupby("driverId").cumcount()

results["rata_accidente_pilot"] = np.where(
    results["starturi_pilot"] > 0,
    results["istoric_accidente_pilot"] / results["starturi_pilot"],
    0.0
)

pilot_feat = results.loc[:, ["raceId", "driverId", "istoric_accidente_pilot", "rata_accidente_pilot"]].copy()

# istoric echipa: defectiuni anterioare + rata
# exclud valorile din cursa curentă pentru a evita data leakage
team_race = (
    results.groupby(["constructorId", "raceId", "year", "round"], as_index=False)
    .agg(
        defectiuni_echipa_cursa=("is_mechanical", "sum"),
        starturi_echipa_cursa=("driverId", "count")
    )
)

team_race = team_race.sort_values(by=["constructorId", "year", "round"]).copy()

team_race["istoric_defectiuni_echipa"] = (
    team_race.groupby("constructorId")["defectiuni_echipa_cursa"].cumsum()
    - team_race["defectiuni_echipa_cursa"]
)

team_race["starturi_echipa_istoric"] = (
    team_race.groupby("constructorId")["starturi_echipa_cursa"].cumsum()
    - team_race["starturi_echipa_cursa"]
)

team_race["rata_defectiuni_echipa"] = np.where(
    team_race["starturi_echipa_istoric"] > 0,
    team_race["istoric_defectiuni_echipa"] / team_race["starturi_echipa_istoric"],
    0.0
)

team_feat = team_race.loc[:, ["raceId", "constructorId", "istoric_defectiuni_echipa", "rata_defectiuni_echipa"]].copy()

# istoric circuit: accidente anterioare + rata
# exclud valorile din cursa curentă pentru a evita data leakage

circuit_race = (
    results.groupby(["circuitId", "raceId", "year", "round"], as_index=False)
    .agg(
        accidente_circuit_cursa=("is_accident", "sum"),
        starturi_circuit_cursa=("driverId", "count")
    )
)

circuit_race = circuit_race.sort_values(by=["circuitId", "year", "round"]).copy()

circuit_race["accidente_circuit_istoric"] = (
    circuit_race.groupby("circuitId")["accidente_circuit_cursa"].cumsum()
    - circuit_race["accidente_circuit_cursa"]
)

circuit_race["starturi_circuit_istoric"] = (
    circuit_race.groupby("circuitId")["starturi_circuit_cursa"].cumsum()
    - circuit_race["starturi_circuit_cursa"]
)

circuit_race["rata_accidente_circuit"] = np.where(
    circuit_race["starturi_circuit_istoric"] > 0,
    circuit_race["accidente_circuit_istoric"] / circuit_race["starturi_circuit_istoric"],
    0.0
)

circuit_feat = circuit_race.loc[:, ["raceId", "circuitId", "rata_accidente_circuit"]].copy()

# reunirea tuturor feature-urilor pe fiecare pilot in acea cursa
base_keys = results.loc[:, ["raceId", "driverId", "constructorId", "circuitId"]].copy()

features_abandon = base_keys.merge(pilot_feat, on=["raceId", "driverId"], how="left")
features_abandon = features_abandon.merge(team_feat, on=["raceId", "constructorId"], how="left")
features_abandon = features_abandon.merge(circuit_feat, on=["raceId", "circuitId"], how="left")

abandon_features = features_abandon.loc[:, [
    "raceId", "driverId",
    "istoric_accidente_pilot",
    "rata_accidente_pilot",
    "istoric_defectiuni_echipa",
    "rata_defectiuni_echipa",
    "rata_accidente_circuit"
]].drop_duplicates(subset=["raceId", "driverId"])

print("-- 5. lipirea feature-urilor de abandon in dataset --")
live_laps = live_laps.merge(abandon_features, on=["raceId", "driverId"], how="left")

cols_abandon = [
    "istoric_accidente_pilot",
    "rata_accidente_pilot",
    "istoric_defectiuni_echipa",
    "rata_defectiuni_echipa",
    "rata_accidente_circuit",
]
live_laps[cols_abandon] = live_laps[cols_abandon].fillna(0)

print("-- 6. salvez pasul 3 --")
save_path = os.path.join(data_folder, "dataset_03_istoric_abandon.csv")
live_laps.to_csv(save_path, index=False)

print(f"am salvat pasul 3 in: {save_path}")