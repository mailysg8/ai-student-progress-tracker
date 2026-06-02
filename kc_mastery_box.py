import pandas as pd
import altair as alt
import numpy as np

# ── colour constants ────────────────────────────────────────────────────────

MASTERED_FILL    = "#60D394" 
MASTERED_STROKE  = "#34714F"
MASTERED_TEXT    = "#5F5E5A"

PROGRESS_FILL    = "#FFD97D"
PROGRESS_STROKE  = "#FFBA81"
PROGRESS_TEXT    = "#5F5E5A"

ATTENTION_FILL      = "#FF9B85"
ATTENTION_STROKE    = "#EE6055"
ATTENTION_TEXT      = "#5F5E5A"

BAR_FILL = '#60D394'
BAR_TRACK = "#DAE3DE"

# ── helpers ─────────────────────────────────────────────────────────────────

def classify(score, mastery_threshold=0.5, warning_threshold=0.1):
    if score >= mastery_threshold:
        return "Mastered"
    elif score <= warning_threshold:
        return "Needs Attention" 
    else:
        return "Progressing"


def tile_positions(n, cols = 8) :
    """Return (col_index, row_index) lists for n tiles in a left-to-right grid."""
    col_idx = [i % cols for i in range(n)]
    row_idx = [i // cols for i in range(n)]
    return col_idx, row_idx


def status_color(status: str, key: str) -> str:
    mapping = {
        "Mastered":    {"fill": MASTERED_FILL, "stroke": MASTERED_STROKE, "text": MASTERED_TEXT},
        "Progressing": {"fill": PROGRESS_FILL,  "stroke": PROGRESS_STROKE,  "text": PROGRESS_TEXT},
        "Needs Attention": {"fill": ATTENTION_FILL,    "stroke": ATTENTION_STROKE,    "text": ATTENTION_TEXT},
    }
    return mapping.get(status, mapping["Needs Attention"])[key]

# ── main function ────────────────────────────────────────────────────────────

def kc_mastery_box(
    kc_name: str,
    data: pd.DataFrame,
    mastery_threshold: float = 0.70,
    warning_threshold: float = 0.30,
    cols: int = 8,
    tile_size: int = 38,
    tile_gap: int = 6,
    show_names: bool = False,
) : 
    """
    Build a two-layer Altair chart:
      • Top card  – KC name, mastery %, progress bar, legend
      • Bottom grid – one tile per student coloured by mastery status

    Parameters
    ----------
    kc_name    : displayed name of the knowledge component
    students   : DataFrame with at least columns ``name`` (str) and ``score`` (float 0-1).
                 An optional ``student_id`` column is used for tile labels when present
                 and show_names is False; otherwise initials are derived from ``name``.
    threshold  : mastery cut-off (default 0.80)
    cols       : tiles per row in the student grid (default 8)
    tile_size  : pixel size of each square tile (default 38)
    tile_gap   : gap between tiles in pixels (default 6)
    show_names : if True, show name initials (from ``name`` column) instead of ``student_id``.

    
    Returns
    -------
    alt.VConcatChart  – use .show() or return from a Quarto cell
    """

    # ── prepare data ────────────────────────────────────────────────────────
    df = data.copy()
    df['status']=df['state_predictions'].apply(classify, args=(mastery_threshold, warning_threshold))

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
        df["label"] = df["user_id"]

    # ── summary stats ────────────────────────────────────────────────────────
    
    n_total    = df['user_id'].nunique()
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
    label_bar = alt.Chart(pd.DataFrame([{"Value": max(pct, 10), "Text": f"{pct}%"}])).mark_text(
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

    title_layer = alt.Chart(pd.DataFrame([{"text": kc_name}])).mark_text(
    align="left",
    baseline="top",
    fontSize=20,
    fontWeight="bold",
    color="#000000",
    ).encode(
        x=alt.value(0),
        y=alt.value(0),
        text="text:N",
    ).properties(width="container", height=30)
    
    bar_chart = (bar_track + bar_fill + label_bar).properties(
        width=350,
        height=20,
        title=alt.Title(
            text=f"Percentage of class that has mastered the KC:",
            fontSize=12,
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
            fontSize=10,
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
        width=grid_w,
        height=grid_h,
        title=alt.Title(
            text=f"Students  ({n_mastered} mastered · {n_total - n_mastered} working toward mastery)",
            fontSize=12,
            fontWeight="normal",
            color="#888780",
            anchor="start",
        ),
    )

    # ── legend layer ─────────────────────────────────────────────────────────

    legend_df = pd.DataFrame([
        {"x": 0,   "label": f"■  Mastered ({n_mastered})", "color": MASTERED_STROKE},
        {"x": 100, "label": f"■  Progressing ({(df['status']=='Progressing').sum()})", "color": PROGRESS_STROKE},
        {"x": 220, "label": f"■  Need Attention ({(df['status']=='Need Attention').sum()})", "color": ATTENTION_STROKE},
    ])

    legend = (
        alt.Chart(legend_df)
        .mark_text(align="left", baseline="middle", fontSize=11)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, grid_w]), axis=None),
            y=alt.value(8),
            text="label:N",
            color=alt.Color("color:N", scale=None),
        )
        .properties(width=grid_w, height=20)
    )

    # ── assemble ─────────────────────────────────────────────────────────────

    full = alt.vconcat(
        title_layer,
        bar_chart,
        tile_chart,
        legend,
        spacing=16,
    ).configure(
        background="transparent",
        view=alt.ViewConfig(strokeOpacity=0),
    )

    return full
