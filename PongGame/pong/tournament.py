import json
import uuid
import random
import logging
from django.http import JsonResponse
from django.core.exceptions import ValidationError

class Player:
    def __init__(self, player_id=0, name="default_name", AI=True, difficulty="easy", defeated=False):
        self.player_id = player_id
        self.name = name
        self.AI = AI
        self.difficulty = difficulty
        self.defeated = defeated

    def __str__(self):
        return f"Player {self.player_id}: {self.name}, {self.AI} AI with difficulty {self.difficulty} and {self.defeated} defeated"

    def get_id(self):
        return self.player_id

    def get_name(self):
        return self.name

    def get_AI(self):
        return self.AI

    def get_difficulty(self):
        return self.difficulty

    def get_defeated(self):
        return self.defeated

    def lose(self):
        self.defeated = True

class Tournament:
    def __init__(self, uid='', players_list=[]):
        self.uid = uid
        self.players = players_list.copy()
        self.current_matches = []
        if len(self.players) < 2:
            raise ValueError("You need at least 2 players to start a tournament")
        random.shuffle(self.players)

    def create_matches(self):
        available_players = [player for player in self.players if not player.get_defeated()]
        if len(available_players) < 2:
            return False
        self.current_matches = []
        while len(available_players) >= 2:
            player1 = available_players.pop(0)
            player2 = available_players.pop(0)
            self.current_matches.append((player1, player2))
        return True

    def set_match_results(self, loser_id):
        try:
            player = next(player for player in self.players if player.get_id() == loser_id)
            player.defeated = True
            self.current_matches.pop(0)
        except StopIteration:
            logging.info(f"No player found with id {loser_id}")

    def get_next_match(self):
        if not self.current_matches:
            return None
        return [player.get_id() for player in self.current_matches[0] if player]

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


import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


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
        if request.method == 'GET':
            # GET logic remains the same
            ...

        elif request.method == 'POST':
            if not request.body:
                return JsonResponse({'error': 'Empty request body'}, status=400)

            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")
                return JsonResponse({'error': 'Invalid JSON format'}, status=400)

            logging.info(f"POST Data: {data}")
            players_data = data.get('players', [])

            if not players_data or len(players_data) < 2:
                return JsonResponse({'error': 'At least 2 players are required'}, status=400)

            players_list = []
            for player_data in players_data:
                logging.info(f"Player data: {player_data}")
                try:
                    validate_player_data(player_data)
                    players_list.append(Player(
                        len(players_list),
                        player_data['name'],
                        player_data['ai'],
                        player_data['difficulty']
                    ))
                except ValidationError as e:
                    return JsonResponse({'error': str(e)}, status=400)

            tournament_id = create_tournament(players_list)
            tournament = next((t for t in tournaments_list if t.uid == tournament_id), None)
            tournament.create_matches()
            return JsonResponse({'tournament_id': tournament_id, 'matches': [
                [player.get_id() for player in match] for match in tournament.current_matches
            ]})

        else:
            return JsonResponse({'error': 'Unauthorized method'}, status=405)

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)