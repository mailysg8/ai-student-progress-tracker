import pandas as pd
import altair as alt

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

# ── helpers ──────────────────────────────────────────────────────────────────

def opp_status(n: int) -> str:
    if n == 0:          return "not started"
    elif n >= HIGH_OPP: return "well practiced"
    elif n >= LOW_OPP:  return "some practice"
    else:               return "low practice"


def compute_opportunity_counts(data: pd.DataFrame) -> pd.DataFrame:
    """
    For each student × KC pair, compute the total number of practice
    opportunities. Missing combinations are filled with 0 / 'not started'.

    Parameters
    ----------
    data : DataFrame containing 'student_id', 'modeling_kc_id',
           'modeling_kc_label', and 'order_id' columns.

    Returns
    -------
    DataFrame with columns:
        student_id, modeling_kc_label, n_opportunities, status
    """
    # Opportunity number per student per KC
    data = data.copy()
    data['opportunity'] = (
        data
        .groupby(['student_id', 'modeling_kc_id'])
        .cumcount() + 1
    )

    # Max opportunity = total practice count
    opp_counts = (
        data
        .groupby(['student_id', 'modeling_kc_label'])['opportunity']
        .max()
        .reset_index()
        .rename(columns={'opportunity': 'n_opportunities'})
    )

    # Fill in every student × KC combination (including not started)
    all_students = opp_counts['student_id'].unique()
    all_kcs      = opp_counts['modeling_kc_label'].unique()

    full_index = pd.MultiIndex.from_product(
        [all_students, all_kcs],
        names=['student_id', 'modeling_kc_label']
    )

    opp_counts = (
        opp_counts
        .set_index(['student_id', 'modeling_kc_label'])
        .reindex(full_index)
        .reset_index()
    )

    opp_counts['n_opportunities'] = opp_counts['n_opportunities'].fillna(0).astype(int)
    opp_counts['status']          = opp_counts['n_opportunities'].apply(opp_status)

    return opp_counts


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
    text_scale = alt.Scale(
        domain=["well practiced", "some practice", "low practice", "not started"],
        range=[MASTERED_STROKE, PROGRESS_STROKE, PRACTICE_STROKE, NOTSTARTED_STROKE],
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
            width="container",      # fills available width
            height=alt.Step(28),    # keep row height fixed per student,
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