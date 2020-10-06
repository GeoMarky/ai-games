# This is another buggy implementation
# Also the current logic for detecting adding rules to detect previous patterns is incredibly slow

import itertools
import time
from typing import List
from typing import Tuple
from typing import Union

import numpy as np
import pydash
import z3
from fastcache import clru_cache

from constraint_satisfaction.fix_submission import is_valid_solution
from hashmaps.reverse_patterns import reverse_pattern_lookup


@clru_cache(None)
def get_z3_solver(delta=1, size=(25,25), patterns=False):
    z3_solver = z3.Solver()
    t_cells = [
        [
            [ z3.Bool(f"({x:02d},{y:02d})@t={t}") for y in range(size[1]) ]
            for x in range(size[0])
        ]
        for t in range(0, delta+1)
    ]
    z3_solver.add( get_game_of_life_ruleset(t_cells) )
    if patterns:
        z3_solver.add( get_reverse_pattern_constraints(t_cells) )
    z3_solver.push()
    return z3_solver, t_cells


def get_game_of_life_ruleset(t_cells, size=(25,25), delta=1, warmup=0, zero_point_distance=1):

    # Create a 25x25 board for each timestep we need to solve for
    # T=0 for start_time, T=delta-1 for stop_time
    max_t = warmup + delta  # BUGFIX: delta not delta-1 | see fix_submission()
    size_x, size_y = size

    # Rules expressed forwards:
    # living + 4-8 neighbours = dies
    # living + 2-3 neighbours = lives
    # living + 0-1 neighbour  = dies
    # dead   +   3 neighbours = lives
    constraints = []
    for t in range(1, max_t+1):
        for x,y in itertools.product(range(size_x), range(size_y)):
            cell            = t_cells[t][x][y]
            past_cell       = t_cells[t-1][x][y]
            past_neighbours = get_neighbourhood_cells(t_cells[t-1], x, y)  # excludes self
            constraints.append(
                # dead   + 3 neighbours   = lives
                # living + 2-3 neighbours = lives
                cell == z3.And([
                    z3.AtLeast( past_cell, *past_neighbours, 3 ),
                    z3.AtMost(             *past_neighbours, 3 ),
                ])
            )

    # Add constraint that there can be no empty boards
    for t in range(1, max_t+1):
        layer = pydash.flatten_deep(t_cells[t])
        constraints.append( z3.AtLeast( *layer, 1 ) )

    return constraints


def get_zero_point_constraint(t_cells, zero_point_distance: int):
    # Ignore any currently dead cell with 0 neighbours,
    # This considerably reduces the state space and prevents zero-point energy solutions
    # BUGFIX: distance=1 breaks test_df[90081]
    max_t = len(t_cells)
    size_x, size_y = ( len(t_cells[0]), len(t_cells[0][0]) )

    constraints = []
    for t in range(1, max_t):
        for x,y in itertools.product(range(size_x), range(size_y)):
            cell      = t_cells[t][x][y]
            past_cell = t_cells[t-1][x][y]
            if zero_point_distance:
                current_neighbours = get_neighbourhood_cells(t_cells[t], x, y, distance=zero_point_distance)
                constraints.append(
                    z3.If(
                        z3.AtMost( cell, *current_neighbours, 0 ),
                        past_cell == False,
                        True
                    )
                )
    return constraints


def get_reverse_pattern_constraints(t_cells):
    ### reverse_pattern_lookup[ tuplize(current) ] = [ np.array(previous), np.array(previous) ]
    size_x, size_y = len(t_cells[0]), len(t_cells[0][0])
    constraints = []
    for t, bx, by in itertools.product(range(1, len(t_cells)), range(size_x), range(size_y)):
        print('t, bx, by', t, bx, by)
        for current_pattern, previous_patterns in reverse_pattern_lookup.items():
            current_pattern = np.array(current_pattern,  dtype=np.int8)
            if_clause    = []
            then_clauses = [ [] ] * len(previous_patterns)
            for px, py in itertools.product(range(current_pattern.shape[0]), range(current_pattern.shape[1])):
                x = ( bx + px ) % size_x
                y = ( bx + px ) % size_y
                current_cell  = t_cells[t][x][y]
                previous_cell = t_cells[t-1][x][y]

                # The pattern constraint only applies to a distance of 1 whitespace away from the alive cells
                if np.any( get_neighbourhood_cells(current_pattern, px, py) ):
                    if_clause.append( current_cell == bool(current_pattern[px][py]) )

                for i, previous_pattern in enumerate(previous_patterns):
                    if np.any( get_neighbourhood_cells(previous_pattern, px, py) ):
                        then_clauses[i].append( previous_cell == bool(previous_pattern[px][py]) )

            constraints.append(
                z3.If(
                    z3.And(if_clause),
                    z3.Or([ z3.And(then_clause) for then_clause in then_clauses ]),
                    True
                )
            )
    return constraints


def get_initial_board_constraints(t_cells, board):
    constraints = [
        t_cells[-1][x][y] == bool(board[x][y])
        for x,y in itertools.product(range(board.shape[0]), range(board.shape[1]))
    ]
    return constraints


# The true kaggle solution requires warmup=5, but this is very slow to compute
# noinspection PyUnboundLocalVariable
def game_of_life_solver_patterns(board: np.ndarray, delta=1, warmup=0, timeout=0, verbose=True):
    time_start = time.perf_counter()
    size       = (size_x, size_y) = board.shape

    # BUGFIX: zero_point_distance=1 breaks test_df[90081]
    # NOTE:   zero_point_distance=2 results in: 2*delta slowdown
    # NOTE:   zero_point_distance=3 results in another 2-6x slowdown (but in rare cases can be quicker)
    z3_solver, t_cells = get_z3_solver(
        size=size,
        delta=delta,
    )
    try:
        while True: z3_solver.pop()
    except: pass

    # This is a safety catch to prevent timeouts when running in Kaggle notebooks
    if timeout: z3_solver.set("timeout", int(timeout * 1000/2.5))  # timeout is in milliseconds, but inexact and ~2.5x slow

    # Add constraints for T=delta-1 the problem defined in the input board
    z3_solver.add( get_initial_board_constraints(t_cells, board) )
    z3_solver.push()

    for zero_point_distance in [1,2]:
        z3_solver.pop()
        z3_solver.add( get_zero_point_constraint(t_cells, zero_point_distance) )
        z3_solver.push()

        # if z3_solver.check() != z3.sat: print('Unsolvable!')
        solution_3d = solver_to_numpy_3d(z3_solver, t_cells[warmup:])  # calls z3_solver.check()
        time_taken  = time.perf_counter() - time_start

        # Validate that forward play matches backwards solution
        if np.count_nonzero(solution_3d):  # quicker than calling z3_solver.check() again
            assert is_valid_solution(solution_3d[0], board, delta)
            if verbose: print(f'game_of_life_solver() - took: {time_taken:6.1f}s | Solved! ')
            break
    else:
        if verbose: print(f'game_of_life_solver() - took: {time_taken:6.1f}s | unsolved')
    return z3_solver, t_cells, solution_3d


def game_of_life_next_solution(z3_solver, t_cells, verbose=True):
    time_start = time.perf_counter()
    z3_solver.add(z3.Or(*[
        cell != z3_solver.model()[cell]
        for cell in pydash.flatten_deep(t_cells[0])
    ]))
    solution_3d = solver_to_numpy_3d(z3_solver, t_cells)
    time_taken  = time.perf_counter() - time_start
    if verbose: print(f'game_of_life_next_solution() - took: {time_taken:.1f}s')
    return z3_solver, t_cells, solution_3d


@clru_cache(None)
def get_neighbourhood_coords(shape: Tuple[int,int], x: int, y: int, distance=1) -> List[Tuple[int,int]]:
    output = []
    for dx, dy in itertools.product(range(-distance,distance+1), range(-distance,distance+1)):
        if dx == dy == 0: continue      # ignore self
        nx = (x + dx) % shape[0]        # modulo loop = board wraparound
        ny = (y + dy) % shape[1]
        output.append( (nx, ny) )
    return output


def get_neighbourhood_cells(cells: Union[np.ndarray, List[List[int]]], x: int, y: int, distance=1) -> List[int]:
    shape  = ( len(cells), len(cells[0]) )
    coords = get_neighbourhood_coords(shape, x, y, distance)
    output = [ cells[x][y] for (x,y) in coords ]
    return output


def solver_to_numpy_3d(z3_solver, t_cells) -> np.ndarray:  # np.int8[time][x][y]
    is_sat = z3_solver.check() == z3.sat
    output = np.array([
        [
            [
                int(z3.is_true(z3_solver.model()[cell])) if is_sat else 0
                for y, cell in enumerate(cells)
            ]
            for x, cells in enumerate(t_cells[t])
        ]
        for t in range(len(t_cells))
    ], dtype=np.int8)
    return output