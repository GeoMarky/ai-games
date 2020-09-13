# Functions for implementing Game of Life Forward Play

import numpy as np
from numba import njit


# Source: https://www.kaggle.com/ianmoone0617/reversing-conways-game-of-life-tutorial
def life_step_1(X: np.ndarray):
    """Game of life step using generator expressions"""
    nbrs_count = sum(np.roll(np.roll(X, i, 0), j, 1)
                     for i in (-1, 0, 1) for j in (-1, 0, 1)
                     if (i != 0 or j != 0))
    return (nbrs_count == 3) | (X & (nbrs_count == 2))


# Source: https://www.kaggle.com/ianmoone0617/reversing-conways-game-of-life-tutorial
def life_step_2(X: np.ndarray):
    """Game of life step using scipy tools"""
    from scipy.signal import convolve2d
    nbrs_count = convolve2d(X, np.ones((3, 3)), mode='same', boundary='wrap') - X
    return (nbrs_count == 3) | (X & (nbrs_count == 2))



# NOTE: @njit doesn't like np.roll(axis=) so reimplement explictly
@njit
def life_neighbours_xy(board: np.ndarray, x, y, max_value=3):
    size_x = board.shape[0]
    size_y = board.shape[1]
    neighbours = 0
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if i == j == 0: continue    # ignore self
            xi = (x + i) % size_x
            yj = (y + j) % size_y
            neighbours += board[xi, yj]
            if neighbours > max_value:  # shortcircuit return 4 if overpopulated
                return neighbours
    return neighbours


@njit
def life_neighbours(board: np.ndarray, max_value=3):
    size_x = board.shape[0]
    size_y = board.shape[1]
    output = np.zeros(board.shape, dtype=np.int8)
    for x in range(size_x):
        for y in range(size_y):
            output[x,y] = life_neighbours_xy(board, x, y, max_value)
    return output


@njit
def life_step(board: np.ndarray):
    """Game of life step using generator expressions"""
    size_x = board.shape[0]
    size_y = board.shape[1]
    output = np.zeros(board.shape, dtype=np.int8)
    for x in range(size_x):
        for y in range(size_y):
            cell       = board[x,y]
            neighbours = life_neighbours_xy(board, x, y, max_value=3)
            if ( (cell == 0 and      neighbours == 3 )
              or (cell == 1 and 2 <= neighbours <= 3 )
            ):
                output[x, y] = 1
    return output
