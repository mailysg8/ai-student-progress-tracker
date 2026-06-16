from pipeline.load import load_observations, load_kc_map, load_weights, load_class_plan
from pipeline.merge import merge_kc_mapping, merge_weights, merge_class_plan, merge_bkt_predictions
from pipeline.predict import run_bkt_predictions
from pipeline.save import save_final_output



# ---------------------------------------------------------------------------
# Load Raw Data
# ---------------------------------------------------------------------------

print('Loading data...')
obs        = load_observations()
class_plan = load_class_plan()
kc_map     = load_kc_map()
weights    = load_weights()
print('Data loaded!')


print(f'Creating final data set ...')

print(f'Merging data sets ...')
df = merge_kc_mapping(obs, kc_map)
df = merge_weights(df, weights)
df = merge_class_plan(df, class_plan)
print(f'Data sets merged!')

print(f'Getting bkt predictions...')
bkt_preds = run_bkt_predictions(df, kc_col="modeling_kc_id")

df_final = merge_bkt_predictions(df, bkt_preds)
save_final_output(df_final, filename="test_output.csv")
print(f'All ready! ...')