"""
Module that splits data into train and test sets.
"""
from sklearn.model_selection import train_test_split
from preprocess import preprocess

def split(data, kc_col = 'primary_kc_id'):
  
    train_data, test_data = train_test_split(data, test_size=0.3, random_state=42)
    val_data, test_data = train_test_split(test_data, test_size=0.3,random_state=42)

    train_data = preprocess(train_data, kc_col)
    test_data = preprocess(test_data, kc_col)
    val_data = preprocess(val_data, kc_col)
    
    return train_data, test_data, val_data