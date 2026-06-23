"""
Stellar Education - Student "My Practice Plan" view (core logic).
 
This module is the data-and-visualization layer behind the student-facing
"Next Steps & Training Agenda" page of the Stellar Education Student View dashboard. It loads
the Bayesian Knowledge Tracing (BKT) mastery predictions together with the
modeling-KC (MKC) prerequisite graph, then exposes helper functions that the
Shiny app calls to render the page.
 
The page is built from four pieces:
 
1. KPI value boxes (KCs mastered, exam readiness, level, blocked KCs);
2. a unit-level prerequisite Sankey overview, with per-unit drill-down;
3. a weight-ranked, prerequisite-aware training agenda; and
4. the HTML for the agenda cards.
 
All logic operates at the modeling-KC (MKC) grain. A student's "mastery" of an
MKC is the BKT ``state_predictions`` value from their most recent attempt on
that MKC, classified against ``MASTERY_THRESHOLD``.
 
Notes
-----
Data sources are resolved from environment variables (loaded from a local
``.env`` file):
 
- ``FINAL_FILE``  : processed per-student, per-attempt BKT predictions (CSV).
- ``KC_MAP_FILE`` : modeling-KC nodes and edges (Excel workbook with the
  ``Modeling_KC_Nodes`` and ``Modeling_KC_Edges`` sheets).
"""

####################################################################################
### CORE ALGOTHIRMS 
####################################################################################
from pathlib import Path
import numpy as np
import re
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import os
from dotenv import load_dotenv

load_dotenv()


####################################################################################
### Basic Configs
####################################################################################
MASTERY_THRESHOLD = 0.65   

# Band cutoffs for "Your Level" (applied to the exam-readiness score)
PROGRESSING_CUTOFF = 0.35


BANDS = [("Mastered", MASTERY_THRESHOLD), ("Progressing", PROGRESSING_CUTOFF)] 
# Background colours for the KPI cards / bands
BAND_BG = {"Mastered": "#60D394","Progressing": "#FECD54", "Needs Practice": "#EE6055"} 

def band_color(p: float | None) -> str:
    """Map a mastery probability to its band colour.

    Parameters
    ----------
    p : float or None
        Mastery probability in ``[0, 1]``. ``None`` or ``NaN`` is treated as
        "not attempted".
    
    Returns
    -------
    str
        A hex colour string: grey for not-attempted, green at or above
        ``MASTERY_THRESHOLD``, amber at or above ``PROGRESSING_CUTOFF``, and red
        below that.
    """
    """Grey = not attempted; green/amber/red by mastery band (for graph nodes)."""
    if p is None or  pd.isna(p) or  (isinstance(p, float) and np.isnan(p)):
        return "#C9CDD2"
    if p >= MASTERY_THRESHOLD:
        return "#60D394"
    if p >= PROGRESSING_CUTOFF:
        return "#FFD97D"
    return "#EE6055"


####################################################################################
### File paths and data loading 
####################################################################################
DATA_DIR = Path("data")
base_path = Path().resolve()
file_path = base_path / "data" / "processed" 
raw_path = base_path / "data" / "raw"
final_file = os.environ["FINAL_FILE"]
kc_map_file = os.environ["KC_MAP_FILE"]

# student_df : long table of student observations and BKT predictions, one row per student-attempt.
# nodes_df   : one row per modeling KC (id, label, unit, ...).
# edges_df   : one row per MKC -> MKC prerequisite edge.

student_df = pd.read_csv(file_path / final_file)
nodes_df = pd.read_excel(raw_path / kc_map_file, sheet_name="Modeling_KC_Nodes")
edges_df = pd.read_excel(raw_path / kc_map_file, sheet_name="Modeling_KC_Edges")

# Coerce the model/dashboard numeric columns; stray strings become NaN.
for col in ["weight", "estimated_exam_share_pct", "downstream_dependents",
            "direct_dependents", "order_id", "state_predictions",
            "correct_predictions", "correct"]:
    if col in student_df.columns:
        student_df[col] = pd.to_numeric(student_df[col], errors="coerce")

"""
    Make sure every edge has a numeric fine_edge_count; clean up any wrong values, 
    and default to 1 if the column or a value is missing,
    so the Sankey always has a valid thickness for every link."
"""
if "fine_edge_count" in edges_df.columns:
    # column exists: coerce to numbers, and treat bad/missing values as 1
    edges_df["fine_edge_count"] = pd.to_numeric(
        edges_df["fine_edge_count"], errors="coerce"
    ).fillna(1)
else:
    # column missing: every edge gets a default thickness of 1
    edges_df["fine_edge_count"] = 1
    
# edges_df["fine_edge_count"] = (
#     pd.to_numeric(edges_df.get("fine_edge_count", 1), errors="coerce").fillna(1)
#     if "fine_edge_count" in edges_df.columns else 1)


####################################################################################
### VARIABLES 
####################################################################################
# MKC labels / units from the Nodes sheet.
LABELS = dict(zip(nodes_df["modeling_kc_id"], nodes_df["modeling_kc_label"]))
MKC_UNIT = dict(zip(nodes_df["modeling_kc_id"], nodes_df.get("unit", pd.Series())))

# Total number of MKCs in the whole curriculum (denominator for "X / N").
TOTAL_MKCS = nodes_df["modeling_kc_id"].nunique()

# Prerequisite graph: directed edge source MKC --> target MKC.
G = nx.DiGraph()
G.add_edges_from(zip(edges_df["source_modeling_kc_id"], 
                    edges_df["target_modeling_kc_id"]))

# All student ids, for the dropdown.
STUDENT_IDS = sorted(student_df["student_id"].astype(str).unique().tolist())

def _unit_key(u: str) -> tuple[int, str]:
    """Sort key that orders unit labels by their embedded number.

    Parameters
    ----------
    u : str
        A unit label such as ``"Unit 2"`` or ``"Unit 10"``.

    Returns
    -------
    tuple of (int, str)
        ``(number, label)``, so ``"Unit 2"`` sorts before ``"Unit 10"``.
        Labels with no number sort last (number ``999``).
    """
    m = re.search(r"(\d+)", str(u))
    return (int(m.group(1)) if m else 999, str(u))

# All unit labels, sorted by unit number if possible (for the dropdown).
UNIT_LIST = sorted({u for u in MKC_UNIT.values() if isinstance(u, str)}, key=_unit_key)
OVERVIEW_LABEL = "Overview: All Units"


def student_mkc_table(student_id: str | int) -> pd.DataFrame:
    """Build the per-student MKC table: latest mastery plus MKC attributes.

    For each MKC the student has attempted, keep only their most recent attempt
    (latest ``order_id``), since BKT is sequential and the last estimate is the
    current belief.

    Parameters
    ----------
    student_id : str or int
        The student identifier to filter on (compared as a string).

    Returns
    -------
    pandas.DataFrame
        One row per attempted MKC with columns (where available):
        ``modeling_kc_id``, ``mastery`` (renamed from ``state_predictions``),
        ``weight``, ``tier``, ``downstream`` (from ``downstream_dependents``),
        ``direct`` (from ``direct_dependents``), ``exam_share`` (from
        ``estimated_exam_share_pct``), ``label`` and ``unit``. An empty frame is
        returned if the student has no rows.
    """
    #s = student_df[student_df["student_id"].astype(str) == str(student_id)].copy()
    key = str(student_id).strip().upper()
    ids = student_df["student_id"].astype(str).str.strip().str.upper()
    s = student_df[ids == key].copy()
    
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


def exam_readiness(tbl: pd.DataFrame, mastery_col: str = "mastery", weight_col: str = "weight") -> float:
    """Compute a single weight-weighted average mastery (exam-readiness score).

    Defined as ``sum(mastery * weight) / sum(weight)`` so that Stellar Education's
    high-weight KCs move the score more than low-weight ones. Rows with missing
    mastery are dropped first.

    Parameters
    ----------
    tbl : pandas.DataFrame
        Per-student MKC table (e.g. from :func:`student_mkc_table`).
    mastery_col : str, optional
        Column holding mastery probabilities. Default ``"mastery"``.
    weight_col : str, optional
        Column holding the KC importance weights. Default ``"weight"``.

    Returns
    -------
    float
        The readiness score in ``[0, 1]``. Falls back to a plain mean of mastery
        if there is no weight column or the weights sum to zero, and returns
        ``0.0`` if the table is empty after dropping missing mastery.
    """
    tbl = tbl.dropna(subset=[mastery_col])
    if tbl.empty:
        return 0.0
    if weight_col not in tbl.columns:
        return float(tbl[mastery_col].mean())
    w = tbl[weight_col].fillna(0)
    if w.sum() == 0:
        return float(tbl[mastery_col].mean())
    return float(np.average(tbl[mastery_col], weights=w))


def level_band(score: float) -> tuple[str, str]:
    """Classify a mastery / readiness score into a named band.

    Parameters
    ----------
    score : float
        A mastery or readiness score in ``[0, 1]``.

    Returns
    -------
    tuple of (str, str)
        ``(band_name, hex_colour)``. Bands are checked high-to-low against
        :data:`BANDS`; the first cutoff the score clears wins, otherwise the
        ``"Needs Practice"`` fallback is returned."""
    for name, cutoff in BANDS:
        if score >= cutoff:
            return name, BAND_BG[name]
    return "Needs Practice", BAND_BG["Needs Practice"]


def _unmastered_prereqs(kc: str, mastery_map: dict[str, float]) -> list[str]:
    """List the direct prerequisites of an MKC that are not yet mastered.

    Parameters
    ----------
    kc : str
        Modeling-KC id to inspect.
    mastery_map : dict
        Mapping ``modeling_kc_id -> mastery`` for the current student. KCs absent
        from the map are treated as mastery ``0.0`` (not mastered).
        
    Returns
    -------
    list of str
        The prerequisite MKC ids whose mastery is below ``MASTERY_THRESHOLD``.
        Empty if ``kc`` is not in the graph.
    """
    if kc not in G:
        return []
    return [pr for pr in G.predecessors(kc)
            if mastery_map.get(pr, 0.0) < MASTERY_THRESHOLD]


def find_blocked(mastery_map: dict[str, float]) -> list[str]:
    """Find MKCs that are unmastered *and* still have an unmastered prerequisite.

    Parameters
    ----------
    mastery_map : dict
        Mapping ``modeling_kc_id -> mastery`` for the current student.

    Returns
    -------
    list of str
        MKC ids that the student cannot fairly tackle yet (below threshold and
        gated by at least one unmastered prerequisite).
    """
    return [kc for kc, p in mastery_map.items()
            if p < MASTERY_THRESHOLD and _unmastered_prereqs(kc, mastery_map)]


def _norm(x: pd.Series) -> pd.Series:
    """Min-max normalize a numeric Series to ``[0, 1]``.

    Parameters
    ----------
    x : pandas.Series
        Values to normalize; ``NaN`` is treated as ``0``.

    Returns
    -------
    pandas.Series
        The input rescaled so the smallest value maps to 0 and the largest to 1.
        When every value is identical, there is no range to scale against, so the
        function returns 0.5 for all of them instead of dividing by zero.
    """
    x = x.fillna(0).astype(float)
    rng = x.max() - x.min()
    return (x - x.min()) / rng if rng > 0 else pd.Series(0.5, index=x.index)


def build_agenda(tbl: pd.DataFrame, n: int = 3) -> list[dict[str, object]]:
    """Build the student's top-``n`` "next steps" recommendation cards.

    Strategy
    --------
    1. Consider only WEAK topics (mastery below ``MASTERY_THRESHOLD``); mastered
    ones need no action.
    2. Split weak topics into READY (all prerequisites already mastered, so the
    student can tackle them now) versus BLOCKED (still missing a prerequisite).
    3. Rank the READY ones by the priority score below and take ``n``.
    4. If fewer than ``n`` are ready, top up with the highest-``weight`` BLOCKED
    topics so the agenda always shows ``n`` cards; these are badged "locked" and 
    list the prerequisites to clear first.

    Priority score (ready topics only)
    -----------------------------------
    ``score = normalized weight`` -- the partner's importance score is the sole
    ranking signal, reflecting the stated business priority.

    Parameters
    ----------
    tbl : pandas.DataFrame
        Per-student MKC table (e.g. from :func:`student_mkc_table`).
    n : int, optional
        Number of cards to return. Default ``3``.

    Returns
    -------
    list of dict
        One dict per card with keys: ``name``, ``mastery``, ``weight``, ``tier``,
        ``downstream`` (count), ``atype`` and ``badge`` (recommendation type),
        ``ready`` (bool), ``missing`` (prerequisite labels for locked cards), and
        ``unlocks`` (list of ``(label, is_mastered)`` for downstream topics).
        Empty list if there is nothing weak to recommend.
    """
    if tbl.empty:
        return []
    
    # Fast lookup: modeling_kc_id; this student's mastery.
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
        elif p >= PROGRESSING_CUTOFF:
            atype, badge = "quickwin", "🎯 Almost there"
        elif dn >= 3:
            atype, badge = "unblock", "🔓 Key unlock"
        else:
            atype, badge = "foundation", "🏗 Foundation"

        # Downstream topics this one unlocks (for the card's "Will unlock" list).
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


####################################################################################
### GRAPH BUILDERS 
####################################################################################

def _style(fig):
    """Apply the shared, responsive Plotly layout to a figure.

    Sets ``autosize`` (no fixed height, so the figure fills an expandable panel),
    tight margins, base font, and white backgrounds.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure
        The figure to style, modified in place.

    Returns
    -------
    plotly.graph_objects.Figure
        The same figure, for chaining.
    """
    fig.update_layout(autosize=True, margin=dict(l=8, r=8, t=8, b=8),
                    font=dict(size=12), paper_bgcolor="white", plot_bgcolor="white")
    return fig


def _unit_avg(unit:str, mastery_map: dict[str, float]) -> float | None:
    """Average a student's mastery across the attempted MKCs in one unit.

    Parameters
    ----------
    unit : str
        Unit label (e.g. ``"Unit 3"``).
    mastery_map : dict
        Mapping ``modeling_kc_id -> mastery`` for the current student.

    Returns
    -------
    float or None
        Mean mastery over the unit's MKCs that have a (non-``NaN``) value, or
        ``None`` if the student has attempted none of them.
    """
    vals = [mastery_map[k] for k, u in MKC_UNIT.items() 
            if u == unit and k in mastery_map and pd.notna(mastery_map[k])]
    return sum(vals) / len(vals) if vals else None


def build_unit_sankey(mm):
    """Build the unit-level prerequisite Sankey (overview).

    Nodes are course units, coloured by the student's average mastery in each
    unit. Links aggregate the cross-unit prerequisite edges (within-unit edges
    are omitted), with link value summing ``fine_edge_count``.

    Parameters
    ----------
    mm : dict
        Mapping ``modeling_kc_id -> mastery`` for the current student.

    Returns
    -------
    plotly.graph_objects.Figure
        A styled Sankey figure giving a high-level, unit-to-unit view.
    """
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
    """Build the drill-down Sankey for a single unit.

    Shows the selected unit's MKCs plus their immediate graph neighbours
    (predecessors and successors), with the prerequisite edges among that node
    set. Neighbour nodes from other units are annotated with their unit name.

    Parameters
    ----------
    unit : str
        The unit label to drill into.
    mm : dict
        Mapping ``modeling_kc_id -> mastery`` for the current student.

    Returns
    -------
    plotly.graph_objects.Figure
        A styled Sankey for the unit; if no prerequisite links touch the unit, a
        figure with an explanatory annotation is returned instead.
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
    idx = {node_name: i for i, node_name in enumerate(nodes)}
    labels = [LABELS.get(node_name, node_name) + ("" if MKC_UNIT.get(node_name) == unit
            else f"  ·{MKC_UNIT.get(node_name)}") for node_name in nodes]
    colors = [band_color(mm.get(node_name)) for node_name in nodes]
    hover = [f"{LABELS.get(node_name, node_name)}<br>Mastery: " +
            ("Not attempted" if mm.get(node_name) is None or pd.isna(mm.get(node_name))
            else f"{mm.get(node_name):.0%}") 
            for node_name in nodes]
    
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
    """
    Render the training-agenda cards as an HTML string.

    Calls :func:`build_agenda` and lays the items out as a three-column grid of
    cards. Each card shows the topic, a recommendation badge, current mastery (a
    progress bar), concrete next-step bullets, any prerequisites still to clear,
    and the downstream topics it will unlock (first four inline, the rest behind
    an expandable ``<details>``).

    Parameters
    ----------
    tbl : pandas.DataFrame
        Per-student MKC table (e.g. from :func:`student_mkc_table`).

    Returns
    -------
    str
        An HTML fragment for embedding via ``ui.HTML``. If nothing is weak, a
        short celebratory message is returned instead.
    """
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
        
        # ── Next-step bullets ─────────────────────────────────────────────────
        # Two strategies are kept here; ONE is active at a time.
        #
        # OPTION A (inactive, commented out below): choose advice by MASTERY level.
        #   Note: every agenda card is already weak (mastery < MASTERY_THRESHOLD),
        #   so the tiers barely differ and all cards tend to look the same.
        #
        # OPTION B (ACTIVE): choose advice by the BADGE (atype), i.e. WHY the card
        #   was recommended. The badge varies across cards, so each gets distinct,
        #   relevant advice. To switch strategies, comment this block and
        #   uncomment Option A.

        ####################################################################################
        #### OPTION A: by mastery level (inactive)
        #####################################################################################
        # if pct >= PROGRESSING_CUTOFF:
        #     bullets = ["Review the few items you missed here.",
        #                "Redo homework questions below 60%.",
        #                "Ask your teacher about the hardest part."]
        # else:
        #     bullets = ["Start from the scaffolded examples.",
        #                "Watch a short explainer for this concept.",
        #                "Build the basics before moving on."]

        ####################################################################################
        #### OPTION B: by badge / recommendation type (active)
        #####################################################################################
        if it["atype"] == "locked":
            bullets = ["First master the prerequisite skills listed below.",
                        "Come back to this once those are green.",
                        "Ask your teacher if you're unsure where to start."]
        elif it["atype"] == "quickwin":
            bullets = ["You're close! Review the items you missed here.",
                        "Redo the practice questions you got wrong.",
                        "Try one exam-style question on this skill."]
        elif it["atype"] == "unblock":
            bullets = ["Spend focused practice on this — it unlocks several later topics.",
                        "Work through the worked examples step by step.",
                        "Ask your teacher to check your understanding."]
        else:  # foundation
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
                fg = "#9aa0a6" if mastered else "#185FA5" # text:  grey if mastered, blue if not
                bgc = "#f1f3f4" if mastered else "#E6F1FB" # box:   light grey if mastered, light blue if not
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
                            f"<div style='font-size:10.5px;color:#aaa;margin-bottom:4px'>"
                            f"<span style='color:#185FA5'>■</span> still to learn &nbsp; "
                            f"<span style='color:#9aa0a6'>■</span> already covered</div>"
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
            <div style="text-align:right;font-size:11px;color:#bbb;margin-top:2px">Target {MASTERY_THRESHOLD:.0%}</div>
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
# Page-level CSS injected into the Shiny UI: dark banner, compact coloured KPI
# value boxes, section-card headers, and tighter tab spacing.
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
    
    /* friendly hover tooltip */
    .info-tip {
        position:relative; cursor:help; display:inline-block;
        width:18px; height:18px; line-height:18px; text-align:center;
        border-radius:50%; background:#185FA5; color:#fff;
        font-size:12px; font-weight:700; margin-left:6px;
    }
    .info-tip:hover::after {
        content: attr(data-tip);
        position:absolute; left:24px; top:-6px; z-index:100;
        width:240px; padding:10px 12px;
        background:#20303d; color:#fff; font-size:12px; font-weight:400;
        line-height:1.5; border-radius:8px;
        box-shadow:0 4px 14px rgba(0,0,0,0.22);
        white-space:normal;
    }
""")

# Dark page banner with the dashboard title and the Stellar Education brand mark.
banner = ui.div(
    ui.h1("Your Progress Dashboard"),
    ui.div(ui.div("Stellar Education", class_="brand-name"),
        ui.div(ui.span(class_="bar bar-red"), ui.span(class_="bar bar-yellow"),
                ui.span(class_="bar bar-dot"), style="margin-top:6px"),
           class_="brand"),
    class_="dash-banner")

# Student selector; the rest of the page reacts to the chosen student id.
student_picker = ui.div(
    ui.input_select("student", "Student:", choices=STUDENT_IDS,
                    selected=STUDENT_IDS[0] if STUDENT_IDS else None, width="220px"),
    class_="student-pick")