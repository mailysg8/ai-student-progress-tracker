"""Altair chart for the class-comparison panel on the Student Summary dashboard.

`class_comparison_chart` — signed difference per unit (this student – class average),
color-coded green (ahead) / coral (behind). Directly answers "Am I falling behind?".
"""
import pandas as pd
import altair as alt
from student_kpi_cards import COLORS


def class_comparison_chart(summary: dict, class_avg: dict) -> alt.Chart:
    rows = []
    for t in summary["tiles"]:
        u = t["unit"]
        if t["avg_mastery"] is None or u not in class_avg:
            continue
        diff = round(t["avg_mastery"] - class_avg[u] * 100, 1)
        rows.append({
            "unit":       u,
            "diff":       diff,
            "you":        t["avg_mastery"],
            "class_avg":  round(class_avg[u] * 100, 1),
            "direction":  "Ahead of class" if diff >= 0 else "Behind class",
        })
    df = pd.DataFrame(rows).sort_values("diff")
    unit_sort = df["unit"].tolist()

    max_abs = max(abs(df["diff"].min()), abs(df["diff"].max()), 5)

    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("unit:N", sort=unit_sort, title=None,
                    axis=alt.Axis(labelFontSize=12, labelPadding=8)),
            x=alt.X("diff:Q",
                    title="Your mastery minus class average (percentage points)",
                    scale=alt.Scale(domain=[-max_abs, max_abs])),
            color=alt.Color("direction:N",
                            scale=alt.Scale(
                                domain=["Ahead of class", "Behind class"],
                                range=[COLORS["ahead"], COLORS["behind"]]),
                            legend=alt.Legend(orient="top", title=None,
                                              labelFontSize=12, symbolSize=200)),
            tooltip=[alt.Tooltip("unit:N"),
                     alt.Tooltip("you:Q",       format=".1f", title="You (%)"),
                     alt.Tooltip("class_avg:Q", format=".1f", title="Class avg (%)"),
                     alt.Tooltip("diff:Q",      format="+.1f", title="Difference (pp)")],
        )
        .properties(height=320, width="container")
    )
