import pandas as pd
from datetime import datetime
from shiny import ui
def kpi_value_box(data, status, theme, value_now, value_first):
    """
    Builds a value box tag. All values must be pre-computed scalars —
    no reactive calls inside this function.

    Parameters
    ----------
    data        : pd.DataFrame  used only for the date range header
    status      : str           e.g. "Mastered", used for title and output id
    theme       : ui.value_box_theme
    value_now   : int           current count for this status
    value_first : int           first-attempt count for comparison
    """
    # ── Date range ───────────────────────────────────────────────────────
    d_start = datetime.strptime(data['class_date'].unique().min(), "%Y-%m-%d")
    d_end   = datetime.strptime(data['class_date'].unique().max(), "%Y-%m-%d")

    # ── Delta ────────────────────────────────────────────────────────────
    delta       = value_now - value_first
    arrow       = "↑" if delta >= 0 else "↓"
    delta_str   = f"{arrow} {abs(delta)} vs first attempt"
    arrow_color = "#263744"

    # ── Header ───────────────────────────────────────────────────────────
    header_content = ui.div(
        ui.span(
            f"Latest Attempts : {d_start.strftime('%b %d, %Y')} – {d_end.strftime('%b %d, %Y')}",
            style="font-size:0.85rem; font-weight:500; display:block; opacity:0.85;",
        ),
        ui.span(
            f"Number of KCs {status}" if status!='Needs Practice' else f"Number of KCs Needing Practice",
            style="font-size:1.25rem; font-weight:bold;",
        ),
    )

    # ── Footer ───────────────────────────────────────────────────────────
    footer_content = ui.div(
        ui.span(
            delta_str,
            style=(
                f"font-size:0.78rem; font-weight:600; color:{arrow_color};"
                "background:rgba(255,255,255,0.25); border-radius:4px;"
                "padding:0.15rem 0.45rem; display:inline-block;"
            ),
        ),
    )

    return ui.value_box(
        header_content,
        str(value_now),
        footer_content,
        theme=theme,
        id=f"vb_{status.lower().replace(' ', '_')}_box",
        style="cursor: pointer;",
    )
