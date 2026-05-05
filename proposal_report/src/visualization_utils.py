"""
Visualisation functions for proposal report
"""

import pandas as pd
import altair as alt

def create_kc_coverage_chart(student_observations : pd.DataFrame):
    student_observations['kc_id']=student_observations['primary_kc_id'].str.extract(r'(\.(\d+)\.)')[1]
    kc_coverage = student_observations.groupby('kc_id')[['student_id']].agg('count').reset_index()
    plot = alt.Chart(kc_coverage).encode(
    x=alt.X('student_id', title='Count'),
    y=alt.Y('kc_id:N', sort='x', title='Knowledge Component'),
    text='student_id'
    ).properties(
        title='KC coverage Imbalance'
    )
    return plot.mark_bar() + plot.mark_text(align='left', dx=2)


def create_assignement_spread_chart(student_observations : pd.DataFrame):
    assignement_avg = student_observations.groupby(['student_id','assignment_id']).agg('sum').reset_index()[['student_id','assignment_id','score','max_score']]
    assignement_avg['percent_score'] = round(assignement_avg['score']/assignement_avg['max_score']*100,1)
    chart = alt.Chart(assignement_avg).mark_bar().encode(
        x=alt.X('percent_score', title='Score (%)', bin=True),
        y=alt.Y('count()', title='Nb of students') 
    )

    mean_line = alt.Chart(assignement_avg).mark_rule(color='red').encode(
        x='mean(percent_score):Q'
    )

    return (chart + mean_line).facet(
        column=alt.Column('assignment_id:N', title = 'Assignment'), 
        title='Wide spread in student performance within assignments'
    )

def create_performance_band_chart(overall_scores : pd.DataFrame):
    chart = alt.Chart(overall_scores).mark_bar().encode(
    x=alt.X('count()', title='Nb of students'),
    y=alt.Y('performance_band', title='Performance band', sort='-x') 
    ).properties(
        title='Most of the students are performing as expected'
    )
    return chart