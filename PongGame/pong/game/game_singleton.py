# pong/game/singleton_game.py

from .game import Game
from .player import Player
import asyncio

class GameSingleton:
    _instance = None

    game_is_initialized = asyncio.Event()
    ai_is_initialized = asyncio.Event()
    start_event = asyncio.Event()
    game_over = asyncio.Event()
    all_players_connected = asyncio.Event()
    resume_on_goal = asyncio.Event()
    waiting_for_ai = asyncio.Event()
    ai_partner = True

    has_resumed_count = 0
    has_resumed = asyncio.Event()

    player_1 = Player()
    player_2 = Player()

    present_players = 0
    game = Game()
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GameSingleton, cls).__new__(cls)

    @classmethod
    def get_game(cls):
        if cls._instance is None:
            cls()
        return cls._instance
