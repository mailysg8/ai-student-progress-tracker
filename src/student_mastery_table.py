import pandas as pd
import altair as alt
from src.student_status_boxes import assign_status

# ── colour constants ─────────────────────────────────────────────────────────

BAR_FILL   = "#3B82C4"
BAR_TRACK  = "#DCE6F2"
TEXT_COLOR = "#263744"
PCT_COLOR  = "#888780"

BADGE_FILL = {
    "Ahead":    "#34A853",
    "On Track": "#7DC47F",
    "At Risk":  "#FFD24D",
    "Behind":   "#F07070",
}
BADGE_TEXT = {
    "Ahead":    "#FFFFFF",
    "On Track": "#263744",
    "At Risk":  "#263744",
    "Behind":   "#FFFFFF",
}

# Canvas geometry (single shared 0..1000 x scale for every layer)
CANVAS_W = 1000
KC_X     = 10
BAR_X0   = 430
BAR_X1   = 800
PCT_X    = 815
BADGE_X0 = 880
BADGE_X1 = 970


def student_mastery_table(
    student_id: str,
    data: pd.DataFrame,
    quantile: bool = False,
    status_filter: str = "All statuses",
    row_height: int = 44,
    max_rows: int = 40,
):
    """
    Build a P(Mastery) table for a single student: one row per KC with a
    progress bar and a status badge. Mirrors the Streamlit Overview table.

    All layers share one quantitative x scale with a fixed [0, CANVAS_W]
    domain. Every horizontal position is an x / x2 field pair on that scale;
    x2 is never a standalone field against a constant x (which triggers a
    Vega-Lite "undefined type" error).
    """
    # Last attempt per KC for this student
    df = data[data["student_id"] == student_id].copy()
    df = (
        df.sort_values("order_id")
        .groupby("modeling_kc_id")
        .last()
        .reset_index()
    )

    df["status"] = assign_status(df, quantile)
    df["pct"] = (df["state_predictions"] * 100).round().astype(int)

    if status_filter != "All statuses":
        df = df[df["status"] == status_filter]

    df = df.sort_values("state_predictions", ascending=False).head(max_rows)
    df = df.reset_index(drop=True)

    # If nothing matches, show a single placeholder so the spec stays valid
    # and Vega-Lite never receives an empty/typeless field.
    if len(df) == 0:
        empty = pd.DataFrame({"row": [0], "label": ["No KCs match this filter"], "x": [KC_X]})
        msg = (
            alt.Chart(empty)
            .mark_text(align="left", baseline="middle", fontSize=14, color=PCT_COLOR)
            .encode(
                x=alt.X("x:Q", scale=alt.Scale(domain=[0, CANVAS_W]), axis=None),
                y=alt.Y("row:O", axis=None),
                text="label:N",
            )
            .properties(width=CANVAS_W, height=row_height)
        )
        return msg.configure(background="transparent", view=alt.ViewConfig(strokeWidth=0))

    df["row"] = range(len(df))
    df["fill"] = df["status"].map(BADGE_FILL)
    df["badge_text"] = df["status"].map(BADGE_TEXT)
    df["pct_label"] = df["pct"].astype(str) + "%"

    # Bar geometry as explicit fields on the shared x scale
    df["kc_x"] = KC_X
    df["bar_x0"] = BAR_X0
    df["bar_x1"] = BAR_X1
    df["bar_fill_x1"] = BAR_X0 + (df["pct"] / 100) * (BAR_X1 - BAR_X0)
    df["pct_x"] = PCT_X
    df["badge_x0"] = BADGE_X0
    df["badge_x1"] = BADGE_X1
    df["badge_cx"] = (BADGE_X0 + BADGE_X1) / 2

    total_h = len(df) * row_height

    x_scale = alt.Scale(domain=[0, CANVAS_W])
    y_enc = alt.Y("row:O", axis=None, scale=alt.Scale(paddingInner=0.3))

    # ── KC name ──────────────────────────────────────────────────────────────
    kc_labels = (
        alt.Chart(df)
        .mark_text(align="left", baseline="middle", fontSize=14, color=TEXT_COLOR)
        .encode(
            x=alt.X("kc_x:Q", scale=x_scale, axis=None),
            y=y_enc,
            text="modeling_kc_label_x:N",
            tooltip=[
                alt.Tooltip("modeling_kc_label_x:N", title="KC"),
                alt.Tooltip("state_predictions:Q", title="P(Mastery)", format=".2%"),
                alt.Tooltip("status:N", title="Status"),
            ],
        )
    )

    # ── progress bar track ───────────────────────────────────────────────────
    bar_track = (
        alt.Chart(df)
        .mark_bar(cornerRadius=6, color=BAR_TRACK, height=10)
        .encode(
            x=alt.X("bar_x0:Q", scale=x_scale, axis=None),
            x2="bar_x1:Q",
            y=y_enc,
        )
    )

    # ── progress bar fill ────────────────────────────────────────────────────
    bar_fill = (
        alt.Chart(df)
        .mark_bar(cornerRadius=6, color=BAR_FILL, height=10)
        .encode(
            x=alt.X("bar_x0:Q", scale=x_scale, axis=None),
            x2="bar_fill_x1:Q",
            y=y_enc,
        )
    )

    # ── percent label ────────────────────────────────────────────────────────
    pct_text = (
        alt.Chart(df)
        .mark_text(align="left", baseline="middle", fontSize=12, color=PCT_COLOR)
        .encode(
            x=alt.X("pct_x:Q", scale=x_scale, axis=None),
            y=y_enc,
            text="pct_label:N",
        )
    )

    # ── status badge ─────────────────────────────────────────────────────────
    badge = (
        alt.Chart(df)
        .mark_bar(cornerRadius=13, height=26)
        .encode(
            x=alt.X("badge_x0:Q", scale=x_scale, axis=None),
            x2="badge_x1:Q",
            y=y_enc,
            color=alt.Color("fill:N", scale=None, legend=None),
        )
    )
    badge_label = (
        alt.Chart(df)
        .mark_text(align="center", baseline="middle", fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("badge_cx:Q", scale=x_scale, axis=None),
            y=y_enc,
            text="status:N",
            color=alt.Color("badge_text:N", scale=None, legend=None),
        )
    )

    # ── header row ───────────────────────────────────────────────────────────
    header_df = pd.DataFrame([
        {"x": KC_X,     "label": "Skill / KC"},
        {"x": BAR_X0,   "label": "P(Mastery)"},
        {"x": BADGE_X0, "label": "Status"},
    ])
    headers = (
        alt.Chart(header_df)
        .mark_text(align="left", baseline="middle", fontSize=13,
                   fontWeight="bold", color=TEXT_COLOR)
        .encode(
            x=alt.X("x:Q", scale=x_scale, axis=None),
            y=alt.value(12),
            text="label:N",
        )
        .properties(width=CANVAS_W, height=24)
    )

    table = (
        alt.layer(kc_labels, bar_track, bar_fill, pct_text, badge, badge_label)
        .properties(width=CANVAS_W, height=total_h)
    )

    return (
        alt.vconcat(headers, table, spacing=8)
        .configure(background="transparent", view=alt.ViewConfig(strokeWidth=0))
    )