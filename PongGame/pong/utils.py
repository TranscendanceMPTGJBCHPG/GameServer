from functools import partial
from asgiref.sync import sync_to_async
from django.middleware.csrf import _get_new_csrf_string

# Créer une version asynchrone de _get_new_csrf_string
get_new_csrf_string_async = sync_to_async(
    partial(_get_new_csrf_string),
    thread_sensitive=False
)