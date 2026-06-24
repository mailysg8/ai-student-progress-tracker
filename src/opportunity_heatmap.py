"""
This module contains helper functions to create the opportunity dashboard and KC opportunity list on the Teacher Portal dashboard.

Two chart variants are provided:
    opp_heatmap        : a student × KC grid heatmap, coloured by practice
                          level, with click-to-highlight selection.
    opportunity_table   : a ranked table-style chart showing average
                           opportunities per KC, with a coloured pill per row.

Typical usage :
    from helpers.opportunity_charts import opp_heatmap, opportunity_table

    heatmap_chart = opp_heatmap(df_final)
    table_chart   = opportunity_table(avg_opp_df, n=5)
"""
import pandas as pd
import altair as alt

from src.classify import opp_status, compute_opportunity_counts

# ── colour constants ─────────────────────────────────────────────────────────

MASTERED_FILL   = "#60D394"
MASTERED_STROKE = "#34714F"

PROGRESS_FILL   = "#FFD97D"
PROGRESS_STROKE = "#FFBA81"

PRACTICE_FILL   = "#FF9B85"
PRACTICE_STROKE = "#EE6055"

NOTSTARTED_FILL   = "#8B9DBB"
NOTSTARTED_STROKE = "#888780"

TEXT_COLOR          = "#263744"

# ── status thresholds ────────────────────────────────────────────────────────

LOW_OPP  = 5   # fewer than this = low practice
HIGH_OPP = 15   # more than this = well practiced

def opp_heatmap(data: pd.DataFrame) -> alt.Chart:
    """
    Build an opportunity heatmap: students (rows) × KCs (columns),
    coloured by practice level.

    Parameters
    ----------
    data : raw DataFrame passed directly to compute_opportunity_counts.

    Returns
    -------
    Altair Chart ready to display or embed in a dashboard.
    """
    opp_counts = compute_opportunity_counts(data)

    color_scale = alt.Scale(
        domain=["well practiced", "some practice", "low practice", "not started"],
        range=[MASTERED_FILL, PROGRESS_FILL, PRACTICE_FILL, NOTSTARTED_FILL],
    )

    kc_selection = alt.selection_point(
        name="kc_click",
        fields=["modeling_kc_label", "student_id"],
        on="click",
        clear="dblclick",
    )

    heatmap = (
        alt.Chart(opp_counts)
        .mark_rect(cornerRadius=4)
        .encode(
            x=alt.X(
                "modeling_kc_label:N",
                title=None,
                axis=alt.Axis(
                    labelFontSize=14,
                    labelAngle=-35,
                    labelLimit=200,
                ),
            ),
            y=alt.Y("student_id:N", title=None, sort=None),
            color=alt.Color(
                "status:N",
                scale=color_scale,
                legend=alt.Legend(title="Practice Level"),
                ),
            opacity=alt.condition(
                    kc_selection, 
                    alt.value(1.0), 
                    alt.value(0.4)
                ),
            tooltip=[
                alt.Tooltip("student_id:N",           title="Student"),
                alt.Tooltip("modeling_kc_label:N",  title="KC"),
                alt.Tooltip("n_opportunities:Q",       title="Opportunities"),
                alt.Tooltip("status:N",                title="Practice Level"),
            ],
        ).add_params(kc_selection)
    )

    chart =  (
        (heatmap)
        .properties(
            width="container",      
            height=alt.Step(28),    
        )
        .configure(
            font="system-ui, sans-serif",
            background="transparent",
            view=alt.ViewConfig(strokeWidth=0),
        )
    )
    return chart

def opportunity_table(avg_opp: pd.DataFrame, n: int = 5) -> alt.Chart:
    """
    Table-style chart showing the N KCs with the average opportunities.
    """
    avg_opp = avg_opp.copy()

    # Assign status and colours based on opportunity count
    avg_opp['status'] = avg_opp['avg_opportunities'].apply(opp_status)
    avg_opp['pill_color'] = avg_opp['status'].map({
        'well practiced': MASTERED_FILL,
        'some practice':  PROGRESS_FILL,
        'low practice':   PRACTICE_FILL,
        'not started':    NOTSTARTED_FILL,
    })
    avg_opp['text_color'] = avg_opp['status'].map({
        'well practiced': TEXT_COLOR,
        'some practice':  TEXT_COLOR,
        'low practice':   TEXT_COLOR,
        'not started':    TEXT_COLOR,
    })

    avg_opp['row'] = range(len(avg_opp))

    # ── KC name column ────────────────────────────────────────────────────
    kc_labels = (
        alt.Chart(avg_opp)
        .mark_text(align='left', baseline='middle', fontSize=16, color=TEXT_COLOR)
        .encode(
            x=alt.value(10),
            y=alt.Y('row:O', axis=None),
            text='modeling_kc_label:N',
        )
    )

    # ── coloured pill behind the number ──────────────────────────────────
    pill = (
        alt.Chart(avg_opp)
        .mark_rect(cornerRadius=6, width=60, height=26)
        .encode(
            x=alt.value(510),
            y=alt.Y('row:O', axis=None),
            color=alt.Color('pill_color:N', scale=None),
        )
    )

    # ── number inside the pill ────────────────────────────────────────────
    pill_text = (
        alt.Chart(avg_opp)
        .mark_text(align='center', baseline='middle', fontSize=14, fontWeight=600)
        .encode(
            x=alt.value(510),
            y=alt.Y('row:O', axis=None),
            text=alt.Text('avg_opportunities:Q', format='.1f'),
            color=alt.Color('text_color:N', scale=None),
        )
    )

    # ── column headers ────────────────────────────────────────────────────
    header_df = pd.DataFrame([
        {'x': 10,  'label': 'Knowledge Components (KC)'},
        {'x': 400, 'label': 'Average opportunities per student'},
    ])
    headers = (
        alt.Chart(header_df)
        .mark_text(align='left', baseline='middle', fontSize=13,
                   fontWeight=600, color=TEXT_COLOR)
        .encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[0, 400]), axis=None),
            y=alt.value(0),
            text='label:N',
        )
    )

    n_rows = len(avg_opp)
    return (
        alt.vconcat(
            headers.properties(width=400, height=20),
            alt.layer(kc_labels, pill, pill_text)
            .resolve_scale(y='shared')
            .properties(width=400, height=n_rows * 40),
            spacing=2,
        )
        .configure(
            background="transparent",
            view=alt.ViewConfig(strokeWidth=0),
        )
    )