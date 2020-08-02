
from agents.AlphaBetaAgent.AlphaBetaAgent import AlphaBetaAgent
from agents.AlphaBetaAgent.AlphaBetaBitboard import AlphaBetaBitboard
from agents.MontyCarlo.MontyCarloTreeSearch import MontyCarloTreeSearch
from agents.Negamax.Negamax import Negamax



agents = [
    ('Negamax',              Negamax()),
    ('AlphaBetaAgent',       AlphaBetaAgent.agent()),
    ('AlphaBetaBitboard',    AlphaBetaBitboard.agent()),
    ('MontyCarloTreeSearch', MontyCarloTreeSearch),
]

kaggle_agents = [
    "random",
    "negamax",
]
