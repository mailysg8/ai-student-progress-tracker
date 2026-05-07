"""
Visualisation and summary functions for proposal report
"""

import pandas as pd
import altair as alt

def create_kc_coverage_chart(kc : pd.DataFrame):
    chart = alt.Chart(kc).mark_bar().encode(
    x=alt.X('num_items', title='Number of items').bin(maxbins=15),
    y=alt.Y('count()', title='Number of KCs'),
    tooltip=['count()']  
    ).properties(
        title='KC Coverage Imbalance'
    )
    return chart
    
def get_student_kc_coverage(student_id, student_observations, kc_coverage):
    q_to_kc = (student_observations
               .set_index('student_id')
               .loc[student_id, ['assignment_id', 'observation_id', 'all_kc_ids']])
    q_to_kc['kc_covered'] = q_to_kc['all_kc_ids'].str.split('|')
    q_to_kc = (q_to_kc
               .explode('kc_covered')
               .reset_index()
               .groupby('kc_covered')
               .agg(num_items=('assignment_id', 'count'))
               .reset_index())
    
    missing_kcs = set(kc_coverage) - set(q_to_kc['kc_covered'])
    q_to_kc = pd.concat([q_to_kc, pd.DataFrame({'kc_covered': list(missing_kcs), 'num_items': 0})])
    q_to_kc['student_id'] = student_id
    return q_to_kc

def create_comparison_kc_coverage_chart(kc : pd.DataFrame, student_observations : pd.DataFrame):
    comparison = pd.concat([
        get_student_kc_coverage('S001', student_observations, kc['kc_id']),
        get_student_kc_coverage('S012', student_observations, kc['kc_id'])
    ])

    chart = alt.Chart(comparison).mark_bar().encode(
        x=alt.X('num_items', title='Number of items').bin(maxbins=15),
        y=alt.Y('count()', title='Number of KCs'),
        tooltip=['count()'] 
    ).facet(
        column = alt.Column('student_id', title = 'Student')
    ).properties(
        title='KC Coverage Imbalance by Student '
    )
    
    return chart

def create_missing_assignement_table(student_observations : pd.DataFrame):
    nb_students = len(student_observations['student_id'].unique())

    completed_hwk = (student_observations
                        .groupby(['student_id','assignment_id'])
                        .agg(completed=('assignment_id','count'))
                        .reset_index()
                        .groupby(['assignment_id'])
                        .agg(nb_assignments=('student_id','count')))
    completed_hwk['nb_missing']=nb_students-completed_hwk['nb_assignments']
    completed_hwk = completed_hwk.groupby('nb_missing').agg('count')
    return completed_hwk

def create_student_missing_assignement_table(student_observations : pd.DataFrame):
    nb_assignments = len(student_observations['assignment_id'].unique())

    student_hwk = (student_observations
                    .groupby(['student_id','assignment_id'])
                    .agg(completed=('assignment_id','count'))
                    .reset_index()
                    .groupby(['student_id'])
                    .agg(nb_students=('assignment_id','count')))
    student_hwk['nb_missing']=nb_assignments-student_hwk['nb_students']
    student_hwk = student_hwk.groupby('nb_missing').agg('count')
    return student_hwk

def create_performance_band_chart(overall_scores : pd.DataFrame):
    chart = alt.Chart(overall_scores).mark_bar().encode(
    x=alt.X('count()', title='Number of students'),
    y=alt.Y('performance_band', title='Performance band', sort='-x') 
    ).properties(
        title='Most of the students are performing as expected'
    )
    return chart

