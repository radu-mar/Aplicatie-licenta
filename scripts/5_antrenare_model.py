import os
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")


def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


def build_eval_df(test_df: pd.DataFrame, proba: np.ndarray) -> pd.DataFrame:
    """
    construieste tabelul de evaluare cu cheile (raceId, lap, driverId),
    probabilitatea p_win, target-ul is_winner si race_progress.
    include deduplicare defensiva pe (raceId, lap, driverId).
    """
    df_eval = test_df.loc[:, ["raceId", "lap", "driverId", "is_winner", "race_progress"]].copy()
    df_eval["p_win"] = proba

    df_eval = (
        df_eval.groupby(["raceId", "lap", "driverId"], as_index=False)
        .agg(
            is_winner=("is_winner", "max"),
            race_progress=("race_progress", "max"),
            p_win=("p_win", "max"),
        )
    )

    # sortare astfel incat primii sa fie cei cu probabilitate mai mare
    df_eval = df_eval.sort_values(by=["raceId", "lap", "p_win"], ascending=[True, True, False])
    return df_eval


def top1_top3_winner_metrics(df_eval: pd.DataFrame) -> dict:
    """
    metrica pentru winner:
      - top1 hit rate: winner este pe locul 1 dupa p_win
      - top3 hit rate: winner este in primii 3 dupa p_win
    """
    top1 = df_eval.groupby(["raceId", "lap"]).head(1)
    top1_hit = top1["is_winner"].mean()

    top3 = df_eval.groupby(["raceId", "lap"]).head(3)
    top3_hit = top3.groupby(["raceId", "lap"])["is_winner"].max().mean()

    return {
        "top1_hit_rate": float(top1_hit),
        "top3_hit_rate": float(top3_hit),
    }


def podium_top3_metrics(df_eval: pd.DataFrame, podium_map: pd.DataFrame) -> dict:
    """
    metrica pentru podium final:
      - avg hits din 3: cate pozitii din top3 sunt in podium final (0..3), medie
      - precision@3: avg_hits/3
      - exact 3/3: cat de des top3 prezis contine fix podiumul
      - >=2/3, >=1/3: cat de des prinzi cel putin 2 sau 1 din podium
    """
    pred_top3 = df_eval.groupby(["raceId", "lap"]).head(3).copy()
    pred_top3 = pred_top3.merge(podium_map, on=["raceId", "driverId"], how="left")
    pred_top3["is_podium_final"] = pred_top3["is_podium_final"].fillna(0).astype(int)

    hits_per_lap = pred_top3.groupby(["raceId", "lap"])["is_podium_final"].sum()

    avg_hits = hits_per_lap.mean()
    precision_at_3 = (hits_per_lap / 3).mean()
    rate_3of3 = (hits_per_lap == 3).mean()
    rate_2plus = (hits_per_lap >= 2).mean()
    rate_1plus = (hits_per_lap >= 1).mean()

    return {
        "avg_hits": float(avg_hits),
        "precision_at_3": float(precision_at_3),
        "rate_3of3": float(rate_3of3),
        "rate_2plus": float(rate_2plus),
        "rate_1plus": float(rate_1plus),
    }


def print_block(title: str, metrics: dict) -> None:
    print(f"\n{title}")
    for k, v in metrics.items():
        if "avg_hits" in k:
            print(f"{k}: {v:.3f}")
        else:
            print(f"{k}: {v:.4f}")

import os

csv_path = "dataset_04_master_live.csv"
print("cwd =", os.getcwd())
print("csv absolut =", os.path.abspath(csv_path))


print("-- 1. incarcare dataset --")
df = read_csv("dataset_04_master_live.csv")

print("-- 2. alegerea feature-urilor --")
# features = [
#     # dinamica live
#     "lap",
#     "position",
#     "grid",
#     "positions_gained",
#     "laps_remaining",
#     "laps_remaining_ratio",
#     "race_progress",
#     "started_from_pitlane",
#     # gap-uri
#     "gap_to_leader_sec",
#     "gap_ratio",
#     "gap_trend",
#     "delta_leader_lap",
#     # calificari
#     "gap_to_pole_sec",
#     "gap_to_pole_ratio",
#     "qualy_position",
#     # pit
#     "istoric_pit_echipa_sec",
#     # abandon
#     "rata_accidente_pilot",
#     "rata_defectiuni_echipa",
#     "rata_accidente_circuit",
#     # momentum
#     "pilot_momentum_3",
#     "pilot_momentum_6",
#     "team_momentum_3",
#     "team_momentum_6",
#     # standings (4.5 imbunatatit)
#     "driver_gap_lider_campionat",
#     "echipa_gap_lider_campionat",
#     "driver_top3_campionat",
#     "echipa_top3_campionat",
# ]


features = [
    "lap",
    "position",
    "grid",
    "positions_gained",
    "race_progress",
    "started_from_pitlane",

    "gap_to_leader_sec",
    "gap_trend",

    "gap_to_pole_sec",

    "istoric_pit_echipa_sec",

    "rata_accidente_pilot",
    "rata_defectiuni_echipa",
    "rata_accidente_circuit",

    "pilot_momentum_3",
    "pilot_momentum_6",
    "team_momentum_3",
    "team_momentum_6",

    "driver_gap_lider_campionat",
    "echipa_gap_lider_campionat",
    "driver_top3_campionat",
    "echipa_top3_campionat",
]


required = features + ["is_winner", "year", "raceId", "driverId", "lap", "race_progress"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"lipsesc coloane din dataset: {missing}")

df = df.dropna(subset=features + ["is_winner"]).copy()

print("-- 3. impartire cronologica train/test --")
train_df = df[df["year"] < 2023].copy()
test_df = df[df["year"] >= 2023].copy()

if train_df.empty or test_df.empty:
    raise ValueError("train sau test este gol. verifica anii disponibili si split-ul ales.")

X_train = train_df[features]
y_train = train_df["is_winner"].astype(int)

X_test = test_df[features]
y_test = test_df["is_winner"].astype(int)

print(f" -> train: {len(X_train)} randuri (2014-2022)")
print(f" -> test:  {len(X_test)} randuri (2023-prezent)")

print("-- 4. antrenez modelul ales pentru top-3 --")
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=12,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
model.fit(X_train, y_train)

print("-- 5. calculez probabilitatile pe test --")
proba = model.predict_proba(X_test)[:, 1]

# prag standard 0.5 pentru eticheta prezisa
y_pred = (proba >= 0.5).astype(int)

# metrici clasice de clasificare
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, zero_division=0)
recall = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)

# roc/pr pentru ranking global
roc_auc = roc_auc_score(y_test, proba)
pr_auc = average_precision_score(y_test, proba)

# construiesc dataframe-ul de evaluare (o singura data)
eval_df = build_eval_df(test_df, proba)

# pregatesc podiumul final (locurile 1-3) din results.csv
print("-- 5.1 pregatesc podiumul final --")
results = read_csv("results.csv")
podium = results.loc[results["positionOrder"].isin([1, 2, 3]), ["raceId", "driverId"]].copy()
podium["is_podium_final"] = 1
podium_map = podium.drop_duplicates(subset=["raceId", "driverId"])

print("-- 5.2 evaluare overall (toate tururile) --")
overall_podium = podium_top3_metrics(eval_df, podium_map)
overall_winner = top1_top3_winner_metrics(eval_df)

print_block("podium final (overall)", overall_podium)
print_block("winner ranking (overall)", overall_winner)
print(f"\nroc-auc (overall): {roc_auc:.4f}")
print(f"pr-auc  (overall): {pr_auc:.4f}")

print(f"accuracy (threshold=0.5): {accuracy:.4f}")
print(f"precision: {precision:.4f}")
print(f"recall:    {recall:.4f}")
print(f"f1-score:  {f1:.4f}")

# -----------------------------
# evaluare pe segmente: early / mid / late
# -----------------------------
print("\n-- 5.3 evaluare pe segmente de cursa (early/mid/late) --")

segments = {
    "early (race_progress < 0.25)": eval_df[eval_df["race_progress"] < 0.25].copy(),
    "mid (0.25 <= race_progress <= 0.75)": eval_df[(eval_df["race_progress"] >= 0.25) & (eval_df["race_progress"] <= 0.75)].copy(),
    "late (race_progress > 0.75)": eval_df[eval_df["race_progress"] > 0.75].copy(),
}

for seg_name, seg_df in segments.items():
    if seg_df.empty:
        print(f"\n{seg_name}: (nu exista date in acest segment)")
        continue

    seg_podium = podium_top3_metrics(seg_df, podium_map)
    seg_winner = top1_top3_winner_metrics(seg_df)

    print_block(f"podium final - {seg_name}", seg_podium)
    print_block(f"winner ranking - {seg_name}", seg_winner)


print("\n-- 6. salvez modelul --")
model_path = os.path.join(data_folder, "f1_live_model.pkl")
joblib.dump(model, model_path)
print(f"modelul a fost salvat: {model_path}")