#!/usr/bin/env python3
import argparse
import contextlib
import os
import time
import traceback

import json5
from kaggle_environments import make

from agents.AlphaBetaAgent.AlphaBetaAgent import AlphaBetaAgent
from agents.AlphaBetaAgent.AlphaBetaBitboard import AlphaBetaBitboard
from agents.AlphaBetaAgent.AlphaBetaBitsquares import AlphaBetaBitsquares
from agents.AlphaBetaAgent.AlphaBetaOddEven import AlphaBetaOddEven
from agents.AlphaBetaAgent.MinimaxBitboard import MinimaxBitboard
from agents.MontyCarlo.AntColonyTreeSearch import AntColonyTreeSearch
from agents.MontyCarlo.MontyCarloBitsquares import MontyCarloBitsquares
from agents.MontyCarlo.MontyCarloHeuristic import MontyCarloHeuristic
from agents.MontyCarlo.MontyCarloOddEven import MontyCarloOddEven
from agents.MontyCarlo.MontyCarloPure import MontyCarloPure
from agents.Negamax.Negamax import Negamax

env = make("connectx", debug=True)
env.render()
env.reset()

parser = argparse.ArgumentParser()
parser.add_argument('--debug',         action="store_true")
parser.add_argument('--inline',        action="store_true")
parser.add_argument('-v', '--verbose', action="store_true")
parser.add_argument('-q', '--quiet',   action="store_true")
parser.add_argument('-t', '--timeout', type=int)
parser.add_argument('-r', '--rounds',  type=int, default=1)
parser.add_argument('-1', '--p1',      type=str, required=True)
parser.add_argument('-2', '--p2',      type=str, default='negamax')
parser.add_argument('--arg1',          type=json5.loads)  # eg: '{ "exploration": 1 }'
parser.add_argument('--arg2',          type=json5.loads)


argv = parser.parse_args()
print(argv)

if argv.timeout:
    env.configuration.timeout = argv.timeout

agent_args = {}
if argv.debug:
    env.configuration.timeout = 24*60*60
    env.configuration.steps   = 1

agent_1 = agent_2 = agent_1_name = agent_2_name = None
agent_1_args = { }  # "safety_time": 0
agent_2_args = { }  # "safety_time": 0
for agent_name, position in [ (argv.p1, 'p1'), (argv.p2, 'p2') ]:
    kwargs = (argv.arg1 if position == 'p1' else argv.arg2) or {}
    if   agent_name == 'AlphaBetaAgent':           agent = AlphaBetaAgent.agent(**kwargs)
    elif agent_name == 'AlphaBetaBitboard':        agent = AlphaBetaBitboard.agent(**kwargs)
    elif agent_name == 'AlphaBetaOddEven':         agent = AlphaBetaOddEven.agent(**kwargs)
    elif agent_name == 'AlphaBetaBitsquares':      agent = AlphaBetaBitsquares.agent(**kwargs)
    elif agent_name == 'MinimaxBitboard':          agent = MinimaxBitboard.agent(**kwargs)
    elif agent_name == 'MontyCarloPure':           agent = MontyCarloPure(**kwargs)
    elif agent_name == 'MontyCarloHeuristic':      agent = MontyCarloHeuristic(**kwargs)
    elif agent_name == 'MontyCarloBitsquares':     agent = MontyCarloBitsquares(**kwargs)
    elif agent_name == 'MontyCarloOddEven':        agent = MontyCarloOddEven(**kwargs)
    elif agent_name == 'AntColonyTreeSearch':      agent = AntColonyTreeSearch(**kwargs)
    elif agent_name == 'Negamax':                  agent = Negamax(**kwargs)
    elif agent_name == 'negamax':                  agent = agent_name
    elif agent_name == 'random':                   agent = agent_name
    else: raise Exception(f'runner.py: invalid agent {position} == {agent_name}')

    if position == 'p1':
        agent_1 = agent
        agent_1_name = agent_name
        agent_1_args = kwargs
    else:
        agent_2 = agent
        agent_2_name = agent_name
        agent_2_args = kwargs

if argv.inline:
    # env.configuration.timeout = 120
    observation   = env.state[0].observation
    configuration = env.configuration
    agent_1(observation, configuration)
    # agent_2(observation, configuration)

else:
    scores = [0,0]
    rounds = 0
    try:
        for round in range(argv.rounds):
            rounds += 1
            if round % 2 == 0:
                agent_order = [
                    { "agent": agent_1, "name": f"{agent_1_name}({agent_1_args or ''}) (p1)", "index": 0, },
                    { "agent": agent_2, "name": f"{agent_2_name}({agent_2_args or ''}) (p2)", "index": 1, },
                ]
            else:
                agent_order = [
                    { "agent": agent_2, "name": f"{agent_2_name}({agent_2_args or ''}) (p1)", "index": 1, },
                    { "agent": agent_1, "name": f"{agent_1_name}({agent_1_args or ''}) (p2)", "index": 0, },
                ]


            env.reset()
            time_start = time.perf_counter()

            # Disable logfiles with --quiet
            # BUG: this throws exception on next print() in debugger if argv.quiet
            if argv.quiet:
                with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
                    env.run([agent_order[0]['agent'], agent_order[1]['agent']])
            else:
                env.run([agent_order[0]['agent'], agent_order[1]['agent']])
                print()

            time_taken = time.perf_counter() - time_start

            rewards = [
                env.state[0].reward if env.state[0].reward is not None else -1,
                env.state[1].reward if env.state[1].reward is not None else -1,
            ]
            scores[ agent_order[0]['index'] ] += ((rewards[0] or 0) + 1)/2
            scores[ agent_order[1]['index'] ] += ((rewards[1] or 0) + 1)/2

            message = (
                     f"Draw: {agent_order[0]['name']} vs {agent_order[1]['name']}"           if rewards[0] == rewards[1]
                else f"Winner: {agent_order[0]['name']} vs Loser: {agent_order[1]['name']} " if rewards[0] >  rewards[1]
                else f"Winner: {agent_order[1]['name']} vs Loser: {agent_order[0]['name']}"
            )

            print(f'Round {round} ({time_taken:.1f}s) = {message}')
            if argv.verbose: print(env.render(mode="ansi"))

    except Exception as exception:
        print('runner.py: Exception: ', exception)
        traceback.print_tb(exception.__traceback__)

    print()
    print('runner.py', argv)
    print(f'{scores[0]:3.1f}/{rounds:.1f} = {100 * scores[0]/rounds:3.0f}% | {agent_1_name}({agent_1_args})')
    print(f'{scores[1]:3.1f}/{rounds:.1f} = {100 * scores[1]/rounds:3.0f}% | {agent_2_name}({agent_2_args})')
    if scores[0] == scores[1]:
        print('Draw!')
    else:
        winner = f"{agent_1_name}({agent_1_args or ''})" if scores[0] > scores[1] else f"{agent_2_name}({agent_2_args or ''})"
        loser  = f"{agent_1_name}({agent_1_args or ''})" if scores[0] < scores[1] else f"{agent_2_name}({agent_2_args or ''})"
        print(f'Winner: {winner}')
        print(f'Loser:  {loser}')
