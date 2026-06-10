from pyBKT.models import Model
from src.preprocess_split import preprocess 

def bkt(data, kc_col = 'modeling_kc_id', seed=42, num_fits=10):
    processed_data = preprocess(data, kc_col)
    model = Model(seed = seed, num_fits = num_fits)
    model.fit(data = processed_data)
    predictions = model.predict(data=processed_data)
    return predictions