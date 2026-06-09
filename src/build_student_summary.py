"""Student Summary HTML mockup — tile-based, action-oriented version per advisor's spec.

Changes in this revision:
1. Tile color now reflects KC counts, not avg %:
   red = has any 'needs practice' KC, yellow = has developing KCs but no needs,
   green = mostly mastered, gray = unattempted.
2. KPI strip splits "not mastered" into "still developing" vs "need practice".
3. Sort toggle: Course order  ↔  Needs attention first.
4. Modal includes a "Start with: <skill>" recommendation + practice button.
5. CTA explicitly mentions red vs orange skills.
"""
import json
from pathlib import Path
import pandas as pd

# Portable path resolution: works whether the script sits in src/ or repo root
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if (HERE.name == "src" and (HERE.parent / "notebooks").exists()) else HERE

SEARCH = [REPO_ROOT/"data"/"raw", REPO_ROOT/"data", REPO_ROOT, Path.cwd(), Path.cwd()/"data"/"raw"]
def find_file(name):
    for b in SEARCH:
        f = b / name
        if f.exists():
            return f
    raise FileNotFoundError(f"{name} not found in any of: {[str(s) for s in SEARCH]}")

DATA = find_file("final_data.xlsx")
PACK = find_file("mkc_mapping_pack_v1.0..xlsx")
OUT  = REPO_ROOT / "notebooks" / "student_summary.html"
OUT.parent.mkdir(parents=True, exist_ok=True)
print(f"  Using data: {DATA}")
print(f"  Using MKC pack: {PACK}")
print(f"  Output: {OUT}")

obs    = pd.read_excel(DATA, sheet_name="Student_Observations")
scores = pd.read_excel(DATA, sheet_name="Overall_Scores")
mnodes = pd.read_excel(PACK, sheet_name="Modeling_KC_Nodes")
fmap   = pd.read_excel(PACK, sheet_name="FineKC_to_ModelingKC_Map")

fine2mkc  = dict(zip(fmap["fine_kc_id"], fmap["modeling_kc_id"]))
mkc2unit  = dict(zip(mnodes["modeling_kc_id"], mnodes["unit"]))
mkc2label = dict(zip(mnodes["modeling_kc_id"], mnodes["modeling_kc_label"]))

UNITS = [f"Unit {i}" for i in range(1, 11)]
unit_mkcs = {u: list(mnodes[mnodes["unit"]==u]["modeling_kc_id"]) for u in UNITS}

o = obs[obs["score"] != 0.5].copy()
o["correct"] = o["score"].astype(int)
o["mkc"]     = o["primary_kc_id"].map(fine2mkc)
o["unit"]    = o["mkc"].map(mkc2unit)

T_MASTERED   = 0.70
T_DEVELOPING = 0.40

def tier_overall(overall):
    # badge background colors — match the dashboard palette
    if overall >= 0.60: return ("on_track",  "On track",        "#60D394")  # Emerald
    if overall >= 0.45: return ("attention", "Needs attention", "#FFD97D")  # Jasmine
    return                    ("at_risk",   "At risk",          "#EE6055")  # Vibrant Coral

def tier_for_tile(t):
    """Advisor's spec: tile color directly tells the student what to do.
       red    = has any 'needs practice' KC → action needed
       yellow = no needs but has developing → still working on it
       green  = mostly or all mastered
       gray   = nothing attempted yet"""
    if t["total"] == t["n_unattempted"]: return "gray"
    if t["n_needs"] > 0:                 return "red"
    if t["n_developing"] > t["n_mastered"]: return "yellow"
    return "green"

per_stu_per_unit = (o.groupby(["student_id","unit"])["correct"].mean().unstack("unit"))
class_avg = {u: float(per_stu_per_unit[u].mean()) for u in UNITS if u in per_stu_per_unit.columns}


def _get_class_avg_totals():
    """Compute average (mastered, developing, needs, unattempted) counts across all
    students. Used to give per-student KPI cards a class-relative context — so the
    student sees not just "12 skills mastered" but "12 vs class avg of 14".

    Cached after first call (sub-second to compute, but called on every render).
    """
    if hasattr(_get_class_avg_totals, "_cache"):
        return _get_class_avg_totals._cache

    sids = scores["student_id"].unique().tolist()
    sums = {"mastered": 0, "developing": 0, "needs": 0, "unattempted": 0, "all": 0}
    n_students = 0

    for sid in sids:
        sob_s = o[o["student_id"] == sid]
        if sob_s.empty:
            continue
        mkc_mast_s = sob_s.groupby("mkc")["correct"].mean().to_dict()

        s_mast = s_dev = s_need = s_unatt = s_total = 0
        for u in UNITS:
            for m in unit_mkcs[u]:
                s_total += 1
                if m not in mkc_mast_s:
                    s_unatt += 1
                else:
                    v = mkc_mast_s[m]
                    if   v >= T_MASTERED:   s_mast += 1
                    elif v >= T_DEVELOPING: s_dev  += 1
                    else:                   s_need += 1

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


DEFAULT_PICKS = [("S004","High performer"), ("S019","Middle performer"), ("S001","Low performer")]


def build_html(picks=None):
    """Generate the full HTML mockup as a string.

    picks : list of (student_id, label) tuples.
            Default = three demo students.
            Pass [(sid, "")] for single-student rendering — picker/demo-banner/topbar auto-hidden.
    """
    picks = picks or DEFAULT_PICKS
    students = []
    for sid, profile in picks:
        rec  = scores[scores["student_id"]==sid].iloc[0]
        sob  = o[o["student_id"]==sid]
        overall = sob["correct"].mean()
        mkc_mast = sob.groupby("mkc")["correct"].mean().to_dict()

        tile_data = []
        unit_avgs = {}
        for u in UNITS:
            total_in_unit = unit_mkcs[u]
            attempted     = [m for m in total_in_unit if m in mkc_mast]
            unattempted   = [m for m in total_in_unit if m not in mkc_mast]
            mastered, developing, needs = [], [], []
            for m in attempted:
                v = mkc_mast[m]
                entry = {"id": m, "label": mkc2label.get(m, m), "mastery": round(v*100, 1)}
                if   v >= T_MASTERED:   mastered.append(entry)
                elif v >= T_DEVELOPING: developing.append(entry)
                else:                   needs.append(entry)
            avg = sum(mkc_mast[m] for m in attempted) / len(attempted) if attempted else None
            unit_avgs[u] = avg

            tile = {
                "unit": u,
                "avg_mastery": round(avg*100, 1) if avg is not None else None,
                "total": len(total_in_unit),
                "n_mastered": len(mastered),
                "n_developing": len(developing),
                "n_needs": len(needs),
                "n_unattempted": len(unattempted),
                "mastered_list":    sorted(mastered,   key=lambda x: -x["mastery"]),  # high first
                "developing_list":  sorted(developing, key=lambda x:  x["mastery"]),  # priority first
                "needs_list":       sorted(needs,      key=lambda x:  x["mastery"]),  # priority first
                "unattempted_list": [{"id": m, "label": mkc2label.get(m, m)} for m in unattempted],
            }
            tile["tier"] = tier_for_tile(tile)
            # advisor #4: recommended first action when student opens this unit
            if   tile["needs_list"]:      tile["start_with"] = tile["needs_list"][0];      tile["start_verb"] = "Start with"
            elif tile["developing_list"]: tile["start_with"] = tile["developing_list"][0]; tile["start_verb"] = "Keep practicing"
            else:                         tile["start_with"] = None;                       tile["start_verb"] = None
            tile_data.append(tile)

        attempted_units = {u: v for u, v in unit_avgs.items() if v is not None}
        strongest_unit = max(attempted_units, key=attempted_units.get)
        weakest_unit   = min(attempted_units, key=attempted_units.get)

        diffs = [(u, round((unit_avgs[u]-class_avg[u])*100, 1))
                 for u in UNITS if unit_avgs.get(u) is not None and u in class_avg]
        n_ahead  = sum(1 for _, d in diffs if d > 0)
        n_behind = sum(1 for _, d in diffs if d < 0)
        ahead_sorted  = sorted([(u,d) for u,d in diffs if d > 0], key=lambda x: -x[1])[:2]
        behind_sorted = sorted([(u,d) for u,d in diffs if d < 0], key=lambda x:  x[1])[:2]

        tier_id, tier_label, tier_color = tier_overall(overall)

        totals = {
            "mastered":     sum(t["n_mastered"]     for t in tile_data),
            "developing":   sum(t["n_developing"]   for t in tile_data),
            "needs":        sum(t["n_needs"]        for t in tile_data),
            "unattempted":  sum(t["n_unattempted"]  for t in tile_data),
            "all":          sum(t["total"]          for t in tile_data),
        }

        students.append({
            "id": sid, "name": rec["display_name"], "profile": profile,
            "band": rec["performance_band"],
            "overall": round(overall*100, 1),
            "course_final": round(rec["course_final_dataset_percent"], 1),
            "tier_id": tier_id, "tier_label": tier_label, "tier_color": tier_color,
            "strongest_unit": strongest_unit, "strongest_unit_value": round(attempted_units[strongest_unit]*100, 1),
            "weakest_unit": weakest_unit,     "weakest_unit_value": round(attempted_units[weakest_unit]*100, 1),
            "unit_tiles": tile_data,
            "totals": totals,
            "class_avg_totals": _get_class_avg_totals(),   # for KPI card comparison
            "at_risk": (tier_id == "at_risk"),             # hide class-comparison for at-risk students (empathetic UX)
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
  body{margin:0;font-family:"Helvetica Neue",Arial,sans-serif;background:#fff;color:var(--ink);line-height:1.45}

  /* Jet Black header band — the only dark area on the page (Quarto's outer
     navbar is hidden in the dashboard wrapper). */
  .hdr{background:var(--bg);color:var(--on-dark);padding:22px 0 20px}
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
  .stack{display:flex;height:8px;border-radius:3px;overflow:hidden;background:#EEF1F5;margin-bottom:8px}
  .stack > div{height:100%}
  .seg-green{background:var(--green)} .seg-yellow{background:var(--amber)}
  .seg-red{background:var(--red)} .seg-gray{background:var(--gray)}
  .counts{font-size:11px;line-height:1.5;color:var(--ink)}
  .counts .row{display:flex;align-items:center;gap:5px}
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
  .msec{margin-top:14px}
  .msec h3{font-size:12px;font-weight:700;margin:0 0 5px;text-transform:uppercase;letter-spacing:.5px}
  .msec ul{list-style:none;padding:0;margin:0}
  .msec li{font-size:13px;padding:7px 10px;border-radius:4px;margin-bottom:3px;display:flex;justify-content:space-between;gap:14px}
  .msec.mastered  li{background:rgba(96,211,148,0.14)}
  .msec.developing li{background:rgba(255,217,125,0.20)}
  .msec.needs     li{background:rgba(238,96,85,0.12)}
  .msec.unattempted li{background:rgba(139,157,187,0.14);color:var(--mute)}
  .msec li .pct{font-weight:600;font-variant-numeric:tabular-nums}
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
  <div class="kpi">
    <!-- ───── Skills mastered ───── -->
    <div class="kcard" onclick="openCategory('mastered')">
      <div class="accent" style="background:var(--green)"></div><div class="arrow">›</div>
      <h3>Skills mastered</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_mastered_num">—</span>
        <span class="denom"  id="kc_mastered_denom">/ —</span>
      </div>
      <div class="desc">Skills you've reached 70%+ on this term</div>
      <div class="bar"><div class="bar-fill" id="kc_mastered_bar" style="background:var(--green);width:0%"></div></div>
      <div class="pct-label" id="kc_mastered_pct" style="color:#2D8D5B">—</div>
      <div class="compare" id="kc_mastered_cmp"></div>
      <div class="tagline" id="kc_mastered_tag">—</div>
    </div>

    <!-- ───── Still developing ───── -->
    <div class="kcard" onclick="openCategory('developing')">
      <div class="accent" style="background:var(--amber)"></div><div class="arrow">›</div>
      <h3>Still developing</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_developing_num">—</span>
        <span class="denom"  id="kc_developing_denom">/ —</span>
      </div>
      <div class="desc">40–69% — your active work zone</div>
      <div class="bar"><div class="bar-fill" id="kc_developing_bar" style="background:var(--amber);width:0%"></div></div>
      <div class="pct-label" id="kc_developing_pct" style="color:#B8860B">—</div>
      <div class="compare" id="kc_developing_cmp"></div>
      <div class="tagline" id="kc_developing_tag">—</div>
    </div>

    <!-- ───── Need practice ───── -->
    <div class="kcard" onclick="openCategory('needs')">
      <div class="accent" style="background:var(--red)"></div><div class="arrow">›</div>
      <h3>Need practice</h3>
      <div class="bignum-row">
        <span class="bignum" id="kc_needs_num">—</span>
        <span class="denom"  id="kc_needs_denom">/ —</span>
      </div>
      <div class="desc">Below 40% — focus area for tonight</div>
      <div class="bar"><div class="bar-fill" id="kc_needs_bar" style="background:var(--red);width:0%"></div></div>
      <div class="pct-label" id="kc_needs_pct" style="color:#B53C32">—</div>
      <div class="compare" id="kc_needs_cmp"></div>
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
    <span><span class="dot" style="background:var(--green)"></span>Mastered (≥70%)</span>
    <span><span class="dot" style="background:var(--amber)"></span>Developing (40–69%)</span>
    <span><span class="dot" style="background:var(--red)"></span>Needs practice (&lt;40%)</span>
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
    <button onclick="alert('Goes to the training-agenda page (Godsgift\\'s view).')">View my practice plan →</button>
  </div>

  <div class="note">
    Mastery = raw average correctness per skill (MKC). Tile color tells you what to do: red = at least one skill needs practice, orange = skills still developing, green = mostly or all mastered. Class average computed from all 25 students.
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

// ─── KPI card population (Ilya's redesign: every number gets context) ─────────
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

  // comparison badge
  const cmpEl = document.getElementById("kc_"+cat+"_cmp");
  if(atRisk || classAvg === undefined || classAvg === null){
    // empathetic UX: at-risk students don't get hit with class rankings
    cmpEl.classList.add("hidden");
    cmpEl.innerHTML = "";
  } else {
    cmpEl.classList.remove("hidden");
    const delta = value - classAvg;
    let arrow, kind, text;
    if(delta === 0){
      arrow = "→"; kind = "neutral"; text = "matches class average ("+classAvg+")";
    } else if(delta > 0){
      arrow = "↑";
      kind = (biggerIsBetter === true)  ? "good"
           : (biggerIsBetter === false) ? "bad"
           : "neutral";
      text = "above class average ("+classAvg+")";
    } else {
      arrow = "↓";
      kind = (biggerIsBetter === true)  ? "bad"
           : (biggerIsBetter === false) ? "good"
           : "neutral";
      text = "below class average ("+classAvg+")";
    }
    cmpEl.className = "compare " + kind;
    cmpEl.innerHTML = "<strong>" + arrow + " " + Math.abs(delta) + "</strong>&nbsp;" + text;
  }

  // tagline
  const tagEl = document.getElementById("kc_"+cat+"_tag");
  tagEl.textContent = taglineFor(cat, value);
  tagEl.className = "tagline" + (cat === "needs" && value > 0 ? " action" : "");
}

function tileHTML(t, origIdx){
  const segs = [
    {n: t.n_mastered,    cls:"seg-green"},
    {n: t.n_developing,  cls:"seg-yellow"},
    {n: t.n_needs,       cls:"seg-red"},
    {n: t.n_unattempted, cls:"seg-gray"},
  ].map(x => x.n>0 ? `<div class="${x.cls}" style="flex:${x.n}"></div>` : "").join("");
  return `
    <div class="tile ${t.tier}" onclick="openUnit(${origIdx})">
      <div class="accent"></div>
      <h4>${t.unit}</h4>
      <div class="pct ${t.avg_mastery==null?'na':''}">${t.avg_mastery==null?'—':t.avg_mastery+'%'}</div>
      <div class="stack">${segs}</div>
      <div class="counts">
        <div class="row"><span class="dot" style="background:${COLORS.green}"></span>${t.n_mastered} mastered</div>
        <div class="row"><span class="dot" style="background:${COLORS.amber}"></span>${t.n_developing} developing</div>
        <div class="row"><span class="dot" style="background:${COLORS.red}"></span>${t.n_needs} needs practice</div>
        <div class="row"><span class="dot" style="background:${COLORS.gray}"></span>${t.n_unattempted} unattempted</div>
      </div>
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
  mastered:    {title:"Skills mastered",   color: COLORS.green, sub:"≥ 70% correctness", listKey:"mastered_list",    withPct:true,  emptyMsg:"No mastered skills yet."},
  developing:  {title:"Still developing", color: COLORS.amber, sub:"40–69% correctness — keep practicing", listKey:"developing_list", withPct:true, emptyMsg:"No skills in this category."},
  needs:       {title:"Need practice",  color: COLORS.red,   sub:"Below 40% — focus here", listKey:"needs_list",  withPct:true, emptyMsg:"No skills need practice — well done!"},
  unattempted: {title:"Unattempted",    color: COLORS.gray,  sub:"No practice yet", listKey:"unattempted_list", withPct:false, emptyMsg:"You've attempted every skill."},
};

function openCategory(cat){
  const s = STUDENTS[currentStudent];
  const cfg = CATEGORY_META[cat];
  // collect items per unit
  const sections = s.unit_tiles
    .map(t => ({unit:t.unit, items:t[cfg.listKey] || []}))
    .filter(sec => sec.items.length > 0);
  const total = sections.reduce((a, sec) => a + sec.items.length, 0);

  const body = total === 0
    ? `<div class="empty">${cfg.emptyMsg}</div>`
    : sections.map(sec => `
        <div class="msec ${cat}">
          <h3 style="color:${cfg.color}">${sec.unit} <span style="color:var(--mute);font-weight:400;text-transform:none;letter-spacing:0">— ${sec.items.length} skill${sec.items.length===1?"":"s"}</span></h3>
          <ul>${sec.items.map(m => `<li><span>${m.label}</span><span class="pct">${cfg.withPct ? (m.mastery+'%') : '—'}</span></li>`).join("")}</ul>
        </div>`).join("");

  document.getElementById("modal-content").innerHTML = `
    <div class="modal-header">
      <div>
        <h2><span style="color:${cfg.color}">●</span> ${cfg.title} — ${total} skill${total===1?"":"s"}</h2>
        <div class="meta">${cfg.sub} · across ${sections.length} unit${sections.length===1?"":"s"}</div>
      </div>
      <button class="close" onclick="document.getElementById('modal').classList.remove('show')">×</button>
    </div>
    ${body}`;
  document.getElementById("modal").classList.add("show");
}

function openUnit(i){
  const u = STUDENTS[currentStudent].unit_tiles[i];
  document.getElementById("modal-content").innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${u.unit}</h2>
        <div class="meta">Average mastery: <b>${u.avg_mastery==null?'n/a':u.avg_mastery+'%'}</b> · ${u.total} skills in this unit</div>
      </div>
      <button class="close" onclick="document.getElementById('modal').classList.remove('show')">×</button>
    </div>
    ${modalSection("Needs practice",u.needs_list,      "needs",      COLORS.red,   true)}
    ${modalSection("Developing",    u.developing_list, "developing", COLORS.amber, true)}
    ${modalSection("Mastered",      u.mastered_list,   "mastered",   COLORS.green, true)}
    ${modalSection("Unattempted",   u.unattempted_list,"unattempted","#6B7280",    false)}`;
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
    "Performance band: " + s.band + " · course-to-date final: " + s.course_final + "% · overall mastery: " + s.overall + "%";

  // Enhanced KPI cards: number + denominator + visual progress + class comparison + tagline
  const ca = s.class_avg_totals || {};
  const atRisk = !!s.at_risk;
  setKpiCard("mastered",    s.totals.mastered,    s.totals.all, ca.mastered,    atRisk, /*biggerIsBetter*/ true);
  setKpiCard("developing",  s.totals.developing,  s.totals.all, ca.developing,  atRisk, /*biggerIsBetter*/ null);  // neutral
  setKpiCard("needs",       s.totals.needs,       s.totals.all, ca.needs,       atRisk, /*biggerIsBetter*/ false);
  setKpiCard("unattempted", s.totals.unattempted, s.totals.all, ca.unattempted, atRisk, /*biggerIsBetter*/ false);

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
