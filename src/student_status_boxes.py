import pandas as pd
import altair as alt

# ── colour constants (shared palette) ────────────────────────────────────────

AHEAD_FILL    = "#34A853"
ONTRACK_FILL  = "#7DC47F"
ATRISK_FILL   = "#FFD24D"
BEHIND_FILL   = "#F07070"
LABEL_DARK    = "#263744"
LABEL_LIGHT   = "#FFFFFF"

# ── status classification (4-tier, absolute) ─────────────────────────────────

def classify_4(score: float) -> str:
    """Four-tier absolute classification used by the Student Overview boxes."""
    if score >= 0.80:
        return "Ahead"
    elif score >= 0.55:
        return "On Track"
    elif score >= 0.30:
        return "At Risk"
    else:
        return "Behind"


def assign_status(df: pd.DataFrame, quantile: bool) -> pd.Series:
    """
    Assign a status per row.

    quantile=False : fixed absolute thresholds (classify_4)
    quantile=True  : relative ranking, splitting rows into four ~equal buckets
                     (top 25% Ahead ... bottom 25% Behind)
    """
    scores = df["state_predictions"]
    if not quantile or len(scores) < 4:
        return scores.apply(classify_4)

    ranks = scores.rank(method="first", ascending=True, pct=True)
    bins = pd.cut(
        ranks,
        bins=[0.0, 0.25, 0.50, 0.75, 1.0],
        labels=["Behind", "At Risk", "On Track", "Ahead"],
        include_lowest=True,
    )
    return bins.astype(str)


# ── main function ────────────────────────────────────────────────────────────

def student_status_boxes(
    student_id: str,
    data: pd.DataFrame,
    quantile: bool = False,
    box_height: int = 150,
):
    """
    Build four status summary cards for a single student.

    Each card shows a status label (top-left), the percentage of the student's
    KCs in that status (large, centred) and the KC count (bottom-left).

    All layers share one quantitative x scale (domain 0..100, four 25-wide
    slots) and one quantitative y scale (domain 0..box_height) so text always
    lands inside its card. x2 is always a field on the shared scale, never a
    standalone field against a constant x.
    """
    # Keep the last attempt per KC for this student
    df = data[data["student_id"] == student_id].copy()
    df = (
        df.sort_values("order_id")
        .groupby("modeling_kc_id")
        .last()
        .reset_index()
    )
    df["status"] = assign_status(df, quantile)

    order = ["Ahead", "On Track", "At Risk", "Behind"]
    fills = {
        "Ahead": AHEAD_FILL, "On Track": ONTRACK_FILL,
        "At Risk": ATRISK_FILL, "Behind": BEHIND_FILL,
    }
    # Darker fills carry light text; lighter fills carry dark text
    text_colors = {
        "Ahead": LABEL_LIGHT, "On Track": LABEL_DARK,
        "At Risk": LABEL_DARK, "Behind": LABEL_LIGHT,
    }

    n_total = len(df)
    counts = df["status"].value_counts().reindex(order, fill_value=0)

    # Four equal slots on a 0..100 x scale, with a small gap between cards
    slot_w = 25.0
    gap = 1.5
    rows = []
    for i, status in enumerate(order):
        n = int(counts[status])
        pct = round(n / n_total * 100) if n_total else 0
        x0 = i * slot_w + gap / 2
        x1 = (i + 1) * slot_w - gap / 2
        rows.append({
            "x0": x0,
            "x1": x1,
            "x_text": x0 + 1.2,          # left padding for labels
            "x_pct": x1 - 1.2,           # right padding for the big number
            "status": status,
            "fill": fills[status],
            "text_c": text_colors[status],
            "pct_text": f"{pct} %",
            "count_text": f"{n} KCs",
        })
    box_df = pd.DataFrame(rows)

    x_scale = alt.Scale(domain=[0, 100])
    y_scale = alt.Scale(domain=[0, box_height])

    # ── card rectangles (x and x2 both fields on the shared scale) ───────────
    # Cards span the full box height via a y / y2 field pair on a 0..box_height
    # scale, so they always fill the card area regardless of layout.
    box_df["y0"] = 0
    box_df["y1"] = box_height
    cards = (
        alt.Chart(box_df)
        .mark_rect(cornerRadius=12)
        .encode(
            x=alt.X("x0:Q", scale=x_scale, axis=None),
            x2="x1:Q",
            y=alt.Y("y0:Q", scale=y_scale, axis=None),
            y2="y1:Q",
            color=alt.Color("fill:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("status:N", title="Status"),
                alt.Tooltip("count_text:N", title="KCs"),
            ],
        )
    )

    # ── status label (top-left) ──────────────────────────────────────────────
    status_label = (
        alt.Chart(box_df)
        .mark_text(align="left", baseline="top", fontSize=15, fontWeight="bold")
        .encode(
            x=alt.X("x_text:Q", scale=x_scale, axis=None),
            y=alt.value(16),
            text="status:N",
            color=alt.Color("text_c:N", scale=None, legend=None),
        )
    )

    # ── big percentage (centred) ─────────────────────────────────────────────
    pct_label = (
        alt.Chart(box_df)
        .mark_text(align="right", baseline="middle", fontSize=30, fontWeight="bold")
        .encode(
            x=alt.X("x_pct:Q", scale=x_scale, axis=None),
            y=alt.value(box_height / 2),
            text="pct_text:N",
            color=alt.Color("text_c:N", scale=None, legend=None),
        )
    )

    # ── KC count (bottom-left) ───────────────────────────────────────────────
    count_label = (
        alt.Chart(box_df)
        .mark_text(align="left", baseline="bottom", fontSize=12)
        .encode(
            x=alt.X("x_text:Q", scale=x_scale, axis=None),
            y=alt.value(box_height - 14),
            text="count_text:N",
            color=alt.Color("text_c:N", scale=None, legend=None),
        )
    )

    return (
        alt.layer(cards, status_label, pct_label, count_label)
        .properties(width=900, height=box_height)
        .configure(background="transparent", view=alt.ViewConfig(strokeWidth=0))
    )