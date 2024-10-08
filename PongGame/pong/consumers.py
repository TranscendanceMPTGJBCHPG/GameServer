import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .game.game_singleton import GameSingleton
import logging
import random
from .ai_notify_ws_singleton import WebSocketSingleton
import websockets
import urllib.request
import urllib.error
import aiohttp
from django.middleware.csrf import get_token
from .utils import get_new_csrf_string_async

AI = 2
FRONT = 1

#add greetings from both clients
#add clients to clients
#dict in dict, initial key = game_id
#on getting greetings, create players with pID and type
class PongConsumer(AsyncWebsocketConsumer):
    # print("Pong consumer")
    logger = logging.getLogger(__name__)
    game_wrapper = None
    client = None
    is_main = False
    has_resumed = False
    mode = None

    clients = {}

    async def connect(self):
        # self.logger.info(f"scope: {self.scope}")
        self.game_id = self.scope['url_route']['kwargs']['uid']
        # self.logger.info(f"game id: {self.game_id}")
        self.group_name = f"pong_{self.game_id}"
        # self.logger.info(f"Group name: {self.group_name}")
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        if 'csrf_token' not in self.scope['session']:
            try:
                csrf_token = await get_new_csrf_string_async()
                self.scope['session']['csrf_token'] = csrf_token
                await self.scope["session"].save()
            except Exception as e:
                logging.error(f"Error generating CSRF token: {e}")

        await self.accept()
        # self.logger.info(f"New client connected: {self.channel_name}")
        #check if game_id exists in clients

        self.clients[self.channel_name] = self
        self.game_wrapper = GameSingleton.get_game()

        if self.game_id[0] == 'k' and self.game_id[-1] == 'k':
            self.shared_screen_init()

        elif self.game_id[0] == 'P' and self.game_id[1] == 'V' and self.game_id[2] == 'P':
            self.LAN_init()
        else:
            self.PVE_init()

        if self.is_main is True:
            asyncio.ensure_future(self.generate_states())

    def shared_screen_init(self):
        self.mode = 'PVP_keyboard'
        self.client = FRONT
        self.is_main = True


        self.game_wrapper.present_players += 2
        self.game_wrapper.player_1.type = "Human"
        self.game_wrapper.player_2.type = "Human"
        self.game_wrapper.player_1.is_connected = True# self.logger.info("Main client connected")
            # self.logger.info(f"number of connected clients: {self.game_wrapper.present_players}")
        self.game_wrapper.player_2.is_connected = True
        self.game_wrapper.all_players_connected.set()
        # self.game_wrapper.ai_is_initialized.set()
        # self.game_wrapper.waiting_for_ai.set()
        self.game_wrapper.game.RUNNING_AI = False

    def LAN_init(self):
        self.mode = 'PVP_LAN'
        self.client = FRONT
        self.game_wrapper.present_players += 1
        if self.game_wrapper.present_players == 2:
            self.is_main = True
            self.game_wrapper.all_players_connected.set()
            self.game_wrapper.player_2.type = "Human"
            self.game_wrapper.player_2.is_connected = True
        else:
            self.game_wrapper.player_1.type = "Human"
            self.game_wrapper.player_1.is_connected = True
        self.game_wrapper.ai_is_initialized.set()
        self.game_wrapper.waiting_for_ai.set()
        self.game_wrapper.game.RUNNING_AI = False

    def PVE_init(self):
        self.mode = "PVE"
        self.game_wrapper.present_players += 1
        if self.game_wrapper.present_players == 2:
            # self.logger.info("Main client connected")
            # self.logger.info(f"number of connected clients: {self.game_wrapper.present_players}")
            self.game_wrapper.player_2.type = "AI"
            self.game_wrapper.player_2.is_connected = True
            self.game_wrapper.player_2.is_ready = True
            self.is_main = True
            self.game_wrapper.all_players_connected.set()
        else:
            self.game_wrapper.player_1.type = "Human"
            self.game_wrapper.player_1.is_connected = True
        self.game_wrapper.game.RUNNING_AI = True

    # self.logger.info(f"PongConsumer connected and added to group 'pong': {self.channel_name}")


    async def disconnect(self, close_code):
        # Déconnecter WebSocket proprement
        await self.channel_layer.group_discard("pong", self.channel_name)
        del self.clients[self.channel_name]
        self.game_wrapper.present_players -= 1
        self.game_wrapper.game.pause = True
        self.game_wrapper.game_over.set()
        self.logger.info(f"Client disconnected: {self.channel_name}")
        try:
            if self.client == FRONT:
                winner = "AI"
            else:
                winner = "Human"
            url = 'http://nginx:7777/game/new/'
            data = {
                'type': 'gameover',
                'sender': 'game',
                'uid': self.game_id,
                'winner': winner,
            }
            logging.info(f"before get token")
            csrf_token = self.scope['session'].get('csrf_token', get_new_csrf_string_async())
            logging.info(f"csrf token: {csrf_token}")

            headers = {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf_token
            }

            # logging.info(f"Sending gameover event: {data}")

            # Convertir le corps de la requête en JSON
            # data = json.dumps(data).encode('utf-8')

            # Créer l'objet Request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url,
                        json=data,
                        headers=headers,
                        cookies={'csrftoken': csrf_token}
                ) as response:
                    if response.status == 403:
                        logging.error("CSRF validation failed")
                        return None

                    content = await response.text()
                    return json.loads(content)
                    # print(f"UID: {data}")

        except Exception as e:
            logging.error(f"Error sending gameover event: {str(e)}")



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
            # logging.info(f"AI move event: {event}\n\n")
            if event["direction"] == "up":
                for _ in range(3):
                    self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)
            if event["direction"] == "down":
                for _ in range(3):
                    self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)


    async def send_ai_setup_instructions(self):
        # self.logger.info(f"Sending AI setup instructions")
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
        # self.logger.info(f"Sending AI setup instructions: {ai_data}")
        await self.send(json.dumps(ai_data))
        self.game_wrapper.ai_is_initialized.set()
        await asyncio.sleep(0.00000001)

    def handle_player1_input(self, event):
        if event["event"] == "player1Up":
            for _ in range(5):
                self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=True)

        if event["event"] == "player1Down":
            for _ in range(5):
                self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=False)

    def handle_player2_input(self, event):
        if event["event"] == "player2Up" and self.game_wrapper.game.RUNNING_AI is False:
            for _ in range(5):
                self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)

        if event["event"] == "player2Down" and self.game_wrapper.game.RUNNING_AI is False:
            for _ in range(5):
                self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)


    async def handle_front_input(self, event):
        self.client = FRONT
        if event["type"] == "resumeOnGoal":
            logging.info(f"resume on goal event: {event}")
            await self.game_wrapper.game.resume_on_goal()
            self.game_wrapper.has_resumed = True
            # logging.info(f"etat du jeu: pause={self.game_wrapper.game.pause}, score p2={self.game_wrapper.game.paddle2.score}")
        elif self.game_wrapper.game.display is True:
            return
        # self.logger.info(f"Handling front input: {event}")
        if event["type"] == "greetings":
            return
        elif event["type"] == "start":
            if self.mode == "PVE":
                self.game_wrapper.player_1.is_ready = True
                self.game_wrapper.start_event.set()
            if self.is_main is True:
                self.game_wrapper.player_2.is_ready = True
                self.game_wrapper.start_event.set()
            else:
                self.game_wrapper.player_1.is_ready = True


        elif event["type"] == "keyDown":
            # logging.info(f"key down event: {event}")

            if event["event"] == "pause":
                if self.mode == "PVE" or "PVP_keyboard":
                    self.game_wrapper.game.pause = not self.game_wrapper.game.pause

            if self.is_main is False:
                self.handle_player1_input(event)


            if self.is_main is True:
                self.handle_player2_input(event)

            # if event["event"] == "reset":
            #     self.game_wrapper.game.ball.reset(self.game_wrapper.game.ball.x, self.game_wrapper.game.display)
            #     self.game_wrapper.game.state = self.game_wrapper.game.getGameState()
            #     self.game_wrapper.game.lastSentInfos = 0

        elif event["type"] == "keyUp":
            if event["event"] == "c":
                if self.game_wrapper.game.display is False:
                    self.game_wrapper.game.init_display()
                else:
                    self.game_wrapper.game.deactivate_CLI()
            if event["event"] == 1:
                self.game_wrapper.game.p1_successive_inputs.clear()
            else:
                self.game_wrapper.game.p2_successive_inputs.clear()


    async def generate_states(self):
        self.logger.info("in generate states")
        await self.game_wrapper.ai_is_initialized.wait()
        self.logger.info("in generate states, ai is initialized")
        await self.game_wrapper.start_event.wait()
        self.logger.info("state gen set")
        x = 0
        async for state in self.game_wrapper.game.rungame():
            # logging.info("in state gen")
            # print(f"in state, waiting for ai: {self.game_wrapper.waiting_for_ai.is_set()}")
            if self.game_wrapper.game.RUNNING_AI is True:
                await self.game_wrapper.waiting_for_ai.wait()

            state_dict = json.loads(state)
            if state_dict["type"] == "gameover":
                self.game_wrapper.game.quit()
                self.game_wrapper.game_over.set()
                break
            if self.game_wrapper.has_resumed is True:
                state_dict["type"] = "ResumeOnGoalDone"
                logging.info(f"state dict: {state_dict}")
                self.game_wrapper.has_resumed = False
            try:
                for client in self.clients.values():
                    await client.send(text_data=json.dumps(state_dict))
                    self.game_wrapper.waiting_for_ai.clear()
                    await asyncio.sleep(0.0000001)
            except Exception as e:
                logging.info(f"an error happened, during send")
                return ;
            x += 1

            await asyncio.sleep(0.00000001)

