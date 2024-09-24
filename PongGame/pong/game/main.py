from game import Game
import asyncio

async def launch(game):
    async for state in game.rungame():
        print(state)

if __name__ == "__main__":
    game = Game()
    asyncio.run(launch(game))
