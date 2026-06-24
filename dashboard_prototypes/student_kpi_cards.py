"""Data prep + per-student summary for the Student Summary dashboard.

Single source of truth for thresholds, colors, and the per-student aggregation logic.
Used by `student_summary_dash.qmd` to populate KPI valueboxes and feed the charts.
"""
import pandas as pd
import numpy as np

# Shared palette — matches the dashboard color tokens defined in
# src/kc_mastery_box.py.
COLORS = {
    "mastered":    "#60D394",   # Emerald
    "developing":  "#FFD97D",   # Jasmine
    "needs":       "#FF9B85",   # Sweet Salmon (matches teacher view ATTENTION_FILL)
    "unattempted": "#8B9DBB",   # Lavender Grey
    "ahead":       "#60D394",
    "behind":      "#FF9B85",
}

# Per-MKC mastery thresholds (raw average correctness)
T_MASTERED   = 0.70
T_DEVELOPING = 0.40


def load_data(data_path: str, pack_path: str):
    """Load observations + the partner's MKC mapping pack. Returns a long-form
    DataFrame keyed by (student_id, mkc, unit, correct) plus the mkc/unit list."""
    obs    = pd.read_excel(data_path, sheet_name="Student_Observations")
    fmap   = pd.read_excel(pack_path, sheet_name="FineKC_to_ModelingKC_Map")
    mnodes = pd.read_excel(pack_path, sheet_name="Modeling_KC_Nodes")

    fine2mkc  = dict(zip(fmap["fine_kc_id"], fmap["modeling_kc_id"]))
    mkc2unit  = dict(zip(mnodes["modeling_kc_id"], mnodes["unit"]))
    mkc2label = dict(zip(mnodes["modeling_kc_id"], mnodes["modeling_kc_label"]))

    o = obs[obs["score"] != 0.5].copy()
    o["correct"] = o["score"].astype(int)
    o["mkc"]     = o["primary_kc_id"].map(fine2mkc)
    o["unit"]    = o["mkc"].map(mkc2unit)
    o = o.rename(columns={"student_id": "user_id"})

    units = [f"Unit {i}" for i in range(1, 11)]
    unit_mkcs = {u: list(mnodes[mnodes["unit"] == u]["modeling_kc_id"]) for u in units}

    return o, mkc2label, mkc2unit, unit_mkcs, units


def tier_overall(overall: float) -> tuple[str, str, str]:
    """Status tier for the whole student. Color is a hex from the team palette
    so valueboxes render in the dashboard's actual colors instead of stock
    Bootstrap green/yellow/red."""
    if overall >= 0.60: return ("on_track",  "On track",        "#60D394")  # Emerald
    if overall >= 0.45: return ("attention", "Needs attention", "#FFD97D")  # Jasmine
    return                    ("at_risk",    "At risk",         "#FF9B85")  # Sweet Salmon


def tier_for_unit(t: dict) -> str:
    """Tile color: red = any needs-practice KC, yellow = developing majority,
    green = mostly mastered, gray = unattempted."""
    if t["total"] == t["n_unattempted"]:    return "gray"
    if t["n_needs"] > 0:                    return "red"
    if t["n_developing"] > t["n_mastered"]: return "yellow"
    return                                          "green"


def compute_student_summary(o, mkc2label, mkc2unit, unit_mkcs, units, student_id):
    """For one student: per-unit breakdown + totals + class comparison vectors."""
    sob = o[o["user_id"] == student_id]
    overall = float(sob["correct"].mean()) if len(sob) else 0.0
    mkc_mast = sob.groupby("mkc")["correct"].mean().to_dict()

    tiles = []
    for u in units:
        total       = unit_mkcs[u]
        attempted   = [m for m in total if m in mkc_mast]
        unattempted = [m for m in total if m not in mkc_mast]

        mastered, developing, needs = [], [], []
        for m in attempted:
            v = mkc_mast[m]
            entry = {"label": mkc2label.get(m, m), "mastery": round(v * 100, 1)}
            if   v >= T_MASTERED:   mastered.append(entry)
            elif v >= T_DEVELOPING: developing.append(entry)
            else:                   needs.append(entry)

        avg = sum(mkc_mast[m] for m in attempted) / len(attempted) if attempted else None
        tile = {
            "unit": u,
            "avg_mastery":   round(avg * 100, 1) if avg is not None else None,
            "total":         len(total),
            "n_mastered":    len(mastered),
            "n_developing":  len(developing),
            "n_needs":       len(needs),
            "n_unattempted": len(unattempted),
            "mastered_list":    sorted(mastered,   key=lambda x: -x["mastery"]),
            "developing_list":  sorted(developing, key=lambda x:  x["mastery"]),
            "needs_list":       sorted(needs,      key=lambda x:  x["mastery"]),
            "unattempted_list": [{"label": mkc2label.get(m, m)} for m in unattempted],
        }
        tile["tier"] = tier_for_unit(tile)
        tiles.append(tile)

    totals = {
        "mastered":    sum(t["n_mastered"]    for t in tiles),
        "developing":  sum(t["n_developing"]  for t in tiles),
        "needs":       sum(t["n_needs"]       for t in tiles),
        "unattempted": sum(t["n_unattempted"] for t in tiles),
        "all":         sum(t["total"]         for t in tiles),
    }
    tier_id, tier_label, tier_color = tier_overall(overall)

    return {
        "student_id":   student_id,
        "overall":      round(overall * 100, 1),
        "tier_id":      tier_id,
        "tier_label":   tier_label,
        "tier_color":   tier_color,
        "tiles":        tiles,
        "totals":       totals,
    }


def class_average_per_unit(o, units) -> dict:
    """Student-weighted class average correctness per unit, over all 25 students."""
    per = o.groupby(["user_id", "unit"])["correct"].mean().unstack("unit")
    return {u: float(per[u].mean()) for u in units if u in per.columns}
