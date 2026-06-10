from pathlib import Path
import numpy as np
import re
import pandas as pd
import networkx as nx
import plotly.graph_objects as go

from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget


####################################################################################
### Basic Configs
####################################################################################
MASTERY_THRESHOLD = 0.65   

# Band cutoffs for "Your Level" (applied to the exam-readiness score)
ADVANCED_CUTOFF = 0.65
PROFICIENT_CUTOFF = 0.50
EMERGING_CUTOFF = 0.35

BANDS = [("Advanced", ADVANCED_CUTOFF), ("Proficient", PROFICIENT_CUTOFF), ("Emerging", EMERGING_CUTOFF)]
# Background colours for the KPI cards / bands
BAND_BG = {"Advanced": "#60D394", "Proficient": "#185FA5",
           "Emerging": "#FECD54", "Developing": "#EE6055"} # "#C77F0A" # red-other; "#C0392B"


def band_color(p):
    """Grey = not attempted; green/amber/red by mastery band (for graph nodes)."""
    if p is None or  pd.isna(p) or  (isinstance(p, float) and np.isnan(p)):
        return "#C9CDD2"
    if p >= MASTERY_THRESHOLD:
        return "#60D394"
    if p >= EMERGING_CUTOFF:
        return "#FFD97D"
    return "#EE6055"


####################################################################################
### File paths and data loading 
####################################################################################
DATA_DIR = Path("data")
base_path = Path().resolve()
file_path = base_path / "data" / "processed" 

student_df = pd.read_csv(file_path / "final_student_kc_data.csv")
nodes_df = pd.read_excel(file_path / "mkc_mapping_pack_v1.0..xlsx", sheet_name="Modeling_KC_Nodes")
edges_df = pd.read_excel(file_path / "mkc_mapping_pack_v1.0..xlsx", sheet_name="Modeling_KC_Edges")

for col in ["weight", "estimated_exam_share_pct", "downstream_dependents",
            "direct_dependents", "order_id", "state_predictions",
            "correct_predictions", "correct"]:
    if col in student_df.columns:
        student_df[col] = pd.to_numeric(student_df[col], errors="coerce")

edges_df["fine_edge_count"] = (
    pd.to_numeric(edges_df.get("fine_edge_count", 1), errors="coerce").fillna(1)
    if "fine_edge_count" in edges_df.columns else 1)


####################################################################################
### VARIABLES 
####################################################################################
# MKC labels / units from the Nodes sheet.
LABELS = dict(zip(nodes_df["modeling_kc_id"], nodes_df["modeling_kc_label"]))
MKC_UNIT = dict(zip(nodes_df["modeling_kc_id"], nodes_df.get("unit", pd.Series())))

# Total number of MKCs in the whole curriculum (denominator for "X / N").
TOTAL_MKCS = nodes_df["modeling_kc_id"].nunique()

# Prerequisite graph: source MKC --> target MKC.
G = nx.DiGraph()
G.add_edges_from(zip(edges_df["source_modeling_kc_id"], 
                    edges_df["target_modeling_kc_id"]))

def _unit_key(u):
    """
    Helper to sort unit labels by their number if possible (e.g. "Unit 2" before "Unit 10"). 
    """
    m = re.search(r"(\d+)", str(u))
    return (int(m.group(1)) if m else 999, str(u))

# All student ids, for the dropdown.
STUDENT_IDS = sorted(student_df["student_id"].astype(str).unique().tolist())

# All unit labels, sorted by unit number if possible (for the dropdown).
UNIT_LIST = sorted({u for u in MKC_UNIT.values() if isinstance(u, str)}, key=_unit_key)
OVERVIEW_LABEL = "Overview: All Units"


####################################################################################
### CORE ALGOTHIRMS 
####################################################################################
def student_mkc_table(student_id):
    """PER-STUDENT: one row per MKC = the student's LATEST mastery + attributes."""
    s = student_df[student_df["student_id"].astype(str) == str(student_id)].copy()
    if s.empty:
        return pd.DataFrame(columns=["modeling_kc_id", "mastery", "weight",
                                    "tier", "downstream", "label", "unit"])
    s = s.sort_values(["modeling_kc_id", "order_id"])
    latest = s.groupby("modeling_kc_id", as_index=False).tail(1)
    latest = latest.rename(columns={"state_predictions": "mastery",
                                    "downstream_dependents": "downstream",
                                    "direct_dependents": "direct",
                                    "estimated_exam_share_pct": "exam_share"})
    latest["label"] = latest["modeling_kc_id"].map(LABELS).fillna(latest["modeling_kc_id"])
    if "unit" not in latest.columns:
        latest["unit"] = latest["modeling_kc_id"].map(MKC_UNIT)
    keep = ["modeling_kc_id", "mastery", "weight", "tier",
            "downstream", "direct", "exam_share", "label", "unit"]
    return latest[[c for c in keep if c in latest.columns]].reset_index(drop=True)


def exam_readiness(tbl, mastery_col="mastery", weight_col="weight"):
    """
    Σ(mastery·weight)/Σ(weight), weight = partner's importance score.
    If no weights, just average mastery. If no data, return 0.
    """
    tbl = tbl.dropna(subset=[mastery_col])
    if tbl.empty:
        return 0.0
    if weight_col not in tbl.columns:
        return float(tbl[mastery_col].mean())
    w = tbl[weight_col].fillna(0)
    if w.sum() == 0:
        return float(tbl[mastery_col].mean())
    return float((tbl[mastery_col] * w).sum() / w.sum())
    # return float(np.average(valid_data[mastery_col], weights=weights))


def level_band(score):
    for name, cutoff in BANDS:
        if score >= cutoff:
            return name, BAND_BG[name]
    return "Developing", BAND_BG["Developing"]


def _unmastered_prereqs(kc, mastery_map):
    if kc not in G:
        return []
    return [pr for pr in G.predecessors(kc)
            if mastery_map.get(pr, 0.0) < MASTERY_THRESHOLD]


def find_blocked(mastery_map):
    return [kc for kc, p in mastery_map.items()
            if p < MASTERY_THRESHOLD and _unmastered_prereqs(kc, mastery_map)]


def _norm(x):
    x = x.fillna(0).astype(float)
    rng = x.max() - x.min()
    return (x - x.min()) / rng if rng > 0 else pd.Series(0.5, index=x.index)


def build_agenda(tbl, n=3):
    """
Build the student's top-`n` "next steps" cards.

    Strategy
    --------
    1. Look only at WEAK topics (mastery < 0.80) — mastered ones need no action.
    2. Split weak topics into READY (all prerequisites already mastered → the
       student can tackle them now) vs BLOCKED (still missing a prerequisite).
    3. Rank the READY ones by a weighted priority score (see below) and take n.
    4. If there aren't n ready topics, top up with the highest-`weight` BLOCKED
       topics so the agenda always shows n cards — these are badged "locked"
       and list the prerequisites to clear first.

    Priority score (ready topics only)
    -----------------------------------
        score =importance 
      - importance = normalized `weight`     (partner's 1-100 priority)
    importance is the stated business priority;
    Returns
    -------
    list[dict] : one dict per card, each carrying the topic name, mastery,
    weight, tier, downstream count, a badge/type, ready flag, the missing
    prerequisites (for locked cards), and the downstream topics it unlocks.
    """
    if tbl.empty:
        return []
    
    # Fast lookup: modeling_kc_id - this student's mastery.
    mm = dict(zip(tbl["modeling_kc_id"], tbl["mastery"]))
    weak = tbl[tbl["mastery"] < MASTERY_THRESHOLD].copy()
    
    # only weak topics are candidates for "next steps".
    if weak.empty:
        return []
    # which weak topics are learnable right now (prereqs satisfied)?
    weak["missing"] = weak["modeling_kc_id"].apply(lambda kc: _unmastered_prereqs(kc, mm))
    weak["ready"] = weak["missing"].apply(lambda m: len(m) == 0)
    # rank the ready topics by the priority weight score.
    ready = weak[weak["ready"]].copy()
    if not ready.empty:
        w = ready["weight"] if "weight" in ready.columns else pd.Series(0.5, index=ready.index)
        #d = ready["downstream"] if "downstream" in ready.columns else pd.Series(0, index=ready.index)
        #closeness = (ready["mastery"] / MASTERY_THRESHOLD).clip(0, 1)
        # ready["score"] = 0.5 * _norm(w) + 0.3 * _norm(d) + 0.2 * closeness
        ready["score"] = _norm(w)
        ready = ready.sort_values("score", ascending=False)
    chosen = ready.head(n)

    # if fewer than n are ready, fill remaining slots with the most
    # important BLOCKED topics so the agenda still shows n cards.
    if len(chosen) < n:  # top up with highest-weight blocked MKCs
        rest = weak[(~weak["ready"]) & (~weak["modeling_kc_id"].isin(chosen["modeling_kc_id"]))].copy()
        sort_col = "weight" if "weight" in rest.columns else "mastery"
        rest = rest.sort_values(sort_col, ascending=False)
        chosen = pd.concat([chosen, rest]).head(n)

    # Build the display payload for each chosen topic.
    items = []
    for _, r in chosen.iterrows():
        p = float(r["mastery"])
        dn = int(r["downstream"]) if "downstream" in r and not pd.isna(r["downstream"]) else 0
        ready_flag = bool(r["ready"])
        
        # Badge = the KIND of recommendation, so the student sees WHY it's here.
        if not ready_flag:
            atype, badge = "locked", "🔒 Clear prerequisites"
        elif p >= PROFICIENT_CUTOFF:
            atype, badge = "quickwin", "🎯 Almost there"
        elif dn >= 3:
            atype, badge = "unblock", "🔓 Key unlock"
        else:
            atype, badge = "foundation", "🏗 Foundation"

        # Downstream topics this one unlocks (for the card's "Will unlock" list).
        # nx.descendants = every topic reachable from this one in the prereq graph.
        kc = r["modeling_kc_id"]
        desc = nx.descendants(G, kc) if kc in G else set()
        unlocks = sorted(((LABELS.get(x, x), mm.get(x, 0) >= MASTERY_THRESHOLD) for x in desc),
                        key=lambda t: (t[1], t[0]))    # not-yet-mastered first, then alphabetical
        items.append({
            "name": r.get("label", kc), "mastery": p,
            "weight": (None if "weight" not in r or pd.isna(r["weight"]) else r["weight"]),
            "tier": (r["tier"] if "tier" in r and not pd.isna(r["tier"]) else None),
            "downstream": dn, "atype": atype, "badge": badge, "ready": ready_flag,
            "missing": [LABELS.get(x, x) for x in r["missing"]],
            "unlocks": unlocks,
        })
    return items

# ---- Graph builders ----------------------------------------------------------
def _style(fig):
    """Responsive layout:
    NO fixed height, so it fills the (expandable) panel."""
    fig.update_layout(autosize=True, margin=dict(l=8, r=8, t=8, b=8),
                    font=dict(size=12), paper_bgcolor="white", plot_bgcolor="white")
    return fig


def _unit_avg(unit, mastery_map):
    vals = [mastery_map[k] for k, u in MKC_UNIT.items() 
            if u == unit and k in mastery_map and pd.notna(mastery_map[k])]
    return sum(vals) / len(vals) if vals else None


def build_unit_sankey(mm):
    """
    OVERVIEW: nodes = units (colour = avg mastery), 
    links = cross-unit prereqs.
    Note: this is a high-level overview for the student, so we only show links between units, not individual MKCs."""
    agg = {}
    for s, t, v in zip(edges_df["source_modeling_kc_id"],
                    edges_df["target_modeling_kc_id"], edges_df["fine_edge_count"]):
        su, tu = MKC_UNIT.get(s), MKC_UNIT.get(t)
        if su and tu and su != tu:
            agg[(su, tu)] = agg.get((su, tu), 0) + float(v)
    present = {u for pair in agg for u in pair}
    units = [u for u in UNIT_LIST if u in present] or UNIT_LIST
    idx = {u: i for i, u in enumerate(units)}
    colors = [band_color(_unit_avg(u, mm)) for u in units]
    hover = [f"{u}<br>Avg mastery: " +
            #("n/a" if _unit_avg(u, mm) is None 
            ("Not attempted" if _unit_avg(u, mm) is None
            else f"{_unit_avg(u, mm):.0%}") 
            for u in units]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=units, color=colors, customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
                pad=20, thickness=22, line=dict(color="white", width=0.6)),
        link=dict(source=[idx[a] for a, _ in agg], target=[idx[b] for _, b in agg],
                value=list(agg.values()), color="rgba(170,175,180,0.4)", hovercolor="#80ffdb",  
                hovertemplate="%{value:.0f} topics in %{target.label} depend on %{source.label}<extra></extra>")))
    return _style(fig)


def build_unit_detail_sankey(unit, mm):
    """
    DRILL-DOWN: a unit's MKCs + immediate neighbours (few nodes, readable).
    
    """
    core = [k for k, u in MKC_UNIT.items() if u == unit]
    nodeset = set(core)
    for k in core:
        if k in G:
            nodeset.update(G.predecessors(k)); nodeset.update(G.successors(k))
    pairs = [(s, t, float(v)) for s, t, v in zip(
        edges_df["source_modeling_kc_id"], edges_df["target_modeling_kc_id"],
        edges_df["fine_edge_count"]) if s in nodeset and t in nodeset]
    if not pairs:
        fig = go.Figure()
        fig.add_annotation(text=f"No prerequisite links found within {unit}.",
                        showarrow=False, font=dict(size=14, color="#888"))
        return _style(fig)
    nodes = list(dict.fromkeys([s for s, _, _ in pairs] + [t for _, t, _ in pairs]))
    idx = {nname: i for i, nname in enumerate(nodes)}
    labels = [LABELS.get(nname, nname) + ("" if MKC_UNIT.get(nname) == unit
            else f"  ·{MKC_UNIT.get(nname)}") for nname in nodes]
    colors = [band_color(mm.get(nname)) for nname in nodes]
    hover = [f"{LABELS.get(nname, nname)}<br>Mastery: " +
            #("n/a" if mm.get(nname) is None 
            ("Not attempted" if mm.get(nname) is None or pd.isna(mm.get(nname))
            else f"{mm.get(nname):.0%}") 
            for nname in nodes]
    
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, color=colors, customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
                pad=16, thickness=18, line=dict(color="white", width=0.5)),
        link=dict(source=[idx[s] for s, _, _ in pairs], target=[idx[t] for _, t, _ in pairs],
                value=[v for _, _, v in pairs], color="rgba(170,175,180,0.35)", hovercolor="#80ffdb",
                hovertemplate="source: %{source.label}<br>target: %{target.label}<extra></extra>")))
    return _style(fig)

def render_agenda_html(tbl):
    items = build_agenda(tbl, n=3)
    if not items:
        return ("<div style='padding:24px;color:#1D9E75;font-size:16px'>"
                "🎉 Every attempted modeling-KC is at or above mastery — no next steps needed.</div>")

    style = {"quickwin": ("#1D9E75", "#E1F5EE"), "unblock": ("#185FA5", "#E6F1FB"),
             "foundation": ("#854F0B", "#FAEEDA"), "locked": ("#6B7280", "#EEF0F2")}

    def chip(lbl, fg, bg):
        return (f"<span style='display:inline-block;background:{bg};color:{fg};border-radius:5px;"
                f"font-size:12px;padding:1px 7px;margin:2px 3px 0 0'>{lbl}</span>")

    cards = ("<div style='display:grid;grid-template-columns:repeat(3,1fr);"
             "gap:12px;align-items:start'>")
    for i, it in enumerate(items):
        col, bg = style.get(it["atype"], ("#555", "#f3f3f3"))
        pct = it["mastery"]; bar_col = band_color(pct)

        if pct >= 0.70:
            bullets = ["Review the few items you missed here.",
                       "Redo homework questions below 80%.",
                       "Try one exam-style question on this skill."]
        elif pct >= 0.40:
            bullets = ["Re-read the relevant notes / textbook section.",
                       "Complete ~5 more practice problems.",
                       "Ask your teacher about the hardest part."]
        else:
            bullets = ["Start from the scaffolded examples.",
                       "Watch a short explainer for this concept.",
                       "Build the basics before moving on."]
        bullet_html = "".join(f"<li style='margin-bottom:2px'>{b}</li>" for b in bullets)

        meta = []
        if it["tier"]:
            meta.append(chip(it["tier"], col, bg))
        if it["weight"] is not None:
            meta.append(chip(f"weight {it['weight']:g}", "#555", "#f0f0f0"))
        meta_html = "".join(meta)

        # Prerequisites still needed (for locked cards)
        prereq_html = ""
        if not it["ready"] and it["missing"]:
            tags = "".join(chip(m, "#A32D2D", "#FCEBEB") for m in it["missing"])
            prereq_html = (f"<div style='border-top:1px solid #eee;padding-top:8px'>"
                           f"<div style='font-size:12px;color:#888;font-weight:600;margin-bottom:4px'>"
                           f"⚠ Master these first:</div>{tags}</div>")

        # Downstream KCs this unlocks — first 4 inline, the rest behind <details>
        unlock_html = ""
        if it["unlocks"]:
            def utag(lbl, mastered):
                fg = "#9aa0a6" if mastered else "#185FA5"
                bgc = "#f1f3f4" if mastered else "#E6F1FB"
                return chip(lbl, fg, bgc)
            inline = it["unlocks"][:4]; rest = it["unlocks"][4:]
            inline_html = "".join(utag(l, m) for l, m in inline)
            more_html = ""
            if rest:
                rest_html = "".join(utag(l, m) for l, m in rest)
                more_html = (f"<details style='margin-top:4px'>"
                             f"<summary style='cursor:pointer;color:#185FA5;font-size:12px;"
                             f"list-style:none;font-weight:600'>+{len(rest)} more ▾</summary>"
                             f"<div style='margin-top:4px'>{rest_html}</div></details>")
            unlock_html = (f"<div style='border-top:1px solid #eee;padding-top:8px'>"
                           f"<div style='font-size:12px;color:#888;font-weight:600;margin-bottom:4px'>"
                           f"🔓 Will unlock ({len(it['unlocks'])} downstream):</div>"
                           f"{inline_html}{more_html}</div>")

        cards += f"""
        <div style="border:1px solid #e3e3e3;border-top:3px solid {col};border-radius:0 0 10px 10px;
                    padding:14px 16px;background:white;display:flex;flex-direction:column;gap:8px">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="background:{bg};color:{col};border-radius:50%;width:24px;height:24px;
                         display:flex;align-items:center;justify-content:center;font-weight:700;
                         font-size:14px;flex-shrink:0">{i+1}</span>
            <strong style="font-size:15px;line-height:1.3">{it['name']}</strong>
            <span style="margin-left:auto;background:{bg};color:{col};border-radius:6px;
                         font-size:12px;padding:2px 7px;white-space:nowrap">{it['badge']}</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">{meta_html}</div>
          <div>
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#777;margin-bottom:3px">
              <span>Current mastery</span><strong style="color:{bar_col}">{pct:.0%}</strong></div>
            <div style="background:#eee;border-radius:4px;height:6px;overflow:hidden">
              <div style="background:{bar_col};width:{int(pct*100)}%;height:100%"></div></div>
            <div style="text-align:right;font-size:11px;color:#bbb;margin-top:2px">Target 80%</div>
          </div>
          <div>
            <div style="font-size:12px;color:#888;font-weight:600;margin-bottom:4px">✅ What to do next:</div>
            <ul style="font-size:13.5px;color:#444;margin:0;padding-left:16px;line-height:1.6">{bullet_html}</ul>
          </div>
          {prereq_html}
          {unlock_html}
        </div>"""
    cards += "</div>"
    return cards


####################################################################################
### STYLING
####################################################################################
custom_css = ui.tags.style("""
    body { background:#20303d; }
    .dash-banner 
    {   background:#20303d;
        color:#fff;padding:14px 24px;
        border-radius:8px;
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:6px; }
    .dash-banner h1 
    { 
        font-size:30px;
        font-weight:800;
        margin:0; }
    .brand .brand-name 
        { font-size:18px;
        font-weight:800; }
    .brand .bar 
        { display:inline-block;
        height:6px;
        border-radius:4px;
        vertical-align:middle; }
    .bar-red{width:44px;background:#e2674a;} 
    .bar-yellow{width:32px;background:#e8c93f;margin-left:6px;}
    .bar-dot{width:6px;background:#fff;margin-left:6px;}
    .student-pick { background:#20303d;padding:0 24px 8px;display:flex;align-items:center;gap:10px; }
    .student-pick label { color:#cdd6df;font-weight:600;margin:0; }
    .student-pick .form-group, .student-pick .shiny-input-container { margin:0; }
    
    /* compact, coloured KPI cards */
    .metric-row { margin-top:0 !important; --bs-gutter-y:0; }
    .metric-row .bslib-value-box { min-height:0 !important; }
    .metric-row .value-box-area { padding:8px 14px !important; }
    .metric-row .value-box-title { font-size:13px !important;margin:0 0 2px !important;opacity:.9; }
    .metric-row .value-box-value { font-size:26px !important;margin:0 !important;line-height:1.1; }
    
    /* section cards */
    .section-card .card-header { font-size:20px;font-weight:700;background:#fff;border-bottom:none; }
    .kc-head { display:flex;justify-content:space-between;align-items:center;gap:12px; }
    .kc-head .shiny-input-container { margin:0; }
    .section-card .card-body { display:flex;flex-direction:column;padding-top:6px; }
    .tab-pane.bslib-gap-spacing { gap:0.4rem !important; }
""")

banner = ui.div(
    ui.h1("Your Progress Dashboard"),
    ui.div(ui.div("Stellar Education", class_="brand-name"),
        ui.div(ui.span(class_="bar bar-red"), ui.span(class_="bar bar-yellow"),
                ui.span(class_="bar bar-dot"), style="margin-top:6px"),
           class_="brand"),
    class_="dash-banner")

student_picker = ui.div(
    ui.input_select("student", "Student:", choices=STUDENT_IDS,
                    selected=STUDENT_IDS[0] if STUDENT_IDS else None, width="220px"),
    class_="student-pick")


####################################################################################
### UI
####################################################################################
metric_row = ui.layout_columns(
    ui.output_ui("kc_box"), ui.output_ui("readiness_box"),
    ui.output_ui("level_box"), ui.output_ui("blocked_box"),
    col_widths=(3, 3, 3, 3), fill=False, class_="metric-row")

graph_card = ui.card(
    ui.card_header(
        ui.div("KC Prerequisite Graph: Your Mastery at a Glance",
            ui.input_select("kc_view", None, choices=[OVERVIEW_LABEL] + UNIT_LIST,
                            selected=OVERVIEW_LABEL, width="240px"),
            class_="kc-head")),
    output_widget("sankey", fillable=True),
    class_="section-card", height="380px", full_screen=True, fill=True)

agenda_card = ui.card(
    ui.card_header("🌟 Your Personalized Next Steps & Training Agenda"),
    ui.output_ui("agenda"),
    class_="section-card", height="440px", full_screen=True)

dashboard_page = ui.nav_panel("Dashboard", banner, student_picker,
                            metric_row, graph_card, agenda_card)
home_page = ui.nav_panel("Home", ui.div())

app_ui = ui.page_navbar(home_page, dashboard_page,
                        title="Stellar Education", header=custom_css, fillable=True)

####################################################################################
### SERVER
####################################################################################
def server(input, output, session):

    @reactive.calc
    def tbl():
        return student_mkc_table(input.student())   # per-student entry point

    @reactive.calc
    def mastery_map():
        t = tbl()
        return dict(zip(t["modeling_kc_id"], t["mastery"]))

    @reactive.calc
    def readiness():
        return exam_readiness(tbl())

    # ---- coloured KPI cards (rendered reactively so colour reflects context) ----
    def vbox(title, value, bg):
        return ui.value_box(title, value,
                            theme=ui.value_box_theme(bg=bg, fg="white"),
                            max_height="92px")

    @render.ui
    def kc_box():
        n = int((tbl()["mastery"] >= MASTERY_THRESHOLD).sum())
        return vbox("KCs mastered", f"{n} / {TOTAL_MKCS}", "#0E7C86")

    @render.ui
    def readiness_box():
        band, bg = level_band(readiness())
        return vbox("Exam Readiness", f"{readiness():.0%}", bg)

    @render.ui
    def level_box():
        band, bg = level_band(readiness())
        return vbox("Your Level", band, bg)

    @render.ui
    def blocked_box():
        nb = len(find_blocked(mastery_map()))
        bg = "#60D394" if nb == 0 else "#a63c06" #ffd100 #"#e8c93f" #("#FFD97D" if nb <= 2 else "#EE6055")
        return vbox("Blocked KCs", str(nb), bg)

    @render_widget
    def sankey():
        v = input.kc_view()
        if not v or v == OVERVIEW_LABEL:
            return build_unit_sankey(mastery_map())
        return build_unit_detail_sankey(v, mastery_map())

    @render.ui
    def agenda():
        return ui.HTML(render_agenda_html(tbl()))


app = App(app_ui, server)



# # Band cutoffs for "Your Level" (applied to the exam-readiness score, 0–1)
# BANDS = [("Advanced", ADVANCED_CUTOFF), ("Proficient", PROFICIENT_CUTOFF), ("Emerging", EMERGING_CUTOFF)]  # else Developing
# BAND_UI = {"Advanced": "success", "Proficient": "primary",
#            "Emerging": "warning", "Developing": "danger"}


# # Mastery colour (for the Sankey nodes and progress bars)
# def band_color(p):
#     """Grey = not attempted yet; green/amber/red by mastery band."""
#     if p is None or (isinstance(p, float) and np.isnan(p)):
#         return "#C9CDD2"
#     if p >= MASTERY_THRESHOLD:
#         return "#60D394"
#     if p >= 0.50:
#         return "#FFD97D"
#     return "#E24B4A"
 

########################################################################################
### Checks to ensure numeric columns are valid 
########################################################################################
# for col in ["weight", "estimated_exam_share_pct", "downstream_dependents",
#             "direct_dependents", "order_id", "state_predictions",
#             "correct_predictions", "correct"]:
#     if col in student_df.columns:
#         student_df[col] = pd.to_numeric(student_df[col], errors="coerce")
 
# if "fine_edge_count" in edges_df.columns:
#     edges_df["fine_edge_count"] = pd.to_numeric(
#         edges_df["fine_edge_count"], errors="coerce").fillna(1)
# else:
#     edges_df["fine_edge_count"] = 1


# custom_css = ui.tags.style(
#     """
#     /* App background */
#     body { background-color: #263744; }
 
#     /* Dark banner header inside the dashboard page */
#     .dash-banner {
#         background-color: #263744;
#         color: #ffffff;
#         padding: 18px 24px;
#         border-radius: 8px;
#         display: flex;
#         justify-content: space-between;
#         align-items: center;
#         margin-bottom: 1px;
#     }
#     /* Kill the default top margin/gutter Bootstrap adds to the metric row */
#     .metric-row {
#         margin-top: 0 !important;
#         --bs-gutter-y: 0;
#     }
#     .tab-pane.bslib-gap-spacing {
#         gap: 0.7rem !important;
#     }
#     .dash-banner h1 {
#         font-size: 36px;
#         font-weight: 800;
#         margin: 0;
#     }
#     .dashboard-subtitle {
#     font-size: 1.25rem;
#     font-style: italic;
#     color: #FF9B85;
#     margin-top: 5px;
#     }
#     .brand { text-align: right; }
#     .brand .brand-name { font-size: 20px; font-weight: 800; color: #ffffff;}
#     .brand .brand-bars { margin-top: 6px; }
#     .brand .bar {
#         display: inline-block;
#         height: 6px;
#         border-radius: 4px;
#         vertical-align: middle;
#     }
#     .brand .bar-red   { width: 46px; background:#EE6055; }
#     .brand .bar-yellow{ width: 34px; background:#FFD97D; margin-left:6px; }
#     .brand .bar-dot   { width: 6px;  background:#ffffff; margin-left:6px; }
 
#     /* Metric value boxes */
#     .metric-card .card-title { font-size: 20px; font-weight: 700; }
 
#     /* Section cards */
#     .section-card .card-header {
#         font-size: 22px;
#         font-weight: 700;
#         background-color: #ffffff;
#         border-bottom: none;
#     }
#     """
# )
