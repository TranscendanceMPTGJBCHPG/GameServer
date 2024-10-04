from django.shortcuts import render
import os

#recuper key from environment



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


def handle_PVE_mode(difficulty):
    logging.info(f"handle_PVE_mode, difficulty: {difficulty}")
    uid = str(uuid.uuid4())
    uid = difficulty[0] + uid[1:]
    while uid in uids:
        uid = str(uuid.uuid4())
        uid = difficulty[0] + uid[1:]
    uids[uid] = {}
    uids[uid]['mode'] = difficulty
    uids[uid]['status'] = 'waiting_ai'
    return uid


def handle_PVP_mode(option):
    #pvp LAN
    if option == '1':
        for key, value in uids.items():
            if value['status'] == 'waiting_player':
                value['status'] = 'ready'
                return JsonResponse({'uid': key})
        uid = str(uuid.uuid4())
        while uid in uids:
            uid = str(uuid.uuid4())
        uids[uid] = {}
        uids[uid]['mode'] = option
        uids[uid]['status'] = 'waiting_player'
        response = uid
        return response
    else:
        uid = str(uuid.uuid4())
        #put k at the beginning and end of the uid to identify it as a PVP mode
        uid = 'k' + uid[1:]
        uid = uid[:-1] + 'k'
        while uid in uids:
            uid = str(uuid.uuid4())
            uid = 'k' + uid[1:]
            uid = uid[:-1] + 'k'
        uids[uid] = {}
        uids[uid]['mode'] = option
        uids[uid]['status'] = 'ready'
        logger.info(f"PVP mode, uid: {uids[uid]}, returning")
        return uid

def handle_AI_mode():
    uid = ai_get_uid()
    if uid is not None:
        logger.info(f"AI mode, uid: {uids[uid]}")
        uids[uid]['status'] = 'ready'
        return uid
    else:
        logger.info(f"AI mode, no uid found")
        return ('error')


async def generate_uid(request):
    logging.info(f"generate_uid, request: {request}")
    uid = None
    if request.method == 'GET':
        try:
            mode = request.GET.get('mode')
            if mode == 'PVE':
                uid = handle_PVE_mode(request.GET.get('option'))
            elif mode == 'PVP':
                uid = handle_PVP_mode(request.GET.get('option'))
            elif mode == 'AI':
                uid = handle_AI_mode()
        except Exception as e:
            logger.error(f"Error in generate_uid: {e}")
        logger.info(f"before last return: generate_uid, uid: {uid}")
        return JsonResponse({'uid': uid})

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
