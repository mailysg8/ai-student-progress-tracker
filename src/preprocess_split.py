"""
Module that preprocesses data to have the needed format for pyBKT and splits data into train and test sets.
"""
from sklearn.model_selection import train_test_split

def preprocess(data, kc_col = 'primary_kc_id'):

  # Consider any non-full marks as incorrect (replace 0.5 -> 0)
  data['correct'] = data['score'].case_when([
      (data['score'] == 0.5, 0)
  ]).astype(int)

  # Rename  columns
  obs = data.rename(columns={
      'student_id':     'user_id',
      kc_col:  'skill_name',
      'observation_id': 'order_id'
  })[['user_id', 'skill_name', 'correct', 'order_id']].reset_index(drop=True)
  obs['order_id'] = obs.groupby('user_id').cumcount()

  return obs

def split(data, kc_col = 'primary_kc_id'):
  
    train_data, test_data = train_test_split(data, test_size=0.3, random_state=42)
    val_data, test_data = train_test_split(test_data, test_size=0.3,random_state=42)

    train_data = preprocess(train_data, kc_col)
    test_data = preprocess(test_data, kc_col)
    val_data = preprocess(val_data, kc_col)
    
    return train_data, test_data, val_data