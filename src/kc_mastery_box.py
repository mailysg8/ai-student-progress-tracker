"""
This module contains helper functions to create the KC progress card used on the dashboard with a class-wide progress bar, a per-student tile grid colour-coded by
mastery status, and a legend.

Expects a DataFrame with at minimum these columns:
    student_id         : unique student identifier
    state_predictions  : BKT mastery probability (float, 0-1)
    name               : student display name (required only if show_names=True)

Typical usage :
    from src.kc_mastery_box import kc_mastery_box

    chart = kc_mastery_box(df_final, mastery_threshold=0.70, practice_threshold=0.30)
"""
import pandas as pd
import altair as alt
import numpy as np
from src.classify import classify

# ── colour constants ────────────────────────────────────────────────────────

MASTERED_FILL    = "#60D394" 
MASTERED_STROKE  = "#34714F"
MASTERED_TEXT    = "#5F5E5A"

PROGRESS_FILL    = "#FFD97D"
PROGRESS_STROKE  = "#FFBA81"
PROGRESS_TEXT    = "#5F5E5A"

PRACTICE_FILL      = "#FF9B85"
PRACTICE_STROKE    = "#EE6055"
PRACTICE_TEXT      = "#5F5E5A"

BAR_FILL = '#60D394'
BAR_TRACK = "#DAE3DE"

# ── helpers ─────────────────────────────────────────────────────────────────
def tile_positions(n, cols = 8) :
    """Return (col_index, row_index) lists for n tiles in a left-to-right grid."""
    col_idx = [i % cols for i in range(n)]
    row_idx = [i // cols for i in range(n)]
    return col_idx, row_idx


def status_color(status: str, key: str) -> str:
    """Assign a colors to each mastery level."""
    mapping = {
        "Mastered":    {"fill": MASTERED_FILL, "stroke": MASTERED_STROKE, "text": MASTERED_TEXT},
        "Progressing": {"fill": PROGRESS_FILL,  "stroke": PROGRESS_STROKE,  "text": PROGRESS_TEXT},
        "Needs Practice": {"fill": PRACTICE_FILL,    "stroke": PRACTICE_STROKE,    "text": PRACTICE_TEXT},
    }
    return mapping.get(status, mapping["Needs Practice"])[key]

# ── main function ────────────────────────────────────────────────────────────

def kc_mastery_box(
    data: pd.DataFrame,
    mastery_threshold: float = 0.70,
    practice_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    show_names: bool = False,
):
    """Build a two-layer Altair chart summarising KC mastery for a class.

    Layer 1 (top)    : a horizontal progress bar showing the percentage of
                        students who have mastered the knowledge component.
    Layer 2 (middle) : a tile grid with one square per student, colour-coded
                        by mastery status (Mastered / Progressing / Needs
                        Practice), with hover tooltips showing the exact
                        mastery probability.
    Layer 3 (bottom) : a text legend with per-status counts.

    Mastery status is derived per student via classify().

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with one row per student for a single knowledge component.
        Must contain:
            student_id : unique student identifier
            state_predictions : BKT mastery probability (float, 0-1)
        Must also contain ``name`` if ``show_names=True``.
    mastery_threshold : float, default 0.70
        Minimum ``state_predictions`` value to classify a student as
        "Mastered".
    practice_threshold : float, default 0.30
        Maximum ``state_predictions`` value to classify a student as
        "Needs Practice" (values at or above this but below
        ``mastery_threshold`` are "Progressing").
    cols : int, default 8
        Number of tiles per row in the student grid.
    tile_size : int, default 38
        Pixel size of each square tile.
    tile_gap : int, default 6
        Gap between tiles in pixels.
    show_names : bool, default False
        If True, tile labels show initials derived from the ``name`` column
        (first letter of up to the first two words, uppercased). If False,
        tile labels show ``student_id``.

    Returns
    -------
    alt.VConcatChart

    Examples
    --------
    >>> chart = kc_mastery_box(df_final, mastery_threshold=0.70, practice_threshold=0.30)
    """

    # ── prepare data ────────────────────────────────────────────────────────
    df = data.copy()
    df['status']=df['state_predictions'].apply(classify, args=(mastery_threshold, practice_threshold))

    # tile grid positions
    col_idx, row_idx = tile_positions(len(df), 8)
    df["col"] = col_idx
    df["row"] = row_idx

    # colours
    df["fill"]   = df["status"].apply(lambda s: status_color(s, "fill"))
    df["stroke"] = df["status"].apply(lambda s: status_color(s, "stroke"))
    df["text_c"] = df["status"].apply(lambda s: status_color(s, "text"))

    # tile label
    if show_names:
        df["label"] = df["name"].apply(
            lambda n: "".join(p[0].upper() for p in n.split()[:2])
        )
    else :
        df["label"] = df["student_id"]

    # ── summary stats ────────────────────────────────────────────────────────
    
    n_total    = df['student_id'].nunique()
    n_mastered = sum(df["status"] == "Mastered")
    pct        = round(n_mastered / n_total * 100) if n_total else 0

    # ── progress bar ────────────────────────────────────────────────────────

    # progress bar – track
    bar_track = (
        alt.Chart(pd.DataFrame({"x": [0], "x2": [100], "y": [0]}))
        .mark_rect(
            cornerRadius=5,
            color=BAR_TRACK,
            height=20
        )
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), axis=None),
            x2="x2:Q",
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1, 1]), axis=None),
        )
    )

    # progress bar – fill
    bar_fill = (
        alt.Chart(pd.DataFrame({"x": [0], "x2": [pct], "y": [0]}))
        .mark_rect(
            cornerRadius=5,
            color=BAR_FILL,
            height=20
        )
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), axis=None),
            x2="x2:Q",
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1, 1]), axis=None),
        )
    )
    label_bar = alt.Chart(pd.DataFrame([{"Value": max(pct, 7), "Text": f"{pct}%"}])).mark_text(
            align="right",
            dx=-10,
            dy=10,
            color="black",
            fontWeight="bold",
            fontSize=14
            ).encode(
            x="Value:Q",
            y=alt.value(0),
            text="Text:N"
        )

    
    bar_chart = (bar_track + bar_fill + label_bar).properties(
        width="container",
        height=20,
        title=alt.Title(
            text=f"Percentage of class that has mastered the KC:",
            fontSize=17,
            fontWeight="normal",
            color="#888780",
            anchor="start",
        ),
    )
    
    # ── student tile grid  ───────────────────────────────────────────
    step = tile_size + tile_gap
    grid_w = cols * step - tile_gap
    n_rows = int(np.ceil(n_total / cols))
    grid_h = n_rows * step - tile_gap

    tile_bg = (
        alt.Chart(df)
        .mark_rect(
            cornerRadius=5,
        )
        .encode(
            x=alt.X(
                "col:O",
                scale=alt.Scale(
                    domain=list(range(cols)),
                    paddingInner=tile_gap / step,
                    paddingOuter=0,
                ),
                axis=None,
            ),
            y=alt.Y(
                "row:O",
                scale=alt.Scale(
                    domain=list(range(n_rows)),
                    paddingInner=tile_gap / step,
                    paddingOuter=0,
                ),
                axis=None,
            ),
            color=alt.Color(
                "fill:N",
                scale=None,   # use the raw hex values in the column
                legend=None,
            ),
            stroke=alt.Stroke("stroke:N", scale=None, legend=None),
            strokeWidth=alt.value(1),
            tooltip=[
                alt.Tooltip("label:N",      title="Student"),
                alt.Tooltip("state_predictions:Q", format=',.2%', title="Mastery Probability(%)"),
                alt.Tooltip("status:N",    title="Status"),
            ],
        )
    )


    tile_labels = (
        alt.Chart(df)
        .mark_text(
            fontSize=12,
            fontWeight="bold",
            baseline="middle",
            align="center",
        )
        .encode(
            x=alt.X("col:O", axis=None),
            y=alt.Y("row:O", axis=None),
            text=alt.Text("label:N"),
            color=alt.Color("text_c:N", scale=None, legend=None),
        )
    )

    tile_chart = (tile_bg + tile_labels).properties(
        width="container",
        height=grid_h,
        title=alt.Title(
            text=f"Students  ({n_mastered} mastered · {n_total - n_mastered} working toward mastery)",
            fontSize=17,
            fontWeight="normal",
            color="#888780",
            anchor="start",
        ),
    )

    # ── legend layer ─────────────────────────────────────────────────────────

    legend_df = pd.DataFrame([
        {"x": 0,   "label": f"■  Mastered ({n_mastered})", "color": MASTERED_STROKE},
        {"x": 110, "label": f"■  Progressing ({(df['status']=='Progressing').sum()})", "color": PROGRESS_STROKE},
        {"x": 220, "label": f"■  Needs Practice ({(df['status']=='Needs Practice').sum()})", "color": PRACTICE_STROKE},
    ])

    legend = (
        alt.Chart(legend_df)
        .mark_text(align="left", baseline="middle", fontSize=15)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, grid_w]), axis=None),
            y=alt.value(8),
            text="label:N",
            color=alt.Color("color:N", scale=None),
        )
        .properties(width="container", height=20)
    )

    # ── assemble ─────────────────────────────────────────────────────────────

    full = alt.vconcat(
        bar_chart,
        tile_chart,
        legend,
        spacing=16,
    ).configure(
        background="transparent",
        view=alt.ViewConfig(strokeOpacity=0),
    )

    return full
