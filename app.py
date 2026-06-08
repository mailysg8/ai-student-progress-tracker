import pandas as pd
import altair as alt
from shiny import App, ui, render, reactive, req
from shinywidgets import render_altair, output_widget, reactive_read
from src.kc_mastery_box import kc_mastery_box, classify
from src.unit_mastery_box import unit_mastery
from src.opportunity_heatmap import opp_heatmap, opportunity_table, compute_opportunity_counts 
from src.student_status_boxes import student_status_boxes
from src.student_mastery_table import student_mastery_table
from src.modal_builds import build_kc_modal, build_total_kc_modal
from src.kc_opp import kc_opp_highest, kc_opp_lowest, kc_opp_rank

MASTERY_THRESHOLD = 0.7
ATTENTION_THRESHOLD = 0.3

mkc_data = pd.read_csv('data/processed/final_student_kc_data.csv')

kc_list_rank = list(mkc_data.groupby(['modeling_kc_label_x','rank']).count().sort_values('rank').reset_index().loc[0:3,'modeling_kc_label_x'])


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



# Student dropdown choices (data is already loaded here)
STUDENT_IDS = sorted(mkc_data["student_id"].unique().tolist())


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
                                # --- Total KCs ---
                                ui.value_box(
                                    "Total KCs",
                                    ui.output_text("vb_total"),
                                    theme=ui.value_box_theme(bg="#8B9DBB", fg="#263744"),
                                    id="vb_total_box",
                                    style="cursor: pointer;",
                                ),

                                # --- Mastered ---
                                ui.value_box(
                                    "Number of KCs Mastered",
                                    ui.output_text("vb_mastered"),
                                    theme=ui.value_box_theme(bg="#60D394", fg="#263744"),
                                    id="vb_mastered_box",
                                    style="cursor: pointer;",
                                ),

                                # --- Progressing ---
                                ui.value_box(
                                    "Number of KCs Progressing",
                                    ui.output_text("vb_progressing"),
                                    theme=ui.value_box_theme(bg="#FFD97D", fg="#263744"),
                                    id="vb_progressing_box",
                                    style="cursor: pointer;",
                                ),

                                # --- Need Attention ---
                                ui.value_box(
                                    "Number of KCs Needing Attention",
                                    ui.output_text("vb_needs"),
                                    theme=ui.value_box_theme(bg="#FF9B85", fg="#263744"),
                                    id="vb_needs_box",
                                    style="cursor: pointer;",
                                ),

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
                                        Green = class has largely mastered it, yellow = still in progress, red = needs attention.
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
                                    Squares represent individual students — green = mastered, yellow = progressing, red = needs attention. 
                                    The progress bar shows the class mastery rate. 
                                    Switch tabs to focus on KCs needing attention or showing good progress.
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
                                "Need Attention",
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
                                    choices=[],          # populated server-side from real KC names
                                    multiple=True,
                                    options={"placeholder": "Type to search for a KC...", "maxItems": 4},
                                ),
                                # Dynamic output slots for up to 4 selected KCs
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
                        style="height: 100%;",
                    ),
                    style="height: calc(100vh - 120px); padding: 1rem;"
                )
            )
        )
    ),
# ── Page 2: Student Overview ─────────────────────────────────────────── 
    ui.nav_panel(
        "Student Overview",
        ui.div(
            ui.layout_columns(
                ui.input_select("so_student", "Student", choices=STUDENT_IDS, width="100%"),
                ui.input_switch("so_quantile", "Relative (quantile) status", value=False),
                ui.input_select(
                    "so_status", "Status",
                    choices=["All statuses", "Ahead", "On Track", "At Risk", "Behind"],
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

    title=ui.tags.span("Stellar Education", style="color: white;"),
    navbar_options=ui.navbar_options(bg="#263744"),
)



def server(input, output, session):

    # ── shared pre-computed data ─────────────────────────────────────────
    @reactive.calc
    def aggregated():
        bar_data = mkc_data.copy()
        last_attempt = (
            bar_data
            .groupby(['student_id', 'modeling_kc_id'])
            .last()
            .reset_index()
        )
        return last_attempt

    @reactive.calc
    def kc_summary():
        df = (
            aggregated()
            .groupby(['unit', 'modeling_kc_id', 'modeling_kc_label_x'])['state_predictions']
            .apply(lambda x: (x >= 0.70).mean())
            .reset_index()
            .rename(columns={'state_predictions': 'pct_mastered'})
        )
        df['status'] = df['pct_mastered'].apply(classify)
        return df
    
    @reactive.calc
    def kc_list_lowest():
        """Bottom 4 KCs by class mastery percentage."""
        return (
            kc_summary()
            .sort_values('pct_mastered', ascending=True)
            .head(4)['modeling_kc_label_x']
            .tolist()
        )
    
    @reactive.calc
    def kc_list_highest():
        """Top 4 KCs by class mastery percentage."""
        return (
            kc_summary()
            .sort_values('pct_mastered', ascending=False)
            .head(4)['modeling_kc_label_x']
            .tolist()
        )
    
    @reactive.calc
    def opp_counts():
        return compute_opportunity_counts(mkc_data)

    # ── value boxes ──────────────────────────────────────────────────────
    ## Values
    @render.text
    def vb_mastered():
        df = kc_summary()
        return str((df['status'] == 'Mastered').sum())

    @render.text
    def vb_progressing():
        df = kc_summary()
        return str((df['status'] == 'Progressing').sum())

    @render.text
    def vb_needs():
        df = kc_summary()
        return str((df['status'] == 'Need Attention').sum())

    @render.text
    def vb_total():
        return str(len(kc_summary()))
    
    ## Pop up after clicking on box
    # --- Total KCs modal ---
    @reactive.effect
    @reactive.event(input.vb_total_clicked)
    def modal_total():
        df = kc_summary()
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
        df = kc_summary()   
        n = len(df[df["status"] == "Mastered"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Mastered", mastery=MASTERY_THRESHOLD, attention=ATTENTION_THRESHOLD),
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
        df = kc_summary()
        n = len(df[df["status"] == "Progressing"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Progressing",mastery=MASTERY_THRESHOLD, attention=ATTENTION_THRESHOLD),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#FFD97D;"),
                f"Skills Progressing — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True, size="l", footer=None,
        ))

    # --- Need Attention modal ---
    @reactive.effect
    @reactive.event(input.vb_needs_clicked)
    def modal_needs():
        df = kc_summary()
        n = len(df[df["status"] == "Need Attention"])
        ui.modal_show(ui.modal(
            build_kc_modal(df, status="Need Attention",mastery=MASTERY_THRESHOLD, attention=ATTENTION_THRESHOLD),
            title=ui.tags.span(
                ui.tags.span("● ", style="color:#FF9B85;"),
                f"Skills Needing Attention — {n} skill{'s' if n > 1 else ''}",
            ),
            easy_close=True, size="l", footer=None,
        ))


    # ── unit mastery grid ────────────────────────────────────────────────
    @output
    @render_altair
    def unit_mastery_chart():
        return unit_mastery(aggregated())

    # ── opportunity heatmap ──────────────────────────────────────────────
    @output
    @render_altair
    def opp_heatmap_plot():
        return opp_heatmap(mkc_data)
    
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
        return opportunity_table(kc_opp_rank(kc_list_rank, opp_counts()))
    
    # ── Search tab ─────────────────────
    @reactive.effect
    def opp_search_choices():
        choices = sorted(mkc_data["modeling_kc_label_x"].unique().tolist())
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
            last_attempt = aggregated()[aggregated()['modeling_kc_label_x'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)

    for i, kc_name in enumerate(kc_list_rank):
        make_render_rank(kc_name, f"kc_rank_{i}")

        # ── titles for rank tab ──────────────────────────────────────────────
    for i, kc_name in enumerate(kc_list_rank):
        def make_title_rank(name):
            @output(id=f"kc_rank_title_{i}")
            @render.text
            def _title():
                return name
        make_title_rank(kc_name)

    # ── Low tab ─────────────────────
    def make_render_low(kc_name, output_id):
        @output(id=output_id)
        @render_altair
        def _render():
            last_attempt = aggregated()[aggregated()['modeling_kc_label_x'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)

    for i in range(4):
        output_id = f"kc_low_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_lowest()[i]
            last_attempt = aggregated()[aggregated()['modeling_kc_label_x'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)
        
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
            last_attempt = aggregated()[aggregated()['modeling_kc_label_x'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)
    
    for i in range(4):
        output_id = f"kc_high_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_highest()[i]
            last_attempt = aggregated()[aggregated()['modeling_kc_label_x'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)
    
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
        choices = sorted(mkc_data["modeling_kc_label_x"].unique().tolist())
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
                    last_attempt = aggregated()[aggregated()["modeling_kc_label_x"] == name]
                    return kc_mastery_box(name, last_attempt)
            
            safe_id = kc_name.replace(",", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
            make_chart(kc_name, safe_id)

    # ── Student Overview ─────────────────────────────────────────────────
    @output
    @render_altair
    def so_status_boxes():
        return student_status_boxes(
            student_id=input.so_student(),
            data=mkc_data,
            quantile=input.so_quantile(),
        )

    @output
    @render_altair
    def so_mastery_table():
        return student_mastery_table(
            student_id=input.so_student(),
            data=mkc_data,
            quantile=input.so_quantile(),
            status_filter=input.so_status(),
        )

app = App(app_ui, server)