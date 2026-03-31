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


def time_to_sec(value) -> float:
    if pd.isna(value) or value == r"\N":
        return np.nan

    try:
        parts = str(value).split(":")
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        return float(parts[0])
    except Exception:
        return np.nan


print("-- 1. incarcare dataset --")
master = read_csv("dataset_04_master_live.csv")
qualifying = read_csv("qualifying.csv")

print("-- 2. transform timpii din q1/q2/q3 in secunde --")
for col in ["q1", "q2", "q3"]:
    qualifying[col] = qualifying[col].apply(time_to_sec)

print("-- 3. aleg cel mai bun timp per pilot (min dintre q1/q2/q3) --")
qualifying["best_q_time"] = qualifying[["q1", "q2", "q3"]].min(axis=1)
qualy_ok = qualifying.dropna(subset=["best_q_time"]).copy()

print("-- 4. calculez gap-ul fata de pole (secunde si procent) --")
pole_times = (
    qualy_ok.groupby("raceId", as_index=False)["best_q_time"]
    .min()
    .rename(columns={"best_q_time": "pole_time"})
)

qualy_ok = qualy_ok.merge(pole_times, on="raceId", how="left")
qualy_ok["gap_to_pole_sec"] = qualy_ok["best_q_time"] - qualy_ok["pole_time"]
qualy_ok["gap_to_pole_ratio"] = qualy_ok["gap_to_pole_sec"] / qualy_ok["pole_time"]

qualy_final = qualy_ok.loc[:, [
    "raceId",
    "driverId",
    "gap_to_pole_sec",
    "gap_to_pole_ratio",
    "position",
]].rename(columns={"position": "qualy_position"})

print("-- 5. lipesc informatia de calificari in master (idempotent) --")
# daca rerulam scriptul, scot coloanele existente ca sa evit _x / _y
cols_qualy = ["gap_to_pole_sec", "gap_to_pole_ratio", "qualy_position"]
master = master.drop(columns=[c for c in cols_qualy if c in master.columns], errors="ignore")

out = master.merge(qualy_final, on=["raceId", "driverId"], how="left")

# penalizare pentru cazurile fara timp de calificare
penalty_sec = 10.0
penalty_ratio = 0.10

out["gap_to_pole_sec"] = out["gap_to_pole_sec"].fillna(penalty_sec)
out["gap_to_pole_ratio"] = out["gap_to_pole_ratio"].fillna(penalty_ratio)
out["qualy_position"] = out["qualy_position"].fillna(20)

print("-- 6. salvarea datasetului --")
save_path = os.path.join(data_folder, "dataset_04_master_live.csv")
out.to_csv(save_path, index=False)

print(f"am adaugat feature-urile de calificari (gap_to_pole_sec / ratio).")
print(f"fisier salvat: {save_path}")