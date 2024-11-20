from enum import Enum

class GameStatus(Enum):
    WAITING = "waiting"        # En attente du second joueur
    STARTING = "starting"      # Tous les joueurs sont là, initialisation en cours
    IN_PROGRESS = "in_progress"  # Partie en cours
    PAUSED = "paused"         # Partie en pause
    FINISHED = "finished"      # Partie terminée
    CANCELLED = "cancelled"    # Partie annulée (déconnexion, timeout, etc.)

    def __str__(self):
        return self.value