import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .game.game_wrapper import GameWrapper
import logging
import aiohttp
from .utils import get_new_csrf_string_async
from enum import Enum
from .game.game_manager import game_manager

from urllib.parse import parse_qs
import jwt
import base64
import time

import os

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


class Errors(Enum):
    WRONG_UID = 1
    WRONG_TOKEN = 2


class PongConsumer(AsyncWebsocketConsumer):
    logger = logging.getLogger(__name__)
    game_wrapper = None
    side = None
    is_main = False
    has_resumed = False
    mode = None
    adversary = None
    error_on_connect = 0
    client = None
    sleeping = False
    message_timestamp = 0


    clients = {}

    def decode_jwt_unsafe(self, token):
        """Décode le JWT en base64 sans vérification de signature"""
        try:
            header_b64, payload_b64, _ = token.split('.')
            padding = '=' * (-len(payload_b64) % 4)
            payload_b64_padded = payload_b64 + padding
            payload_json = base64.urlsafe_b64decode(payload_b64_padded)
            return json.loads(payload_json)
        except Exception as e:
            logging.error(f"Erreur décodage base64: {str(e)}")
            return None

    async def verify_token(self):
        """
        Vérifie le token d'authentification dans les sous-protocoles WebSocket.
        Supporte les tokens de service et les JWT.
        """
        try:
            protocols = self.scope.get('subprotocols', [])
            # logging.info(f"Protocoles reçus: {protocols}")

            if not protocols:
                logging.error("Aucun sous-protocole reçu")
                self.error_on_connect = Errors.WRONG_TOKEN.value
                return False

            # Extraire le token
            token = protocols[0].replace('token_', '')
#             logging.info(f"Token extrait: {token[:10]}...")  # Log début du token

            # Vérification des tokens de service
            service_tokens = [
                os.getenv('AI_SERVICE_TOKEN', '').replace('Bearer', '').strip(),
                os.getenv('CLI_SERVICE_TOKEN', '').replace('Bearer', '').strip(),
                os.getenv('UNKNOWN_USER_SERVICE_TOKEN', '').replace('Bearer', '').strip()
            ]

            # Vérifier les tokens de service d'abord
            if token in service_tokens:
#                 logging.info("Token de service validé")
                return True

            # Pour les JWT, vérifier avec les deux méthodes
            # 1. Décodage non sécurisé
            unsafe_payload = self.decode_jwt_unsafe(token)
            if not unsafe_payload:
                logging.error("Échec du décodage base64")
                self.error_on_connect = Errors.WRONG_TOKEN.value
                return False

#             logging.info(f"Payload décodé (non sécurisé): {unsafe_payload}")

            # 2. Décodage sécurisé
            secret_key = os.getenv('JWT_SECRET_KEY')
            if not secret_key:
                logging.error("JWT_SECRET_KEY non définie")
                self.error_on_connect = Errors.WRONG_TOKEN.value
                return False

            secure_payload = jwt.decode(
                token,
                secret_key,
                algorithms=['HS256']
            )
#             logging.info(f"Payload décodé (sécurisé): {secure_payload}")

            # 3. Vérifier la correspondance
            if unsafe_payload != secure_payload:
                logging.error("Les payloads ne correspondent pas")
                self.error_on_connect = Errors.WRONG_TOKEN.value
                return False

            # Token validé, sauvegarder l'utilisateur
            self.user = secure_payload.get('username')
#             logging.info(f"JWT validé pour l'utilisateur: {self.user}")
            return True

        except jwt.InvalidTokenError as e:
            logging.error(f"Token JWT invalide: {str(e)}")
            self.error_on_connect = Errors.WRONG_TOKEN.value
            return False

        except Exception as e:
            logging.error(f"Erreur inattendue lors de la vérification: {str(e)}")
            self.error_on_connect = Errors.WRONG_TOKEN.value
            return False


    async def connect(self):

        logging.info(f"tentative de Connexion de {self.scope['user']}")

        await self._setup_csrf()
        if not await self.verify_game_uid():
            logging.info("verify game uid failed")
            await self.disconnect(4002)
            await self.close(4002)
            return
        # else:
#             logging.info("verify uid ok")
        if not await self.verify_token():
            logging.info(f"verify token is false")
            await self.disconnect(4001)
            await self.close(4001)
            return
        # else:
#             logging.info("verify token ok")

        self.game_wrapper = await game_manager.create_or_get_game(self.game_id)

        self.group_name = f"pong_{self.game_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        if self.group_name not in self.clients:
            self.clients[self.group_name] = []
        self.clients[self.group_name].append(self)
#         # logging.info(f"in connect, clients: {self.clients}\n\n size of clients[channel_name]: {len(self.clients[self.group_name])}")


        subprotocol = self.scope.get('subprotocols', [''])[0]
        await self.accept(subprotocol=subprotocol)

        await self._initialize_game_mode()
        logging.info(f"Game mode: {self.mode}")
#         logging.info(f"number of connected players: {self.game_wrapper.present_players}")

        if self.is_main is True:
            asyncio.ensure_future(self.generate_states())

        else:
            asyncio.ensure_future(self.wait_for_second_player())


    async def wait_for_second_player(self):
           try:
               timestamp = time.time()
               timeout = 10  # 10 secondes
               if self.mode == GameMode.PVP_LAN.value:
                   timeout = 3
                #    timeout = 30

               while time.time() - timestamp < timeout:
                   if self.game_wrapper.all_players_connected.is_set():
                       await self.send(json.dumps({
                           "type": "opponent_connected",
                           "opponent_connected": True
                       }))
                       await self.send(json.dumps({
                           "type": "names",
                           "p1": self.game_wrapper.player_1.name,
                           "p2": self.game_wrapper.player_2.name
                           }))
                       logging.info("Second player connected successfully")
                       return

                   await asyncio.sleep(0.1)

               # Timeout atteint
               logging.error("Timeout waiting for second player")
               await self.send(json.dumps({
                   "type": "timeout",
                   "message": "Second player failed to connect",
                   "game_mode": self.mode
               }))
               await self.disconnect(close_code=4003)
               await self.close(code=4003)
               return

           except Exception as e:
               logging.error(f"Error in wait_for_second_player: {e}")
               await self.disconnect(close_code=4003)
               await self.close(code=4003)
               return

              
    async def _setup_csrf(self):
        if 'csrf_token' not in self.scope['session']:
            try:
                csrf_token = await get_new_csrf_string_async()
                self.scope['session']['csrf_token'] = csrf_token
                await self.scope["session"].save()
            except Exception as e:
                self.logger.error(f"Error generating CSRF token: {e}")


    async def verify_game_uid(self):
        self.game_id = self.scope['url_route']['kwargs']['uid']
#         # logging.info(f"in verify game_uid: uid: {self.game_id}")
        if self.game_id is None:
            self.error_on_connect = Errors.WRONG_UID.value
            return False
        async with aiohttp.ClientSession() as session:
                verify_url = f"https://nginx:7777/game/verify/{self.game_id}/"
                headers = await self.generate_headers(self.scope['session'].get('csrf_token'))
#                 # logging.info(f"in verify game_uid: headers: {headers}")

                try:
                    async with session.get(
                            verify_url,
                            ssl=False,
                            headers=headers
                    ) as response:
                        # logging.info(f"verify uid response: {response}")
                        response_text = await response.text()
                        # logging.info(f"response.text: {response_text}")
                        if response.status not in [200]:  # On accepte 404 si le jeu est déjà nettoyé
                            logging.error(f"verify failed: {response.status}")
                            logging.error(f"Response: {response_text}")
                            return False
                        else:
#                             # logging.info(f"verify successful for game {self.game_id}")
                            return True
                except Exception as e:
                    logging.error(f"verify request error: {str(e)}")
                    return False


#*********************GAME MODE INITIALIZATION START********************************
    async def _initialize_game_mode(self):
        if self._is_shared_screen_mode():
            self._init_shared_screen()
        elif self._is_lan_mode():
            self._init_lan_mode()
        else:
            self._init_pve_mode()
        await self.send(json.dumps({"type": "greetings", "side": self.side}))


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
        self.game_wrapper.player_2.is_connected = True
        self.game_wrapper.all_players_connected.set()
        self.game_wrapper.player_2.type = PlayerType.HUMAN.value

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
        logging.info(f"ai_is_player_one: {ai_is_player_one}")

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
        logging.info(f"ai_is_player_one: {ai_is_player_one}")

        if ai_is_player_one is True:
            self.side = "p1"
            self.game_wrapper.player_1.name = "AI"
            self.game_wrapper.player_1.is_connected = True
            self.game_wrapper.player_1.is_ready = True
        else:
            self.side = "p2"
            self.game_wrapper.player_2.name = "AI"
            self.game_wrapper.player_2.is_connected = True
            self.game_wrapper.player_2.is_ready = True

        self.is_main = True
        self.game_wrapper.all_players_connected.set()

    #*********************PVE MODE INITIALIZATION END********************************

#*********************GAME MODE INITIALIZATION END********************************

#******************************DISCONNECT********************************


    async def handle_connect_error(self, error_code):
        pass

    async def disconnect(self, close_code):
        try:
#             logging.info(f"on disconnect, error: {self.error_on_connect}")
            if self.error_on_connect != 0:
                await self.handle_connect_error(self.error_on_connect)
            else:
                await self.channel_layer.group_discard("pong", self.channel_name)
                if self.game_wrapper:
                    self.game_wrapper.present_players -= 1
                    self.game_wrapper.game.pause = True
                    self.game_wrapper.game_over.set()

            await self.send_cleanup_request()

            data = self.generate_gameover_data()
            await self.send_gameover_to_remaining_client(data)
            await game_manager.remove_game(self.game_id)

        except Exception as e:
            logging.error(f"Error in disconnect: {str(e)}")
            logging.error(f"Full error details: {e.__class__.__name__}")

    async def send_cleanup_request(self):

        base_url = f"https://nginx:7777"
        if self.game_id is None:
            self.game_id = self.scop
        async with aiohttp.ClientSession() as session:
            # Cleanup request
            cleanup_url = f"{base_url}/game/cleanup/{self.game_id}/"
            headers = await self.generate_headers(self.scope['session'].get('csrf_token'))

            try:
                async with session.delete(
                        cleanup_url,
                        ssl=False,
                        headers=headers
                ) as response:
                    response_text = await response.text()
                    if response.status not in [200, 404]:  # On accepte 404 si le jeu est déjà nettoyé
                        logging.error(f"Cleanup failed: {response.status}")
                        logging.error(f"Response: {response_text}")
            except Exception as e:
                logging.error(f"Cleanup request error: {str(e)}")

    async def send_gameover_to_remaining_client(self, data):
#         logging.info(f"Sending gameover event to remaining client")
        if self.mode == "PVP_keyboard":
            return
        remaining_client = None
        for client in self.clients[self.group_name]:
            if client != self:
                remaining_client = client
                break
        if remaining_client is not None:
            await remaining_client.send(json.dumps(data))

    async def generate_headers(self, token):
        if not token:
            token = await self._setup_csrf()
        headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': token,
            "Authorization": f"{os.getenv('GAME_SERVICE_TOKEN')}"
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

    async def parse_received_event(self, event):
        if event is None:
            logging.error("0")
            return False
        if "type" not in event:
            logging.error("1")
            return False
        if event["type"] == "greetings":
            if event["sender"] not in ["front", "cli", "AI"] or len(event) < 2 or len(event) > 3:
                # check if name is valid
                logging.error("2")
                return False

        elif event["type"] == "start":
            if event["sender"] not in ["front", "cli"] or event["data"] != "init" or len(event) != 3 :
                logging.error("3")
                return False

        elif event["type"] == "keyDown":
            if event["sender"] not in ["front", "cli"]:
                logging.error("4")
                return False
            if event["event"] not in ["player1Up", "player1Down", "player2Up", "player2Down"]:
                return False
            if event["sender"] == "front":
                if len(event) != 5:
                    return False
            if event["sender"] == "cli":
                if len(event) != 3:
                    return False

        elif event["type"] == "move":
            if event["sender"] not in ["AI"] or len(event) != 3 or event["direction"] not in ["up", "down", "still"]:
                logging.error("5")
                return False

        elif event["type"] == "resumeOnGoal":
            if event["sender"] not in ["front", "cli"] or len(event) != 2:
                logging.error("6")
                return False
        return True

    async def receive(self, text_data):
        # Traiter les messages reçus du client
        current_time = time.time()
        if current_time - self.message_timestamp >= 1/80:
            self.message_timestamp = time.time()
            try:
                event = json.loads(text_data)
                # logging.info(f"Received event: {event}")
                # if await self.parse_received_event(event) is False:
                    # await self.close(4004)
                    # return
                if event["sender"] == "front" or event["sender"] == "cli":
                    await self.handle_front_input(event)
                elif event["sender"] == "AI":
                    await self.handle_ai_input(event)
                    # self.game_wrapper.waiting_for_ai.set()
            except Exception as e:
                self.logger.info(f"Error in receive: {e}")
                await self.disconnect(4004)
                await self.close(4004)
                return
        else:
            logging.info(f"SPAMMMMMMMMMMMMMMMMMMMMM")


    async def handle_ai_input(self, event):
        self.client = ClientType.AI
        if event["type"] == "greetings":
            self.game_wrapper.ai_is_initialized.set()
        if event["type"] == "move":
#             # logging.info(f"AI move event: {event}\n\n")
            if event["direction"] == "up":
                if self.side == "p1":
                    self.game_wrapper.player_1.action = 1
                else:
                    self.game_wrapper.player_2.action = 1
            elif event["direction"] == "down":
                if self.side == "p1":
                    self.game_wrapper.player_1.action = -1
                else:
                    self.game_wrapper.player_2.action = -1
            else:
                if self.side == "p1":
                    self.game_wrapper.player_1.action = 0
                else:
                    self.game_wrapper.player_2.action = 0

    async def handle_player1_input(self, event):
        if event["player"] == "p1" and self.side == "p1":
            self.game_wrapper.player_1.action = event["value"][0]

    async def handle_player2_input(self, event):
        if event["player"] == "p2" and self.side == "p2":
            self.game_wrapper.player_2.action = event["value"][1]

    
    async def get_player_name(self, event):
        if self.side == "p1":
            self.game_wrapper.player_1.name = event["name"]
        else:
            self.game_wrapper.player_2.name = event["name"]


    async def handle_front_input(self, event):
        self.client = ClientType.FRONT
        # logging.info(f"got in handle_front_input:")
        if event["type"] == "resumeOnGoal":
            if self.mode == "PVP_LAN":
                if self.side == "p1":
                    self.game_wrapper.player_1.is_ready_for_next_point = True
                elif self.side == "p2":
                    self.game_wrapper.player_2.is_ready_for_next_point = True
                if self.game_wrapper.player_1.is_ready_for_next_point == True and self.game_wrapper.player_2.is_ready_for_next_point == True:
                    self.game_wrapper.player_1.is_ready_for_next_point = False
                    self.game_wrapper.player_2.is_ready_for_next_point = False
                    await self.game_wrapper.game.resume_on_goal()
                    self.game_wrapper.has_resumed.set()
            else:
                await self.game_wrapper.game.resume_on_goal()
                self.game_wrapper.has_resumed.set()
    
        if event["type"] == "greetings":
            await self.get_player_name(event)
            return
        
        elif event["type"] == "start":
            # logging.info(f"got start from {event["sender"]}")
            if self.mode == "PVE":
                if self.side == "p1":
                    self.game_wrapper.player_1.is_ready = True
                    self.game_wrapper.start_event.set()
                elif self.side == "p2":
                    self.game_wrapper.player_2.is_ready = True
                    self.game_wrapper.start_event.set()
            elif self.mode == "PVP_keyboard":
                self.game_wrapper.start_event.set()
            elif self.mode == "PVP_LAN":
                if self.side == "p1":
                    self.game_wrapper.player_1.is_ready = True
                elif self.side == "p2":
                    self.game_wrapper.player_2.is_ready = True
                if self.game_wrapper.player_1.is_ready == True and self.game_wrapper.player_2.is_ready == True:
                    self.game_wrapper.start_event.set()

        elif event["type"] == "keyDown" and self.sleeping is False:
            # logging.info("got keydown from front")
            # logging.info(f"mode: {self.mode}")
            # logging.info(f"GameModePVP_KEYBOARD: {GameMode.PVP_KEYBOARD.value}")
            # if event["event"] == "pause":
            #     if self.mode == GameMode.PVE.value or self.mode == GameMode.PVP_KEYBOARD.value:
            #         self.game_wrapper.game.pause = not self.game_wrapper.game.pause
            if self.mode == GameMode.PVP_KEYBOARD.value:
                await self.handle_PVP_keyboard_input(event)
            else:
                if self.side == "p1":
                    await self.handle_player1_input(event)
                if self.side == "p2":
                    await self.handle_player2_input(event)

    async def handle_PVP_keyboard_input(self, event):
        # logging.info(f"got in PVP_keyboard_input")
        value = event["value"]
        # logging.info(f"value: {value}")
        # logging.info(f"value [0]: {value[0]}")
        self.game_wrapper.player_1.action = value[0]
        self.game_wrapper.player_2.action = value[1]


    async def generate_states(self):
        self.logger.info("in generate states")
        await self.game_wrapper.ai_is_initialized.wait()
        self.logger.info("in generate states, ai is initialized")
        await self.game_wrapper.start_event.wait()
        self.logger.info("state gen set")
        x = 0
        self.sleeping = True
        await asyncio.sleep(2)
        self.sleeping = False
        logging.info("starting game")
        async for state in self.game_wrapper.game.rungame():
            # logging.info(f"state: {state}")
            state_dict = json.loads(state)
            state_dict["game_mode"] = self.mode
            # logging.info(f"state dict: {state_dict}")
            if self.game_wrapper.has_resumed.is_set() is False:
                state_dict["resumeOnGoal"] = False
            else:
                state_dict["resumeOnGoal"] = True
                self.game_wrapper.has_resumed.clear()


            try:
                if state_dict['winner'] is not None:
                    winner = state_dict['winner']
                else:
                    winner = None
#                 # logging.info(f"self.clients[self.channel_name]: {self.clients[self.group_name]}")
                for client in self.clients[self.group_name]:
                    state_dict['side'] = client.side
                    if winner is not None:
                        state_dict = await self.determine_winner(state_dict, winner, client)
                    await client.send(text_data=json.dumps(state_dict))
                    # self.game_wrapper.waiting_for_ai.clear()
                    await asyncio.sleep(0.0000001)
                if state_dict["gameover"] == "Score":
                    self.game_wrapper.game.quit()
                    self.game_wrapper.game_over.set()
                    await self.handle_gameover_score_limit()
                    return
                await self.move_paddles()

            except Exception as e:
#                 logging.info(f"an error happened, during send")
                return
            x += 1

            await asyncio.sleep(0.00000001)

    async def move_paddles(self):
        asyncio.create_task(self._move_paddle_1())
        asyncio.create_task(self._move_paddle_2())

    async def _move_paddle_1(self):
        if self.game_wrapper.player_1.action == 1:
            for _ in range(5):
                await self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=True)
                await asyncio.sleep(0)
        elif self.game_wrapper.player_1.action == -1:
            for _ in range(5):
                await self.game_wrapper.game.paddle1.move(self.game_wrapper.game.height, up=False)
                await asyncio.sleep(0)

    async def _move_paddle_2(self):
        if self.game_wrapper.player_2.action == 1:
            for _ in range(5):
                await self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=True)
                await asyncio.sleep(0)
        elif self.game_wrapper.player_2.action == -1:
            for _ in range(5):
                await self.game_wrapper.game.paddle2.move(self.game_wrapper.game.height, up=False)
                await asyncio.sleep(0)

    async def determine_winner(self, state_dict, winner, client):
#         # logging.info(f"in determine winner")
        if state_dict["game_mode"] != GameMode.PVP_KEYBOARD.value:
            if winner == '1':
                if client.side == "p1":
                    state_dict["winner"] = "self"
                else:
                    state_dict["winner"] = "adversary"
            else:
                if client.side == "p2":
                    state_dict["winner"] = "self"
                else:
                    state_dict["winner"] = "adversary"
        else:
            state_dict["winner"] = winner
#         # logging.info(f"state dict return determine_winner: {state_dict}")
        return state_dict

    async def handle_gameover_score_limit(self):
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



{"type": "name", "name": "<name1>"}

