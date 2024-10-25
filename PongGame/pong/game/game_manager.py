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
            logging.info(f"Creating or getting game with id: {game_id}")
            if game_id not in self.active_games:
                self.active_games[game_id] = GameWrapper(game_id)
                logging.info(f"Game created with id: {game_id}")
            return self.active_games[game_id]

# Instance unique
game_manager = GameManager()

# class GameManager:
#     def __init__(self):
#         self.active_games = {}  # uid: GameWrapper
#         self._lock = asyncio.Lock()
#
#     async def create_game(self, game_id: str) -> GameWrapper:
#         async with self._lock:
#             if game_id not in self.active_games:
#                 self.active_games[game_id] = GameWrapper(game_id)
#             return self.active_games[game_id]
#
#     async def remove_game(self, game_id: str):
#         async with self._lock:
#             if game_id in self.active_games:
#                 del self.active_games[game_id]
#
#     async def get_game(self, game_id: str) -> Optional[GameWrapper]:
#         return self.active_games.get(game_id)
#
#     async def cleanup_stale_games(self):
#         while True:
#             async with self._lock:
#                 current_time = datetime.now()
#                 for game_id, game in list(self.active_games.items()):
#                     if (game.status == GameStatus.WAITING and
#                             (current_time - game.created_at).seconds > 60):
#                         await self.remove_game(game_id)
#             await asyncio.sleep(30)