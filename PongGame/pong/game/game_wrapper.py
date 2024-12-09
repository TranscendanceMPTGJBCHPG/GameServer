from .game import Game
from .player import Player
from _datetime import datetime
from .game_status import GameStatus

import asyncio

class GameWrapper:
    def __init__(self, game_id: str):

        self.created_at = datetime.now()
        self.status = GameStatus.WAITING

        self.game_id = game_id
        self.game_is_initialized = asyncio.Event()
        self.ai_is_initialized = asyncio.Event()
        self.start_event = asyncio.Event()
        self.game_over = asyncio.Event()
        self.all_players_connected = asyncio.Event()
        self.resume_on_goal = asyncio.Event()
        self.waiting_for_ai = asyncio.Event()
        self.received_names = asyncio.Event()
        self.ai_partner = True

        self.has_resumed_count = 0
        self.has_resumed = asyncio.Event()

        self.player_1 = Player()
        self.player_2 = Player()

        self.present_players = 0
        self.game = Game()  # Supposant que vous avez une classe GameInstance

    def get_game(self):
        return self.game
