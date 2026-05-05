"""Performs exploratory data analysis and generates visualizations.

This script:
1. Creates KC coverage chart
2. Creates assignement spread chart
3. Creates performance band chart

Usage: python proposal_report/src/eda.py [OPTIONS]

[OPTIONS] :
--student_observations    Path to student_observations CSV file (default: data/raw/student_observations.csv)
--overall_scores          Path to overall_scores CSV file (default: data/raw/overall_scores.csv)
--chart_to                Directory to save figures (default: proposal_report/figures)
"""

import click
import pandas as pd
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.visualization_utils import create_kc_coverage_chart, create_assignement_spread_chart, create_performance_band_chart

@click.command()
@click.option('--student_observations', type=str, required=False, default="data/raw/student_observations.csv", help='Path to student_observations CSV file')
@click.option('--overall_scores', type=str, required=False, default="data/raw/overall_scores.csv", help='Path to overall_scores CSV file')
@click.option('--chart_to', type=str, required=False, default="proposal_report/figures", help='Directory to save figures')

def main(student_observations : str, overall_scores : str, chart_to : str):
    """Generate EDA visualizations and summary tables."""

    os.makedirs(chart_to, exist_ok=True)

    # Load data
    print(f"Loading data from: {student_observations}")
    student_observations = pd.read_csv(student_observations)
    print(f"Loaded {student_observations.shape[0]} student observations")

    print(f"Loading data from: {overall_scores}")
    overall_scores = pd.read_csv(overall_scores)
    print(f"Loaded {overall_scores.shape[0]} student scores")

    # Create KC coverage chart
    print("Creating KC coverage chart...")
    kc_coverage = create_kc_coverage_chart(student_observations)
    kc_coverage_path = os.path.join(chart_to, "kc_coverage.png")
    kc_coverage.save(kc_coverage_path)
    print(f"Saved: {kc_coverage_path}")

    # Create assignement spread chart
    print("Creating assignement spread chart...")
    assignment_spread = create_assignement_spread_chart(student_observations)
    assignment_spread_path = os.path.join(chart_to, "assignment_spread.png")
    assignment_spread.save(assignment_spread_path)
    print(f"Saved: {assignment_spread_path}")

    # Create performance band chart
    print("Creating performance band chart...")
    performance_band = create_performance_band_chart(overall_scores)
    performance_band_path = os.path.join(chart_to, "performance_band.png")
    performance_band.save(performance_band_path)
    print(f"Saved: {performance_band_path}")
    


if __name__ == "__main__":
    main()