"""
This module contains helper functions to build the unit mastery overview element for the Teacher
Portal dashboard.

Three pieces compose the final chart:
    unit_kc_chart : one unit's row — a label plus a grid of KC tiles.
    unit_mastery  : the full assembled grid across all units, plus an
                    inline summary legend.

Expects a data DataFrame (passed to unit_mastery) with at minimum:
    unit                : str, e.g. "Unit 1" (must contain a digit)
    modeling_kc_id       : KC identifier
    modeling_kc_label    : KC display name
    state_predictions    : per-student BKT mastery probability (float, 0-1)

Typical usage :
    from src.unit_mastery_box import unit_mastery

    chart = unit_mastery(df_final, mastery_threshold=0.70, practice_threshold=0.30)
"""

import pandas as pd
import altair as alt
import numpy as np
from src.classify import classify

# ── colour constants ────────────────────────────────────────────────────────
 
MASTERED_FILL       = "#60D394"
MASTERED_STROKE     = "#34714F"
 
PROGRESS_FILL       = "#FFD97D"
PROGRESS_STROKE     = "#FFBA81"
 
PRACTICE_FILL    = "#FF9B85"
PRACTICE_STROKE  = "#EE6055"
 
TEXT_COLOR          = "#263744"
LABEL_COLOR         = "#888780"
BG_COLOR            = "#F5F4F0"
 
# ── helpers ─────────────────────────────────────────────────────────────────
 
def status_color(status: str, key: str) -> str:
    """Assign a colors to each mastery level."""
    mapping = {
        "Mastered":          {"fill": MASTERED_FILL,    "stroke": MASTERED_STROKE},
        "Progressing":       {"fill": PROGRESS_FILL,    "stroke": PROGRESS_STROKE},
        "Needs Practice": {"fill": PRACTICE_FILL, "stroke": PRACTICE_STROKE},
    }
    return mapping.get(status, mapping["Needs Practice"])[key]
 
 
def tile_positions(n: int, cols: int = 8):
    """Return (col_index, row_index) lists for n tiles in a left-to-right grid."""
    col_idx = [i % cols for i in range(n)]
    row_idx = [i // cols for i in range(n)]
    return col_idx, row_idx
 
 
# ── per-unit tile chart ──────────────────────────────────────────────────────
 
def unit_kc_chart(
    unit_name: str,
    unit_df: pd.DataFrame,
    mastery_threshold: float = 0.70,
    practice_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    label_width: int = 90,
) -> alt.Chart:
    """Build one row of the dashboard for a single unit.

    Renders a left-aligned unit label next to a left-to-right grid of
    clickable tiles, one per knowledge component in ``unit_df``, coloured
    by mastery status. Clicking a tile toggles its highlight; clicking
    a second time, or double-clicking, clears the selection.

    Parameters
    ----------
    unit_name : str
        Display label shown to the left of the tile grid.
    unit_df : pd.DataFrame
        DataFrame for this unit only, with at least:
            modeling_kc_label : str, KC name shown in the tooltip
            pct_mastered       : float in [0, 1], fraction of the class
                                  that has mastered this KC
    mastery_threshold : float, default 0.70
        Minimum ``pct_mastered`` to classify a KC as "Mastered".
    practice_threshold : float, default 0.30
        Maximum ``pct_mastered`` to classify a KC as "Needs Practice".
    cols : int, default 8
        Maximum tiles per row before wrapping to a new row inside the grid.
    tile_size : int, default 38
        Width/height of each square tile, in pixels.
    tile_gap : int, default 6
        Gap between tiles, in pixels.
    label_width : int, default 90
        Pixel width reserved for the unit label column on the left.

    Returns
    -------
    alt.Chart
        A horizontally concatenated label + tile grid for this unit.
    """
    df = unit_df.copy().reset_index(drop=True)
    df["status"] = df["pct_mastered"].apply(
        classify, args=(mastery_threshold, practice_threshold)
    )
 
    # grid positions (KC = one tile)
    col_idx, row_idx = tile_positions(len(df), cols)
    df["col"] = col_idx
    df["row"] = row_idx
 
    # colours
    df["fill"]   = df["status"].apply(lambda s: status_color(s, "fill"))
    df["stroke"] = df["status"].apply(lambda s: status_color(s, "stroke"))
 
    # grid dimensions
    step   = tile_size + tile_gap
    grid_w = cols * step - tile_gap
    n_rows = int(np.ceil(len(df) / cols))
    grid_h = n_rows * step - tile_gap

    kc_selection = alt.selection_point(
        name=f"{unit_name}_click",
        fields=["col", "row"],
        toggle=True,
        on="click",
        clear="dblclick",
    )
 
    # ── tile rectangles ──────────────────────────────────────────────────────
    tiles = (
        alt.Chart(df)
        .mark_rect(cornerRadius=5)
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
            color=alt.Color("fill:N",   scale=None, legend=None),
            opacity=alt.condition(
                    kc_selection, 
                    alt.value(1.0), 
                    alt.value(0.4)
                ),
            stroke=alt.Stroke("stroke:N", scale=None, legend=None),
            strokeWidth=alt.value(1.5),
            tooltip=[
                alt.Tooltip("modeling_kc_label:N", title="KC"),
                alt.Tooltip("pct_mastered:Q",  title="% of class mastered", format=".0%"),
                alt.Tooltip("status:N",              title="Status"),
            ],
        )
        .properties(width=grid_w, height=grid_h)
    ).add_params(kc_selection)
 
    # ── unit label on the left ───────────────────────────────────────────────
    label_df = pd.DataFrame({"x": [0], "y": [0], "label": [unit_name]})
    label = (
        alt.Chart(label_df)
        .mark_text(
            align="right",
            baseline="middle",
            fontSize=18,
            fontWeight=500,
            color=TEXT_COLOR,
        )
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 1]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1, 1]), axis=None),
            text="label:N",
        )
        .properties(width=label_width, height=grid_h)
    )
 
    return alt.hconcat(label, tiles, spacing=16).resolve_scale(
        x="independent", y="independent"
    )



def unit_mastery(
    data: pd.DataFrame,
    mastery_threshold: float = 0.70,
    practice_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    label_width: int = 90,
) -> alt.VConcatChart:
    """Build the full multi-unit KC mastery grid with a summary legend.

    For each (unit, KC) pair, computes the fraction of students whose
    state_predictions meets mastery_threshold ("pct_mastered"), classifies
    each KC by that fraction via classify(), then renders one tile-grid
    row per unit (via unit_kc_chart) stacked vertically, followed by an
    inline legend showing Mastered / Needs Practice / Progressing counts
    across all KCs and units.

    Units are sorted numerically by the digit embedded in their name
    (e.g. "Unit 2" before "Unit 10"), then by ascending pct_mastered
    within each unit.

    Parameters
    ----------
    data : pd.DataFrame
        Full observations DataFrame. Must contain 'unit', 'modeling_kc_id',
        'modeling_kc_label', and 'state_predictions'.
    mastery_threshold : float, default 0.70
        Minimum per-student state_predictions to count as "mastered" when
        computing pct_mastered, and minimum pct_mastered to classify a KC
        as "Mastered".
    practice_threshold : float, default 0.30
        Maximum pct_mastered to classify a KC as "Needs Practice".
    cols : int, default 8
        Maximum tiles per row within each unit's grid.
    tile_size : int, default 38
        Width/height of each square tile, in pixels.
    tile_gap : int, default 6
        Gap between tiles, in pixels.
    label_width : int, default 90
        Pixel width reserved for each unit's label column.

    Returns
    -------
    alt.VConcatChart
        One tile-grid row per unit, stacked vertically, followed by a
        summary legend row.


    Examples
    --------
    >>> chart = unit_mastery(df_final, mastery_threshold=0.70, practice_threshold=0.30)
    """

    df = (
        data
        .groupby(['unit','modeling_kc_id','modeling_kc_label'])['state_predictions']
        .apply(lambda x: (x >= mastery_threshold).mean())
        .reset_index()
        .rename(columns={'state_predictions': 'pct_mastered'})
    )

    # Extract unit number for correct numeric ordering
    df['unit_num'] = df['unit'].str.extract(r'(\d+)').astype(int)
    df = df.sort_values(['unit_num', 'pct_mastered']).drop(columns='unit_num')
 
    units = df["unit"].unique()
 
    rows = [
        unit_kc_chart(
            unit_name=unit,
            unit_df=df[df["unit"] == unit][["modeling_kc_label", "pct_mastered"]],
            mastery_threshold=mastery_threshold,
            practice_threshold=practice_threshold,
            cols=cols,
            tile_size=tile_size,
            tile_gap=tile_gap,
            label_width=label_width,
        )
        for unit in units
    ]
 
    # summary counts
    df["_status"] = df["pct_mastered"].apply(
        classify, args=(mastery_threshold, practice_threshold)
    )
    n_mastered    = (df["_status"] == "Mastered").sum()
    n_progressing = (df["_status"] == "Progressing").sum()
    n_needs       = (df["_status"] == "Needs Practice").sum()
 
    grid_w = cols * (tile_size + tile_gap) - tile_gap
    total_w = label_width + 16 + grid_w  

    legend_df = pd.DataFrame([
        {"order": 0, "label": f"■  Mastered ({n_mastered})",       "color": MASTERED_STROKE},
        {"order": 1, "label": f"■  Needs Practice ({n_needs})",    "color": PRACTICE_STROKE},
        {"order": 2, "label": f"■  Progressing ({n_progressing})", "color": PROGRESS_STROKE},
    ])

    legend = (
        alt.Chart(legend_df)
        .mark_text(align="center", baseline="middle", fontSize=15)
        .encode(
            x=alt.X(
                "order:O",
                axis=None,
                scale=alt.Scale(paddingOuter=0.5, paddingInner=0.3),
            ),
            y=alt.value(10),
            text="label:N",
            color=alt.Color("color:N", scale=None),
        )
        .properties(width=total_w, height=24)
    )

    return (
        alt.vconcat(*rows, legend, spacing=12)
        .configure_view(strokeWidth=0)
        .configure_concat(spacing=12)
    )