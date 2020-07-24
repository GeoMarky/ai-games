# This is a functional implementation of ConnectX that has been optimized using both numpy and numba

from collections import namedtuple
from typing import List
from typing import Tuple

import numba
import numpy as np
from numba import int64
from numba import int8
from numba import njit
from numba import prange

# Hardcode for simplicity
# observation   = {'mark': 1, 'board': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
# configuration = {'columns': 7, 'rows': 6, 'inarow': 4, 'steps': 1000, 'timeout': 8}

bitboard_type = numba.typeof(np.ndarray((2,), dtype=np.int64))
Configuration = namedtuple('configuration', ['rows', 'columns', 'inarow'])
configuration = Configuration(
    rows=6,
    columns=7,
    inarow=4
)

### Conversions

def cast_configuration(configuration):
    return Configuration(
        rows    = configuration.rows,
        columns = configuration.columns,
        inarow  = configuration.inarow
    )

@njit # (int64[::1](int64[:]))
def list_to_bitboard(listboard: List[int]) -> np.ndarray:
    # bitboard[0] = played, is a square filled             | 0 = empty, 1 = filled
    # bitboard[1] = player, who's token is this, if filled | 0 = empty, 1 = filled
    bitboard_played = 0  # 42 bit number for if board square has been played
    bitboard_player = 0  # 42 bit number for player 0=p1 1=p2
    for n in prange(len(listboard)):
        if listboard[n] != 0:
            bitboard_played |= (1 << n)        # is a square filled (0 = empty | 1 = filled)
            if listboard[n] == 2:
                bitboard_player |= (1 << n)    # is a square filled
    bitboard = np.array([bitboard_played, bitboard_player], dtype=np.int64)
    return bitboard

@njit # (int64[:,:](int64[:]))
def bitboard_to_numpy2d(bitboard: np.ndarray) -> np.ndarray:
    global configuration
    rows    = configuration.rows
    columns = configuration.columns
    size    = rows * columns
    output  = np.zeros((size,), dtype=np.int8)
    for i in prange(size):
        is_played = bitboard[0] >> i & 1
        if is_played:
            player = bitboard[1] >> i & 1
            output[i] = 1 if player == 0 else 2
    return output.reshape((rows, columns))


### Lookups

# @clru_cache(1)
@njit(int64[:]())
def get_gameovers() -> np.ndarray:
    """Creates a list of all winning board positions, over 4 directions: horizontal, vertical and 2 diagonals"""
    global configuration
    rows    = configuration.rows
    columns = configuration.columns
    inarow  = configuration.inarow

    gameovers = []

    mask_horizontal  = 0
    mask_vertical    = 0
    mask_diagonal_dl = 0
    mask_diagonal_ul = 0
    for n in prange(inarow):
        mask_horizontal  |= 1 << n
        mask_vertical    |= 1 << n * columns
        mask_diagonal_dl |= 1 << n * columns + n
        mask_diagonal_ul |= 1 << n * columns + (inarow - 1 - n)

    row_inner = rows    - inarow
    col_inner = columns - inarow
    for row in prange(rows):
        for col in prange(columns):
            offset = col + row * columns
            if col <= col_inner:
                gameovers.append( mask_horizontal << offset )
            if row <= row_inner:
                gameovers.append( mask_vertical << offset )
            if col <= col_inner and row <= row_inner:
                gameovers.append( mask_diagonal_dl << offset )
                gameovers.append( mask_diagonal_ul << offset )
    return np.array(gameovers, dtype=np.int64)


### Coordinates

@njit
def index_to_coords(index: int) -> Tuple[int,int]:
    global configuration
    row    = index // configuration.columns
    column = index - row * configuration.columns
    return (row, column)

@njit
def coords_to_index(row: int, column: int) -> int:
    global configuration
    return column + row * configuration.columns


### Moves
@njit(int64[:](int8))
def get_bitcount_mask(size: int) -> np.ndarray:
    global configuration
    return np.array([ 1 << index for index in range(size) ], dtype=int64)

@njit(int8(int64[:]))
def get_move_number(bitboard: np.ndarray) -> np.ndarray:
    global configuration
    size          = configuration.columns * configuration.rows
    bitcount_mask = get_bitcount_mask(size)
    move_number   = np.sum( bitboard[0] & bitcount_mask == bitcount_mask )
    return move_number

@njit(int8(int64[:], int8))
def is_legal_move(bitboard: np.ndarray, action: int) -> int8:
    # First 7 bytes represent the top row. Moves are legal if the sky is unplayed
    return int( bitboard[0] >> action & 1 == 0 )

@njit
def get_legal_moves(bitboard: np.ndarray) -> np.ndarray:
    # First 7 bytes represent the top row. Moves are legal if the sky is unplayed
    global configuration
    return np.array([ action for action in range(configuration.columns) if is_legal_move(bitboard, action) ])

# @clru_cache(1)
@njit
def get_all_moves() -> List[int]:
    # First 7 bytes represent the top row. Moves are legal if the sky is unplayed
    global configuration
    return [ action for action in range(configuration.columns) ]


@njit
def get_next_row(bitboard: np.ndarray, action: int) -> int:
    global configuration
    # Start at the ground, and return first row that contains a 0
    for row in range(configuration.rows, -1, -1):
        index = action + row * configuration.columns
        value = bitboard[0] >> index & 1
        if value == 0:
            return row  # first playable row
    return 0            # implies not is_legal_move(bitboard, action) - this should never happen

@njit
def result_action(bitboard: np.ndarray, action: int, player_id: int) -> np.ndarray:
    if not is_legal_move(bitboard, action): return bitboard
    column   = action
    row      = get_next_row(bitboard, column)
    index    = coords_to_index(row, column)
    mark     = 0 if player_id == 1 else 1
    output = np.array([
        bitboard[0] | 1    << index,
        bitboard[1] | mark << index
    ], dtype=bitboard.dtype)
    return output


### Endgame Utility

@njit
def is_gameover(bitboard: np.ndarray) -> bool:
    if has_no_more_moves(bitboard):  return True
    if get_winner(bitboard) != 0:    return True
    return False

@njit
def has_no_more_moves(bitboard: np.ndarray) -> bool:
    """If all the squares on the top row have been played, then there are no more moves"""
    global configuration
    mask = (2 ** configuration.columns) - 1
    return bitboard[0] & mask == mask

@njit
def get_winner(bitboard: np.ndarray) -> int:
    """ Endgammer get_winner: 0 for no get_winner, 1 = player 1, 2 = player 2"""
    gameovers        = get_gameovers()
    gameovers_played = gameovers[ gameovers & bitboard[0] == gameovers ]  # exclude any unplayed squares
    if np.any(gameovers_played):                                          # have 4 tokens been played in a row yet
        p1_wins = gameovers_played & ~bitboard[1] == gameovers_played
        p2_wins = gameovers_played &  bitboard[1] == gameovers_played
        if np.any(p1_wins): return 1
        if np.any(p2_wins): return 2
    return 0

@njit
def get_utility(bitboard: np.ndarray, player_id: int) -> float:
    winning_player = get_winner(bitboard)
    if winning_player == 0: return 0
    return np.inf if winning_player == player_id else -np.inf
