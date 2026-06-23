import pandas as pd
import altair as alt

MASTERED_FILL = "#60D394"
PRACTICE_FILL = "#FF9B85"
PROGRESS_FILL = "#FFD97D"
BAR_FILL      = "#60D394"
BAR_TRACK     = "#DAE3DE"
TEXT_COLOR    = "#263744"
LABEL_COLOR   = "#263744"


def student_kc_card(data: pd.DataFrame, student_id: str, kc_label: str):
    df = (
        data[
            (data["student_id"] == student_id) &
            (data["modeling_kc_label"] == kc_label)
        ]
        .copy()
        .reset_index(drop=True)
    )

    # ── empty state ────────────────────────────────────────────────────
    if df.empty:
        # Find any assignments/questions linked to this KC across all students
        kc_rows = data[data["modeling_kc_label"] == kc_label]
        if not kc_rows.empty:
            suggestions = (
                kc_rows[["assignment_id", "source_question"]]
                .drop_duplicates()
                .head(3)
            )
            suggestion_lines = ", ".join(
                f"{row['assignment_id']} – {row['source_question']}"
                for _, row in suggestions.iterrows()
            )
            msg = (
                f"No attempts yet for '{kc_label}'. "
                f"Try: {suggestion_lines}"
            )
        else:
            msg = f"No attempts yet for '{kc_label}'."

        return (
            alt.Chart(pd.DataFrame([{"text": msg}]))
            .mark_text(
                align="left",
                baseline="middle",
                fontSize=20,
                color=LABEL_COLOR,
            )
            .encode(
                x=alt.value(10),
                y=alt.value(60),
                text="text:N",
            )
            .properties(width="container", height=120)
            .configure_view(strokeWidth=0)
            .configure(background="transparent")
        )

    df["state_predictions"] = pd.to_numeric(df["state_predictions"], errors="coerce")
    df["correct"]           = pd.to_numeric(df["correct"], errors="coerce")
    df = df.dropna(subset=["state_predictions"])

    df["color_status"] = df["correct"].map(
        {1.0: "Correct", 0.0: "Incorrect"}
    )

    for col in ["class_date", "source_question", "assignment_id"]:
        if col in df.columns:
            df[col] = df[col].fillna("—")

    df = df[[
        "kc_attempt", "state_predictions", "color_status",
        "correct", "class_date", "source_question", "assignment_id", "unit",
    ]].copy()

    unit     = df["unit"].iloc[0]
    latest_p    = df.nlargest(1, "kc_attempt").iloc[0]["state_predictions"]
    mastery_pct = round(float(latest_p) * 100, 1)

    # ── progress bar ─────────────────────────────────────────────────────
    bar_df = pd.DataFrame([
        {"x": 0, "x2": 100,         "layer": "track"},
        {"x": 0, "x2": mastery_pct, "layer": "fill"},
    ])

    bar_track = (
        alt.Chart(bar_df[bar_df["layer"] == "track"])
        .mark_bar(cornerRadius=6, color=BAR_TRACK, height=22)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), axis=None),
            x2="x2:Q",
            y=alt.Y("layer:N", axis=None),
        )
    )

    bar_fill = (
        alt.Chart(bar_df[bar_df["layer"] == "fill"])
        .mark_bar(cornerRadius=6, color=BAR_FILL, height=22)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), axis=None),
            x2="x2:Q",
            y=alt.Y("layer:N", axis=None),
        )
    )

    label_x = max(mastery_pct-0.5, 2)
    bar_label = (
        alt.Chart(pd.DataFrame([{"x": label_x, "text": f"{mastery_pct}%"}]))
        .mark_text(
            align="right",
            baseline="middle",   
            fontWeight="bold",
            fontSize=13,
            color=TEXT_COLOR,
        )
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]), axis=None),
            y=alt.value(20),     
            text="text:N",
        )
    )

    bar_chart = (
        (bar_track + bar_fill + bar_label)
        .properties(
            width="container",
            height=40,
            title=alt.Title(
                text="Latest Mastery Probability:",
                fontSize=13,
                fontWeight="normal",
                color=LABEL_COLOR,
                anchor="start",
                dy=-2,
            ),
        )
        .resolve_scale(y="independent")
    )

    # ── line chart ────────────────────────────────────────────────────────
    color_scale = alt.Scale(
        domain=["Correct", "Incorrect"],
        range=[MASTERED_FILL, PRACTICE_FILL],
    )

    line = (
        alt.Chart(df)
        .mark_line(color="#CCCCCC", strokeWidth=2)
        .encode(
            x=alt.X("kc_attempt:Q", title="Attempt",
                    axis=alt.Axis(tickMinStep=1, tickCount=len(df))),
            y=alt.Y("state_predictions:Q", title="P(Mastery)",
                    scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format=".0%")),
        )
    )

   
    points = (
        alt.Chart(df)
        .mark_circle(size=200, strokeWidth=2)
        .encode(
            x=alt.X("kc_attempt:Q"),
            y=alt.Y("state_predictions:Q", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("color_status:N", scale=color_scale,
                            legend=alt.Legend(title="Result", orient="right")),
            stroke=alt.Color("color_status:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("kc_attempt:Q",        title="Attempt #"),
                alt.Tooltip("state_predictions:Q", title="Mastery Probability", format=".3f"),
                alt.Tooltip("correct:Q",           title="Correct"),
                alt.Tooltip("class_date:N",        title="Date"),
                alt.Tooltip("source_question:N",   title="Question"),
                alt.Tooltip("assignment_id:N",     title="Assignment"),
            ],
        )
    )

    threshold_df = pd.DataFrame([{"y": 0.7}])

    threshold = (
        alt.Chart(threshold_df)
        .mark_rule(strokeDash=[4, 4], color=LABEL_COLOR, strokeWidth=1.5)
        .encode(y="y:Q")
    )


    threshold_label = (
        alt.Chart(threshold_df)
        .mark_text(
            align="left",
            baseline="bottom",   
            dy=-4,               
            fontSize=13,
            color=LABEL_COLOR,
        )
        .encode(
            y="y:Q",
            x=alt.value(4),
            text=alt.value("Mastery threshold"),
        )
    )

    line_chart = (
        (line + threshold + threshold_label + points)
        .properties(
            width="container",
            height=220,

        )
    )

    return (
        alt.vconcat(bar_chart, line_chart, spacing=16)
        .configure_view(strokeWidth=0)
        .configure(background="transparent", autosize="fit-x")
        .configure_axis(
            labelColor=LABEL_COLOR,
            titleColor=LABEL_COLOR,
            gridColor="#EEEEEE",
            domainColor="#DDDDDD",
        )
    )