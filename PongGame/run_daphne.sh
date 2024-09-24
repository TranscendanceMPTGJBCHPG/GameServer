#!/bin/bash

# Lancer le premier serveur Daphne en arrière-plan et capturer son PID
daphne -p 8001 PongGame.asgi:application &
DAPHNE_PID_1=$!


# Lancer le second serveur Daphne en arrière-plan et capturer son PID
#daphne -p 7777 PongGame.asgi:application &
#DAPHNE_PID_2=$!

# Fonction pour arrêter proprement les serveurs Daphne
function stop_servers {
    echo "Arrêt des serveurs Daphne..."
    kill  $DAPHNE_PID_1
#    kill  $DAPHNE_PID_2
    wait $DAPHNE_PID_1
#    wait $DAPHNE_PID_2
    echo "Serveurs arrêtés proprement."
}

# Piège pour capturer l'arrêt du script (Ctrl+C ou autre signal)
trap stop_servers SIGINT

# Garder le script en cours d'exécution jusqu'à l'arrêt des serveurs
wait $DAPHNE_PID_1
#wait $DAPHNE_PID_2
