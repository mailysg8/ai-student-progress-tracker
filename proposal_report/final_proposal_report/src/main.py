"""Performs generates data for final_report.

This script:
1. Creates summary table of data
2. Creates summary table of attempts per student per KC

Usage: python proposal_report/final_proposal_report/src/main.py [OPTIONS]

[OPTIONS] :
--data_path               Path to final_student_kc_data csv file (default: data/processed/final_student_kc_data.csv)
--table_to                Directory to save tables (default: proposal_report/final_proposal_report/tables)
"""

import click
import pandas as pd
import os
import sys

from main_utils import bucket

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..','..','..'))

from src.classify import compute_opportunity_counts

@click.command()
@click.option('--data_path', type=str, required=False, default="data/processed/final_student_kc_data.csv", help='Path to final_student_kc_data csv file')
@click.option('--table_to', type=str, required=False, default="proposal_report/final_proposal_report/tables", help='Directory to save tables')

def main(data_path : str, table_to : str):
    """Generate EDA visualizations and summary tables."""

    os.makedirs(table_to, exist_ok=True)

    # Load data
    print(f"Loading data from: {data_path}")
    final_student_kc_data = pd.read_csv(data_path)
    print(f"Loaded {final_student_kc_data.shape[0]} student observations")

    print("Computing opportunity counts...")
    opp_counts = compute_opportunity_counts(final_student_kc_data)

    
    # Create summary table
    print("Creating summary table...")
    summary_table= pd.DataFrame({
            'observation': ['nb_students', 
                            'nb_units',
                            'nb_kc',
                            'start_date',
                            'end_date',
                            'min_nb_attempts',
                            'max_nb_attempts',
                            ] ,
            'value' : [final_student_kc_data['student_id'].nunique(),
                    final_student_kc_data['unit'].nunique(),
                    final_student_kc_data['modeling_kc_id'].nunique(),
                    final_student_kc_data['class_date'].unique().min(),
                    final_student_kc_data['class_date'].unique().max(),
                    opp_counts['n_opportunities'].unique().min(),
                    opp_counts['n_opportunities'].unique().max()
                    ]
                        }).set_index('observation')
    summary_table_path = os.path.join(table_to, "summary_table.csv")
    summary_table.to_csv(summary_table_path)
    print(f"Saved: {summary_table_path}")

    # Create practice counts table
    print("Creating practice counts table...")
    practice_summary = (
        opp_counts['n_opportunities']
        .apply(bucket)
        .value_counts()
        .reindex(['no attempts', 'low practice', 'some practice', 'well practiced'])
        .reset_index()
        )
    practice_summary.columns = ['Practice Level', 'count']
    practice_summary_path = os.path.join(table_to, "practice_summary.csv")
    practice_summary.to_csv(practice_summary_path)
    print(f"Saved: {practice_summary_path}")



if __name__ == "__main__":
    main()