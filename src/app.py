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
           "Emerging": "#C77F0A", "Developing": "#C0392B"}


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
base_path = Path().resolve().parent
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
    """OVERVIEW: nodes = units (colour = avg mastery), links = cross-unit prereqs."""
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
                hovertemplate="%{source.label} → %{target.label}: %{value} links<extra></extra>")))
    return _style(fig)


def build_unit_detail_sankey(unit, mm):
    """DRILL-DOWN: a unit's MKCs + immediate neighbours (few nodes, readable)."""
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
                value=[v for _, _, v in pairs], color="rgba(170,175,180,0.35)", hovercolor="#80ffdb")))
    return _style(fig)


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


custom_css = ui.tags.style(
    """
    /* App background */
    body { background-color: #263744; }
 
    /* Dark banner header inside the dashboard page */
    .dash-banner {
        background-color: #263744;
        color: #ffffff;
        padding: 18px 24px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1px;
    }
    /* Kill the default top margin/gutter Bootstrap adds to the metric row */
    .metric-row {
        margin-top: 0 !important;
        --bs-gutter-y: 0;
    }
    .tab-pane.bslib-gap-spacing {
        gap: 0.7rem !important;
    }
    .dash-banner h1 {
        font-size: 36px;
        font-weight: 800;
        margin: 0;
    }
    .dashboard-subtitle {
    font-size: 1.25rem;
    font-style: italic;
    color: #FF9B85;
    margin-top: 5px;
    }
    .brand { text-align: right; }
    .brand .brand-name { font-size: 20px; font-weight: 800; color: #ffffff;}
    .brand .brand-bars { margin-top: 6px; }
    .brand .bar {
        display: inline-block;
        height: 6px;
        border-radius: 4px;
        vertical-align: middle;
    }
    .brand .bar-red   { width: 46px; background:#EE6055; }
    .brand .bar-yellow{ width: 34px; background:#FFD97D; margin-left:6px; }
    .brand .bar-dot   { width: 6px;  background:#ffffff; margin-left:6px; }
 
    /* Metric value boxes */
    .metric-card .card-title { font-size: 20px; font-weight: 700; }
 
    /* Section cards */
    .section-card .card-header {
        font-size: 22px;
        font-weight: 700;
        background-color: #ffffff;
        border-bottom: none;
    }
    """
)


banner = ui.div(
    ui.div(
        ui.h1("Welcome to Your Progress Dashboard"),
        ui.p("Let's see what you've accomplished!", class_="dashboard-subtitle"),
    ),
    ui.div(
        ui.div("Stellar Education", class_="brand-name"),
        ui.div(
            ui.span(class_="bar bar-red"),
            ui.span(class_="bar bar-yellow"),
            ui.span(class_="bar bar-dot"),
            class_="brand-bars",
        ),
        class_="brand"
    ),
    class_="dash-banner",
)

########## This is for the KPI metric cards on the "Your Next Steps" page ##########
metric_cards = ui.layout_columns(
    ui.value_box(
        "KCs Mastered",
        ui.output_text("kcs_mastered"),
        class_="metric-card",
    ),
    ui.value_box(
        "Overall Accuracy",
        ui.output_text("overall_accuracy"),
        class_="metric-card",
    ),
    ui.value_box(
        "Prior Performance Band",
        ui.output_text("prior_performance_band"),
        class_="metric-card",
    ),
    ui.value_box(
        "Blocked KCs",
        ui.output_text("blocked_kcs"),
        class_="metric-card",
    ),
    col_widths=(3, 3, 3, 3),
    fill=False,
    class_="metric-row",
)

kc_graph_card = ui.card(
    ui.card_header("Modules Prerequisite Graph: Your Mastery at a Glance"),
    ui.output_ui("kc_graph"),
    class_="section-card",
    height="320px",
    full_screen=True,
)

next_steps_card = ui.card(
    ui.card_header("\U0001F31F Your Personalized Next Steps & Training Agenda"),
    ui.output_ui("agenda"),
    class_="section-card",
    height="420px",
    full_screen=True,
)


# This is for Sitting's First Page
home_page = ui.nav_panel(
    "Home",
    ui.div(
        ui.div("Stellar Education", class_="brand-name"),
        ui.div(
            ui.span(class_="bar bar-red"),
            ui.span(class_="bar bar-yellow"),
            ui.span(class_="bar bar-dot"),
            class_="brand-bars",
        ),
        class_="brand"
    )
    #banner
)


student_next_steps_page = ui.nav_panel(
    "Your Next Steps",
    banner,
    metric_cards,
    kc_graph_card,
    next_steps_card,
)


app_ui = ui.page_navbar(
    home_page,
    student_next_steps_page,
    #title="Stellar Education",
    header=custom_css,
    fillable=True
)


def server(input, output, session):
    @output
    @render.text
    def kcs_mastered():
        return "12"

    @output
    @render.text
    def overall_accuracy():
        return "85%"

    @output
    @render.text
    def prior_performance_band():
        return "Above Average"

    @output
    @render.text
    def blocked_kcs():
        return "3"
    
    @output
    @render.ui
    def kc_graph_card():
        return ui.div()
    
    @output
    @render.ui
    def next_steps_card():
        return ui.div()



app = App(app_ui, server)