import json
import uuid
import random
import logging
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

class Tournament:
    def __init__(self, uid='', players_list=[]):
        self.uid = uid
        self.players = players_list.copy()
        self.current_matches = []
        if len(self.players) < 2:
            raise ValueError("You need at least 2 players to start a tournament")
        random.shuffle(self.players)

    def create_matches(self):
        available_players = [player for player in self.players if not player['defeated']]
        logging.info(f"Available players: {available_players}")
        if len(available_players) < 2:
            return False
        self.current_matches = []
        while len(available_players) >= 2:
            player1 = available_players.pop(0)
            player2 = available_players.pop(0)
            self.current_matches.append([player1, player2])
        return True

    def set_match_results(self, loser_id):
        try:
            player = next(player for player in self.players if player['id'] == loser_id)
            player['defeated'] = True
            self.current_matches.pop(0)
        except StopIteration:
            logging.info(f"No player found with id {loser_id}")

    def get_next_match(self):
        if not self.current_matches:
            return None
        return [player['id'] for player in self.current_matches[0] if player]

# Map of all the tournaments and their uids
tournaments_list = []

def create_tournament(players):
    """
    Create a new tournament with the given players.

    :param players: Players objects list
    :return: new tournament uuid
    """
    uid = str(uuid.uuid4())
    tournament = Tournament(uid, players)
    tournaments_list.append(tournament)
    return uid

def validate_player_data(player_data):
    """
    Validate the player data.

    :param player_data: Dictionary containing player data
    :raises ValidationError: If the player data is invalid
    """
    required_fields = ['name', 'ai', 'difficulty']
    if not all(field in player_data for field in required_fields):
        raise ValidationError("Every player must have a name, AI and difficulty")

    if not isinstance(player_data['name'], str):
        raise ValidationError("Player name must be a string")

    if not isinstance(player_data['ai'], bool):
        raise ValidationError("AI field must be a boolean")

    if player_data['difficulty'] not in ['off', 'easy', 'medium', 'hard']:
        raise ValidationError("Difficulty must be 'off', 'easy', 'medium' or 'hard'")

@csrf_exempt
def tournament_maker(request):
    """
    Take care of the tournament creation and match results.

    :param request: HttpRequest object
    :return: JsonResponse
    """
    logging.info(f"Request method: {request.method}")
    logging.info(f"Request headers: {request.headers}")
    logging.info(f"Request body: {request.body}")

    try:
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
        
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        if data.get('type') is None:
            return JsonResponse({'error': 'Type field is required'}, status=400)

        elif data.get('type') == 'continue':
            uid = data.get('uid')
            if not uid:
                return JsonResponse({'error': 'UID is required'}, status=400)
            loser_id = data.get('loser_id')
            if not loser_id:
                return JsonResponse({'error': 'loser_id is required'}, status=400)

            tournament = next((t for t in tournaments_list if t.get_uid() == uid), None)
            if not tournament:
                return JsonResponse({'error': 'Tournament not found'}, status=404)

            tournament.set_match_results(loser_id)
            next_match = tournament.get_next_match()

            if not next_match:
                matches = tournament.create_matches()
                if not matches:
                    winner_id = next(player for player in tournament.players if not player['defeated'])['id']()
                    tournaments_list.remove(tournament)
                    return JsonResponse({'winner_id': winner_id})
            return JsonResponse({'next_match': next_match, 'uid': uid})

        elif data.get('type') == 'start':
            logging.info(f"POST Data: {data}")
            players_data = data.get('players', [])

            if not players_data or len(players_data) < 2:
                return JsonResponse({'error': 'At least 2 players are required'}, status=400)

            players_list = []
            for player_data in players_data:
                logging.info(f"Player data: {player_data}")
                try:
                    validate_player_data(player_data)
                    players_list.append({
                        'id' : len(players_list),
                        'name' : player_data['name'],
                        'ai' : player_data['ai'],
                        'difficulty' : player_data['difficulty'],
                        'defeated' : False
                    })
                except ValidationError as e:
                    return JsonResponse({'error': str(e)}, status=400)

            tournament_id = create_tournament(players_list)
            tournament = next((t for t in tournaments_list if t.uid == tournament_id), None)
            tournament.create_matches()
            return JsonResponse({'tournament_id': tournament_id, 'matches': [
                [player['id'] for player in match] for match in tournament.current_matches
            ]})

        else:
            return JsonResponse({'error': 'Unauthorized method'}, status=405)

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)