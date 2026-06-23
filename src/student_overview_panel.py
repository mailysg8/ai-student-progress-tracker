"""Shiny panel for the Student Overview page.

Drop-in for the empty `ui.nav_panel("Student Overview")` slot in app.py.
Mirrors the style of the Class Overview panel: shinywidgets + Altair charts
+ value boxes themed in the team palette.

----- Integration (single-line changes in app.py) ------------------------------

1) Add to the top of app.py:

        from src.student_overview_panel import (
            student_overview_panel_ui,
            student_overview_panel_server,
        )

2) Replace the placeholder:

        # Page 2: Student Overview
        ui.nav_panel("Student Overview"),

   with:

        # Page 2: Student Overview
        student_overview_panel_ui(),

3) Inside the existing `def server(input, output, session): ...` function,
   add one line at the bottom (or anywhere):

        student_overview_panel_server(input, output, session)

That's it — no other changes to app.py.

----- What the panel shows ----------------------------------------------------

* A student dropdown (defaults to S019 for the demo)
* Four KPI value boxes: Skills Mastered / Still Developing / Need Practice /
  Unattempted (palette colors match the rest of the dashboard)
* Two Altair cards side-by-side:
    - Unit breakdown (stacked bars: how many skills mastered/developing/needs
      practice/unattempted per unit)
    - How you compare to the class (signed diff per unit, ahead vs behind)

Data files (loaded from the repository's data/ directory):
* data/raw/final_data.xlsx
* data/raw/mkc_mapping_pack_v1.0..xlsx
"""
import pandas as pd
from shiny import ui, render, reactive
from shinywidgets import render_altair, output_widget

from src.student_kpi_cards import (
    load_data,
    compute_student_summary,
    class_average_per_unit,
    COLORS,
)
from src.student_unit_grid        import unit_breakdown_chart
from src.student_class_comparison import class_comparison_chart


# ─── Module-level data load (same convention as app.py) ──────────────────────
_OBS, _MKC2LABEL, _MKC2UNIT, _UNIT_MKCS, _UNITS = load_data(
    "data/raw/final_data.xlsx",
    "data/raw/mkc_mapping_pack_v1.0..xlsx",
)
_CLASS_AVG   = class_average_per_unit(_OBS, _UNITS)
_STUDENT_IDS = sorted(_OBS["user_id"].unique())

# Inline SVG info-icon helper — kept here so this module is self-contained.
def _bs_info_icon(title: str = "Information"):
    return ui.HTML(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
        f'class="bi bi-info-circle" '
        f'style="height:1em;width:1em;fill:currentColor;" aria-hidden="true" role="img">'
        f'<title>{title}</title>'
        f'<path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>'
        f'<path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/>'
        f'</svg>'
    )


# ─── UI ───────────────────────────────────────────────────────────────────────
def student_overview_panel_ui():
    """The Student Overview nav_panel — drop this into ui.page_navbar()."""
    return ui.nav_panel(
        "Student Overview",
        # student picker
        ui.layout_columns(
            ui.input_select(
                "ss_student_id",
                "Choose a student:",
                {sid: sid for sid in _STUDENT_IDS},
                selected="S019",
            ),
            col_widths=4,
        ),
        # KPI value boxes
        ui.layout_columns(
            ui.value_box(
                "Skills Mastered",
                ui.output_text("ss_vb_mastered"),
                theme=ui.value_box_theme(bg=COLORS["mastered"],    fg="#263744"),
            ),
            ui.value_box(
                "Still Developing",
                ui.output_text("ss_vb_developing"),
                theme=ui.value_box_theme(bg=COLORS["developing"],  fg="#263744"),
            ),
            ui.value_box(
                "Need Practice",
                ui.output_text("ss_vb_needs"),
                theme=ui.value_box_theme(bg=COLORS["needs"],       fg="#263744"),
            ),
            ui.value_box(
                "Unattempted",
                ui.output_text("ss_vb_unattempted"),
                theme=ui.value_box_theme(bg=COLORS["unattempted"], fg="#263744"),
            ),
            col_widths=3,
        ),
        # Charts row: unit breakdown (left) + class comparison (right)
        ui.layout_columns(
            ui.card(
                ui.card_header(
                    ui.div(
                        ui.span("Unit breakdown", style="font-size: 18px;"),
                        ui.tooltip(
                            _bs_info_icon(),
                            "How many skills in each unit are mastered (≥70%), "
                            "still developing (40–69%), or need practice (<40%).",
                        ),
                        style="display:flex;align-items:center;justify-content:space-between;width:100%;",
                    )
                ),
                output_widget("ss_unit_breakdown"),
                style="height: 520px;",
            ),
            ui.card(
                ui.card_header(
                    ui.div(
                        ui.span("How you compare to the class", style="font-size: 18px;"),
                        ui.tooltip(
                            _bs_info_icon(),
                            "Your average mastery in each unit minus the class average. "
                            "Green = you're ahead, coral = the class is ahead of you.",
                        ),
                        style="display:flex;align-items:center;justify-content:space-between;width:100%;",
                    )
                ),
                output_widget("ss_class_comparison"),
                style="height: 520px;",
            ),
            col_widths=(6, 6),
        ),
    )


# ─── Server ───────────────────────────────────────────────────────────────────
def student_overview_panel_server(input, output, session):
    """Register all reactive outputs for the Student Overview panel.
    Call this once from the main `def server(input, output, session)`."""

    @reactive.calc
    def _summary():
        sid = input.ss_student_id()
        return compute_student_summary(
            _OBS, _MKC2LABEL, _MKC2UNIT, _UNIT_MKCS, _UNITS, sid
        )

    # ── KPI value boxes ─────────────────────────────────────────────────────
    @output
    @render.text
    def ss_vb_mastered():
        t = _summary()["totals"]
        return f"{t['mastered']} / {t['all']}"

    @output
    @render.text
    def ss_vb_developing():
        t = _summary()["totals"]
        return f"{t['developing']} / {t['all']}"

    @output
    @render.text
    def ss_vb_needs():
        t = _summary()["totals"]
        return f"{t['needs']} / {t['all']}"

    @output
    @render.text
    def ss_vb_unattempted():
        t = _summary()["totals"]
        return f"{t['unattempted']} / {t['all']}"

    # ── Charts ──────────────────────────────────────────────────────────────
    @output
    @render_altair
    def ss_unit_breakdown():
        return unit_breakdown_chart(_summary())

    @output
    @render_altair
    def ss_class_comparison():
        return class_comparison_chart(_summary(), _CLASS_AVG)
