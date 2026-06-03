import pandas as pd
import altair as alt
from shiny import App, ui, render, reactive, req
from shinywidgets import render_altair, output_widget, reactive_read
from src.kc_mastery_box import kc_mastery_box, classify
from src.unit_mastery_box import unit_mastery
from src.opportunity_heatmap import opp_heatmap, opportunity_table, compute_opportunity_counts 



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
    # Enhanced from https://rstudio.github.io/bsicons/ via `bsicons::bs_icon(&quot;info-circle&quot;, title = icon_title)`
    return ui.HTML(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" class="bi bi-info-circle " style="height:1em;width:1em;fill:currentColor;" aria-hidden="true" role="img" ><title>{title}</title><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"></path><path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"></path></svg>')


# Helper functions
def kc_opp_lowest(opp_counts : pd.DataFrame, n: int = 5):
        """Lowest n KCs by opportunity average."""
        return (
            opp_counts
            .groupby('modeling_kc_label_x')['n_opportunities']
            .mean()
            .reset_index()
            .rename(columns={'n_opportunities': 'avg_opportunities'})
            .sort_values('avg_opportunities')
            .head(n)
            .reset_index(drop=True)
        )


def kc_opp_highest(opp_counts : pd.DataFrame, n: int = 5):
    """Highest n KCs by opportunity average."""
    return (
        opp_counts
        .groupby('modeling_kc_label_x')['n_opportunities']
        .mean()
        .reset_index()
        .rename(columns={'n_opportunities': 'avg_opportunities'})
        .sort_values('avg_opportunities', ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def kc_opp_rank(opp_counts : pd.DataFrame, n: int = 5):
    """n highest ranking KCs and their opportunity average."""
    kc_list_rank = list(mkc_data.groupby(['modeling_kc_label_x','rank']).count().sort_values('rank').reset_index().loc[0:n-1,'modeling_kc_label_x'])

    avg_opp = (
        opp_counts
        .groupby('modeling_kc_label_x')['n_opportunities']
        .mean()
        .reset_index()
        .rename(columns={'n_opportunities': 'avg_opportunities'})
        .sort_values('avg_opportunities', ascending=False)
        .reset_index(drop=True)
    )

    return avg_opp[avg_opp['modeling_kc_label_x'].isin(kc_list_rank)]


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
            ui.nav_panel(
                "General",
                # ── Row 1: value boxes ───────────────────────────────────────────
                ui.layout_columns(
                    ui.value_box(
                        "KCs Mastered",
                        ui.output_text("vb_mastered"),
                        theme=ui.value_box_theme(bg="#60D394", fg="#263744"),
                    ),
                    ui.value_box(
                        "KCs Progressing",
                        ui.output_text("vb_progressing"),
                        theme=ui.value_box_theme(bg="#FFD97D", fg="#263744"),
                    ),
                    ui.value_box(
                        "KCs Needing Attention",
                        ui.output_text("vb_needs"),
                        theme=ui.value_box_theme(bg="#FF9B85", fg="#263744"),
                    ),
                    ui.value_box(
                        "Total KCs",
                        ui.output_text("vb_total"),
                        theme=ui.value_box_theme(bg="#8B9DBB", fg="#263744"),
                    ),
                    col_widths=3,
                    col_heights=2
                ),
                # ── Row 2: unit mastery grid (left) + KC boxes (right) ───────────
                ui.layout_columns(
                    ui.div(
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
                                )

                            ),
                            style="height: 400px;",
                        ),
                    ),
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
                            id="kc_tabs",
                        )
                    ),
                    col_widths=(4,8),
                ),
            ),
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
        "Student Overview"
    ),

    title=ui.tags.span("Stellar Education", style="color: white;"),
    navbar_options=ui.navbar_options(bg="#263744"),
    sidebar=ui.sidebar("Filters", bg="#263744"),
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
    
    # ── low opportunity list ──────────────────────────────────────────────
    @output
    @render_altair
    def low_opp_table():
        return opportunity_table(kc_opp_lowest(opp_counts()))

    # ── high opportunity list ──────────────────────────────────────────────
    @output
    @render_altair
    def high_opp_table():
        return opportunity_table(kc_opp_highest(opp_counts()))

    # ── rank opportunity list ──────────────────────────────────────────────
    @output
    @render_altair
    def rank_opp_table():
        return opportunity_table(kc_opp_rank(opp_counts()))

    # ── top 4 by rank ────────────────────────────────────────────────────
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

    # ── lowest 4 by mastery ──────────────────────────────────────────────
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
        
    # ── highest 4 by mastery ──────────────────────────────────────────────
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
    
        # ── titles for highest tab ────────────────────────────────────────────
    for i in range(4):
        def make_title_high(idx):
            @output(id=f"kc_high_title_{idx}")
            @render.text
            def _title():
                return kc_list_highest()[idx]
        make_title_high(i)

app = App(app_ui, server)