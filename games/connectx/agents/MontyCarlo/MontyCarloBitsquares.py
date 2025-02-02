# This is a LinkedList implementation of MontyCarlo Tree Search
# but using bitboard_gameovers_heuristic() instead of run_random_simulation()
# Inspired by https://www.kaggle.com/matant/monte-carlo-tree-search-connectx
from struct import Struct

from agents.MontyCarlo.MontyCarloHeuristic import MontyCarloHeuristicNode
from core.ConnectXBBNN import *
from heuristics.BitsquaresHeuristic import bitsquares_heuristic_sigmoid

Hyperparameters = namedtuple('hyperparameters', [])

class MontyCarloBitsquaresNode(MontyCarloHeuristicNode):
    heuristic_fn   = bitsquares_heuristic_sigmoid
    heuristic_args = {}  # reward_power=1.75, sigmoid_width=7.0, sigmoid_height=1.0

class MontyCarloBitsquaresNode2(MontyCarloBitsquaresNode):
    pass


def MontyCarloBitsquares(**kwargs):
    # observation   = {'mark': 1, 'board': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
    # configuration = {'columns': 7, 'rows': 6, 'inarow': 4, 'steps': 1000, 'timeout': 8}
    def MontyCarloBitsquares(observation: Struct, configuration: Struct) -> int:
        return MontyCarloBitsquaresNode.agent(**kwargs)(observation, configuration)
    return MontyCarloBitsquares

def MontyCarloBitsquaresKaggle(observation, configuration):
    return MontyCarloBitsquares()(observation, configuration)
