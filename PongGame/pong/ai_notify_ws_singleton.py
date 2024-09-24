import asyncio
import json
import websockets
import logging

class WebSocketSingleton:
    _instance = None

    uri = "http://nginx:81/ws/notify_ai/"
    socket = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebSocketSingleton, cls).__new__(cls)
            cls._instance.logger = logging.getLogger(__name__)
            if not asyncio.get_event_loop().is_running():
                asyncio.run(cls._instance._initialize_connection())
            else:
                asyncio.create_task(cls._instance._initialize_connection())
            return cls._instance

    async def _initialize_connection(self):
        """Initialise la connexion WebSocket à la création du singleton."""
        try:
            self.logger.info(f"Connecting to WebSocket server: {self.uri}")
            self.socket = await websockets.connect(self.uri)
            self.logger.info(f"Connected to WebSocket server: {self.uri}")
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket server: {e}")

# Accès unique à l'instance
    @classmethod
    def get_ai_websocket_singleton(cls):
        if cls._instance is None:
            cls()
        return cls._instance
