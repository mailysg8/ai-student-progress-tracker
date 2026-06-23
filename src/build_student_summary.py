"""Student Summary view — generates the interactive HTML dashboard.

Builds a per-student dashboard with:
  * Top KPI cards (Mastered / Progressing / Needs Practice / Unattempted),
    bucketed by BKT mastery and clickable to a flat skill-list modal.
  * Ten unit tiles showing a BKT-mastery distribution strip plot, count
    breakdown, trend sparkline, and a click-through detail modal.
  * A class-comparison panel and a primary call-to-action.

The output HTML is rendered standalone or embedded in the Shiny app via
an iframe.
"""
import json
from pathlib import Path
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

# Portable path resolution: works whether the script sits in src/ or repo root
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if (HERE.name == "src" and (HERE.parent / "notebooks").exists()) else HERE

SEARCH = [
    REPO_ROOT/"data"/"processed",      # unified data pipeline output
    REPO_ROOT/"data"/"raw",            # raw xlsx files (scores sheet, KC pack)
    REPO_ROOT/"data", REPO_ROOT,
    Path.cwd(), Path.cwd()/"data"/"processed", Path.cwd()/"data"/"raw",
]
def find_file(name):
    """Locate a data file by name across the candidate ``SEARCH`` paths.

    Walks the project's typical data directories (``data/processed``,
    ``data/raw``, the repo root, and the current working directory) and
    returns the first match. Lets the script run unchanged whether it is
    invoked from the repo root or from inside ``src/``.

    Parameters
    ----------
    name : str
        File name to search for (e.g. ``"final_student_kc_data.csv"``).

    Returns
    -------
    pathlib.Path
        The first existing path that matches ``name``.

    Raises
    ------
    FileNotFoundError
        If ``name`` is not present under any of the search paths.
    """
    for b in SEARCH:
        f = b / name
        if f.exists():
            return f
    raise FileNotFoundError(f"{name} not found in any of: {[str(s) for s in SEARCH]}")

CSV  = find_file(os.environ.get("FINAL_FILE"))           # unified data pipeline output
DATA = find_file(os.environ.get("STUDENT_OBS_FILE"))     # Overall_Scores sheet (student-level metadata)
PACK = find_file(os.environ.get("KC_MAP_FILE"))          # canonical KC structure (for unit_mkcs)
OUT  = REPO_ROOT / "notebooks" / "student_summary.html"
OUT.parent.mkdir(parents=True, exist_ok=True)
print(f"  Using CSV: {CSV}")
print(f"  Using xlsx (scores only): {DATA}")
print(f"  Using MKC pack: {PACK}")
print(f"  Output: {OUT}")

# The unified CSV already joins every observation with the modeling-KC mapping,
# the unit, the precomputed `correct` flag, and class_date. This removes the
# need for a separate fine-KC → MKC mapping step at runtime.
csv_df = pd.read_csv(CSV)
scores = pd.read_excel(DATA, sheet_name="Overall_Scores")  # student-level metadata
mnodes = pd.read_excel(PACK, sheet_name="Modeling_KC_Nodes")  # canonical KC list

mkc2unit  = dict(zip(mnodes["modeling_kc_id"], mnodes["unit"]))
mkc2label = dict(zip(mnodes["modeling_kc_id"], mnodes["modeling_kc_label"]))

UNITS = [f"Unit {i}" for i in range(1, 11)]
unit_mkcs = {u: list(mnodes[mnodes["unit"]==u]["modeling_kc_id"]) for u in UNITS}

# Build `o` from the unified CSV instead of the xlsx — `correct`, `modeling_kc_id`,
# and `unit` are already present. We just alias modeling_kc_id → mkc for backward
# compatibility with the rest of the file.
o = csv_df[csv_df["score"] != 0.5].copy()
o["correct"] = o["correct"].astype(int)
o["mkc"]     = o["modeling_kc_id"]
# `unit` and `class_num` already exist in the CSV — used for weekly trend buckets

T_MASTERED   = 0.65   # mastered = ≥ 65%
T_DEVELOPING = 0.35   # progressing = 35–64%, needs practice = < 35%
N_TREND_BUCKETS = 5   # number of bars per KPI sparkline (snapshots over the term)
TOTAL_MKCS = sum(len(unit_mkcs[u]) for u in UNITS)

# ─── BKT mastery layer (unit cards use BKT, not raw correctness) ──
# For each (student, modeling_kc_id), take the LATEST state_predictions across
# all their attempts. This is the BKT model's current estimate of how well the
# student has mastered that KC right now.
_bkt_src = o.sort_values(["student_id", "mkc", "kc_attempt"])
_bkt_latest = _bkt_src.groupby(["student_id", "mkc"])["state_predictions"].last()
# Dict for fast O(1) lookup in build_html
bkt_mastery_map = {(sid, m): float(v) for (sid, m), v in _bkt_latest.items()}

# Per-unit class average of BKT mastery — for unit-tile "vs class" comparison.
# Skip unattempted MKCs (no entry in map for that student × mkc).
bkt_class_per_unit = {}
for _u in UNITS:
    _vals = []
    for _sid in scores["student_id"].unique():
        for _m in unit_mkcs[_u]:
            _v = bkt_mastery_map.get((_sid, _m))
            if _v is not None:
                _vals.append(_v)
    bkt_class_per_unit[_u] = (sum(_vals)/len(_vals)) if _vals else None

def tier_overall(overall):
    """Map a student's overall mastery score to a status-tier badge.

    Used for the header badge next to the student name in the Student Summary
    view ("On track" / "Needs attention" / "At risk").

    Parameters
    ----------
    overall : float
        Overall mastery, in ``[0, 1]``.

    Returns
    -------
    tuple of (str, str, str)
        ``(tier_id, tier_label, hex_color)`` where the hex colour comes from
        the dashboard palette.
    """
    if overall >= 0.60: return ("on_track",  "On track",        "#60D394")  # Emerald
    if overall >= 0.45: return ("attention", "Needs attention", "#FFD97D")  # Jasmine
    return                    ("at_risk",   "At risk",          "#EE6055")  # Vibrant Coral

def tier_for_tile(t):
    """Tile color reflects the unit's OVERALL state via the BKT mastery
    distribution's central tendency (median):
       gray   = nothing attempted yet
       red    = median < 35%  → most of the unit is weak
       yellow = median 35–64% → still developing overall
       green  = median ≥ 65%  → mostly or all mastered

    Previously: any single 'needs practice' KC made the whole tile red, which
    was overly punitive — a student with 5/6 mastered and 1 weak KC still got
    a red card. Now the median drives the color, and the strip plot + count
    rows still surface individual weak skills.
    """
    if t["total"] == t["n_unattempted"]: return "gray"
    med = t.get("median_mastery")
    if med is None: return "gray"
    if med < T_DEVELOPING * 100: return "red"
    if med < T_MASTERED   * 100: return "yellow"
    return "green"

per_stu_per_unit = (o.groupby(["student_id","unit"])["correct"].mean().unstack("unit"))
class_avg = {u: float(per_stu_per_unit[u].mean()) for u in UNITS if u in per_stu_per_unit.columns}


def _get_class_avg_totals():
    """Compute average (mastered, developing, needs, unattempted) counts across all
    students — bucketed by BKT mastery (matches the top-card categorization).
    Used to give per-student KPI cards a class-relative context.

    Cached after first call.
    """
    if hasattr(_get_class_avg_totals, "_cache"):
        return _get_class_avg_totals._cache

    sids = scores["student_id"].unique().tolist()
    sums = {"mastered": 0, "developing": 0, "needs": 0, "unattempted": 0, "all": 0}
    n_students = 0

    for sid in sids:
        s_mast = s_dev = s_need = s_unatt = s_total = 0
        for u in UNITS:
            for m in unit_mkcs[u]:
                s_total += 1
                v = bkt_mastery_map.get((sid, m))
                if v is None:
                    s_unatt += 1
                else:
                    if   v >= T_MASTERED:   s_mast += 1
                    elif v >= T_DEVELOPING: s_dev  += 1
                    else:                   s_need += 1
        if s_total == 0:
            continue
        sums["mastered"]    += s_mast
        sums["developing"]  += s_dev
        sums["needs"]       += s_need
        sums["unattempted"] += s_unatt
        sums["all"]         += s_total
        n_students += 1

    result = {
        "mastered":    round(sums["mastered"]    / n_students) if n_students else 0,
        "developing":  round(sums["developing"]  / n_students) if n_students else 0,
        "needs":       round(sums["needs"]       / n_students) if n_students else 0,
        "unattempted": round(sums["unattempted"] / n_students) if n_students else 0,
        "all":         round(sums["all"]         / n_students) if n_students else 0,
    }
    _get_class_avg_totals._cache = result
    return result


def _compute_student_unit_trends(sid):
    """For each unit, return list of avg BKT mastery snapshots at the same
    class_num cutoffs as _compute_student_weekly_trends.

    Used to render a tiny sparkline + 'since first class' delta on each Unit
    tile so students see momentum per unit ('Unit 3 jumped +12pp this term').

    BKT-based: for each cutoff, take the latest state_predictions per MKC up to
    that point, then average across MKCs in the unit. This shows the BKT model's
    estimate of mastery EVOLVING over the term — distinct from raw correctness
    history (which is what the top KPI sparklines use).
    """
    sob = o[o["student_id"] == sid]
    if sob.empty:
        return {u: [] for u in UNITS}
    classes = sorted(sob["class_num"].unique().tolist())
    if len(classes) < 2:
        return {u: [] for u in UNITS}

    if len(classes) <= N_TREND_BUCKETS:
        cutoffs = classes
    else:
        idxs = [int(round(i * (len(classes) - 1) / (N_TREND_BUCKETS - 1)))
                for i in range(N_TREND_BUCKETS)]
        cutoffs = [classes[i] for i in idxs]

    unit_trends = {u: [] for u in UNITS}
    for cutoff in cutoffs:
        history = sob[sob["class_num"] <= cutoff].sort_values(["mkc", "kc_attempt"])
        # latest state_predictions per MKC, considering only attempts up to cutoff
        per_mkc_bkt = history.groupby("mkc")["state_predictions"].last()
        # Join MKC → unit, then average per unit
        mkc_to_unit = {m: mkc2unit.get(m) for m in per_mkc_bkt.index}
        by_unit = {}
        for m, v in per_mkc_bkt.items():
            u = mkc_to_unit.get(m)
            if u is None:
                continue
            by_unit.setdefault(u, []).append(float(v))
        for u in UNITS:
            vals = by_unit.get(u, [])
            unit_trends[u].append(None if not vals else round(sum(vals)/len(vals)*100, 1))
    return unit_trends


def _compute_student_weekly_trends(sid):
    """Return N_TREND_BUCKETS snapshots of (mastered, developing, needs, unattempted)
    KC counts for one student, bucketed by BKT mastery at each cutoff. Each
    snapshot is CUMULATIVE — for every MKC, we take the latest state_predictions
    observed up to that cutoff.

    Used to draw the mini sparkline on each top KPI card so students see how
    their BKT mastery distribution has shifted across the term — consistent
    with the rest of the dashboard which is BKT throughout.
    """
    sob = o[o["student_id"] == sid]
    if sob.empty:
        return []
    classes = sorted(sob["class_num"].unique().tolist())
    if len(classes) < 2:
        return []

    if len(classes) <= N_TREND_BUCKETS:
        cutoffs = classes
    else:
        idxs = [int(round(i * (len(classes) - 1) / (N_TREND_BUCKETS - 1)))
                for i in range(N_TREND_BUCKETS)]
        cutoffs = [classes[i] for i in idxs]

    trends = []
    for cutoff in cutoffs:
        history = sob[sob["class_num"] <= cutoff].sort_values(["mkc", "kc_attempt"])
        # Latest BKT state_predictions per MKC up to this cutoff
        mkc_bkt = history.groupby("mkc")["state_predictions"].last()
        n_mast  = int((mkc_bkt >= T_MASTERED).sum())
        n_dev   = int(((mkc_bkt >= T_DEVELOPING) & (mkc_bkt < T_MASTERED)).sum())
        n_need  = int((mkc_bkt < T_DEVELOPING).sum())
        n_attempted = len(mkc_bkt)
        n_unatt = TOTAL_MKCS - n_attempted
        trends.append({
            "class_num":  int(cutoff),
            "mastered":   n_mast,
            "developing": n_dev,
            "needs":      n_need,
            "unattempted": n_unatt,
        })
    return trends


DEFAULT_PICKS = [("S004","High performer"), ("S019","Middle performer"), ("S001","Low performer")]


def build_html(picks=None):
    """Generate the full Student Summary dashboard as an HTML string.

    Builds the per-student data payload (KPI counts, unit tiles, strip-plot
    mastery distributions, weekly sparkline trends, class-comparison vectors)
    and substitutes it into ``HTML_TEMPLATE``. The output is a self-contained
    HTML document with inline CSS and JS, suitable for embedding directly via
    an iframe ``data:`` URL.

    Parameters
    ----------
    picks : list of (str, str) or None, optional
        ``(student_id, profile_label)`` pairs to render. When ``None``, the
        default three demo profiles are used. Pass a single-element list with
        an empty label (``[(sid, "")]``) for single-student rendering — the
        picker, demo banner, and topbar are auto-hidden in that case so the
        embedded view looks like a production dashboard.

    Returns
    -------
    str
        A complete HTML document.
    """
    picks = picks or DEFAULT_PICKS
    students = []
    for sid, profile in picks:
        rec  = scores[scores["student_id"]==sid].iloc[0]
        sob  = o[o["student_id"]==sid]
        raw_overall = sob["correct"].mean()

        # ── BKT mastery layer (used consistently across all widgets) ────────
        # Per-MKC current BKT mastery — latest state_predictions per MKC.
        bkt_mkc = sob.sort_values(["mkc", "kc_attempt"]).groupby("mkc")["state_predictions"].last().to_dict()
        bkt_mkc = {m: float(v) for m, v in bkt_mkc.items()}

        # Per-MKC raw correctness — kept ONLY as a secondary stat shown inside
        # each unit's drill-down modal (so the student can still see "what they
        # actually answered correctly" if they want, but it's not the main
        # categorization signal anywhere).
        mkc_raw = sob.groupby("mkc")["correct"].mean().to_dict()

        # Overall BKT — mean of latest state_predictions across attempted MKCs.
        # This is the primary "overall mastery" number shown in the subtitle.
        bkt_overall = (sum(bkt_mkc.values()) / len(bkt_mkc)) if bkt_mkc else 0.0

        # Flat per-category lists for the top-card drill-down modal — now
        # bucketed by BKT mastery (not raw correctness) so the categorization
        # matches what unit tiles use.
        top_categorized = {"mastered": [], "developing": [], "needs": [], "unattempted": []}
        for u in UNITS:
            for m in unit_mkcs[u]:
                base = {"id": m, "label": mkc2label.get(m, m), "unit": u}
                if m not in bkt_mkc:
                    top_categorized["unattempted"].append(base)
                else:
                    v = bkt_mkc[m]
                    base["mastery"] = round(v*100, 1)  # BKT mastery %
                    if   v >= T_MASTERED:   top_categorized["mastered"].append(base)
                    elif v >= T_DEVELOPING: top_categorized["developing"].append(base)
                    else:                   top_categorized["needs"].append(base)

        unit_trends_data = _compute_student_unit_trends(sid)

        tile_data = []
        unit_avgs_bkt = {}
        for u in UNITS:
            total_in_unit = unit_mkcs[u]
            attempted     = [m for m in total_in_unit if m in bkt_mkc]
            unattempted   = [m for m in total_in_unit if m not in bkt_mkc]
            mastered, developing, needs = [], [], []
            for m in attempted:
                v = bkt_mkc[m]
                entry = {"id": m, "label": mkc2label.get(m, m), "mastery": round(v*100, 1)}
                if   v >= T_MASTERED:   mastered.append(entry)
                elif v >= T_DEVELOPING: developing.append(entry)
                else:                   needs.append(entry)
            avg = sum(bkt_mkc[m] for m in attempted) / len(attempted) if attempted else None
            unit_avgs_bkt[u] = avg

            # Mastery distribution — show the full shape, not just an average
            # Each attempted KC's BKT mastery as %, sorted for stable plot order.
            mastery_values = sorted(round(bkt_mkc[m]*100, 1) for m in attempted)
            if mastery_values:
                _mid = len(mastery_values) // 2
                if len(mastery_values) % 2 == 1:
                    _median = mastery_values[_mid]
                else:
                    _median = round((mastery_values[_mid-1] + mastery_values[_mid]) / 2, 1)
            else:
                _median = None

            # Raw correctness avg for this unit — shown as a secondary stat
            # inside the unit drill-down modal (not on the tile itself).
            unit_raw_vals = [mkc_raw[m] for m in attempted if m in mkc_raw]
            raw_correctness_avg = round(sum(unit_raw_vals)/len(unit_raw_vals)*100, 1) if unit_raw_vals else None

            tile = {
                "unit": u,
                "avg_mastery": round(avg*100, 1) if avg is not None else None,
                "median_mastery": _median,
                "mastery_values": mastery_values,   # for the strip plot
                "raw_correctness_avg": raw_correctness_avg,  # secondary stat shown in modal only
                "total": len(total_in_unit),
                "n_mastered": len(mastered),
                "n_developing": len(developing),
                "n_needs": len(needs),
                "n_unattempted": len(unattempted),
                "mastered_list":    sorted(mastered,   key=lambda x: -x["mastery"]),  # high first
                "developing_list":  sorted(developing, key=lambda x:  x["mastery"]),  # priority first
                "needs_list":       sorted(needs,      key=lambda x:  x["mastery"]),  # priority first
                "unattempted_list": [{"id": m, "label": mkc2label.get(m, m)} for m in unattempted],
                "mastery_trend":    unit_trends_data.get(u, []),
                "class_avg":        round(bkt_class_per_unit[u]*100, 1) if bkt_class_per_unit.get(u) is not None else None,
            }
            tile["tier"] = tier_for_tile(tile)
            # Recommended first action when the student opens this unit
            if   tile["needs_list"]:      tile["start_with"] = tile["needs_list"][0];      tile["start_verb"] = "Start with"
            elif tile["developing_list"]: tile["start_with"] = tile["developing_list"][0]; tile["start_verb"] = "Keep practicing"
            else:                         tile["start_with"] = None;                       tile["start_verb"] = None
            tile_data.append(tile)

        attempted_units = {u: v for u, v in unit_avgs_bkt.items() if v is not None}
        strongest_unit = max(attempted_units, key=attempted_units.get) if attempted_units else "—"
        weakest_unit   = min(attempted_units, key=attempted_units.get) if attempted_units else "—"

        # Class comparison: BKT-vs-class diffs per unit
        diffs = [(u, round((unit_avgs_bkt[u]-bkt_class_per_unit[u])*100, 1))
                 for u in UNITS if unit_avgs_bkt.get(u) is not None and bkt_class_per_unit.get(u) is not None]
        n_ahead  = sum(1 for _, d in diffs if d > 0)
        n_behind = sum(1 for _, d in diffs if d < 0)
        ahead_sorted  = sorted([(u,d) for u,d in diffs if d > 0], key=lambda x: -x[1])[:2]
        behind_sorted = sorted([(u,d) for u,d in diffs if d < 0], key=lambda x:  x[1])[:2]

        tier_id, tier_label, tier_color = tier_overall(bkt_overall)

        # Top KPI card totals — BKT-based (sums of top_categorized lists)
        totals = {
            "mastered":    len(top_categorized["mastered"]),
            "developing":  len(top_categorized["developing"]),
            "needs":       len(top_categorized["needs"]),
            "unattempted": len(top_categorized["unattempted"]),
            "all":         TOTAL_MKCS,
        }

        students.append({
            "id": sid, "name": rec["display_name"], "profile": profile,
            "band": rec["performance_band"],
            "overall": round(bkt_overall*100, 1),                  # BKT-based overall mastery
            "overall_raw": round(raw_overall*100, 1),              # secondary: raw correctness avg
            "course_final": round(rec["course_final_dataset_percent"], 1),
            "tier_id": tier_id, "tier_label": tier_label, "tier_color": tier_color,
            "strongest_unit": strongest_unit,
            "strongest_unit_value": round(attempted_units[strongest_unit]*100, 1) if strongest_unit in attempted_units else None,
            "weakest_unit": weakest_unit,
            "weakest_unit_value": round(attempted_units[weakest_unit]*100, 1) if weakest_unit in attempted_units else None,
            "unit_tiles": tile_data,
            "totals": totals,
            "top_categorized": top_categorized,             # top-card modal lists (BKT mastery)
            "class_avg_totals": _get_class_avg_totals(),    # for KPI card comparison
            "at_risk": (tier_id == "at_risk"),              # hide class-comparison for at-risk students
            "weekly_trends": _compute_student_weekly_trends(sid),  # mini sparkline data (BKT mastery counts)
            "n_ahead": n_ahead, "n_behind": n_behind, "n_total": len(diffs),
            "ahead_units":  [{"unit": u, "diff": d} for u, d in ahead_sorted],
            "behind_units": [{"unit": u, "diff": d} for u, d in behind_sorted],
        })

    DATA_JSON = json.dumps(students, indent=2)
    html = HTML_TEMPLATE.replace("__DATA__", DATA_JSON)
    # Auto-hide picker / demo banner / topbar when a single student is embedded
    if len(students) == 1:
        html = html.replace('<div class="picker"', '<div class="picker" style="display:none"', 1)
        html = html.replace('<div class="demo-banner">', '<div class="demo-banner" style="display:none">', 1)
        html = html.replace('<div class="topbar">', '<div class="topbar" style="display:none">', 1)
    return html


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Student Summary — mockup</title>
<style>
  :root{
    --bg:#263744;             /* Jet Black — page background */
    --ink:#1F2933;            /* text on white cards */
    --mute:#5B7271;
    --on-dark:#F5F7FA;        /* text on dark bg */
    --on-dark-mute:#B0BFD0;
    --primary:#EE6055;        /* Vibrant Coral */
    --primary-d:#D14C42;
    --card:#FFFFFF;
    --line:#E5E9EE;
    --green:#60D394;          /* Emerald */
    --green-light:#AAF683;    /* Light Green */
    --amber:#FFD97D;          /* Jasmine */
    --red:#EE6055;            /* Vibrant Coral (same hue, used for "needs practice") */
    --red-light:#FF9B85;      /* Sweet Salmon */
    --gray:#8B9DBB;           /* Lavender Grey */
  }
  *{box-sizing:border-box}
  html{margin:0;padding:0;background:#1F303D}
  body{margin:0;padding:0;font-family:"Helvetica Neue",Arial,sans-serif;background:#fff;color:var(--ink);line-height:1.45}

  /* Jet Black header band — matches the parent Shiny navbar bg color so they
     visually merge into one continuous dark band (no perceived "frame"). */
  .hdr{background:#1F303D;color:var(--on-dark);padding:22px 0 20px;margin:0}
  .hdr-inner{max-width:1080px;margin:0 auto;padding:0 24px}
  .wrap{max-width:1080px;margin:0 auto;padding:20px 24px 64px}

  .topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:12px;color:var(--on-dark-mute)}
  /* Demo banner — explains the student picker is for demo only */
  .demo-banner{margin:12px 0 0;padding:7px 11px;font-size:11px;color:var(--on-dark);background:rgba(238,96,85,0.15);border-left:3px solid var(--primary);border-radius:0 4px 4px 0;line-height:1.4}
  .demo-banner .demo-tag{display:inline-block;background:var(--primary);color:#fff;font-weight:700;font-size:9px;letter-spacing:.5px;padding:1px 6px;border-radius:3px;margin-right:6px;vertical-align:middle}
  .picker{display:flex;gap:6px;margin:8px 0 18px}
  .picker button{border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.06);color:var(--on-dark);padding:7px 12px;border-radius:6px;cursor:pointer;font-size:13px}
  .picker button.active{background:var(--primary);color:#fff;border-color:var(--primary)}
  h1{font-family:Georgia,serif;font-size:30px;margin:4px 0 4px;font-weight:700;color:var(--on-dark)}
  .sub{color:var(--on-dark-mute);font-size:13px;margin-bottom:0}
  .badge{display:inline-block;font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;color:#1F2933;vertical-align:middle;margin-left:8px}
  h2{font-size:16px;font-weight:700;color:var(--ink);margin:22px 0 10px;display:flex;align-items:center;justify-content:space-between}
  h2 .hint{color:var(--mute);font-weight:400;font-size:12px}

  /* How-to note above the KPI strip — explains the categorisation */
  .kpi-howto{background:#F5F8FB;border:1px solid var(--line);border-left:3px solid var(--primary);border-radius:0 6px 6px 0;padding:10px 14px;font-size:12.5px;line-height:1.55;color:var(--ink);margin-bottom:14px}
  .kpi-howto b{font-weight:700}

  /* KPI strip — enhanced cards: number + context + visual + comparison + action */
  .kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
  .kcard{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 14px 12px 18px;position:relative;overflow:hidden;cursor:pointer;transition:transform .1s,box-shadow .1s;color:var(--ink);min-height:200px;display:flex;flex-direction:column}
  .kcard:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,0.22)}
  .kcard .accent{position:absolute;left:0;top:0;bottom:0;width:5px}
  .kcard h3{margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--mute);font-weight:700}
  .kcard .arrow{position:absolute;right:12px;top:14px;color:var(--mute);font-size:13px;opacity:.6}

  /* big number + inline denominator */
  .kcard .bignum-row{display:flex;align-items:baseline;gap:6px;margin:2px 0 1px}
  .kcard .bignum{font-family:Georgia,serif;font-size:32px;font-weight:700;line-height:1;color:var(--ink)}
  .kcard .denom{font-size:15px;color:var(--mute);font-weight:500;font-family:Georgia,serif}

  /* description line — "out of all skills this term" */
  .kcard .desc{font-size:11px;color:var(--mute);margin:0 0 8px;line-height:1.3}

  /* progress bar + percentage */
  .kcard .bar{height:6px;background:#F0F2F5;border-radius:3px;overflow:hidden;margin:2px 0 3px}
  .kcard .bar-fill{height:100%;border-radius:3px;transition:width .3s ease-out}
  .kcard .pct-label{font-size:11px;font-weight:600;margin:0 0 8px;line-height:1.2}

  /* comparison badge: vs class average */
  .kcard .compare{display:inline-flex;align-items:center;gap:4px;font-size:11px;padding:3px 8px;border-radius:4px;margin-top:0;line-height:1.3;align-self:flex-start;max-width:100%;flex-wrap:wrap}
  .kcard .compare.hidden{display:none}
  .kcard .compare.good{background:rgba(96,211,148,0.16);color:#256B47}
  .kcard .compare.bad {background:rgba(238,96,85,0.12);color:#B53C32}
  .kcard .compare.neutral{background:#F0F2F5;color:var(--mute)}
  .kcard .compare strong{font-weight:700}

  /* sparkline + "vs last check" trend indicator */
  .kcard .trend{margin-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
  .kcard .trend svg{height:20px;flex-shrink:0}
  .kcard .trend .delta{font-size:11px;font-weight:600;white-space:nowrap;line-height:1.2}
  .kcard .trend .delta.up{color:#2D8D5B}
  .kcard .trend .delta.down{color:#B53C32}
  .kcard .trend .delta.flat{color:var(--mute);font-weight:400}

  /* action tagline at bottom */
  .kcard .tagline{font-size:11px;color:var(--mute);font-style:italic;margin-top:auto;padding-top:6px;line-height:1.35}
  .kcard .tagline.action{color:var(--primary);font-weight:600;font-style:normal}

  /* Sort toggle */
  .sort{display:inline-flex;gap:0;border:1px solid var(--line);border-radius:6px;overflow:hidden;font-weight:400}
  .sort button{background:#fff;border:0;font-size:11px;padding:5px 10px;cursor:pointer;color:var(--ink)}
  .sort button.active{background:var(--primary);color:#fff}

  /* Unit tile grid */
  .grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:8px}
  .tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:11px 12px 12px 16px;cursor:pointer;position:relative;overflow:hidden;transition:transform .1s,box-shadow .1s;color:var(--ink)}
  .tile:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,0.22)}
  .tile .accent{position:absolute;left:0;top:0;bottom:0;width:5px}
  .tile.green .accent{background:var(--green)}
  .tile.yellow .accent{background:var(--amber)}
  .tile.red .accent{background:var(--red)}
  .tile.gray .accent{background:var(--gray)}
  .tile h4{font-size:13px;font-weight:700;margin:0 0 2px;color:var(--ink)}
  .tile .pct{font-family:Georgia,serif;font-size:20px;font-weight:700;line-height:1;margin:2px 0 7px;color:var(--ink)}
  .tile .pct.na{color:var(--mute);font-size:13px}

  /* Mastery-distribution strip plot — replaces the single big % number.
     Each KC = a colored dot at its BKT mastery position. */
  .mastery-dist{margin:4px 0 4px}
  .mastery-dist svg{display:block;width:100%}
  .mastery-dist.na{color:var(--mute);font-size:13px;font-family:Georgia,serif;font-weight:700;padding:4px 0}
  .dist-meta{font-size:10.5px;color:var(--mute);line-height:1.4;margin:0 0 7px}
  .dist-meta b{color:var(--ink);font-weight:700;font-family:Georgia,serif}
  .stack{display:flex;height:8px;border-radius:3px;overflow:hidden;background:#EEF1F5;margin-bottom:8px}
  .stack > div{height:100%}
  .seg-green{background:var(--green)} .seg-yellow{background:var(--amber)}
  .seg-red{background:var(--red)} .seg-gray{background:var(--gray)}
  .counts{font-size:11px;line-height:1.5;color:var(--ink)}
  .counts .row{display:flex;align-items:center;gap:5px}
  .tile-trend{display:flex;align-items:center;gap:6px;margin-top:8px;padding-top:6px;border-top:1px dashed var(--line)}
  .tile-trend-delta{font-size:10px;font-weight:600;line-height:1.2;white-space:nowrap}
  .tile-trend-delta.up{color:#2D8D5B}
  .tile-trend-delta.down{color:#B53C32}
  .tile-trend-delta.flat{color:var(--mute);font-weight:400}
  .dot{display:inline-block;width:8px;height:8px;border-radius:2px;flex-shrink:0}
  .legend{font-size:11px;color:var(--mute);margin:8px 0 18px;display:flex;gap:14px;flex-wrap:wrap}
  .legend .dot{margin-right:5px;vertical-align:middle}

  /* Class comparison panel */
  .panels{display:grid;grid-template-columns:1fr;gap:14px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px;color:var(--ink)}
  .panel h3{margin:0 0 8px;font-size:13px;color:var(--primary);font-weight:700}
  .panel ul{margin:4px 0 0;padding-left:18px;font-size:13px;color:var(--ink)}
  .panel li{margin:3px 0}
  .panel .footnote{color:var(--mute);font-size:11px;margin-top:8px}
  /* Collapsible class-comparison: gentler intro for at-risk students */
  details > summary{cursor:pointer;list-style:none;padding:2px 0;display:flex;align-items:center;gap:6px;user-select:none}
  details > summary::-webkit-details-marker{display:none}
  details > summary::before{content:"▸";font-size:11px;color:var(--mute);transition:transform .15s}
  details[open] > summary::before{transform:rotate(90deg)}
  details > summary h3{color:var(--teal-d,#115E59);font-size:13px;font-weight:700}

  /* CTA + footer */
  .cta{margin-top:22px;display:flex;justify-content:space-between;align-items:center;background:var(--primary);color:#fff;border-radius:8px;padding:14px 18px;gap:14px}
  .cta button{background:#fff;color:var(--primary-d);border:0;border-radius:6px;padding:8px 14px;font-weight:700;font-size:13px;cursor:pointer;flex-shrink:0}
  .note{margin-top:24px;font-size:11px;color:var(--mute);border-top:1px dashed var(--line);padding-top:12px}

  /* Modal */
  .overlay{display:none;position:fixed;inset:0;background:rgba(15,27,38,0.65);z-index:100;align-items:center;justify-content:center;padding:24px}
  .overlay.show{display:flex}
  .modal{background:#fff;color:var(--ink);border-radius:10px;padding:24px 28px;max-width:640px;width:100%;max-height:84vh;overflow-y:auto;box-shadow:0 20px 50px rgba(0,0,0,0.40)}
  .modal-header{display:flex;justify-content:space-between;align-items:start;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:14px}
  .modal-header h2{font-family:Georgia,serif;font-size:24px;margin:0;color:var(--ink);display:block}
  .modal-header .meta{color:var(--mute);font-size:12px;margin-top:4px}
  .modal-header .close{cursor:pointer;color:var(--mute);font-size:26px;line-height:1;background:none;border:0;padding:0}
  /* ── Unit-drill modal: trend section + at-a-glance ──────────────────────── */
  .unit-modal-trend{margin:14px 0 10px;padding:12px 14px;background:#F7F9FB;border-radius:6px;border:1px solid var(--line)}
  .unit-modal-trend .trend-row{display:flex;align-items:center;gap:14px;margin-top:6px}
  .unit-modal-trend .trend-meta{display:flex;flex-direction:column;gap:4px}
  .unit-modal-trend .trend-delta-big{font-size:15px;font-weight:700}
  .unit-modal-trend .trend-delta-big.up{color:#2D8D5B}
  .unit-modal-trend .trend-delta-big.down{color:#B53C32}
  .unit-modal-trend .trend-delta-big.flat{color:var(--mute);font-weight:500}
  .unit-modal-trend .trend-interp{font-size:12px;color:var(--mute);font-style:italic}
  .trend-label{font-size:11px;color:var(--mute);font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}

  .unit-glance-section{margin:12px 0 14px;padding:12px 14px;background:#F7F9FB;border-radius:6px;border:1px solid var(--line)}
  .ag-stat{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:5px 0;border-bottom:1px dashed var(--line);font-size:13px}
  .ag-stat:last-child{border-bottom:0}
  .ag-label{color:var(--mute);font-weight:500;flex-shrink:0;font-size:12px}
  .ag-val{font-weight:600;text-align:right}
  .ag-val.up{color:#2D8D5B}
  .ag-val.down{color:#B53C32}
  .ag-val.flat{color:var(--mute);font-weight:500}
  .ag-context{font-weight:400;color:var(--mute);font-size:11px;margin-left:4px}

  /* ── Unit-drill modal (clicked from Your units grid): original style ──── */
  .msec{margin-top:14px}
  .msec h3{font-size:12px;font-weight:700;margin:0 0 5px;text-transform:uppercase;letter-spacing:.5px}
  .msec ul{list-style:none;padding:0;margin:0}
  .msec li{font-size:13px;padding:7px 10px;border-radius:4px;margin-bottom:3px;display:flex;justify-content:space-between;gap:14px}
  .msec.mastered  li{background:rgba(96,211,148,0.14)}
  .msec.developing li{background:rgba(255,217,125,0.20)}
  .msec.needs     li{background:rgba(238,96,85,0.12)}
  .msec.unattempted li{background:rgba(139,157,187,0.14);color:var(--mute)}
  .msec li .pct{font-weight:600;font-variant-numeric:tabular-nums}

  /* ── Modal analytics: sparkline + stats + flat skill list ───────────────── */
  .modal-spark-row{display:flex;align-items:center;gap:14px;margin:14px 0 4px;padding:10px 12px;background:rgba(0,0,0,0.025);border-radius:6px}
  .modal-spark{flex-shrink:0}
  .modal-spark svg{height:36px;width:auto}
  .modal-spark-meta{display:flex;flex-direction:column;gap:3px;line-height:1.2}
  .modal-spark-meta .delta{font-size:13px;font-weight:600}
  .modal-spark-meta .delta.up{color:#2D8D5B}
  .modal-spark-meta .delta.down{color:#B53C32}
  .modal-spark-meta .delta.flat{color:var(--mute);font-weight:400}
  .modal-spark-label{font-size:11px;color:var(--mute);text-transform:uppercase;letter-spacing:.5px}

  .modal-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0 14px}
  .modal-stat{background:#F7F9FB;border:1px solid var(--line);border-radius:6px;padding:10px 12px;display:flex;flex-direction:column;gap:2px}
  .modal-stat-label{font-size:10px;color:var(--mute);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
  .modal-stat-value{font-size:14px;font-weight:700;color:var(--ink)}

  .modal-list-head{font-size:11px;color:var(--mute);text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin:14px 0 6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
  .modal-skill-list{list-style:none;padding:0;margin:0}
  .mskill{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:4px;margin-bottom:3px;font-size:13px}
  .mskill.mastered{background:rgba(96,211,148,0.10)}
  .mskill.developing{background:rgba(255,217,125,0.14)}
  .mskill.needs{background:rgba(238,96,85,0.10)}
  .mskill.unattempted{background:rgba(139,157,187,0.10);color:var(--mute)}
  .mskill .skill-row-main{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
  .mskill .unit-tag{font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;flex-shrink:0}
  .mskill .skill-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
  .mskill .skill-row-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
  .mskill .skill-bar{display:inline-block;width:60px;height:5px;background:#E5E9EE;border-radius:3px;overflow:hidden}
  .mskill .skill-bar > span{display:block;height:100%;border-radius:3px}
  .mskill .pct{font-weight:600;font-variant-numeric:tabular-nums;min-width:42px;text-align:right}
  .empty{padding:24px 0;text-align:center;color:var(--mute);font-size:13px;font-style:italic}

  .action{margin-top:18px;background:rgba(238,96,85,0.10);border-left:4px solid var(--primary);padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:14px;border-radius:0 6px 6px 0;font-size:13px}
  .action .lbl{color:var(--mute);font-size:11px;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:2px}
  .action button{background:var(--primary);color:#fff;border:0;border-radius:6px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer;flex-shrink:0}
</style>
</head>
<body>

<header class="hdr">
  <div class="hdr-inner">
    <div class="topbar">
      <span>AP Statistics · Student Portal</span>
      <span>Logged in as: <span id="who">—</span></span>
    </div>
    <div class="demo-banner">
      <span class="demo-tag">DEMO</span>
      Switch between 3 student profiles to see how the page adapts to different performance levels. In production, only the logged-in student's data shows.
    </div>
    <div class="picker" id="picker"></div>
    <h1 id="title">—</h1>
    <div class="sub" id="subtitle">—</div>
  </div>
</header>

<div class="wrap">
  <div class="kpi-howto">
    💡 <b>How these cards work:</b> Each skill is bucketed by your <b>BKT mastery</b> — the model's current estimate of how well you've learned each skill, updated with every attempt —
    <b style="color:#2D8D5B">Mastered</b> (≥ 65%) ·
    <b style="color:#B8860B">Progressing</b> (35–64%) ·
    <b style="color:#B53C32">Needs Practice</b> (&lt; 35%) ·
    <b style="color:#5B7271">Unattempted</b> (not tried yet).
    Click any card to see the skills behind the number.
  </div>
  <div class="kpi">
    <!-- ───── Mastered ───── -->
    <div class="kcard" onclick="openCategory('mastered')">
      <div class="accent" style="background:var(--green)"></div><div class="arrow">›</div>
      <h3>Mastered</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_mastered_num">—</span>
        <span class="denom"  id="kc_mastered_denom">/ —</span>
      </div>
      <div class="desc">Skills with BKT mastery ≥ 65%</div>
      <div class="bar"><div class="bar-fill" id="kc_mastered_bar" style="background:var(--green);width:0%"></div></div>
      <div class="pct-label" id="kc_mastered_pct" style="color:#2D8D5B">—</div>
      <div class="compare" id="kc_mastered_cmp"></div>
      <div class="trend"    id="kc_mastered_trend"></div>
      <div class="tagline"  id="kc_mastered_tag">—</div>
    </div>

    <!-- ───── Progressing ───── -->
    <div class="kcard" onclick="openCategory('developing')">
      <div class="accent" style="background:var(--amber)"></div><div class="arrow">›</div>
      <h3>Progressing</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_developing_num">—</span>
        <span class="denom"  id="kc_developing_denom">/ —</span>
      </div>
      <div class="desc">BKT 35–64% — your active work zone</div>
      <div class="bar"><div class="bar-fill" id="kc_developing_bar" style="background:var(--amber);width:0%"></div></div>
      <div class="pct-label" id="kc_developing_pct" style="color:#B8860B">—</div>
      <div class="compare" id="kc_developing_cmp"></div>
      <div class="trend"   id="kc_developing_trend"></div>
      <div class="tagline" id="kc_developing_tag">—</div>
    </div>

    <!-- ───── Needs Practice ───── -->
    <div class="kcard" onclick="openCategory('needs')">
      <div class="accent" style="background:var(--red)"></div><div class="arrow">›</div>
      <h3>Needs Practice</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_needs_num">—</span>
        <span class="denom"  id="kc_needs_denom">/ —</span>
      </div>
      <div class="desc">BKT &lt; 35% — focus area for tonight</div>
      <div class="bar"><div class="bar-fill" id="kc_needs_bar" style="background:var(--red);width:0%"></div></div>
      <div class="pct-label" id="kc_needs_pct" style="color:#B53C32">—</div>
      <div class="compare" id="kc_needs_cmp"></div>
      <div class="trend"   id="kc_needs_trend"></div>
      <div class="tagline" id="kc_needs_tag">—</div>
    </div>

    <!-- ───── Unattempted ───── -->
    <div class="kcard" onclick="openCategory('unattempted')">
      <div class="accent" style="background:var(--gray)"></div><div class="arrow">›</div>
      <h3>Unattempted</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_unattempted_num">—</span>
        <span class="denom"  id="kc_unattempted_denom">/ —</span>
      </div>
      <div class="desc">Skills you haven't tried yet</div>
      <div class="bar"><div class="bar-fill" id="kc_unattempted_bar" style="background:var(--gray);width:0%"></div></div>
      <div class="pct-label" id="kc_unattempted_pct" style="color:#5B7271">—</div>
      <div class="compare" id="kc_unattempted_cmp"></div>
      <div class="trend"   id="kc_unattempted_trend"></div>
      <div class="tagline" id="kc_unattempted_tag">—</div>
    </div>
  </div>

  <h2>
    <span>Your units <span class="hint">— click a tile to see the skills inside</span></span>
    <span class="sort">
      <button data-sort="order" class="active" onclick="setSort('order')">Course order</button>
      <button data-sort="risk"                onclick="setSort('risk')">Needs attention first</button>
    </span>
  </h2>
  <div class="grid" id="grid"></div>
  <div class="legend">
    <span><span class="dot" style="background:var(--green)"></span>Mastered (≥65%)</span>
    <span><span class="dot" style="background:var(--amber)"></span>Progressing (35–64%)</span>
    <span><span class="dot" style="background:var(--red)"></span>Needs Practice (&lt;35%)</span>
    <span><span class="dot" style="background:var(--gray)"></span>Unattempted</span>
  </div>

  <div class="panels">
    <div class="panel">
      <details id="cmp_details">
        <summary><h3 style="display:inline;margin:0">See how you compare to the class</h3></summary>
        <div id="cmp_summary" style="font-size:13px;margin:10px 0 8px"></div>
        <div style="font-size:12px;color:var(--mute);margin-top:6px"><b style="color:var(--green)">Where you're strongest relative to the class</b></div>
        <ul id="cmp_ahead" style="margin:4px 0 8px;padding-left:18px"></ul>
        <div style="font-size:12px;color:var(--mute)"><b style="color:var(--red)">Where the class is ahead of you</b></div>
        <ul id="cmp_behind" style="margin:4px 0 0;padding-left:18px"></ul>
      </details>
      <div class="footnote">Class average computed from all 25 students in the cohort.</div>
    </div>
  </div>

  <div class="cta">
    <div id="cta_text">—</div>
    <button onclick="window.parent.postMessage('go-practice-plan', '*')">View my practice plan →</button>
  </div>

  <div class="note">
    All counts and tile colors use <b>BKT-predicted mastery</b> — the model's current estimate of how well you've learned each skill, updated with every attempt.
    Raw correctness (your actual answer-by-answer score) is shown as a small secondary stat inside each unit's drill-down.
    Tile color reflects the unit's <b>median</b> BKT mastery: green ≥ 65%, yellow 35–64%, red &lt; 35%. Class average computed from all 25 students.
  </div>
</div>

<div class="overlay" id="modal" onclick="if(event.target===this) this.classList.remove('show')">
  <div class="modal" id="modal-content"></div>
</div>

<script>
const STUDENTS = __DATA__;
const COLORS = {green:"#60D394", amber:"#FFD97D", red:"#EE6055", gray:"#8B9DBB", primary:"#EE6055"};
const TIER_RANK = {red:0, yellow:1, green:2, gray:3};
let currentStudent = 0;
let currentSort = "order";

// ─── Sparkline + trend delta ─────────────────────────────────────────────────
function sparklineSVG(values, color){
  if(!values || values.length < 2) return "";
  const max = Math.max(...values, 1);
  const barWidth = 8, barGap = 3, height = 20;
  const totalWidth = values.length * (barWidth + barGap) - barGap;
  let bars = "";
  for(let i = 0; i < values.length; i++){
    const h = Math.max(2, (values[i] / max) * height);  // min h=2 so empty bars still show
    const y = height - h;
    const isLast = (i === values.length - 1);
    const fill = isLast ? color : "#D0D6DD";
    bars += `<rect x="${i*(barWidth+barGap)}" y="${y}" width="${barWidth}" height="${h}" fill="${fill}" rx="1"/>`;
  }
  return `<svg viewBox="0 0 ${totalWidth} ${height}" preserveAspectRatio="xMinYMid">${bars}</svg>`;
}

function trendDelta(trends, cat, biggerIsBetter){
  if(!trends || trends.length < 2) return "";
  const last = trends[trends.length - 1][cat];
  const prev = trends[trends.length - 2][cat];
  const delta = last - prev;
  if(delta === 0) return `<span class="delta flat">→ no change</span>`;
  const isUp = delta > 0;
  // biggerIsBetter true → up is good; false → up is bad; null → neutral
  let kind = "flat";
  if(biggerIsBetter === true)  kind = isUp ? "up" : "down";
  if(biggerIsBetter === false) kind = isUp ? "down" : "up";
  const arrow = isUp ? "↑" : "↓";
  const sign  = isUp ? "+" : "";
  return `<span class="delta ${kind}">${arrow} ${sign}${delta} since last check</span>`;
}

function renderTrend(cat, trends, color, biggerIsBetter){
  const el = document.getElementById("kc_" + cat + "_trend");
  if(!el) return;
  if(!trends || trends.length < 2){ el.innerHTML = ""; return; }
  const values = trends.map(t => t[cat]);
  el.innerHTML = sparklineSVG(values, color) + trendDelta(trends, cat, biggerIsBetter);
}

// ─── KPI card population — every number is paired with context ──────────────
function taglineFor(cat, value){
  if(cat === "mastered"){
    if(value === 0) return "Your journey starts here.";
    if(value < 5)   return "Building foundations.";
    if(value < 15)  return "Steady progress — keep going.";
    return "Excellent — keep the momentum.";
  }
  if(cat === "developing"){
    if(value === 0) return "Nothing in active practice.";
    return "Your active work zone.";
  }
  if(cat === "needs"){
    if(value === 0) return "No critical gaps right now.";
    return "→ Start with these tonight.";
  }
  if(cat === "unattempted"){
    if(value === 0) return "All skills attempted — great!";
    return "Worth a first attempt soon.";
  }
  return "";
}

function setKpiCard(cat, value, denom, classAvg, atRisk, biggerIsBetter){
  // bignum + denominator
  document.getElementById("kc_"+cat+"_num").textContent   = value;
  document.getElementById("kc_"+cat+"_denom").textContent = "/ " + denom;

  // progress bar + percentage
  const pct = denom > 0 ? Math.round(value/denom*100) : 0;
  document.getElementById("kc_"+cat+"_bar").style.width = pct + "%";
  document.getElementById("kc_"+cat+"_pct").textContent = pct + "% of all skills";

  // comparison badge — removed (was: "matches class average (X)")
  // Now we rely on the sparkline + "since last check" delta for context.
  const cmpEl = document.getElementById("kc_"+cat+"_cmp");
  if(cmpEl){ cmpEl.classList.add("hidden"); cmpEl.innerHTML = ""; }

  // tagline
  const tagEl = document.getElementById("kc_"+cat+"_tag");
  tagEl.textContent = taglineFor(cat, value);
  tagEl.className = "tagline" + (cat === "needs" && value > 0 ? " action" : "");
}

// Tile trend: tiny sparkline + "since first class" pp delta
function tileTrendHTML(trend, color){
  const vals = (trend || []).filter(v => v !== null);
  if(vals.length < 2) return "";
  // Mini line sparkline (smaller than bar version, fits in tile)
  const w = 56, h = 16;
  const max = Math.max(...vals, 1);
  const min = Math.min(...vals, 0);
  const range = (max - min) || 1;
  const step = w / (vals.length - 1);
  const pts = vals.map((v, i) => `${(i*step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`).join(" ");
  // Endpoint dot
  const lastX = (vals.length - 1) * step;
  const lastY = h - ((vals[vals.length-1] - min) / range) * h;
  // pp delta = current - first
  const delta = vals[vals.length - 1] - vals[0];
  const sign = delta > 0 ? "+" : "";
  const arrow = delta > 0 ? "↑" : (delta < 0 ? "↓" : "→");
  const deltaCls = delta > 0.5 ? "up" : (delta < -0.5 ? "down" : "flat");
  return `
    <div class="tile-trend">
      <svg viewBox="0 0 ${w} ${h}" style="height:14px;width:${w}px;flex-shrink:0">
        <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" />
        <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2" fill="${color}" />
      </svg>
      <span class="tile-trend-delta ${deltaCls}">${arrow} ${sign}${delta.toFixed(1)}pp this term</span>
    </div>`;
}

// Mastery-distribution strip plot — show the full shape, not just a mean
// Each attempted KC becomes a colored dot at its BKT mastery position.
function stripPlotSVG(values){
  if(!values || values.length === 0) return "";
  const w = 160, h = 36;
  const padL = 4, padR = 4, padTop = 6, padBot = 10;
  const plotW = w - padL - padR;
  const yMid = padTop + (h - padTop - padBot) / 2;
  // Threshold positions on the 0–100% axis
  const x35 = padL + plotW * 0.35;
  const x65 = padL + plotW * 0.65;
  // Background tinted zones — red < 35%, yellow 35–65%, green ≥ 65%
  let svg = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">`;
  svg += `<rect x="${padL}" y="${padTop}" width="${(x35-padL).toFixed(1)}" height="${(h-padTop-padBot).toFixed(1)}" fill="${COLORS.red}"   opacity="0.07"/>`;
  svg += `<rect x="${x35.toFixed(1)}" y="${padTop}" width="${(x65-x35).toFixed(1)}" height="${(h-padTop-padBot).toFixed(1)}" fill="${COLORS.amber}" opacity="0.10"/>`;
  svg += `<rect x="${x65.toFixed(1)}" y="${padTop}" width="${(padL+plotW-x65).toFixed(1)}" height="${(h-padTop-padBot).toFixed(1)}" fill="${COLORS.green}" opacity="0.10"/>`;
  // Subtle threshold dividers
  svg += `<line x1="${x35.toFixed(1)}" y1="${padTop}" x2="${x35.toFixed(1)}" y2="${h-padBot}" stroke="#D0D6DD" stroke-width="0.4"/>`;
  svg += `<line x1="${x65.toFixed(1)}" y1="${padTop}" x2="${x65.toFixed(1)}" y2="${h-padBot}" stroke="#D0D6DD" stroke-width="0.4"/>`;
  // Dots — slight vertical jitter so clustered values are visible
  values.forEach((v, i) => {
    const x = padL + (v / 100) * plotW;
    const yOff = ((i % 3) - 1) * 3.2;  // -3.2, 0, +3.2
    const y = yMid + yOff;
    const color = v >= 65 ? COLORS.green : (v >= 35 ? COLORS.amber : COLORS.red);
    svg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${color}" stroke="#ffffff" stroke-width="0.9"/>`;
  });
  // Axis ticks at 0 / 50 / 100 %
  svg += `<text x="${padL}"             y="${h-2}" font-size="7" fill="#888">0%</text>`;
  svg += `<text x="${(padL+plotW/2).toFixed(1)}" y="${h-2}" font-size="7" fill="#888" text-anchor="middle">50%</text>`;
  svg += `<text x="${(w-padR).toFixed(1)}" y="${h-2}" font-size="7" fill="#888" text-anchor="end">100%</text>`;
  svg += `</svg>`;
  return svg;
}

function tileHTML(t, origIdx){
  // Pick sparkline color by tier
  const trendColor = ({green:COLORS.green, yellow:COLORS.amber, red:COLORS.red, gray:COLORS.gray})[t.tier] || COLORS.gray;
  // Distribution display: strip plot of attempted KCs' BKT mastery (replaces big avg %)
  // The stacked progress bar was redundant — strip plot conveys distribution; counts below show exact buckets.
  const attemptedN = (t.mastery_values || []).length;
  const distBlock = attemptedN > 0
    ? `<div class="mastery-dist">${stripPlotSVG(t.mastery_values)}</div>
       <div class="dist-meta">median <b>${t.median_mastery}%</b> · ${attemptedN} attempted</div>`
    : `<div class="mastery-dist na">— not attempted yet</div>`;
  return `
    <div class="tile ${t.tier}" onclick="openUnit(${origIdx})">
      <div class="accent"></div>
      <h4>${t.unit}</h4>
      ${distBlock}
      <div class="counts">
        <div class="row"><span class="dot" style="background:${COLORS.green}"></span>${t.n_mastered} mastered</div>
        <div class="row"><span class="dot" style="background:${COLORS.amber}"></span>${t.n_developing} developing</div>
        <div class="row"><span class="dot" style="background:${COLORS.red}"></span>${t.n_needs} needs practice</div>
        <div class="row"><span class="dot" style="background:${COLORS.gray}"></span>${t.n_unattempted} unattempted</div>
      </div>
      ${tileTrendHTML(t.mastery_trend, trendColor)}
    </div>`;
}

function modalSection(title, items, cls, color, withPct){
  if(!items.length) return "";
  return `
    <div class="msec ${cls}">
      <h3 style="color:${color}">${title} (${items.length})</h3>
      <ul>${items.map(m => `<li><span>${m.label}</span><span class="pct">${withPct ? (m.mastery+'%') : '—'}</span></li>`).join("")}</ul>
    </div>`;
}

const CATEGORY_META = {
  mastered:    {title:"Mastered",       color: COLORS.green, sub:"BKT mastery ≥ 65%",                     listKey:"mastered_list",    withPct:true,  biggerIsBetter:true,  emptyMsg:"No mastered skills yet."},
  developing:  {title:"Progressing",    color: COLORS.amber, sub:"BKT 35–64% — keep practicing",          listKey:"developing_list",  withPct:true,  biggerIsBetter:null,  emptyMsg:"No skills in this band."},
  needs:       {title:"Needs Practice", color: COLORS.red,   sub:"BKT < 35% — focus here",                listKey:"needs_list",       withPct:true,  biggerIsBetter:false, emptyMsg:"No skills need practice — well done!"},
  unattempted: {title:"Unattempted",    color: COLORS.gray,  sub:"No attempt yet",                        listKey:"unattempted_list", withPct:false, biggerIsBetter:false, emptyMsg:"You've attempted every skill."},
};

function openCategory(cat){
  const s = STUDENTS[currentStudent];
  const cfg = CATEGORY_META[cat];

  // Top KPI cards categorize on BKT mastery (synced with unit tiles).
  // Use the flat top_categorized lists prepared on the Python side.
  const listKey = {
    mastered: "mastered", developing: "developing",
    needs: "needs", unattempted: "unattempted"
  }[cat];
  const allItems = (s.top_categorized && s.top_categorized[listKey])
    ? s.top_categorized[listKey].map(x => ({...x}))   // shallow copy
    : [];
  const total = allItems.length;
  const units = new Set(allItems.map(x => x.unit));

  // Sort: mastered/developing high-first; needs low-first (worst first → focus area)
  if(cfg.withPct){
    if(cat === "needs") allItems.sort((a,b) => a.mastery - b.mastery);
    else                allItems.sort((a,b) => b.mastery - a.mastery);
  } else {
    allItems.sort((a,b) => a.label.localeCompare(b.label));
  }

  // Analytics: avg mastery + most-concentrated unit
  let avgMastery = null;
  if(cfg.withPct && total > 0){
    avgMastery = allItems.reduce((sum, x) => sum + x.mastery, 0) / total;
  }
  const unitCounts = {};
  allItems.forEach(x => { unitCounts[x.unit] = (unitCounts[x.unit] || 0) + 1; });
  let mostUnit = "", mostUnitN = 0;
  Object.keys(unitCounts).forEach(u => {
    if(unitCounts[u] > mostUnitN){ mostUnit = u; mostUnitN = unitCounts[u]; }
  });

  // Sparkline for THIS category's count over time + delta
  const trends = s.weekly_trends || [];
  let sparkHTML = "";
  if(trends.length >= 2){
    const values = trends.map(t => t[cat]);
    sparkHTML = `
      <div class="modal-spark-row">
        <div class="modal-spark">${sparklineSVG(values, cfg.color)}</div>
        <div class="modal-spark-meta">
          ${trendDelta(trends, cat, cfg.biggerIsBetter)}
          <div class="modal-spark-label">Count over the term</div>
        </div>
      </div>`;
  }

  // Header analytics section
  let statsHTML = "";
  if(total > 0){
    const statCards = [];
    if(avgMastery !== null){
      statCards.push(`<div class="modal-stat"><span class="modal-stat-label">Average BKT mastery</span><span class="modal-stat-value">${avgMastery.toFixed(0)}%</span></div>`);
    }
    if(mostUnitN > 0){
      statCards.push(`<div class="modal-stat"><span class="modal-stat-label">Most concentrated in</span><span class="modal-stat-value">${mostUnit} (${mostUnitN})</span></div>`);
    }
    statCards.push(`<div class="modal-stat"><span class="modal-stat-label">Spread across</span><span class="modal-stat-value">${units.size} unit${units.size===1?"":"s"}</span></div>`);
    statsHTML = `<div class="modal-stats">${statCards.join("")}</div>`;
  }

  // Skill list — flat with unit tag and mini progress bar
  const body = total === 0
    ? `<div class="empty">${cfg.emptyMsg}</div>`
    : `${sparkHTML}${statsHTML}
       <div class="modal-list-head">All ${total} skill${total===1?"":"s"} · ${cat === "needs" ? "lowest mastery first" : (cfg.withPct ? "highest mastery first" : "A–Z")}</div>
       <ul class="modal-skill-list">${allItems.map(m => {
         const pct = cfg.withPct ? m.mastery : 0;
         const barW = Math.max(0, Math.min(100, pct));
         return `<li class="mskill ${cat}">
           <span class="skill-row-main">
             <span class="unit-tag" style="background:${cfg.color}22;color:${cfg.color};border:1px solid ${cfg.color}55">${m.unit}</span>
             <span class="skill-name">${m.label}</span>
           </span>
           <span class="skill-row-right">
             ${cfg.withPct ? `<span class="skill-bar"><span style="width:${barW}%;background:${cfg.color}"></span></span><span class="pct">${m.mastery}%</span>` : `<span class="pct" style="color:var(--mute)">not yet</span>`}
           </span>
         </li>`;
       }).join("")}</ul>`;

  document.getElementById("modal-content").innerHTML = `
    <div class="modal-header">
      <div>
        <h2><span style="color:${cfg.color}">●</span> ${cfg.title} — ${total} skill${total===1?"":"s"}</h2>
        <div class="meta">${cfg.sub} · across ${units.size} unit${units.size===1?"":"s"}</div>
      </div>
      <button class="close" onclick="document.getElementById('modal').classList.remove('show')">×</button>
    </div>
    ${body}`;
  document.getElementById("modal").classList.add("show");
}

function openUnit(i){
  const u = STUDENTS[currentStudent].unit_tiles[i];
  const tierColor = ({green:COLORS.green, yellow:COLORS.amber, red:COLORS.red, gray:COLORS.gray})[u.tier] || COLORS.gray;

  // ── Trend over the term ─────────────────────────────────────────────────
  const trend = (u.mastery_trend || []).filter(v => v !== null);
  let trendHTML = "";
  if(trend.length >= 2){
    // Improved chart: area fill + dots at every snapshot + start/end value labels
    const w = 280, h = 90;
    const padLeft = 28, padRight = 36, padTop = 14, padBot = 22;
    const chartW = w - padLeft - padRight;
    const chartH = h - padTop - padBot;
    const max = Math.max(...trend);
    const min = Math.min(...trend);
    const range = (max - min) || 1;
    const step = chartW / (trend.length - 1);

    const pts = trend.map((v, idx) => ({
      x: padLeft + idx*step,
      y: padTop + chartH - ((v - min) / range) * chartH,
      v
    }));
    const polyStr = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
    const areaPath = `M ${pts[0].x.toFixed(1)},${(padTop+chartH).toFixed(1)} L ` +
                     pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" L ") +
                     ` L ${pts[pts.length-1].x.toFixed(1)},${(padTop+chartH).toFixed(1)} Z`;

    const dots = pts.map((p, idx) => {
      const isLast = idx === pts.length - 1;
      return isLast
        ? `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5" fill="${tierColor}" stroke="white" stroke-width="2.5"/>`
        : `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.8" fill="${tierColor}" opacity="0.55"/>`;
    }).join("");

    const firstP = pts[0], lastP = pts[pts.length-1];
    // Start label (left of first dot) — small gray
    const startLabel = `<text x="${(firstP.x - 4).toFixed(1)}" y="${(firstP.y + 4).toFixed(1)}" font-size="11" fill="#888" text-anchor="end" font-weight="600">${firstP.v.toFixed(1)}%</text>`;
    // End label (right of last dot) — bold tier color
    const endLabel   = `<text x="${(lastP.x + 8).toFixed(1)}" y="${(lastP.y + 4).toFixed(1)}" font-size="13" fill="${tierColor}" font-weight="700">${lastP.v.toFixed(1)}%</text>`;
    // X-axis: simple "this term" caption at bottom
    const xAxisStart = `<text x="${firstP.x.toFixed(1)}" y="${(h - 6).toFixed(1)}" font-size="10" fill="#aaa" text-anchor="middle">start</text>`;
    const xAxisEnd   = `<text x="${lastP.x.toFixed(1)}" y="${(h - 6).toFixed(1)}" font-size="10" fill="#aaa" text-anchor="middle">now</text>`;

    const delta = trend[trend.length-1] - trend[0];
    const arrow = delta > 0.5 ? "↑" : (delta < -0.5 ? "↓" : "→");
    const sign  = delta > 0 ? "+" : "";
    const cls   = delta > 0.5 ? "up" : (delta < -0.5 ? "down" : "flat");
    const interp = delta > 0.5  ? "trending up — keep the momentum going"
                 : delta < -0.5 ? "slipping — worth refreshing this unit"
                 : "holding steady";

    trendHTML = `
      <div class="unit-modal-trend">
        <div class="trend-label">📈 BKT mastery over the term</div>
        <div class="trend-row">
          <svg viewBox="0 0 ${w} ${h}" style="height:90px;width:${w}px;flex-shrink:0">
            <path d="${areaPath}" fill="${tierColor}" opacity="0.18"/>
            <polyline points="${polyStr}" fill="none" stroke="${tierColor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
            ${dots}
            ${startLabel}${endLabel}
            ${xAxisStart}${xAxisEnd}
          </svg>
          <div class="trend-meta">
            <div class="trend-delta-big ${cls}">${arrow} ${sign}${delta.toFixed(1)}pp this term</div>
            <div class="trend-interp">${interp}</div>
          </div>
        </div>
      </div>`;
  }

  // ── At a glance: strongest / weakest / class delta ──────────────────────
  const allRanked = [...u.mastered_list, ...u.developing_list, ...u.needs_list];
  const strongest = allRanked.length > 0 ? allRanked.reduce((a,b) => a.mastery >= b.mastery ? a : b) : null;
  const weakest   = allRanked.length > 0 ? allRanked.reduce((a,b) => a.mastery <= b.mastery ? a : b) : null;
  let classCompareHTML = "";
  if(u.avg_mastery != null && u.class_avg != null){
    const d = (u.avg_mastery - u.class_avg).toFixed(1);
    const cls = d > 0.5 ? "up" : (d < -0.5 ? "down" : "flat");
    const sign = d > 0 ? "+" : "";
    const arrow = d > 0.5 ? "↑" : (d < -0.5 ? "↓" : "→");
    classCompareHTML = `<div class="ag-stat"><div class="ag-label">vs Class avg</div><div class="ag-val ${cls}">${arrow} ${sign}${d}pp <span class="ag-context">(class: ${u.class_avg}%)</span></div></div>`;
  }
  let glanceHTML = "";
  if(strongest || weakest || classCompareHTML){
    const sH = strongest ? `<div class="ag-stat"><div class="ag-label">Your strongest here</div><div class="ag-val"><b>${strongest.label}</b> — ${strongest.mastery}%</div></div>` : "";
    const wH = weakest && weakest !== strongest ? `<div class="ag-stat"><div class="ag-label">Worth focusing on</div><div class="ag-val"><b>${weakest.label}</b> — ${weakest.mastery}%</div></div>` : "";
    glanceHTML = `
      <div class="unit-glance-section">
        <div class="trend-label">🔍 At a glance</div>
        ${sH}${wH}${classCompareHTML}
      </div>`;
  }

  document.getElementById("modal-content").innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${u.unit}</h2>
        <div class="meta">Median BKT mastery: <b>${u.median_mastery==null?'n/a':u.median_mastery+'%'}</b> · ${(u.mastery_values||[]).length} attempted of ${u.total} skills</div>
        <div class="meta" style="font-size:11px;color:#888;margin-top:2px">For reference: raw correctness avg on this unit — <b>${u.raw_correctness_avg==null?'n/a':u.raw_correctness_avg+'%'}</b></div>
      </div>
      <button class="close" onclick="document.getElementById('modal').classList.remove('show')">×</button>
    </div>
    <div class="trend-label">📚 Skill breakdown</div>
    ${modalSection("Needs Practice", u.needs_list,      "needs",      COLORS.red,   true)}
    ${modalSection("Progressing",    u.developing_list, "developing", COLORS.amber, true)}
    ${modalSection("Mastered",       u.mastered_list,   "mastered",   COLORS.green, true)}
    ${modalSection("Unattempted",    u.unattempted_list,"unattempted","#6B7280",    false)}
    ${trendHTML}
    ${glanceHTML}`;
  document.getElementById("modal").classList.add("show");
}

function setSort(mode){
  currentSort = mode;
  document.querySelectorAll(".sort button").forEach(b => b.classList.toggle("active", b.dataset.sort === mode));
  renderGrid();
}

function renderGrid(){
  const s = STUDENTS[currentStudent];
  let order = s.unit_tiles.map((t, i) => ({t, origIdx: i}));
  if(currentSort === "risk"){
    order.sort((a, b) => {
      const dr = TIER_RANK[a.t.tier] - TIER_RANK[b.t.tier];
      if (dr !== 0) return dr;
      const av = a.t.avg_mastery==null ? 999 : a.t.avg_mastery;
      const bv = b.t.avg_mastery==null ? 999 : b.t.avg_mastery;
      return av - bv;
    });
  }
  document.getElementById("grid").innerHTML = order.map(o => tileHTML(o.t, o.origIdx)).join("");
}

function ctaText(s){
  const needs = s.totals.needs, dev = s.totals.developing;
  if(needs > 0 && dev > 0) return `Start with the red skills (${needs} need practice), then review the orange ones (${dev} still developing).`;
  if(needs > 0)            return `Start with the red skills — ${needs} skill${needs===1?"":"s"} need${needs===1?"s":""} practice.`;
  if(dev > 0)              return `No critical gaps. Keep practicing the ${dev} skill${dev===1?"":"s"} still developing.`;
  return "Excellent — you've mastered everything attempted. Keep up the consistent practice.";
}

function render(idx){
  currentStudent = idx;
  const s = STUDENTS[idx];
  document.getElementById("who").textContent = s.name;
  document.getElementById("title").innerHTML = "Welcome back, " + s.name +
    " <span class='badge' style='background:" + s.tier_color + "'>" + s.tier_label + "</span>";
  document.getElementById("subtitle").textContent =
    "Performance band: " + s.band + " · course-to-date final: " + s.course_final + "% · overall BKT mastery: " + s.overall + "% · raw correctness avg: " + s.overall_raw + "%";

  // Enhanced KPI cards: number + denominator + visual progress + class comparison + tagline
  const ca = s.class_avg_totals || {};
  const atRisk = !!s.at_risk;
  setKpiCard("mastered",    s.totals.mastered,    s.totals.all, ca.mastered,    atRisk, /*biggerIsBetter*/ true);
  setKpiCard("developing",  s.totals.developing,  s.totals.all, ca.developing,  atRisk, /*biggerIsBetter*/ null);  // neutral
  setKpiCard("needs",       s.totals.needs,       s.totals.all, ca.needs,       atRisk, /*biggerIsBetter*/ false);
  setKpiCard("unattempted", s.totals.unattempted, s.totals.all, ca.unattempted, atRisk, /*biggerIsBetter*/ false);

  // Sparklines + "vs last check" delta
  const trends = s.weekly_trends || [];
  renderTrend("mastered",    trends, COLORS.green, true);
  renderTrend("developing",  trends, COLORS.amber, null);   // neutral
  renderTrend("needs",       trends, COLORS.red,   false);
  renderTrend("unattempted", trends, COLORS.gray,  false);

  renderGrid();

  // Open the class-comparison panel by default for students who are on track
  // or only need attention. Keep it collapsed for at-risk so they aren't hit
  // with "behind on 10 of 10 units" the moment they log in.
  document.getElementById("cmp_details").open = (s.tier_id !== "at_risk");

  // Softer phrasing: lead with the positive count, frame the negative as a
  // direction ("the class is ahead") rather than a deficit on the student.
  const sumColor = s.n_ahead >= s.n_behind ? COLORS.green : COLORS.amber;
  document.getElementById("cmp_summary").innerHTML =
    `Across ${s.n_total} units, you're <b style="color:${sumColor}">stronger than the class average on ${s.n_ahead}</b> ` +
    `and the class is ahead on ${s.n_behind}.`;
  const fmt = d => `<span style="color:${d>=0?COLORS.green:COLORS.red};font-variant-numeric:tabular-nums">${d>=0?'+':''}${d}pp</span>`;
  document.getElementById("cmp_ahead").innerHTML =
    (s.ahead_units.length ? s.ahead_units : [{unit:"—",diff:0}])
      .map(u => `<li><b>${u.unit}</b> &nbsp;${fmt(u.diff)} vs class avg</li>`).join("");
  document.getElementById("cmp_behind").innerHTML =
    (s.behind_units.length ? s.behind_units : [{unit:"—",diff:0}])
      .map(u => `<li><b>${u.unit}</b> &nbsp;${fmt(u.diff)} vs class avg</li>`).join("");

  document.getElementById("cta_text").textContent = ctaText(s);
}

const pk = document.getElementById("picker");
STUDENTS.forEach((s,i)=>{
  const b = document.createElement("button");
  b.textContent = s.profile + " · " + s.name;
  b.onclick = ()=>{ document.querySelectorAll(".picker button").forEach(x=>x.classList.remove("active")); b.classList.add("active"); render(i); };
  pk.appendChild(b);
});
pk.firstChild.classList.add("active");
render(0);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    html = build_html()
    OUT.write_text(html)
    print("WROTE", OUT, "size:", OUT.stat().st_size, "bytes")
