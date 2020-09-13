import math
from typing import Dict

import numpy as np


def csv_to_delta(df, idx, type='start'):
    return int(df.loc[idx]['delta'])

def csv_to_numpy(df, idx, key='start') -> np.ndarray:
    columns = [col for col in df if col.startswith(key)]
    size    = int(math.sqrt(len(columns)))
    X = df.loc[idx][columns].values
    X = X.reshape((size,size)).astype(np.int8)
    return X


# noinspection PyTypeChecker,PyUnresolvedReferences
def numpy_to_dict(board: np.ndarray, key='start') -> Dict:
    board  = np.array(board).flatten().tolist()
    output = { f"{key}_{n}": board[n] for n in range(len(board))}
    return output


# Source: https://stackoverflow.com/questions/8290397/how-to-split-an-iterable-in-constant-size-chunks
def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

