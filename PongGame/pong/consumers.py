import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .game.game_singleton import GameSingleton
import logging
import random
from .ai_notify_ws_singleton import WebSocketSingleton
import websockets

AI = 2
FRONT = 1

#add greetings from both clients
#add clients to clients
#dict in dict, initial key = game_id
#on getting greetings, create players with pID and type
class PongConsumer(AsyncWebsocketConsumer):
    print("Pong consumer")
    logger = logging.getLogger(__name__)
    game_wrapper = None
    client = None
    is_main = False

    clients = {}
    async def connect(self):
        self.logger.info(f"scope: {self.scope}")

        self.game_id = self.scope['url_route']['kwargs']['uid']
        self.logger.info(f"game id: {self.game_id}")
        self.group_name = f"pong_{self.game_id}"
        self.logger.info(f"Group name: {self.group_name}")
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()
        self.logger.info(f"New client connected: {self.channel_name}")
        #check if game_id exists in clients
        self.clients[self.channel_name] = self
        self.game_wrapper = GameSingleton.get_game()
        self.game_wrapper.present_players += 1
        if self.game_wrapper.present_players == 2:
            self.logger.info("Main client connected")
            self.logger.info(f"number of connected clients: {self.game_wrapper.present_players}")
            self.is_main = True
            self.game_wrapper.all_players_connected.set()
        self.logger.info(f"PongConsumer connected and added to group 'pong': {self.channel_name}")

        if self.is_main is True:
            asyncio.ensure_future(self.generate_states())

    async def disconnect(self, close_code):
        # Déconnecter WebSocket proprement
        await self.channel_layer.group_discard("pong", self.channel_name)
        del self.clients[self.channel_name]
        self.game_wrapper.present_players -= 1

    async def receive(self, text_data):
        # Traiter les messages reçus du client
        try:
            event = json.loads(text_data)
            if event["sender"] == "front":
                await self.handle_front_input(event)
            if event["sender"] == "AI":
                await self.handle_ai_input(event)
                self.game_wrapper.waiting_for_ai.set()
        except Exception as e:
            self.logger.info(f"Error in receive: {e}")


    async def handle_ai_input(self, event):
        self.client = AI
        if event["type"] == "greetings":
            await self.send_ai_setup_instructions()
        if event["type"] == "setup":
            self.game_wrapper.ai_is_initialized.set()
        if event["type"] == "move":
            logging.info(f"AI move event: {event}\n\n")
            if event["direction"] == "up":
                for _ in range(3):
                    self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)
            if event["direction"] == "down":
                for _ in range(3):
                    self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)


    async def send_ai_setup_instructions(self):
        self.logger.info(f"Sending AI setup instructions")
        ai_data = {
            "type": "setup",
            "width": self.game_wrapper.game.width,
            "height": self.game_wrapper.game.height,
            "paddle_width": self.game_wrapper.game.paddle2.width,
            "paddle_height": self.game_wrapper.game.paddle2.height,
            "loading": self.game_wrapper.game.LOADING,
        }
        if self.game_wrapper.game.RUNNING_AI is False:
            ai_data["difficulty"] = 0
        else:
            ai_data["difficulty"] = self.game_wrapper.game.DIFFICULTY
        self.logger.info(f"Sending AI setup instructions: {ai_data}")
        await self.send(json.dumps(ai_data))
        self.game_wrapper.ai_is_initialized.set()
        await asyncio.sleep(0.00000001)

    async def handle_front_input(self, event):
        self.client = FRONT
        # self.logger.info(f"Handling front input: {event}")
        if event["type"] == "greetings":
            return
        elif event["type"] == "start":
            self.logger.info(f"start event: {event}")
            self.game_wrapper.start_event.set()

        elif event["type"] == "resumeOnGoal":
            logging.info(f"resume on goal event: {event}")
            await self.game_wrapper.game.resume_on_goal()
            logging.info(f"etat du jeu: pause={self.game_wrapper.game.pause}, score p2={self.game_wrapper.game.paddle2.score}")

        elif event["type"] == "keyDown":
            # logging.info(f"key down event: {event}")

            if event["event"] == "pause":
                self.game_wrapper.game.pause = not self.game_wrapper.game.pause

            elif event["event"] == "player1Up":
                for _ in range(10):
                    self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=True)

            elif event["event"] == "player1Down":
                for _ in range(10):
                    self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=False)

            elif event["event"] == "player2Up" and self.game.RUNNING_AI is False:
                for _ in range(10):
                    self.game_wrapper.game.paddle2.move(self.game.game_wrapper.height, up=True)

            elif event["event"] == "player2Down" and self.game.RUNNING_AI is False:
                for _ in range(10):
                    self.game_wrapper.game.paddle2.move(self.game.game_wrapper.height, up=False)

            elif event["event"] == "reset":
                self.game_wrapper.game.ball.reset(self.game_wrapper.game.ball.x)
                self.game_wrapper.game.state = self.game_wrapper.game.getGameState()
                self.game_wrapper.game.lastSentInfos = 0

    async def generate_states(self):
        self.logger.info("in generate states")
        await self.game_wrapper.ai_is_initialized.wait()
        self.logger.info("in generate states, ai is initialized")
        await self.game_wrapper.start_event.wait()
        self.logger.info("state gen set")
        x = 0
        async for state in self.game_wrapper.game.rungame():
            print(f"in state, waiting for ai: {self.game_wrapper.waiting_for_ai.is_set()}") 
            await self.game_wrapper.waiting_for_ai.wait()

            state_dict = json.loads(state)
            if state_dict["type"] == "gameover":
                self.game_wrapper.game.quit()
                self.game_wrapper.game_over.set()
                break
            for client in self.clients.values():
                await client.send(text_data=json.dumps(state_dict))
                self.game_wrapper.waiting_for_ai.clear()
                await asyncio.sleep(0.0000001)
            x += 1

            await asyncio.sleep(0.00000001)

