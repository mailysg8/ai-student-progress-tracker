"""
Script that creates bootstrap samples.
"""
import pandas as pd
from sklearn.utils import resample


def bootstrap_students(initial_data, target_students, seed = 42): 
    """Create bootstrap samples."""
    
     # Unique student list
    student_ids = initial_data["student_id"].unique()
    
    # Resample student IDs with replacement 
    sampled_ids = resample(
        student_ids,
        replace=True,
        n_samples=target_students,
        random_state=seed,
    )

    # Expand to full attempt rows with fresh IDs 
    new_rows = []
    for new_idx, orig_sid in enumerate(sampled_ids, start=1):
        all_attempts = initial_data[initial_data["student_id"] == orig_sid].copy()
        all_attempts["student_id"] = f"S{new_idx:03d}"
        new_rows.append(all_attempts)

    return pd.concat(new_rows, ignore_index=True)

# Read data
initial_data = pd.read_excel('data/raw/final_data.xlsx', sheet_name='Student_Observations')
grouped_data = pd.read_csv('data/processed/full_grouped_data.csv')

# Create samples with 50 and 100 students for intial and grouped data
sample_50 = bootstrap_students(initial_data, 50)
sample_100 = bootstrap_students(initial_data, 100)
grouped_sample_50 = bootstrap_students(grouped_data, 50)
grouped_sample_100 = bootstrap_students(grouped_data, 100)

# Save created samples
sample_50.to_csv('data/sample/sample_50.csv')
sample_100.to_csv('data/sample/sample_100.csv')
grouped_sample_50.to_csv('data/sample/grouped_sample_50.csv')
grouped_sample_100.to_csv('data/sample/grouped_sample_100.csv')