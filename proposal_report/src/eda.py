"""Performs exploratory data analysis and generates visualizations.

This script:
1. Creates KC coverage chart
2. Creates student KC coverage comparison chart
3. Creates summary table of assignments missing students
4. Creates summary table of students missing assignments
3. Creates performance band chart

Usage: python proposal_report/src/eda.py [OPTIONS]

[OPTIONS] :
--data_path               Path to student_observations excel file (default: data/raw/Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx)
--chart_to                Directory to save figures (default: proposal_report/figures)
--table_to                Directory to save tables (default: proposal_report/tables)
"""

import click
import pandas as pd
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.eda_utils import create_kc_coverage_chart, create_comparison_kc_coverage_chart, create_performance_band_chart, create_missing_assignement_table, create_student_missing_assignement_table, get_student_kc_coverage

@click.command()
@click.option('--data_path', type=str, required=False, default="data/raw/Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx", help='Path to student_observations excel file')
@click.option('--chart_to', type=str, required=False, default="proposal_report/figures", help='Directory to save figures')
@click.option('--table_to', type=str, required=False, default="proposal_report/tables", help='Directory to save tables')

def main(data_path : str,  chart_to : str, table_to : str):
    """Generate EDA visualizations and summary tables."""

    os.makedirs(chart_to, exist_ok=True)

    # Load data
    print(f"Loading data from: {data_path}")
    student_observations = pd.read_excel(data_path, sheet_name="Student_Observations")
    print(f"Loaded {student_observations.shape[0]} student observations")

    overall_scores = pd.read_excel(data_path, sheet_name="Overall_Scores")
    print(f"Loaded {overall_scores.shape[0]} student scores")

    kc_coverage = pd.read_excel(data_path, sheet_name="KC_Coverage")
    print(f"Loaded {kc_coverage.shape[0]} knowledge components")
    
    # Create student performance summary table
    print("Creating student performance summary table...")
    student_summary = pd.DataFrame({
            'observation': ['nb_students', 
                            'nb_assignments', 
                            'nb_observations',
                            'nb_items'
                            ] ,
            'value' : [student_observations['student_id'].nunique(), 
                       student_observations['assignment_id'].nunique(), 
                       student_observations['observation_id'].nunique(),
                       student_observations.shape[0]]
                       }).set_index('observation')
    student_summary_path = os.path.join(table_to, "student_summary.csv")
    student_summary.to_csv(student_summary_path)
    print(f"Saved: {student_summary_path}")

    # Create knowledge structure summary table
    print("Creating knowledge structure summary table...")
    kc_summary = pd.DataFrame({
        'observation': ['nb_kc', 
                        'nb_skills', 
                        'nb_sub_skills',
                        'median_items_per_kc',
                        'max_obs_per_kc',
                        'min_obs_per_kc',
                        'nb_zero_coverage'] ,
        'value' : [kc_coverage['kc_id'].nunique(), 
                    4, 
                    18,
                    kc_coverage['num_items'].median(),
                    kc_coverage['num_items'].max()*student_observations['student_id'].nunique(),
                    kc_coverage['num_items'].min()*student_observations['student_id'].nunique(),
                    kc_coverage[kc_coverage['num_items']==0]['kc_id'].nunique()
                    ]}).set_index('observation')
    kc_summary_path = os.path.join(table_to, "kc_summary.csv")
    kc_summary.to_csv(kc_summary_path)
    print(f"Saved: {kc_summary_path}")

     # Create performance band summary table
    print("Creating performance band summary table...")
    perf_summary = overall_scores.groupby('performance_band').agg(nb_students=('student_id','count'))
    perf_summary_path = os.path.join(table_to, "perf_summary.csv")
    perf_summary.to_csv(perf_summary_path)
    print(f"Saved: {perf_summary_path}")

    # Create KC coverage chart
    print("Creating KC coverage chart...")
    kc_coverage_chart = create_kc_coverage_chart(kc_coverage)
    kc_coverage_path = os.path.join(chart_to, "kc_coverage.png")
    kc_coverage_chart.save(kc_coverage_path)
    print(f"Saved: {kc_coverage_path}")

    # Create KC coverage student comparison chart
    print("Creating KC coverage student comparison chart...")
    kc_coverage_comparison = create_comparison_kc_coverage_chart(kc_coverage, student_observations)
    kc_coverage_comparison_path = os.path.join(chart_to, "kc_coverage_comparison.png")
    kc_coverage_comparison.save(kc_coverage_comparison_path)
    print(f"Saved: {kc_coverage_comparison_path}")

    # Create KC coverage student comparison table
    print("Creating KC coverage student comparison chart...")
    kc_coverage_comparison_table = pd.concat([
        get_student_kc_coverage('S001', student_observations, kc_coverage['kc_id']),
        get_student_kc_coverage('S012', student_observations, kc_coverage['kc_id'])
    ])
    kc_coverage_comparison_table_path = os.path.join(table_to, "kc_coverage_comparison_table.csv")
    kc_coverage_comparison_table.to_csv(kc_coverage_comparison_table_path, index=False)
    print(f"Saved: {kc_coverage_comparison_table_path}")
    

    # Create missing assignment table.
    print("Creating missing assignment table...")
    missing_assignment = create_missing_assignement_table(student_observations)
    missing_assignment_path = os.path.join(table_to, "missing_assignment.csv")
    missing_assignment.to_csv(missing_assignment_path, index=False)
    print(f"Saved: {missing_assignment_path}")

    # Create missing student assignment table.
    print("Creating missing student assignment table...")
    missing_student_assignment = create_student_missing_assignement_table(student_observations)
    missing_student_assignment_path = os.path.join(table_to, "missing_student_assignment.csv")
    missing_student_assignment.to_csv(missing_student_assignment_path,  index=False)
    print(f"Saved: {missing_student_assignment_path}")

    # Create performance band chart
    print("Creating performance band chart...")
    performance_band = create_performance_band_chart(overall_scores)
    performance_band_path = os.path.join(chart_to, "performance_band.png")
    performance_band.save(performance_band_path)
    print(f"Saved: {performance_band_path}")


if __name__ == "__main__":
    main()