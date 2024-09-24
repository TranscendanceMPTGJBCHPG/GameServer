from .game import Game
import asyncio
class SharedState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedState, cls).__new__(cls)
            cls._instance.game = None
            cls._instance.game_is_initialized = asyncio.Event()
            cls._instance.ai_is_initialized = asyncio.Event()
            cls._instance.start_event = asyncio.Event()
            cls._instance.game_over = asyncio.Event()
        return cls._instance

    def set_game(self, game):
        self.game = game
        self.game_is_initialized.set()

    def get_game(self):
        return self.game