"""
Module that contains helper functions for main.py. 
"""
def bucket(n):
    if n == 0:
        return 'no attempts'
    elif 1 <= n <= 9:
        return 'low practice'
    elif 10 <= n <= 25:
        return 'some practice'
    else:
        return 'well practiced'