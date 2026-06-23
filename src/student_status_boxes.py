import pandas as pd
import altair as alt

# ── colour constants (shared palette) ────────────────────────────────────────

MASTERED_FILL    = "#34A853"   # green
PROGRESSING_FILL = "#FFD24D"   # yellow
NEEDS_FILL       = "#F07070"   # red
LABEL_DARK    = "#263744"
LABEL_LIGHT   = "#FFFFFF"

# ── status classification (3-tier, absolute) ─────────────────────────────────

def classify_3(score: float) -> str:
    """
    Three-tier absolute classification used by the Student Overview boxes.

    Mastered       : P(mastery) >= 0.65
    Progressing    : 0.35 <= P(mastery) < 0.65
    Needs Practice : P(mastery) < 0.35
    """
    if score >= 0.65:
        return "Mastered"
    elif score >= 0.35:
        return "Progressing"
    else:
        return "Needs Practice"


def compute_quantile_cuts(data: pd.DataFrame):
    """
    Compute class-wide quantile cut points from every student's last attempt
    per KC. Returns the two thresholds (q33, q67) that split the whole class
    distribution of P(mastery) into three equal-sized buckets.

    These cuts are shared across all students so that a generally strong
    student is not forced to have a third of their KCs marked "Needs Practice".
    """
    last = (
        data.sort_values("order_id")
        .groupby(["student_id", "modeling_kc_id"])
        .last()
        .reset_index()
    )
    q = last["state_predictions"].quantile([1 / 3, 2 / 3])
    return float(q.loc[1 / 3]), float(q.loc[2 / 3])


def classify_quantile(score: float, cuts) -> str:
    """Classify a single score against class-wide quantile cut points."""
    q33, q67 = cuts
    if score >= q67:
        return "Mastered"
    elif score >= q33:
        return "Progressing"
    else:
        return "Needs Practice"


def assign_status(df: pd.DataFrame, quantile: bool, cuts=None) -> pd.Series:
    """
    Assign a status per row.

    quantile=False        : fixed absolute thresholds (classify_3)
    quantile=True, cuts   : class-wide relative status — each score is compared
                            against shared class quantile cut points, so a
                            student's mix reflects how they rank within the
                            whole class rather than only within themselves
    quantile=True, no cuts : fallback to within-student ranking (legacy)
    """
    scores = df["state_predictions"]
    if not quantile:
        return scores.apply(classify_3)

    if cuts is not None:
        return scores.apply(lambda s: classify_quantile(s, cuts))

    # Legacy fallback: rank within this student only
    if len(scores) < 3:
        return scores.apply(classify_3)
    ranks = scores.rank(method="first", ascending=True, pct=True)
    bins = pd.cut(
        ranks,
        bins=[0.0, 1 / 3, 2 / 3, 1.0],
        labels=["Needs Practice", "Progressing", "Mastered"],
        include_lowest=True,
    )
    return bins.astype(str)


# ── main function ────────────────────────────────────────────────────────────

def student_status_boxes(
    student_id: str,
    data: pd.DataFrame,
    quantile: bool = False,
    cuts=None,
    box_height: int = 150,
):
    """
    Build three status summary cards for a single student.

    Each card shows a status label (top-left), the percentage of the student's
    KCs in that status (large, centred) and the KC count (bottom-left).

    All layers share one quantitative x scale (domain 0..100, three equal
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
    df["status"] = assign_status(df, quantile, cuts)

    order = ["Mastered", "Progressing", "Needs Practice"]
    fills = {
        "Mastered": MASTERED_FILL,
        "Progressing": PROGRESSING_FILL,
        "Needs Practice": NEEDS_FILL,
    }
    # Darker fills carry light text; lighter fills carry dark text
    text_colors = {
        "Mastered": LABEL_LIGHT,
        "Progressing": LABEL_DARK,
        "Needs Practice": LABEL_LIGHT,
    }

    n_total = len(df)
    counts = df["status"].value_counts().reindex(order, fill_value=0)

    # Three equal slots on a 0..100 x scale, with a small gap between cards
    slot_w = 100.0 / 3.0
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
            "x_text": x0 + 1.0,          # left padding for labels
            "x_pct": x1 - 1.0,           # right padding for the big number
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