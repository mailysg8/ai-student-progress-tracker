"""Altair charts for the unit-level breakdown on the Student Summary dashboard.

`unit_breakdown_chart` — one stacked horizontal bar per unit, colored by KC status.
Tells the student at a glance: how many skills in each unit are mastered, still
developing, need practice, or unattempted.
"""
import pandas as pd
import altair as alt
from student_kpi_cards import COLORS


STATUS_ORDER = ["Mastered", "Developing", "Needs practice", "Unattempted"]
STATUS_COLORS = [COLORS["mastered"], COLORS["developing"], COLORS["needs"], COLORS["unattempted"]]


def unit_breakdown_chart(summary: dict) -> alt.Chart:
    """Stacked horizontal bars: one row per unit, colored segments per KC status."""
    rows = []
    for t in summary["tiles"]:
        rows.append({"unit": t["unit"], "status": "Mastered",       "count": t["n_mastered"]})
        rows.append({"unit": t["unit"], "status": "Developing",     "count": t["n_developing"]})
        rows.append({"unit": t["unit"], "status": "Needs practice", "count": t["n_needs"]})
        rows.append({"unit": t["unit"], "status": "Unattempted",    "count": t["n_unattempted"]})
    df = pd.DataFrame(rows)

    unit_sort = [t["unit"] for t in summary["tiles"]]

    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("unit:N", sort=unit_sort, title=None,
                    axis=alt.Axis(labelFontSize=12, labelPadding=8)),
            x=alt.X("count:Q", stack="zero", title="Skills in this unit",
                    axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("status:N",
                            scale=alt.Scale(domain=STATUS_ORDER, range=STATUS_COLORS),
                            legend=alt.Legend(orient="top", title=None,
                                              labelFontSize=12, symbolSize=200)),
            order=alt.Order("status:N", sort="ascending"),
            tooltip=["unit:N", "status:N", "count:Q"],
        )
        .properties(height=320, width="container")
    )


def unit_avg_chart(summary: dict) -> alt.Chart:
    """Per-unit average mastery percentage as horizontal bars, color-coded by tier."""
    rows = []
    for t in summary["tiles"]:
        if t["avg_mastery"] is None:
            continue
        if   t["tier"] == "green":  c = COLORS["mastered"]
        elif t["tier"] == "yellow": c = COLORS["developing"]
        elif t["tier"] == "red":    c = COLORS["needs"]
        else:                       c = COLORS["unattempted"]
        rows.append({"unit": t["unit"], "mastery": t["avg_mastery"], "color": c})
    df = pd.DataFrame(rows).sort_values("mastery")
    unit_sort = df["unit"].tolist()

    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("unit:N", sort=unit_sort, title=None,
                    axis=alt.Axis(labelFontSize=12, labelPadding=8)),
            x=alt.X("mastery:Q", title="Average mastery (%)",
                    scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("color:N", scale=None, legend=None),
            tooltip=[alt.Tooltip("unit:N"),
                     alt.Tooltip("mastery:Q", format=".1f", title="Mastery (%)")],
        )
        .properties(height=320, width="container")
    )
