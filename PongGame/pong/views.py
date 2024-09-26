from django.shortcuts import render

import uuid
from django.http import JsonResponse
import logging
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import asyncio
import websockets

#keep track of the existing uid in a dictionnary, with uid as key and a string as value
uids = {}
logger = logging.getLogger(__name__)

def get_public_uid():
    for key, value in uids.items():
        if value == 'public':
            return key
    return None

async def generate_uid(request):
    if request.method == 'GET':
        try:
            # logger.info(f"generate_uid, {request}")
            #get the mode in the request url
            mode = request.GET.get('mode')
            # logger.info(f"mode: {mode}")
            if mode == 'PVE':
                # logger.info("PVE mode")
                difficulty = request.GET.get('difficulty')
                # logger.info(f"difficulty: {difficulty}")
                uid = str(uuid.uuid4())
                uid = difficulty[0] + uid[1:]
                while uid in uids:
                    uid = str(uuid.uuid4())
                    uid = difficulty[0] + uid[1:]
                uids[uid] = {}
                uids[uid]['mode'] = mode
                # logger.info(f"after adding mode: {uids}")
                #add a new value to uids[uid] to indicate if the game is public or private
                uids[uid]['status'] = 'waiting_ai'
                # logger.info(f"Generated uid: {uid}")
                response = JsonResponse({'uid': uid})
                #return response in JSON format
                return response
            elif mode == 'AI':
                # logger.info("AI mode")
                uid = ai_get_uid()
                if uid is not None:
                    # logger.info(f"AI mode, uid: {uids[uid]}")
                    uids[uid]['status'] = 'ready'
                    return JsonResponse({'uid': uid})
                else:
                     return JsonResponse({'error': 'no game available'})
        except Exception as e:
            logger.error(f"Error in generate_uid: {e}")

    elif request.method == 'POST':
        mode = request.GET.get('mode')
        if mode == 'gameover':
            return(handle_gameover(request))
               

def handle_gameover(request):
    try:
        logger.info(f"in handle gameover, request: {request}")
        uid = request.GET.get('uid')
        logger.info(f"handle_gameover, uid: {uid}")
        if uid in uids:
            logger.info(f"handle_gameover, uid found: {uid}")
            del uids[uid]
            logger.info(f"handle_gameover, after deleting uid: {uids}")
        return(JsonResponse({'ok': 'ok'}))
    except Exception as e:
        logger.error(f"Error in handle_gameover: {e}")
        return(JsonResponse({'nok': 'nok'}))

def ai_get_uid():
    #check in uids if one of the game is waiting for an AI
    for key, value in uids.items():
        if value['status'] == 'waiting_ai':
            # logger.info(f"AI_get_uid, key: {key}")
            return key
    return None
