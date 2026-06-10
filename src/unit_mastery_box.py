import pandas as pd
import altair as alt
import numpy as np
from src.classify import classify
# ── colour constants ────────────────────────────────────────────────────────
 
MASTERED_FILL       = "#60D394"
MASTERED_STROKE     = "#34714F"
 
PROGRESS_FILL       = "#FFD97D"
PROGRESS_STROKE     = "#FFBA81"
 
ATTENTION_FILL    = "#FF9B85"
ATTENTION_STROKE  = "#EE6055"
 
TEXT_COLOR          = "#263744"
LABEL_COLOR         = "#888780"
BG_COLOR            = "#F5F4F0"
 
# ── helpers ─────────────────────────────────────────────────────────────────
 
def status_color(status: str, key: str) -> str:
    mapping = {
        "Mastered":          {"fill": MASTERED_FILL,    "stroke": MASTERED_STROKE},
        "Progressing":       {"fill": PROGRESS_FILL,    "stroke": PROGRESS_STROKE},
        "Need Attention": {"fill": ATTENTION_FILL, "stroke": ATTENTION_STROKE},
    }
    return mapping.get(status, mapping["Need Attention"])[key]
 
 
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
    attention_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    label_width: int = 90,
) -> alt.Chart:
    """
    Build one row of the dashboard for a single unit.
 
    Parameters
    ----------
    unit_name         : display label shown on the left
    unit_df           : DataFrame with at least these columns:
                          - modeling_kc_label   (str)  KC name shown in tooltip
                          - state_predictions   (float) mastery probability 0–1
    mastery_threshold : score >= this  → Mastered
    attention_threshold : score <= this  → Need Attention
    cols              : max tiles per row inside the grid
    tile_size         : width/height of each square in px
    tile_gap          : gap between squares in px
    label_width       : pixel width reserved for the unit label on the left
    """
    df = unit_df.copy().reset_index(drop=True)
    df["status"] = df["pct_mastered"].apply(
        classify, args=(mastery_threshold, attention_threshold)
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
            stroke=alt.Stroke("stroke:N", scale=None, legend=None),
            strokeWidth=alt.value(1.5),
            tooltip=[
                alt.Tooltip("modeling_kc_label:N", title="KC"),
                alt.Tooltip("pct_mastered:Q",  title="% of class mastered", format=".0%"),
                alt.Tooltip("status:N",              title="Status"),
            ],
        )
        .properties(width=grid_w, height=grid_h)
    )
 
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
 
 
# ── legend ───────────────────────────────────────────────────────────────────
 
def make_legend() -> alt.Chart:
    items = [
        {"status": "Mastered",          "fill": MASTERED_FILL,    "stroke": MASTERED_STROKE,    "x": 0},
        {"status": "Progressing",       "fill": PROGRESS_FILL,    "stroke": PROGRESS_STROKE,    "x": 1},
        {"status": "Need Attention", "fill": ATTENTION_FILL, "stroke": ATTENTION_STROKE, "x": 2},
    ]
    thresholds = ["≥ 70%", "30 – 70%", "≤ 30%"]
    for item, thr in zip(items, thresholds):
        item["label"] = f"{item['status']}  ({thr})"
 
    ldf = pd.DataFrame(items)
    ldf["y"] = 0
 
    squares = (
        alt.Chart(ldf)
        .mark_rect(cornerRadius=4, width=14, height=14)
        .encode(
            x=alt.X("x:O", axis=None),
            y=alt.Y("y:O", axis=None),
            color=alt.Color("fill:N",   scale=None, legend=None),
            stroke=alt.Stroke("stroke:N", scale=None, legend=None),
            strokeWidth=alt.value(1.5),
        )
    )
 
    labels = (
        alt.Chart(ldf)
        .mark_text(align="left", baseline="middle", dx=12, fontSize=12, color=LABEL_COLOR)
        .encode(
            x=alt.X("x:O", axis=None),
            y=alt.Y("y:O", axis=None),
            text="label:N",
        )
    )
 
    return (
        (squares + labels)
        .properties(width=520, height=24)
        .configure_view(strokeWidth=0)
    )
 
def unit_mastery(
    data: pd.DataFrame,
    mastery_threshold: float = 0.70,
    attention_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    label_width: int = 90
) -> alt.VConcatChart:
    """
    Build the full multi-unit KC mastery grid.
 
    Parameters
    ----------
    data              : DataFrame with columns for unit, KC label, and mastery score
    mastery_threshold : score >= this  → Mastered          (default: 0.70)
    attention_threshold : score <= this  → Need Attention (default: 0.30)
    cols              : max tiles per row                   (default: 8)
    tile_size         : tile width/height in px             (default: 38)
    tile_gap          : gap between tiles in px             (default: 6)
    label_width       : width of the unit-name column       (default: 90)
    title             : chart title                         (default: "Unit Mastery Overview")
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
            attention_threshold=attention_threshold,
            cols=cols,
            tile_size=tile_size,
            tile_gap=tile_gap,
            label_width=label_width,
        )
        for unit in units
    ]
 
    # summary counts
    df["_status"] = df["pct_mastered"].apply(
        classify, args=(mastery_threshold, attention_threshold)
    )
    n_mastered    = (df["_status"] == "Mastered").sum()
    n_progressing = (df["_status"] == "Progressing").sum()
    n_needs       = (df["_status"] == "Need Attention").sum()
 
    grid_w = cols * (tile_size + tile_gap) - tile_gap
    total_w = label_width + 16 + grid_w  

    legend_df = pd.DataFrame([
        {"order": 0, "label": f"■  Mastered ({n_mastered})",       "color": MASTERED_STROKE},
        {"order": 1, "label": f"■  Need Attention ({n_needs})",    "color": ATTENTION_STROKE},
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