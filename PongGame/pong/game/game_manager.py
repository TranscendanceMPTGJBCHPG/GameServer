import asyncio
from typing import Optional
from .game_wrapper import GameWrapper
from _datetime import datetime
from .game_status import GameStatus
import logging

class GameManager:
    def __init__(self):
        self.active_games = {}
        self._lock = asyncio.Lock()

    async def create_or_get_game(self, game_id: str) -> GameWrapper:
        async with self._lock:
            # logging.info(f"Creating or getting game with id: {game_id}")
            if game_id not in self.active_games:
                # logging.info(f"Game CREATED with id: {game_id}")
                self.active_games[game_id] = GameWrapper(game_id)
                # logging.info(f"number of active games: {len(self.active_games)}")
                # logging.info(f"Game created with id: {game_id}")
            # else:
                # logging.info(f"Game RETRIEVED with id: {game_id}")
            return self.active_games[game_id]
        
    async def remove_game(self, game_id: str):
        async with self._lock:
            if game_id in self.active_games:
                del self.active_games[game_id]
                return True
            return False

# Instance unique
game_manager = GameManager()
