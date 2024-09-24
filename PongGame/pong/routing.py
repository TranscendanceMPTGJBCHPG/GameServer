from django.urls import path, re_path
# from .consumers import PongConsumer, AIConsumer
from . import consumers

# websocket_urlpatterns = [
#     path('ws/pong/', consumers.PongConsumer.as_asgi()),
#     path('ws/ai/', consumers.AIConsumer.as_asgi()),
# ]


websocket_urlpatterns = [
    # re_path(r'ws/pong/(?P<game_id>\w+)/$', consumers.PongConsumer.as_asgi()),
    re_path(r'^ws/pong/(?P<uid>[a-zA-Z0-9\-]+)/$', consumers.PongConsumer.as_asgi()),
    # path('ws/notify_ai/', consumers.AIConsumer.as_asgi()),
]

# websocket_urlpatterns = [
#     re_path(r'ws/pong/$', consumers.PongConsumer.as_asgi()),
#     re_path(r'ws/ai/$', consumers.AIConsumer.as_asgi()),
# ]