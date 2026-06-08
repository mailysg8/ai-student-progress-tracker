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
    if p is None or (isinstance(p, float) and np.isnan(p)):
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

# All student ids, for the dropdown.
STUDENT_IDS = sorted(student_df["student_id"].astype(str).unique().tolist())

def _unit_key(u):
    """
    Helper to sort unit labels by their number if possible (e.g. "Unit 2" before "Unit 10"). 
    """
    m = re.search(r"(\d+)", str(u))
    return (int(m.group(1)) if m else 999, str(u))

# All unit labels, sorted by unit number if possible (for the dropdown).
UNIT_LIST = sorted({u for u in MKC_UNIT.values() if isinstance(u, str)}, key=_unit_key)
OVERVIEW_LABEL = "Overview: All Units"

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