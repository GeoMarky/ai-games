# This is a functional implementation of ConnectX that has been optimized using both numpy and numba

from collections import namedtuple
from typing import Tuple

import numba
import numpy as np
# Hardcode for simplicity
# observation   = {'mark': 1, 'board': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
# configuration = {'columns': 7, 'rows': 6, 'inarow': 4, 'steps': 1000, 'timeout': 8}
from numba import int64
from numba import int8
from numba import njit



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


#@njit
def list_to_bitboard(listboard: np.ndarray) -> np.ndarray:
    # bitboard[0] = played, is a square filled             | 0 = empty, 1 = filled
    # bitboard[1] = player, who's token is this, if filled | 0 = empty, 1 = filled
    bitboard_played = 0  # 42 bit number for if board square has been played
    bitboard_player = 0  # 42 bit number for player 0=p1 1=p2
    for n in range(len(listboard)):  # prange
        if listboard[n] != 0:
            bitboard_played |= (1 << n)        # is a square filled (0 = empty | 1 = filled)
            if listboard[n] == 2:
                bitboard_player |= (1 << n)    # mark as player 2 square, else assume p1=0 as default
    bitboard = np.array([bitboard_played, bitboard_player], dtype=np.int64)
    return bitboard


#@njit(int8[:,:](int64[:]))
def bitboard_to_numpy2d(bitboard: np.ndarray) -> np.ndarray:
    global configuration
    rows    = configuration.rows
    columns = configuration.columns
    size    = rows * columns
    output  = np.zeros((size,), dtype=np.int8)
    for i in range(size):  # prange
        is_played = (bitboard[0] >> i) & 1
        if is_played:
            player = (bitboard[1] >> i) & 1
            output[i] = 1 if player == 0 else 2
    return output.reshape((rows, columns))


### Bitboard Operations

# @njit
def empty_bitboard() -> np.ndarray:
    return np.array([0, 0], dtype=np.int64)


@njit
def hash_bitboard( bitboard: np.ndarray ) -> Tuple[int,int]:
    """ Create a tupleised mirror hash, the minimum value of the bitboard and its mirrored reverse """
    if bitboard[0] == 0:
        return ( bitboard[0], bitboard[1] )

    global configuration
    mirror_0 = mirror_bitstring(bitboard[0])
    if bitboard[0] < mirror_0:
        return ( bitboard[0], bitboard[1] )
    else:
        mirror_1 = mirror_bitstring(bitboard[1])
        if bitboard[0] == mirror_0 and bitboard[1] <= mirror_1:
            return ( bitboard[0], bitboard[1] )
        else:
            return ( mirror_0, mirror_1 )


# Use string reverse to create mirror bit lookup table: mirror_bits[ 0100000 ] == 0000010
mirror_bits = np.array([
    int( "".join(reversed(f'{n:07b}')), 2 )
    for n in range(2**configuration.columns)
], dtype=np.int64)

@njit
def mirror_bitstring( bitstring: int ) -> int:
    """ Return the mirror view of the board for hashing:  0100000 -> 0000010 """
    global configuration

    if bitstring == 0:
        return 0  # short-circuit for empty board

    bitsize     = configuration.columns * configuration.rows        # total number of bits to process
    unit_size   = configuration.columns                             # size of each row in bits
    unit_mask   = (1 << unit_size) - 1                              # == 0b1111111 | 0x7f
    offsets     = np.arange(0, bitsize, unit_size, dtype=np.int64)  # == [ 0, 7, 14, 21, 28, 35 ]

    # row_masks   = unit_mask               << offsets  # create bitmasks for each row
    # bits        = (bitstring & row_masks) >> offsets  # extract out the bits for each row
    # stib        = mirror_bits[ bits ]     << offsets  # lookup mirror bits for each row and shift back into position
    # output      = np.sum(stib)                        # np.sum() will bitwise AND the array assuming no overlapping bits

    # This can technically be done as a one liner:
    output = np.sum( mirror_bits[ (bitstring & (unit_mask << offsets)) >> offsets ] << offsets )

    ### Old Loop Implementation
    # output = 0
    # for row in range(configuration.rows):
    #     offset = row * configuration.columns
    #     mask   = unit_mask          << offset
    #     bits   = (bitstring & mask) >> offset
    #     if bits == 0: continue
    #     stib   = mirror_bits[ bits ]
    #     output = output | (stib << offset)

    return int(output)


@njit
def mirror_bitboard( bitboard: np.ndarray ) -> np.ndarray:
    return np.array([
        mirror_bitstring(bitboard[0]),
        mirror_bitstring(bitboard[1]),
    ], dtype=bitboard.dtype)



### Player Id

@njit
def current_player_id( bitboard: np.ndarray ) -> int:
    move_number = get_move_number(bitboard)
    next_player = 1 if move_number % 2 == 0 else 2  # player 1 has the first move on an empty board
    return next_player


@njit(int8(int8))
def next_player_id(player_id: int) -> int:
    assert player_id in [1,2]
    return 1 if player_id == 2 else 2



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
    # return np.array([1 << index for index in range(0, size)], dtype=np.int64)
    return 1 << np.arange(0, size, dtype=np.int64)


@njit(int8(int64[:]))
def get_move_number(bitboard: np.ndarray) -> int:
    global configuration
    if bitboard[0] == 0: return 0
    size          = configuration.columns * configuration.rows
    mask_bitcount = get_bitcount_mask(size)
    move_number   = np.count_nonzero(bitboard[0] & mask_bitcount)
    return move_number


mask_legal_moves = (1 << configuration.columns) - 1

@njit
def has_no_illegal_moves( bitboard: np.ndarray ) -> int:
    """If any the squares on the top row have been played, then there are illegal moves"""
    are_all_moves_legal = ((bitboard[0] & mask_legal_moves) == 0)
    return 1 if are_all_moves_legal else 0


@njit
def has_no_more_moves(bitboard: np.ndarray) -> bool:
    """If all the squares on the top row have been played, then there are no more moves"""
    return bitboard[0] & mask_legal_moves == mask_legal_moves


_legal_moves_mask  = ((1 << configuration.columns) - 1)
_legal_moves_cache = np.array([
    [
        int( (bits >> action) & 1 == 0 )
        for action in range(configuration.columns)
    ]
    for bits in range(2**configuration.columns)
], dtype=np.int8)
@njit
def is_legal_move(bitboard: np.ndarray, action: int) -> int:
    bits = bitboard[0] & _legal_moves_mask  # faster than: int( (bitboard[0] >> action) & 1 == 0 )
    return _legal_moves_cache[bits,action]  # NOTE: [bits,action] is faster than


@njit
def get_legal_moves(bitboard: np.ndarray) -> np.ndarray:
    # First 7 bytes represent the top row. Moves are legal if the sky is unplayed
    global configuration
    if has_no_illegal_moves(bitboard):
        return get_all_moves()
    else:
        return np.array([ action for action in range(configuration.columns) if is_legal_move(bitboard, action) ])


actions = np.array([ action for action in range(configuration.columns) ], dtype=np.int64)
@njit
def get_all_moves() -> np.ndarray:
    # First 7 bytes represent the top row. Moves are legal if the sky is unplayed
    return actions
    # global configuration
    # return np.array([ action for action in range(configuration.columns) ])


@njit
def get_random_move(bitboard: np.ndarray) -> int:
    """ This is slightly quicker than random.choice(get_all_moves())"""
    assert not has_no_more_moves(bitboard)

    global configuration
    while True:
        action = np.random.randint(0, configuration.columns)
        if is_legal_move(bitboard, action):
            return action



# Actions + Results

@njit
def get_next_index(bitboard: np.ndarray, action: int) -> int:
    global configuration
    assert is_legal_move(bitboard, action)

    # Start at the ground, and return first row that contains a 0
    for row in range(configuration.rows-1, -1, -1):
        index = action + (row * configuration.columns)
        value = (bitboard[0] >> index) & 1
        if value == 0:
            return index
    return action  # this should never happen - implies not is_legal_move(action)

@njit
def get_next_row(bitboard: np.ndarray, action: int) -> int:
    global configuration
    index = get_next_index(bitboard, action)
    row   = index // configuration.columns
    return row


@njit
def result_action(bitboard: np.ndarray, action: int, player_id: int) -> np.ndarray:
    assert is_legal_move(bitboard, action)
    index    = get_next_index(bitboard, action)
    mark     = 0 if player_id == 1 else 1
    output = np.array([
        bitboard[0] | 1    << index,
        bitboard[1] | mark << index
    ], dtype=bitboard.dtype)
    return output



### Endgame

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
    for n in range(inarow):  # prange
        mask_horizontal  |= 1 << n
        mask_vertical    |= 1 << n * columns
        mask_diagonal_dl |= 1 << n * columns + n
        mask_diagonal_ul |= 1 << n * columns + (inarow - 1 - n)

    row_inner = rows    - inarow
    col_inner = columns - inarow
    for row in range(rows):  # prange
        for col in range(columns):  # prange
            offset = col + row * columns
            if col <= col_inner:
                gameovers.append( mask_horizontal << offset )
            if row <= row_inner:
                gameovers.append( mask_vertical << offset )
            if col <= col_inner and row <= row_inner:
                gameovers.append( mask_diagonal_dl << offset )
                gameovers.append( mask_diagonal_ul << offset )

    _get_gameovers_cache = np.array(gameovers, dtype=np.int64)
    return _get_gameovers_cache

gameovers = get_gameovers()


@njit
def is_gameover(bitboard: np.ndarray) -> bool:
    if has_no_more_moves(bitboard):  return True
    if get_winner(bitboard) != 0:    return True
    return False


@njit
def get_winner(bitboard: np.ndarray) -> int:
    """ Endgammer get_winner: 0 for no get_winner, 1 = player 1, 2 = player 2"""
    global gameovers
    # gameovers        = get_gameovers()
    gameovers_played = gameovers[ gameovers & bitboard[0] == gameovers ]  # exclude any unplayed squares
    if np.any(gameovers_played):                                          # have 4 tokens been played in a row yet
        p1_wins = gameovers_played & ~bitboard[1] == gameovers_played
        if np.any(p1_wins): return 1

        p2_wins = gameovers_played &  bitboard[1] == gameovers_played
        if np.any(p2_wins): return 2
    return 0



### Utility Scores

@njit
def get_utility_one(bitboard: np.ndarray, player_id: int) -> int:
    """ Like get_utility_inf but returns: 1 for victory, -1 for loss, 0 for draw """
    winning_player = get_winner(bitboard)
    if winning_player == 0: return 0
    return 1 if winning_player == player_id else -1


@njit
def get_utility_zero_one(bitboard: np.ndarray, player_id: int) -> float:
    """ Like get_utility_one but returns: 1 for victory, 0 for loss, 0.5 for draw """
    winning_player = get_winner(bitboard)
    if winning_player == 0: return 0.5
    return 1.0 if winning_player == player_id else 0.0


@njit
def get_utility_inf(bitboard: np.ndarray, player_id: int) -> float:
    """ Like get_utility_one but returns: +inf for victory, -inf for loss, 0 for draw """
    winning_player = get_winner(bitboard)
    if winning_player == 0: return 0
    return +np.inf if winning_player == player_id else -np.inf