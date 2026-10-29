"""Identical normalization and interval math for training and lightweight serving."""
import unicodedata
import numpy as np
import pandas as pd
KIND='dav-feature-price'

def normalize(value):
    if value is None or pd.isna(value):return 'UNKNOWN'
    value=' '.join(unicodedata.normalize('NFC',str(value)).casefold().split())
    return value if value and value!='unknown' else 'UNKNOWN'

def interval(prediction,q):
    log=np.log1p(np.maximum(0,prediction))
    return np.maximum(0,np.expm1(log-q)),np.expm1(np.minimum(40,log+q))
