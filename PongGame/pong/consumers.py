import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .game.game_singleton import GameSingleton
import logging
import aiohttp
from .utils import get_new_csrf_string_async
from enum import Enum

class PlayerType(Enum):
    HUMAN = "Human"
    AI = "AI"

class GameMode(Enum):
    PVP_KEYBOARD = "PVP_keyboard"
    PVP_LAN = "PVP_LAN"
    PVE = "PVE"

class ClientType(Enum):
    AI = 2
    FRONT = 1

class PongConsumer(AsyncWebsocketConsumer):
    logger = logging.getLogger(__name__)
    game_wrapper = None
    side = None
    is_main = False
    has_resumed = False
    mode = None
    adversary = None


    clients = {}

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['uid']
        self.group_name = f"pong_{self.game_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        self.clients[self.channel_name] = self

        await self._setup_csrf()
        await self.accept()

        self.game_wrapper = GameSingleton.get_game()

        await self._initialize_game_mode()

        if self.is_main is True:
            asyncio.ensure_future(self.generate_states())

    async def _setup_csrf(self):
        if 'csrf_token' not in self.scope['session']:
            try:
                csrf_token = await get_new_csrf_string_async()
                self.scope['session']['csrf_token'] = csrf_token
                await self.scope["session"].save()
            except Exception as e:
                self.logger.error(f"Error generating CSRF token: {e}")


#*********************GAME MODE INITIALIZATION START********************************
    async def _initialize_game_mode(self):
        if self._is_shared_screen_mode():
            self._init_shared_screen()
        elif self._is_lan_mode():
            self._init_lan_mode()
        else:
            self._init_pve_mode()


    #********************SHARED SCREEN MODE INITIALIZATION START*********************
    def _is_shared_screen_mode(self):
        return self.game_id[0] == 'k' and self.game_id[-1] == 'k'


    def _init_shared_screen(self):
        self.mode = GameMode.PVP_KEYBOARD.value
        self.client = ClientType.FRONT.value
        self.is_main = True
        self.game_wrapper.present_players += 2

        for player in [self.game_wrapper.player_1, self.game_wrapper.player_2]:
            player.type = PlayerType.HUMAN.value
            player.is_connected = True

        self.game_wrapper.all_players_connected.set()
        self.game_wrapper.ai_is_initialized.set()
        self.game_wrapper.game.RUNNING_AI = False

    #********************SHARED SCREEN MODE INITIALIZATION STOP************************



    #*********************LAN MODE INITIALIZATION START********************************
    def _is_lan_mode(self):
        return self.game_id.startswith('PVP')

    def _init_lan_mode(self):
        self.mode = GameMode.PVP_LAN.value
        self.client = ClientType.FRONT.value
        self.game_wrapper.present_players += 1

        if self.game_wrapper.present_players == 2:
            self._setup_second_lan_player()
        else:
            self._setup_first_lan_player()

        self._setup_lan_common()

    def _setup_first_lan_player(self):
        self.side = "p1"
        self.game_wrapper.player_1.type = PlayerType.HUMAN.value
        self.game_wrapper.player_1.is_connected = True

    def _setup_second_lan_player(self):
        self.side = "p2"
        self.is_main = True
        self.game_wrapper.all_players_connected.set()
        self.game_wrapper.player_2.type = PlayerType.HUMAN.value
        self.game_wrapper.player_2.is_connected = True

    def _setup_lan_common(self):
        self.game_wrapper.ai_is_initialized.set()
        self.game_wrapper.waiting_for_ai.set()
        self.game_wrapper.game.RUNNING_AI = False

    #*********************LAN MODE INITIALIZATION END********************************



    #*********************PVE MODE INITIALIZATION START******************************
    def _init_pve_mode(self):
        self.mode = GameMode.PVE.value
        # self._setup_pve_players()
        self.game_wrapper.present_players += 1

        if self.game_wrapper.present_players == 2:
            self._handle_second_pve_connection(self.game_id)
        else:
            self._handle_first_pve_connection(self.game_id)

        self.game_wrapper.game.RUNNING_AI = True

    def _handle_first_pve_connection(self, game_id):
        ai_is_player_one = game_id[-1] == '1'

        if ai_is_player_one is True:
            self.side = "p2"
            self.game_wrapper.player_2.type = PlayerType.HUMAN.value
            self.game_wrapper.player_1.type = PlayerType.AI.value
            self.game_wrapper.player_2.is_connected = True
        else:
            self.side = "p1"
            self.game_wrapper.player_1.type = PlayerType.HUMAN.value
            self.game_wrapper.player_2.type = PlayerType.AI.value
            self.game_wrapper.player_1.is_connected = True

    def _handle_second_pve_connection(self, game_id):
        ai_is_player_one = game_id[-1] == '1'

        if ai_is_player_one is True:
            self.side = "p1"
            self.game_wrapper.player_1.is_connected = True
            self.game_wrapper.player_1.is_ready = True
        else:
            self.side = "p2"
            self.game_wrapper.player_2.is_connected = True
            self.game_wrapper.player_2.is_ready = True

        self.is_main = True
        self.game_wrapper.all_players_connected.set()

    #*********************PVE MODE INITIALIZATION END********************************

#*********************GAME MODE INITIALIZATION END********************************

#******************************DISCONNECT********************************

    async def disconnect(self, close_code):
        # Déconnecter WebSocket proprement
        await self.channel_layer.group_discard("pong", self.channel_name)
        del self.clients[self.channel_name]
        self.game_wrapper.present_players -= 1
        self.game_wrapper.game.pause = True
        self.game_wrapper.game_over.set()

        try:
            url = 'http://nginx:7777/game/new/'
            csrf_token = self.scope['session'].get('csrf_token', get_new_csrf_string_async())
            data = self.generate_gameover_data()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url,
                        json= data,
                        headers= self.generate_headers(csrf_token),
                        cookies= {'csrftoken': csrf_token}
                ) as response:
                    if response.status == 403:
                        logging.error("CSRF validation failed")
                        return None

            await self.send_gameover_to_remaining_client(data)

        except Exception as e:
            logging.error(f"Error sending gameover event: {str(e)}\n\n\n\n")

    async def send_gameover_to_remaining_client(self, data):
        remaining_client = list(self.clients.values())[0]
        await remaining_client.send(json.dumps(data))

    def generate_headers(self, token):
        headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': token
        }
        return headers

    def generate_gameover_data(self):
        data = {
            'type': 'gameover',
            'sender': 'game',
            'uid': self.game_id,
            'winner': self.get_winner(),
        }
        return data

    def get_winner(self):
        if self.mode == "PVE":
            if self.client == ClientType.FRONT:
                winner = "Human"
            else:
                winner = "AI"
        elif self.mode == "PVP_keyboard":
            if self.game_wrapper.game.paddle1.score > self.game_wrapper.game.paddle2.score:
                winner = "Player1"
            else:
                winner = "Player2"
        else:
            if self.is_main is True:
                winner = "Player1"
            else:
                winner = "Player2"

        return winner
#******************************DISCONNECT********************************


    async def receive(self, text_data):
        # Traiter les messages reçus du client
        try:
            event = json.loads(text_data)
            # self.logger.info(f"Received event: {event}")
            if event["sender"] == "front":
                await self.handle_front_input(event)
            if event["sender"] == "AI":
                await self.handle_ai_input(event)
                self.game_wrapper.waiting_for_ai.set()
        except Exception as e:
            self.logger.info(f"Error in receive: {e}")


    async def handle_ai_input(self, event):
        self.client = ClientType.AI
        if event["type"] == "greetings":
            await self.send_ai_setup_instructions()
        if event["type"] == "setup":
            self.game_wrapper.ai_is_initialized.set()
        if event["type"] == "move":
            # logging.info(f"AI move event: {event}\n\n")
            if event["direction"] == "up":
                for _ in range(3):
                    if self.side == "p1":
                        self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=True)
                    else:
                        self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)
            if event["direction"] == "down":
                for _ in range(3):
                    if self.side == "p1":
                        self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=False)
                    else:
                        self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)


    async def send_ai_setup_instructions(self):
        # self.logger.info(f"Sending AI setup instructions")
        ai_data = {
            "type": "setup",
            "side": "left",
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
        if event["event"] == "player2Up":
            for _ in range(5):
                self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)

        if event["event"] == "player2Down":
            for _ in range(5):
                self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)


    async def handle_front_input(self, event):
        self.client = ClientType.FRONT
        if event["type"] == "resumeOnGoal":
            # logging.info(f"resume on goal event: {event}")
            await self.game_wrapper.game.resume_on_goal()
            self.game_wrapper.has_resumed.set()
            # logging.info(f"etat du jeu: pause={self.game_wrapper.game.pause}, score p2={self.game_wrapper.game.paddle2.score}")
        elif self.game_wrapper.game.display is True:
            return
        # self.logger.info(f"Handling front input: {event}")
        if event["type"] == "greetings":
            print("greetingsssssss")
            return
        elif event["type"] == "start":
            if self.mode == "PVE":
                if self.side == "p1":
                    self.game_wrapper.player_1.is_ready = True
                elif self.side == "p2":
                    self.game_wrapper.player_2.is_ready = True
                    self.game_wrapper.start_event.set()
            elif self.mode == "PVP_keyboard":
                self.game_wrapper.start_event.set()
            elif self.mode == "PVP_LAN":
                if self.is_main is True:
                    self.game_wrapper.start_event.set()
        elif event["type"] == "keyDown":
            # logging.info(f"key down event: {event}")

            if event["event"] == "pause":
                if self.mode == "PVE" or "PVP_keyboard":
                    self.game_wrapper.game.pause = not self.game_wrapper.game.pause

            if self.side == "p1" or self.mode == "PVP_keyboard":
                self.handle_player1_input(event)


            if self.side == "p2" or self.mode == "PVP_keyboard":
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
            # if self.game_wrapper.game.RUNNING_AI is True:
            #     await self.game_wrapper.waiting_for_ai.wait()

            state_dict = json.loads(state)
            # logging.info(f"state dict: {state_dict}")
            if state_dict["gameover"] != None:
                self.game_wrapper.game.quit()
                self.game_wrapper.game_over.set()
                break
            if self.game_wrapper.has_resumed.is_set():
                self.game_wrapper.has_resumed.clear()

            try:
                for client in self.clients.values():
                    # if state_dict["type"] == 'ResumeOnGoalDone':
                    #     logging.info(f"\n\n\nsending resume on goal done {state_dict}\n\n\n")
                    await client.send(text_data=json.dumps(state_dict))
                    self.game_wrapper.waiting_for_ai.clear()
                    await asyncio.sleep(0.0000001)
            except Exception as e:
                logging.info(f"an error happened, during send")
                return
            x += 1

            await asyncio.sleep(0.00000001)

