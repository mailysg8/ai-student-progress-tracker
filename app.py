import pandas as pd
import altair as alt
from shiny import App, ui, render, reactive, req
from shinywidgets import render_altair, output_widget, reactive_read
from kc_mastery_box import kc_mastery_box, classify
from unit_mastery_box import unit_mastery


mkc_data = pd.read_csv('data/processed/mkc_data.csv')

kc_list_rank = list(mkc_data.groupby(['modeling_kc_label','rank']).count().sort_values('rank').reset_index().loc[0:3,'modeling_kc_label'])


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


app_ui = ui.page_navbar(
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
        ),
        # ── Row 2: unit mastery grid (left) + KC boxes (right) ───────────
        ui.layout_columns(
            ui.card(
                ui.card_header("Unit Mastery Overview"),
                output_widget("unit_mastery_chart"),
            ),
            ui.card(
                ui.card_header("KC Progress"),
                ui.navset_tab(
                    ui.nav_panel(
                        "Most Important KCs",
                        ui.layout_columns(
                            *[
                                ui.card(
                                    ui.card_header(ui.output_text(f"kc_rank_title_{i}")),
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
                                    ui.card_header(ui.output_text(f"kc_low_title_{i}")),
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
                                    ui.card_header(ui.output_text(f"kc_high_title_{i}")),
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
            .groupby(['user_id', 'skill_name'])
            .last()
            .reset_index()
        )
        return last_attempt

    @reactive.calc
    def kc_summary():
        df = (
            aggregated()
            .groupby(['unit', 'skill_name', 'modeling_kc_label'])['state_predictions']
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
            .head(4)['modeling_kc_label']
            .tolist()
        )
    
    @reactive.calc
    def kc_list_highest():
        """Top 4 KCs by class mastery percentage."""
        return (
            kc_summary()
            .sort_values('pct_mastered', ascending=False)
            .head(4)['modeling_kc_label']
            .tolist()
        )

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
        return str((df['status'] == 'Needs Attention').sum())

    @render.text
    def vb_total():
        return str(len(kc_summary()))

    # ── unit mastery grid ────────────────────────────────────────────────
    @output
    @render_altair
    def unit_mastery_chart():
        return unit_mastery(aggregated())

    # ── top 4 by rank ────────────────────────────────────────────────────
    def make_render_rank(kc_name, output_id):
        @output(id=output_id)
        @render_altair
        def _render():
            last_attempt = aggregated()[aggregated()['modeling_kc_label'] == kc_name]
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
            last_attempt = aggregated()[aggregated()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)

    for i in range(4):
        output_id = f"kc_low_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_lowest()[i]
            last_attempt = aggregated()[aggregated()['modeling_kc_label'] == kc_name]
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
            last_attempt = aggregated()[aggregated()['modeling_kc_label'] == kc_name]
            return kc_mastery_box(kc_name, last_attempt)
    
    for i in range(4):
        output_id = f"kc_high_{i}"

        @output(id=output_id)
        @render_altair
        def _render(i=i):   # default arg captures loop variable
            kc_name = kc_list_highest()[i]
            last_attempt = aggregated()[aggregated()['modeling_kc_label'] == kc_name]
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