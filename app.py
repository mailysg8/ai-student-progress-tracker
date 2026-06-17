import pandas as pd
import altair as alt
from shiny import App, ui, render, reactive, req
from shinywidgets import render_altair, output_widget, reactive_read
from src.kc_mastery_box import kc_mastery_box
from src.classify import classify
from src.unit_mastery_box import unit_mastery
from src.opportunity_heatmap import opp_heatmap, opportunity_table, compute_opportunity_counts 
from src.student_status_boxes import student_status_boxes, compute_quantile_cuts
from src.student_mastery_table import student_mastery_table
from src.modal_builds import build_kc_modal, build_total_kc_modal
from src.kc_opp import kc_opp_highest, kc_opp_lowest, kc_opp_rank
from src.kc_value_box import kpi_value_box
from src.student_card import student_kc_card
from src.data_import import build_card
from src.data_processing import merge_kc_mapping, merge_weights, merge_class_plan, merge_bkt_predictions, run_bkt_predictions, save_final_output

STU_OBS_COLS = [
    "student_id", "assignment_id", "class_num", "observation_id",
    "source_question", "primary_kc_id", "score", "max_score"
]
CLASS_PLAN_COLS = ["class_date", "homework_id"]
KC_MAP_COLS = [
    "fine_kc_id", "fine_kc_label", "modeling_kc_id",
    "modeling_kc_label", "modeling_unit"
]
WEIGHTS_COLS = [
    "rank", "modeling_kc_id", "modeling_kc_label",
    "unit", "topic_group", "weight", "tier", "estimated_exam_share_pct"
]

DATASETS = {
    "stu":     ("Student Observations", STU_OBS_COLS),
    "class":   ("Class Plan",           CLASS_PLAN_COLS),
    "map":     ("KC Map",               KC_MAP_COLS),
    "weights": ("Weights",              WEIGHTS_COLS),
}

def check_required_columns(df: pd.DataFrame, required: list[str]):
    missing = []
    found = []
    for c in required :
        if c not in df.columns :
            missing.append(c)
        else :
            found.append(c)
    return found, missing

# Thresholds for student mastery status
STUDENT_MASTERY_THRESHOLD = 0.65
STUDENT_PRACTICE_THRESHOLD = 0.35

# Thresholds for KC class percentage mastery status
KC_PERC_MASTERY_THRESHOLD = 0.75
KC_PERC_PRACTICE_THRESHOLD = 0.25

N_RANK = 4


## Colour palette
PALETTE = [
    "#263744",
    "#EE6055",
    "#60D394",
    "#AAF683",
    "#FFD97D",
    "#FF9B85",
    "#8B9DBB",
]

# Info icon
icon_title = "Information"
def bs_info_icon(title: str):
    # Enhanced from https://rstudio.github.io/bsicons/ via `bsicons::bs_icon("info-circle", title = icon_title)`
    return ui.HTML(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" class="bi bi-info-circle " style="height:1em;width:1em;fill:currentColor;" aria-hidden="true" role="img" ><title>{title}</title><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"></path><path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"></path></svg>')




app_ui = ui.page_navbar(
# ── Page 1: Class Overview ───────────────────────────────────────────
    ui.nav_panel(
        "Class Overview",
        ui.head_content(
            ui.tags.style("""
                .navbar-nav .nav-link,
                .navbar-nav .nav-link.active {
                    color: #8B9DBB !important;
                }
                
                /* KC tab styling */
                .nav-tabs .nav-link {
                    color: #8B9DBB !important;
                }
                .nav-tabs .nav-link.active {
                    color: #263744 !important;
                    font-weight: 500;
                }
            """)
        ),
        ui.navset_tab(
    # ── Tab 1: General ─────────────────────────────────────────
            ui.nav_panel(
                "General",
        # ── Row 1: value boxes ─────────────────────────────────
                ui.card(
                    ui.card_header(
                                ui.div(
                                    ui.span("Key KC Insights", style="font-size: 22px;"),
                                    ui.tooltip(
                                        bs_info_icon(icon_title),
                                        """
                                        Each box provides insights into the
                                        Knowledge Components (KCs).
                                        For each KC, the proportion of students
                                        with a BKT mastery probability above
                                        the mastery threshold is computed.
                                        Each KC is then assigned a status
                                        based on that proportion. The boxes
                                        display the count of KCs falling into
                                        each status.
                                        """,
                                    ),
                                    style="display: flex; align-items: center; justify-content: space-between; width: 100%;"
                                )
                    ),
                    ui.layout_columns(
                        ui.value_box(
                            "Total KCs",
                            ui.output_text("vb_total"),
                            theme=ui.value_box_theme(bg="#8B9DBB", fg="#263744"),
                            id="vb_total_box",
                            style="cursor: pointer;",
                        ),
                        ui.output_ui("vb_mastered_box"),
                        ui.output_ui("vb_progressing_box"),
                        ui.output_ui("vb_needs_box"),
                        col_widths=3,
                        col_heights=2,
                    ),

                    # JS: wire up click events for all 4 boxes
                    ui.tags.script("""
                        document.addEventListener('DOMContentLoaded', () => {
                            const boxes = {
                                'vb_total_box':      'vb_total_clicked',
                                'vb_mastered_box':   'vb_mastered_clicked',
                                'vb_progressing_box':'vb_progressing_clicked',
                                'vb_needs_box':      'vb_needs_clicked',
                            };
                            Object.entries(boxes).forEach(([id, inputName]) => {
                                const el = document.getElementById(id);
                                if (el) el.addEventListener('click', () => {
                                    Shiny.setInputValue(inputName, Math.random());
                                });
                            });
                        });
                    """),
                ),
        # ── Row 2 - Left Column ──────────────────────────────────
                ui.layout_columns(
                    ui.div(
            # ── Unit mastery grid ────────────────────────────
                        ui.card(
                            ui.card_header(
                                ui.div(
                                    ui.span("Unit Mastery Overview", style="font-size: 22px;"),
                                    ui.tooltip(
                                        bs_info_icon(icon_title),
                                        """
                                        Each square is a Knowledge Component (KC). 
                                        Green = class has largely mastered it, yellow = still in progress, red = needs practice.
                                        Use this to spot which units may require additional support.
                                        """,
                                    ),
                                    style="display: flex; align-items: center; justify-content: space-between; width: 100%;"
                                )
                            ),
                            output_widget("unit_mastery_chart"),
                            style="height: 650px; overflow-y: auto;",
                        ),
            # ── KC Opportunities ────────────────────────────
                        ui.card(
                            ui.card_header(
                                ui.div(
                                    ui.span("KC Opportunities", style="font-size: 22px;"),
                                    ui.tooltip(
                                        bs_info_icon(icon_title),
                                        "The KCs where students have had the least practice on average. "
                                        "Consider assigning more questions on these skills.",
                                    ),
                                    style="display: flex; align-items: center; justify-content: space-between; width: 100%;"
                                )
                            ),
                            ui.navset_tab(
                                ui.nav_panel(
                                    "Most Important KCs",
                                    output_widget("rank_opp_table")
                                ),
                                ui.nav_panel(
                                    "Low Practice",
                                    output_widget("low_opp_table")
                                ),
                                ui.nav_panel(
                                    "Well Practiced",
                                    output_widget("high_opp_table")
                                ),
                                ui.nav_panel(
                                    "Search",
                                    ui.input_selectize(
                                        "opp_search",
                                        "Select KCs to view:",
                                        choices=[],          # populated server-side from real KC names
                                        multiple=True,
                                        options={"placeholder": "Type to search for a KC...", "maxItems": 8},
                                    ),
                                    # Dynamic output slots for up to 4 selected KCs
                                    output_widget("search_opp_table"),
                                ),
                                id="opp_tabs",
                            ),
                            style="min-height: 500px;",
                        ),
                    ),
        # ── Row 3 - Right Column : KC Progress ──────────────────────────────
                    ui.card(
                        ui.card_header(
                            ui.div(
                                ui.span("KC Progress", style="font-size: 22px;"),
                                ui.tooltip(
                                    bs_info_icon(icon_title),
                                    """
                                    Each card shows one Knowledge Component (KC). 
                                    Squares represent individual students — green = mastered, yellow = progressing, red = needs practice. 
                                    The progress bar shows the class mastery rate. 
                                    Switch tabs to focus on KCs needing practice or showing good progress.
                                    """,
                                ),
                                style="display: flex; align-items: center; justify-content: space-between; width: 100%;"
                            )
                        ),
                        ui.navset_tab(
                            ui.nav_panel(
                                "Most Important KCs",
                                ui.layout_columns(
                                    *[
                                        ui.card(
                                            ui.card_header(ui.output_text(f"kc_rank_title_{i}"), style="font-size: 16px;"),
                                            output_widget(f"kc_rank_{i}"),
                                        )
                                        for i in range(4)
                                    ],
                                    col_widths=6,   
                                ),
                            ),
                            ui.nav_panel(
                                "Needs Practice",
                                ui.layout_columns(
                                    *[
                                        ui.card(
                                            ui.card_header(ui.output_text(f"kc_low_title_{i}"), style="font-size: 16px;"),
                                            output_widget(f"kc_low_{i}"),
                                        )
                                        for i in range(4)
                                    ],
                                    col_widths=6,   
                                ),
                            ),
                            ui.nav_panel(
                                "Good Progress",
                                ui.layout_columns(
                                    *[
                                        ui.card(
                                            ui.card_header(ui.output_text(f"kc_high_title_{i}"), style="font-size: 16px;"),
                                            output_widget(f"kc_high_{i}"),
                                        )
                                        for i in range(4)
                                    ],
                                    col_widths=6,   
                                ),
                            ),
                            ui.nav_panel(
                                "Search",
                                ui.input_selectize(
                                    "kc_search",
                                    "Select KCs to view:",
                                    choices=[],          
                                    multiple=True,
                                    options={"placeholder": "Type to search for a KC...", "maxItems": 4},
                                ),
                                ui.output_ui("search_results"),
                            ),
                            id="kc_tabs",
                        )
                    ),
                 col_widths=(4,8),
                ),
            ),
    # ── Tab 2 : Opportunity Heatmap ──────────────────────────────────
            ui.nav_panel(
                "Opportunity Heatmap",
                ui.div(
                # -- Student info card
                    ui.card(
                        ui.card_header(
                            ui.output_text("student_kc_card_title")
                        ),
                        output_widget("student_kc_detail"),
                        ui.output_ui("student_kc_card_placeholder"),  
                    ),
                    ui.card(
                        ui.card_header(
                            ui.div(
                                ui.span("Opportunity Heatmap", style="font-size: 22px;"),
                                ui.tooltip(
                                    bs_info_icon(icon_title),
                                    "Shows how many practice opportunities each student has had per KC. "
                                    "Green = well practiced (7+), yellow = some practice (3–6), "
                                    "red = low practice (1–2), blue-grey = not started.",
                                ),
                                style="display: flex; align-items: center; justify-content: space-between; width: 100%;"
                            )
                        ),
                        output_widget("opp_heatmap_plot"),
                        full_screen=True,
                        style="height: 90%;",
                    ),
                    style="height: calc(100vh - 120px); padding: 1rem;",
                )
            )
        )
    ),
# ── Page 2: Student Overview ─────────────────────────────────────────── 
    ui.nav_panel(
        "Student Overview",
        ui.div(
            ui.layout_columns(
                ui.input_select("so_student", "Student", choices=[], width="100%"),
                ui.input_switch("so_quantile", "Relative (quantile) status", value=False),
                ui.input_select(
                    "so_status", "Status",
                    choices=["All statuses", "Mastered", "Progressing", "Needs Practice"],
                    selected="All statuses", width="100%",
                ),
                col_widths=(5, 3, 4),
            ),
            ui.card(
                ui.card_header(ui.span("Status summary", style="font-size: 22px;")),
                output_widget("so_status_boxes"),
                style="height: 200px;",
            ),
            ui.card(
                ui.card_header(ui.span("P(Mastery) by KC", style="font-size: 22px;")),
                output_widget("so_mastery_table"),
                full_screen=True,
                style="min-height: 400px; overflow-y: auto;",
            ),
            style="padding: 1rem;",
        ),
    ),
    ui.nav_panel(
        "Data Input",
        ui.tags.link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css"
        ),
        ui.div(
            ui.input_file(
                "files", "Upload CSV files",
                accept=[".csv"], multiple=True, width="100%"
            ),
            ui.output_ui("master_status"),
            style="margin-bottom:1.5rem;"
        ),
        ui.layout_columns(
            ui.output_ui("card_stu"),
            ui.output_ui("card_class"),
            ui.output_ui("card_map"),
            ui.output_ui("card_weights"),
            col_widths=(3, 3, 3, 3),
        ),
        ui.output_ui("dataframes_ready"),
        ui.div(
            ui.input_action_button("process_btn", "Preprocess data"),
            ui.input_action_button("save_btn", "Save and update dashboard"),
            ui.output_ui("processing_status"),
            style="display:flex;align-items:center;gap:12px;margin-top:1rem;"
        ),
    ),

    title=ui.tags.span("Stellar Education", style="color: white;"),
    navbar_options=ui.navbar_options(bg="#263744"),
)



def server(input, output, session):
    # ── the live, in-memory dataset the whole dashboard reads from ──────────
    mkc_data_rv = reactive.value(pd.read_csv('data/processed/final_student_kc_data.csv'))

    def mkc_data():
        return mkc_data_rv()
    
    @reactive.calc
    def kc_list_rank():
        return list(
            mkc_data()
            .groupby(['modeling_kc_label', 'rank'])
            .count()
            .sort_values('rank')
            .reset_index()
            .loc[0:N_RANK, 'modeling_kc_label']
        )

    @reactive.calc
    def student_ids():
        return sorted(mkc_data()["student_id"].unique().tolist())

    @reactive.calc
    def quantile_cuts():
        return compute_quantile_cuts(mkc_data())
    
    # ── shared pre-computed data ─────────────────────────────────────────
    @reactive.calc
    def last_attempt():
        return (
            mkc_data()
            .groupby(['student_id', 'modeling_kc_id'])
            .last()
            .reset_index()
        )

    @reactive.calc
    def first_attempt():
        return (
            mkc_data()
            .groupby(['student_id', 'modeling_kc_id'])
            .first()
            .reset_index()
        )

    @reactive.calc
    def opp_counts():
        return compute_opportunity_counts(mkc_data())

    @reactive.calc
    def last_kc_summary():
        df = (
            last_attempt()
            .groupby(['unit', 'modeling_kc_id', 'modeling_kc_label'])['state_predictions']
            .apply(lambda x: (x >= STUDENT_MASTERY_THRESHOLD).mean())
            .reset_index()
            .rename(columns={'state_predictions': 'pct_mastered'})
        )
        df['status'] = df['pct_mastered'].apply(classify, args=(KC_PERC_MASTERY_THRESHOLD, KC_PERC_PRACTICE_THRESHOLD))
        return df
    
    @reactive.calc
    def first_kc_summary():
        df = (
            first_attempt()
            .groupby(['unit', 'modeling_kc_id', 'modeling_kc_label'])['state_predictions']
            .apply(lambda x: (x >= STUDENT_MASTERY_THRESHOLD).mean())
            .reset_index()
            .rename(columns={'state_predictions': 'pct_mastered'})
        )
        df['status'] = df['pct_mastered'].apply(classify,args=(KC_PERC_MASTERY_THRESHOLD, KC_PERC_PRACTICE_THRESHOLD))
        return df
    
    @reactive.calc
    def kc_list_lowest():
        """Bottom 4 KCs by class mastery percentage."""
        return (
            last_kc_summary()
            .sort_values('pct_mastered', ascending=True)
            .head(4)['modeling_kc_label']
            .tolist()
        )
    
    @reactive.calc
    def kc_list_highest():
        """Top 4 KCs by class mastery percentage."""
        return (
            last_kc_summary()
            .sort_values('pct_mastered', ascending=False)
            .head(4)['modeling_kc_label']
            .tolist()
        )
    

    # ── value boxes ──────────────────────────────────────────────────────
    ## Values
    @render.ui
    def vb_mastered_box():
        last_df  = last_kc_summary()
        first_df = first_kc_summary()
        return kpi_value_box(
            data        = last_attempt(),
            status      = "Mastered",
            theme       = ui.value_box_theme(bg="#60D394", fg="#263744"),
            value_now   = int((last_df['status'] == 'Mastered').sum()),
            value_first = int((first_df['status'] == 'Mastered').sum()),
        )

    @render.ui
    def vb_progressing_box():
        last_df  = last_kc_summary()
        first_df = first_kc_summary()
        return kpi_value_box(
            data        = last_attempt(),
            status      = "Progressing",
            theme       = ui.value_box_theme(bg="#FFD97D", fg="#263744"),
            value_now   = int((last_df['status'] == 'Progressing').sum()),
            value_first = int((first_df['status'] == 'Progressing').sum()),
        )

    @render.ui
    def vb_needs_box():
        last_df  = last_kc_summary()
        first_df = first_kc_summary()
        return kpi_value_box(
            data        = last_attempt(),
            status      = "Needs Practice",
            theme       = ui.value_box_theme(bg="#FF9B85", fg="#263744"),
            value_now   = int((last_df['status'] == 'Needs Practice').sum()),
            value_first = int((first_df['status'] == 'Needs Practice').sum()),
        )


    @render.text
    def vb_total():
        return str(len(last_kc_summary()))
    
    ## Pop up after clicking on box
    # --- Total KCs modal ---
    @reactive.effect
    @reactive.event(input.vb_total_clicked)
    def modal_total():
        df = last_kc_summary()
        n = len(df)
        ui.modal_show(ui.modal(
            build_total_kc_modal(df),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#8B9DBB;"),
                f"All KCs — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True,
            size="l",
            footer=None,
        ))
    
    # --- Mastered modal ---
    @reactive.effect
    @reactive.event(input.vb_mastered_clicked)
    def modal_mastered():
        df = last_kc_summary()   
        n = len(df[df["status"] == "Mastered"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Mastered", mastery=KC_PERC_MASTERY_THRESHOLD, practice=KC_PERC_PRACTICE_THRESHOLD),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#60D394;"),
                f"Skills Mastered — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True, size="l", footer=None,
        ))

    # --- Progressing modal ---
    @reactive.effect
    @reactive.event(input.vb_progressing_clicked)
    def modal_progressing():
        df = last_kc_summary()
        n = len(df[df["status"] == "Progressing"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Progressing",mastery=KC_PERC_MASTERY_THRESHOLD, practice=KC_PERC_PRACTICE_THRESHOLD),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#FFD97D;"),
                f"Skills Progressing — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True, size="l", footer=None,
        ))

    # --- Needs Practice modal ---
    @reactive.effect
    @reactive.event(input.vb_needs_clicked)
    def modal_needs():
        df = last_kc_summary()
        n = len(df[df["status"] == "Needs Practice"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Needs Practice", mastery=KC_PERC_MASTERY_THRESHOLD, practice=KC_PERC_PRACTICE_THRESHOLD),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#FF9B85;"),
                f"Skills Needing Practice — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True, size="l", footer=None,
        ))


    # ── unit mastery grid ────────────────────────────────────────────────
    @output
    @render_altair
    def unit_mastery_chart():
        return unit_mastery(last_attempt(), mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)

    # ── opportunity heatmap ──────────────────────────────────────────────
    @output
    @render_altair
    def opp_heatmap_plot():
        return opp_heatmap(mkc_data())
    
        # ── stores the last clicked student + KC ────────────────────────────
    selected_tile = reactive.Value(None)

    @reactive.effect
    def _on_tile_click():
        sel = reactive_read(opp_heatmap_plot.widget, "_vl_selections")
        if not sel:
            return
        store = sel.get("kc_click", {}).get("store", [])
        if not store:
            return
        values     = store[0]["values"]
        kc_name    = values[0]
        student_id = values[1]

        selected_tile.set({"kc": kc_name, "student": student_id})


    # ── card title (hidden until something is clicked) ───────────────────
    @render.text
    def student_kc_card_title():
        sel = selected_tile.get()
        
        if sel is None:
            return ""
        
        df = mkc_data()
        # Look up the unit for this student/KC
        row = df[
            (df["student_id"] == sel['student']) &
            (df["modeling_kc_label"] == sel['kc'])
        ]
        unit = row["unit"].iloc[0] if not row.empty else ""
        return f"{sel['student']}  ·  {sel['kc']} · {unit}"

    # ── placeholder message before first click ──────────────────────────
    @render.ui
    def student_kc_card_placeholder():
        if selected_tile.get() is not None:
            return ui.tags.div()   # empty — card is showing
        return ui.p(
            "Click any tile on the heatmap to see how a student is progressing.",
            style="color:#8B9DBB; font-style:italic;"
        )

    # ── the card itself ──────────────────────────────────────────────────
    @output
    @render_altair
    def student_kc_detail():
        sel = selected_tile.get()
        if sel is None:
            return alt.Chart(pd.DataFrame()).mark_point()
        return student_kc_card(mkc_data(), sel["student"], sel["kc"])
    
    
    
    # ── opportunity list ──────────────────────────────────────────────
    # ── Low tab ─────────────────────
    @output
    @render_altair
    def low_opp_table():
        return opportunity_table(kc_opp_lowest(opp_counts()))

    # ── High tab ─────────────────────
    @output
    @render_altair
    def high_opp_table():
        return opportunity_table(kc_opp_highest(opp_counts()))

    # ── Rank tab ─────────────────────
    @output
    @render_altair
    def rank_opp_table():
        return opportunity_table(kc_opp_rank(kc_list_rank(), opp_counts()))
    
    # ── Search tab ─────────────────────
    @reactive.effect
    def opp_search_choices():
        choices = sorted(mkc_data()["modeling_kc_label"].unique().tolist())
        ui.update_selectize(
            "opp_search",
            choices=choices,
            server=True,   # server-side filtering — important for large KC lists
        )

    @output
    @render_altair
    def search_opp_table():
        selected = list(input.opp_search()) 

        if not selected:
            return None

        return opportunity_table(kc_opp_rank(selected, opp_counts()))

    # ── KC progress ────────────────────────────────────────────────────
    # ── Rank tab ─────────────────────
    def make_render_rank(kc_name, output_id):
        @output(id=output_id)
        @render_altair
        def _render():
            filter = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)

    for i in range(4):
        @output(id=f"kc_rank_{i}")
        @render_altair
        def _render(i=i):
            names = kc_list_rank()
            if i >= len(names):
                return None
            kc_name = names[i]
            filtered = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filtered, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)

    for i in range(4):
        @output(id=f"kc_rank_title_{i}")
        @render.text
        def _title(i=i):
            names = kc_list_rank()
            return names[i] if i < len(names) else ""

    # ── Low tab ─────────────────────
    def make_render_low(kc_name, output_id):
        @output(id=output_id)
        @render_altair
        def _render():
            filter = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)

    for i in range(4):
        output_id = f"kc_low_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_lowest()[i]
            filter = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)
        
        # ── titles for lowest tab ────────────────────────────────────────────
    for i in range(4):
        def make_title_low(idx):
            @output(id=f"kc_low_title_{idx}")
            @render.text
            def _title():
                return kc_list_lowest()[idx]
        make_title_low(i)
        
    # ── High tab ─────────────────────
    def make_render_high(kc_name, output_id):
        @output(id=output_id)
        @render_altair
        def _render():
            filter = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)
    
    for i in range(4):
        output_id = f"kc_high_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_highest()[i]
            filter = last_attempt()[last_attempt()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)
    
        # ── titles for highest tab ─────────────────────────────────────────
    for i in range(4):
        def make_title_high(idx):
            @output(id=f"kc_high_title_{idx}")
            @render.text
            def _title():
                return kc_list_highest()[idx]
        make_title_high(i)

    # ── Search tab ─────────────────────
    @reactive.effect
    def populate_search_choices():
        choices = sorted(mkc_data()["modeling_kc_label"].unique().tolist())
        ui.update_selectize(
            "kc_search",
            choices=choices,
            server=True,   # server-side filtering — important for large KC lists
        )

        # ── render selected KC charts dynamically ────────────────────────────
    @output
    @render.ui
    def search_results():
        selected = input.kc_search()

        if not selected:
            return ui.tags.p(
                "Select one or more KCs above to view their mastery distribution.",
                style="color:#6c757d; font-size:0.9rem; margin-top:1rem;",
            )

        cards = []
        for kc_name in selected:
            safe_id = kc_name.replace(",", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
            cards.append(
                ui.card(
                    ui.card_header(kc_name, style="font-weight:600; font-size:0.95rem;"),
                    output_widget(f"search_chart_{safe_id}"),
                )
            )

        # Pair cards into rows of 2, matching the layout of the other tabs
        rows = []
        for i in range(0, len(cards), 2):
            pair = cards[i : i + 2]

            # If only 1 card in the last row, pad with an empty div so the
            # grid doesn't stretch it to full width
            if len(pair) == 1:
                pair.append(ui.tags.div())

            rows.append(
                ui.layout_columns(
                    *pair,
                    col_widths=6,
                )
            )

        return ui.tags.div(*rows)

     # ── render each selected KC chart ─────────────────────────────────────
    # Uses a reactive effect that re-runs whenever the selection changes,
    # registering a new altair renderer for each selected KC on the fly
    @reactive.effect
    def render_search_charts():
        selected = input.kc_search()

        for kc_name in selected:
            # Pass both kc_name AND safe_id into the closure together
            def make_chart(name, sid):
                @output(id=f"search_chart_{sid}")
                @render_altair
                def _chart():
                    filter = last_attempt()[last_attempt()['modeling_kc_label'] == name]
                    return kc_mastery_box(filter, mastery_threshold=KC_PERC_MASTERY_THRESHOLD, practice_threshold=KC_PERC_PRACTICE_THRESHOLD)
            
            safe_id = kc_name.replace(",", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
            make_chart(kc_name, safe_id)

    # ── Student Overview ─────────────────────────────────────────────────
    @reactive.effect
    def _update_student_choices():
        ui.update_select("so_student", choices=student_ids())

    @output
    @render_altair
    def so_status_boxes():
        return student_status_boxes(
            student_id=input.so_student(),
            data=mkc_data(),
            quantile=input.so_quantile(),
            cuts=quantile_cuts(),
        )

    @output
    @render_altair
    def so_mastery_table():
        return student_mastery_table(
            student_id=input.so_student(),
            data=mkc_data(),
            quantile=input.so_quantile(),
            status_filter=input.so_status(),
            cuts=quantile_cuts(),
        )
    
    # ── Data Input  ─────────────────────────────────────────────────
        # ── tracks whether preprocessing is currently running ───────────────────
    is_processing = reactive.value(False)

    # ── load every uploaded file once ───────────────────────────────────────
    @reactive.calc
    def file_dfs() -> dict[str, pd.DataFrame]:
        files = input.files()
        if not files:
            return {}
        dfs: dict[str, pd.DataFrame] = {}
        for f in files:
            name = f["name"]
            if name not in dfs:
                try:
                    dfs[name] = pd.read_csv(f["datapath"])
                except Exception:
                    pass
        return dfs

    # ── for each dataset, find the single file (if any) with all its columns ─
    @reactive.calc
    def dataset_sources() -> dict[str, str]:
        dfs = file_dfs()
        sources: dict[str, str] = {}
        for ds_id, (_, dataset_cols) in DATASETS.items():
            for fname, df in dfs.items():
                if all(col in df.columns for col in dataset_cols):
                    sources[ds_id] = fname
                    break
        return sources

    # ── used by the cards: which columns are satisfied right now ─────────────
    @reactive.calc
    def col_to_file() -> dict[str, str]:
        sources = dataset_sources()
        mapping: dict[str, str] = {}
        for ds_id, (_, dataset_cols) in DATASETS.items():
            if ds_id in sources:
                fname = sources[ds_id]
                for col in dataset_cols:
                    mapping[col] = fname
        return mapping

    # ── only build dataframes once every dataset has a single valid source ──
    @reactive.calc
    def built_dataframes() -> dict[str, pd.DataFrame] | None:
        sources = dataset_sources()
        if len(sources) < len(DATASETS):
            return None
        dfs = file_dfs()
        return {
            ds_id: dfs[sources[ds_id]][dataset_cols]
            for ds_id, (_, dataset_cols) in DATASETS.items()
        }
    
    # ── holds the result of the last completed preprocessing run ────────────
    processed_result = reactive.value(None)

    @reactive.effect
    @reactive.event(input.process_btn)
    def _run_processing():
        raw = built_dataframes()
        if raw is None:
            ui.notification_show("Cannot preprocess — make sure all columns have been added", type="error")
            return

        is_processing.set(True)
        try:
            obs        = raw["stu"]
            class_plan = raw["class"]
            kc_map     = raw["map"]
            weights    = raw["weights"]

            df = merge_kc_mapping(obs, kc_map)
            df = merge_weights(df, weights)
            df = merge_class_plan(df, class_plan)

            bkt_preds = run_bkt_predictions(df, kc_col="modeling_kc_id")
            df_final = merge_bkt_predictions(df, bkt_preds)

            processed_result.set(df_final)
            ui.notification_show("Preprocessing complete", type="success")
        finally:
            is_processing.set(False)

    @output
    @render.ui
    def processing_status():
        if is_processing():
            return ui.HTML(
                '<div style="display:flex;align-items:center;gap:6px;'
                'color:#263744;font-size:13px;">'
                '<i class="ti ti-loader-2" style="font-size:16px;'
                'animation:spin 1s linear infinite;" aria-hidden="true"></i>'
                ' Preprocessing data…</div>'
                '<style>@keyframes spin{from{transform:rotate(0deg);}'
                'to{transform:rotate(360deg);}}</style>'
            )
        return ui.HTML("")
    

    @output
    @render.ui
    def master_status():
        sources = dataset_sources()
        complete = len(sources)
        total = len(DATASETS)

        if not input.files():
            return ui.HTML(
                '<p style="color:#263744;font-size:13px;margin:0;">'
                'Upload one or more CSV files. Each dataset needs all its '
                'columns in a single file.</p>'
            )
        if complete == total:
            return ui.HTML(
                '<div style="background:#60D394;color:#263744;'
                'border-radius:var(--border-radius-md);'
                'padding:8px 14px;font-size:13px;font-weight:500;">'
                '<i class="ti ti-circle-check" aria-hidden="true"></i>'
                ' All datasets complete — dataframes are ready.</div>'
            )
        return ui.HTML(
            f'<div style="background:#FF9B85;color:#263744;'
            f'border-radius:var(--border-radius-md);padding:8px 14px;'
            f'font-size:13px;font-weight:500;">'
            f'<i class="ti ti-upload" aria-hidden="true"></i>'
            f' {complete} of {total} datasets complete. '
            f'Upload more files to fill in missing columns.</div>'
        )

    for ds_id, (title, dataset_cols) in DATASETS.items():
        def make_card_renderer(ds_id=ds_id, title=title, dataset_cols=dataset_cols):
            @output(id=f"card_{ds_id}")
            @render.ui
            def _card():
                return ui.HTML(build_card(ds_id, title, dataset_cols, col_to_file()))
        make_card_renderer()

    @output
    @render.ui
    def dataframes_ready():
        dfs = built_dataframes()
        if dfs is None:
            return ui.HTML("")
        previews = []
        for ds_id, (title, _) in DATASETS.items():
            df = dfs.get(ds_id)
            if df is not None:
                shape = f"{df.shape[0]:,} rows × {df.shape[1]} columns"
                previews.append(
                    f'<div style="margin-bottom:8px;padding:10px 14px;'
                    f'background:#60D394;'
                    f'border-radius:var(--border-radius-md);font-size:13px;">'
                    f'<span style="font-weight:500;color:#263744;">{title}</span>'
                    f'<span style="color:#263744;opacity:0.6;margin-left:8px;">{shape}</span>'
                    f'</div>'
                )
        return ui.HTML(
            '<div style="margin-top:1.5rem;">'
            '<p style="font-size:20px;font-weight:500;color:#263744;'
            'margin-bottom:8px;">Built dataframes</p>'
            + "".join(previews)
            + "</div>"
        )
    
    @reactive.effect
    @reactive.event(input.save_btn)
    def _save_to_disk():
        df = processed_result()
        if df is not None:
            save_final_output(df, "final_student_kc_data.csv")
            mkc_data_rv.set(df)
            ui.notification_show("Saved successfully", type="success")
        else:
            ui.notification_show("Cannot save — make sure all columns have been added", type="error")



app = App(app_ui, server)