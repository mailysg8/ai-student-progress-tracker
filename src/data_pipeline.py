import pandas as pd
from pathlib import Path
from src.bkt import bkt

base_path = Path().resolve().parent
file_path = base_path / 'data' / 'raw'
output_path = base_path / 'data' / 'output'

# Student observations
obs = pd.read_excel(
    file_path / 'Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx', 
    sheet_name='Student_Observations')

# Class plan
class_plan = pd.read_excel(
    file_path / 'Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx', 
    sheet_name='Class_Plan')


# Fine KC to Modeling KC mapping
kc_map = pd.read_excel(
    file_path / "mkc_mapping_pack_v1.0..xlsx",
    sheet_name="FineKC_to_ModelingKC_Map"
)


# Modeling KC weights
weights = pd.read_excel(
    file_path / "mkc_weights_dataset.xlsx",
    sheet_name="MKC_Weights"
)


kc_map_slim = kc_map[[
    "fine_kc_id",
    "fine_kc_label",
    "modeling_kc_id",
    "modeling_kc_label",
    "modeling_unit",
    "fine_reporting_group"
]].drop_duplicates()


df = obs.merge(
    kc_map_slim,
    left_on="primary_kc_id",
    right_on="fine_kc_id",
    how="left"         
)

df_2 = df.merge(
    weights,
    on=["modeling_kc_id",'modeling_kc_label'],
    how="left"
)

date = pd.merge(df_2,class_plan[['class_date','homework_id']], left_on='assignment_id', right_on='homework_id').drop(columns='homework_id')

bkt_preds = bkt(date, 'modeling_kc_id')

# Renaming BKT columns to align with our dataframe
bkt_renamed = bkt_preds.rename(columns={
    "user_id"             : "student_id",
    "skill_name"          : "modeling_kc_id"
})

# Add a column that counts the number of attempts for each kc / student pair
bkt_renamed['kc_attempt'] = (
    bkt_renamed
    .groupby(['student_id', 'modeling_kc_id'])
    .cumcount() + 1
)

date['order_id'] = date.groupby('student_id').cumcount()

df_final_attempt = date.merge(
    bkt_renamed,
    on=['order_id','student_id', 'modeling_kc_id','correct'],
    how="left"
)

df_final_attempt.to_csv(base_path / "data" / "processed" / "final_student_kc_data.csv", index=False)