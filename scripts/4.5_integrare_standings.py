import os
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(base_dir, "date_f1")



def read_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(data_folder, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"nu gasesc fisierul: {path}")
    return pd.read_csv(path)


print("-- 1. incarc master dataset-ul si fisierele de standings --")
master = read_csv("dataset_04_master_live.csv")
driver_standings = read_csv("driver_standings.csv")
constructor_standings = read_csv("constructor_standings.csv")
races = read_csv("races.csv")

print("-- 0. curatare + consistenta (idempotent) --")
# daca rerulam scriptul, scot coloanele deja existente ca sa evit _x / _y la merge
standings_cols = [
    "driver_puncte_inainte_de_cursa",
    "driver_pozitie_campionat",
    "echipa_puncte_inainte_de_cursa",
    "echipa_pozitie_campionat",
    "driver_gap_lider_campionat",
    "echipa_gap_lider_campionat",
    "driver_top3_campionat",
    "echipa_top3_campionat",
]
master = master.drop(columns=[c for c in standings_cols if c in master.columns], errors="ignore")

# info cronologica (si filtrare era moderna)
race_info = races.loc[:, ["raceId", "year", "round"]].copy()
race_info = race_info[race_info["year"] >= 2014].copy()

# optional: daca master are year, pastrez doar 2014+
if "year" in master.columns:
    master = master[master["year"] >= 2014].copy()

print("-- 2. pregatesc driver standings (fara leakage) --")
ds = driver_standings.merge(race_info, on="raceId", how="inner")

# convertesc la numeric in caz ca vin ca string
for col in ["points", "position"]:
    ds[col] = pd.to_numeric(ds[col], errors="coerce")

# sortare determinista
ds = ds.sort_values(by=["year", "round", "driverId"]).copy()

# fara leakage: folosesc standings-ul din cursa anterioara (shift in cadrul aceluiasi an)
ds["driver_puncte_inainte_de_cursa"] = ds.groupby(["year", "driverId"])["points"].shift(1)
ds["driver_pozitie_campionat"] = ds.groupby(["year", "driverId"])["position"].shift(1)

# fill pentru inceput de sezon / rezerve
ds["driver_puncte_inainte_de_cursa"] = ds["driver_puncte_inainte_de_cursa"].fillna(0.0)
ds["driver_pozitie_campionat"] = ds["driver_pozitie_campionat"].fillna(20)

# extra: gap fata de liderul campionatului (inainte de cursa)
leader_driver_points = ds.groupby("raceId")["driver_puncte_inainte_de_cursa"].transform("max")
ds["driver_gap_lider_campionat"] = (leader_driver_points - ds["driver_puncte_inainte_de_cursa"]).clip(lower=0)

# extra: flag top3
ds["driver_top3_campionat"] = (ds["driver_pozitie_campionat"] <= 3).astype(int)

ds_clean = ds.loc[:, [
    "raceId", "driverId",
    "driver_puncte_inainte_de_cursa",
    "driver_pozitie_campionat",
    "driver_gap_lider_campionat",
    "driver_top3_campionat",
]].drop_duplicates(subset=["raceId", "driverId"])

print("-- 3. pregatesc constructor standings (fara leakage) --")
cs = constructor_standings.merge(race_info, on="raceId", how="inner")

for col in ["points", "position"]:
    cs[col] = pd.to_numeric(cs[col], errors="coerce")

cs = cs.sort_values(by=["year", "round", "constructorId"]).copy()

cs["echipa_puncte_inainte_de_cursa"] = cs.groupby(["year", "constructorId"])["points"].shift(1)
cs["echipa_pozitie_campionat"] = cs.groupby(["year", "constructorId"])["position"].shift(1)

cs["echipa_puncte_inainte_de_cursa"] = cs["echipa_puncte_inainte_de_cursa"].fillna(0.0)
cs["echipa_pozitie_campionat"] = cs["echipa_pozitie_campionat"].fillna(10)

leader_team_points = cs.groupby("raceId")["echipa_puncte_inainte_de_cursa"].transform("max")
cs["echipa_gap_lider_campionat"] = (leader_team_points - cs["echipa_puncte_inainte_de_cursa"]).clip(lower=0)

cs["echipa_top3_campionat"] = (cs["echipa_pozitie_campionat"] <= 3).astype(int)

cs_clean = cs.loc[:, [
    "raceId", "constructorId",
    "echipa_puncte_inainte_de_cursa",
    "echipa_pozitie_campionat",
    "echipa_gap_lider_campionat",
    "echipa_top3_campionat",
]].drop_duplicates(subset=["raceId", "constructorId"])

print("-- 4. integrez standings in master + verificari rapide --")
rows_before = len(master)

out = master.merge(ds_clean, on=["raceId", "driverId"], how="left")
out = out.merge(cs_clean, on=["raceId", "constructorId"], how="left")

if len(out) != rows_before:
    print(f"atentie: numarul de randuri s-a schimbat! inainte={rows_before}, dupa={len(out)}")
else:
    print(f"ok: numarul de randuri a ramas constant ({rows_before})")

fill_defaults = {
    "driver_puncte_inainte_de_cursa": 0.0,
    "driver_pozitie_campionat": 20,
    "driver_gap_lider_campionat": 0.0,
    "driver_top3_campionat": 0,
    "echipa_puncte_inainte_de_cursa": 0.0,
    "echipa_pozitie_campionat": 10,
    "echipa_gap_lider_campionat": 0.0,
    "echipa_top3_campionat": 0,
}
for col, val in fill_defaults.items():
    out[col] = out[col].fillna(val)

print("verificare rapida coloane standings (non-null):")
for col in fill_defaults.keys():
    print(f" - {col}: {out[col].notna().mean() * 100:.2f}%")

# sanity: pentru acelasi pilot in aceeasi cursa, standing-urile trebuie sa fie constante
max_unique = out.groupby(["raceId", "driverId"])["driver_puncte_inainte_de_cursa"].nunique().max()
print(f"sanity check (max valori distincte driver_puncte_inainte_de_cursa per raceId+driverId): {max_unique}")

print("-- 5. salvez master dataset-ul actualizat --")
save_path = os.path.join(data_folder, "dataset_04_master_live.csv")
out.to_csv(save_path, index=False)

print(f"gata! standings integrate pentru {len(out)} randuri.")
print(f"fisier salvat: {save_path}")