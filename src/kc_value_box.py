"""
This module contains helper function to build a single KPI value-box UI
component for the Teacher Portal dashboard, showing a count of KCs at a
given mastery status alongside a comparison to first-attempt counts.

Used to render the "Mastered" / "Progressing" / "Needs Practice" summary
tiles at the top of the dashboard.

Expects a data DataFrame with at minimum this column:
    class_date : date string in "%Y-%m-%d" format.

Typical usage :
    from src.kc_value_box import kpi_value_box

    box = kpi_value_box(
        data=df_final,
        status="Mastered",
        theme=ui.value_box_theme(bg="#60D394"),
        value_now=12,
        value_first=8,
        text="This box counts the number of Mastered KCs. Click on the box for more information."
    )
"""
from datetime import datetime
from shiny import ui

# Info icon
def info_icon():
    """Helper function to create the info icon"""
    return ui.HTML(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
        f'class="bi bi-question-circle-fill" '
        f'style="height:1em;width:1em;fill:#263744;" '
        f'aria-hidden="true" role="img">'
        f'<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.496 6.033h.825c.138 0 .248-.113.266-.25.09-.656.54-1.134 1.342-1.134.686 0 1.314.343 1.314 1.168 0 .635-.374.927-.965 1.371-.673.489-1.206 1.06-1.168 1.987l.003.217a.25.25 0 0 0 .25.246h.811a.25.25 0 0 0 .25-.25v-.105c0-.718.273-.927 1.01-1.486.609-.463 1.244-.977 1.244-2.056 0-1.511-1.276-2.241-2.673-2.241-1.267 0-2.655.59-2.75 2.286a.237.237 0 0 0 .241.247m2.325 6.443c.61 0 1.029-.394 1.029-.927 0-.552-.42-.94-1.029-.94-.584 0-1.009.388-1.009.94 0 .533.425.927 1.01.927z"></path>'
        f'</svg>'
    )

def kpi_value_box(data, status, theme, value_now, value_first, text):
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
    text        : str           text used in info icon
    """
    # ── Date range ───────────────────────────────────────────────────────
    d_start = datetime.strptime(data['class_date'].unique().min(), "%Y-%m-%d")
    d_end = datetime.strptime(data['class_date'].unique().max(), "%Y-%m-%d")

    # ── Delta ────────────────────────────────────────────────────────────
    delta = value_now - value_first
    arrow = "↑" if delta >= 0 else "↓"
    delta_str = f"{arrow} {abs(delta)} vs first attempt"
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
        ui.tooltip(
            info_icon(),
            text,
            style="display: flex; align-items: center; gap: 8px; width: 100%;",
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
