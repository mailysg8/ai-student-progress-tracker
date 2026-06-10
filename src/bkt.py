from pyBKT.models import Model
from preprocess_split import preprocess 
import random
import numpy as np

def bkt(data, kc_col = 'modeling_kc_id', seed=42, num_fits=10):
    random.seed(seed)
    np.random.seed(seed)

    processed_data = preprocess(data, kc_col)

    model = Model(seed = seed, num_fits = num_fits)
    model.fit(data = processed_data)
    predictions = model.predict(data=processed_data)

    return predictions