"""
Module that creates a dataset that contains both the 'fine KC' and the 'modeling KC'.
"""

import pandas as pd

# Read data
initial_data = pd.read_excel('data/raw/final_data.xlsx', sheet_name='Student_Observations')
grouped_data = pd.read_excel('data/raw/grouped_data.xlsx', sheet_name='FineKC_to_ModelingKC_Map')

# Merge datasets
full_grouped_data = initial_data.merge(grouped_data,left_on='primary_kc_id', right_on='fine_kc_id')

# Save to csv
full_grouped_data.to_csv('data/processed/full_grouped_data.csv')