import math
import pygame
import time
import copy
import random
from .paddle import Paddle
import logging

white = (255, 255, 255)
black = (0, 0, 0)

class Ball:
    
    def __init__(self, x, y, radius, win_width, win_height, display):
        self.lastTouch = 0
        self.touchedWall = None
        self.x = x
        self.y = y
        self.win_width = win_width
        self.win_height = win_height
        self.display = display
        if self.display is True:
            self.max_speed = self.win_width * self.win_height // 350000
        else:
            self.max_speed = self.win_width * self.win_height // 1000000
        self.radius = radius
        self.x_vel = self.max_speed / 3.5
        self.y_vel = 0
        self.frictionTimestamp = time.time()
        # self.x = win_width - 100


    def draw(self, win):
        pygame.draw.circle(win, white, (self.x, self.y), self.radius)


    def move(self):
        self.x += self.x_vel
        self.y += self.y_vel


    def reset(self, x, display):
        self.x = self.win_width // 2
        self.y = self.win_height // 2
        if x > 0:
            goalAngle = random.uniform(-30, 30)
        else:
            rng = random.choice((1, 2))
            if rng == 1:
                goalAngle = random.uniform(-150, -180)
            else:
                goalAngle = random.uniform(150, 180)
        angle_rad = math.radians(goalAngle)
        if display is True:
            self.max_speed = self.win_width * self.win_height // 350000
        else:
            self.max_speed = self.win_width * self.win_height // 700000
            # self.max_speed = self.win_width * self.win_height // 350000
        speed = self.max_speed / 2
        self.x_vel = speed * math.cos(angle_rad)
        self.y_vel = speed * math.sin(angle_rad)

    def update_speed_on_CLI(self, display):

        current_speed = math.sqrt(self.x_vel ** 2 + self.y_vel ** 2)
        logging.info(f"display: {display}")
        logging.info(f"current_speed: {current_speed}")
        proportion = current_speed / self.max_speed
        logging.info(f"proportion: {proportion}")

        if display is True:
            self.max_speed = self.win_width * self.win_height // 350000
        else:
            self.max_speed = self.win_width * self.win_height // 1000000
            #update speed but keep the proportion compared to previous max_speed


            self.x_vel = self.x_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed * proportion
            self.y_vel = self.y_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed * proportion

        new_speed = math.sqrt(self.x_vel ** 2 + self.y_vel ** 2)
        logging.info(f"new_speed: {new_speed}")


    # matrix
    #         -90
    #          |
    #  -180 <-----> 0
    #          |
    #          90

    def updateTrajectoryP2(self, paddle):

        currentTs = time.time()

        if paddle.lastTouch > currentTs - 0.5:
            return
        
        paddle.lastTouch = currentTs
        currentSpeed = math.sqrt(self.x_vel ** 2 + self.y_vel ** 2)
        relativeImpactPoint = (self.y - paddle.y) / paddle.height
        currentAngle = math.degrees(math.atan2(self.y_vel, self.x_vel))
        naturalAngle = math.degrees(math.atan2(self.y_vel, -self.x_vel))

        if (relativeImpactPoint > 1):
            relativeImpactPoint = 1
        if (relativeImpactPoint < 0):
            relativeImpactPoint = 0

        arete = False
        goalAngle: float

        if self.x + self.radius / 2 > paddle.x + paddle.width:
            arete = True
            paddle.canMove = False
            if self.y > paddle.y:
                goalAngle = 80
            else:
                goalAngle = -80


        elif currentAngle < 15 and currentAngle > -15:
            goalAngle = naturalAngle - (35 * (relativeImpactPoint - 0.5))

        elif (currentAngle < 0):
            # la balle monte
            if relativeImpactPoint < 0.5:
                # tape haut -> angle va tendre vers -90 degres
                goalAngle = naturalAngle + (35 * (1 - relativeImpactPoint))
                if (goalAngle > -130):
                    goalAngle = -130

            else:
                # tape bas -> angle va tendre vers -180
                goalAngle = naturalAngle - (((180 - abs(naturalAngle)) * relativeImpactPoint))
        else:
            # balle descend
            if relativeImpactPoint < 0.5:
                # tape haut -> angle va tendre vers 180 degres
                goalAngle = naturalAngle + ((180 - abs(naturalAngle)) * (1 - relativeImpactPoint))

            else:
                # tape bas -> angle va tendre vers 90
                goalAngle = naturalAngle - (35 * (relativeImpactPoint - 0.5))
                if (goalAngle < 130):
                    goalAngle = 130

        self.lastTouch = "2"

        self.x_vel = currentSpeed * (1 + (1 * (1-(currentSpeed / self.max_speed)))) * math.cos(math.radians(goalAngle))
        self.y_vel = currentSpeed * (1 + (1 * (1 - (currentSpeed / self.max_speed)))) * math.sin(math.radians(goalAngle))
        if (arete):
            self.x_vel *= 2
            self.y_vel *= 2
        if (abs(goalAngle) > 180 - 20 and math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) < self.max_speed):
            self.x_vel *= 1.2
            self.y_vel *= 1.2
        if math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) > self.max_speed:
            self.x_vel = self.x_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed
            self.y_vel = self.y_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed


    def updateTrajectoryP1(self, paddle):

        currentTs = time.time()

        if paddle.lastTouch > currentTs - 0.5:
            return
        
        paddle.lastTouch = currentTs
        currentSpeed = math.sqrt(self.x_vel ** 2 + self.y_vel ** 2)
        relativeImpactPoint = (self.y - paddle.y) / paddle.height
        currentAngle = math.degrees(math.atan2(self.y_vel, self.x_vel))
        naturalAngle = math.degrees(math.atan2(self.y_vel, -self.x_vel))

        if (relativeImpactPoint > 1):
            relativeImpactPoint = 1
        if (relativeImpactPoint < 0):
            relativeImpactPoint = 0
        goalAngle: float
        arete = False
      
        if self.x - self.radius / 2 < paddle.x + paddle.width:
            arete = True
            paddle.canMove = False
            if self.y > paddle.y:
                goalAngle = 100
            else:
                goalAngle = -100


        elif currentAngle > 165 or currentAngle < -165:
            goalAngle = naturalAngle + (40 * (relativeImpactPoint - 0.5))

        elif (currentAngle < 0):
            # la balle monte
            if relativeImpactPoint < 0.5:
                # tape haut -> angle va tendre vers -90 degres
                goalAngle = naturalAngle - (35 * (1 - relativeImpactPoint))
                if goalAngle < -50:
                    goalAngle = -50
                self.x += 10

            else:
                # tape bas -> angle va tendre vers -180
                goalAngle = naturalAngle + (((abs(naturalAngle)) * relativeImpactPoint))
        else:
            # balle descend
            if relativeImpactPoint < 0.5:
                # tape haut -> angle va tendre vers 180 degres
                goalAngle = naturalAngle - ((abs(naturalAngle)) * (1 - relativeImpactPoint))
            else:
                # tape bas -> angle va tendre vers 90
                goalAngle = naturalAngle
                goalAngle = (naturalAngle + (35 * relativeImpactPoint))
                self.x += 10
                if goalAngle > 50:
                    goalAngle = 50
                    self.x += 2

        self.lastTouch = "1"

        self.x_vel = currentSpeed * (1 + (1* (1-(currentSpeed / self.max_speed)))) * math.cos(math.radians(goalAngle))
        self.y_vel = currentSpeed * (1 + (1 * (1 - (currentSpeed / self.max_speed)))) * math.sin(math.radians(goalAngle))
        if (arete):
            self.x_vel *= 2
            self.y_vel *= 2
        if (abs(goalAngle) > 180 - 20 and math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) < self.max_speed):
            self.x_vel *= 1.2
            self.y_vel *= 1.2
        if math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) > self.max_speed:
            self.x_vel = self.x_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed
            self.y_vel = self.y_vel / math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) * self.max_speed
                

    def check_collision(self, paddle:Paddle):
        if (self.x - self.radius < paddle.x + paddle.width and
            self.x + self.radius > paddle.x and
            self.y - self.radius < paddle.y + paddle.height and
            self.y + self.radius > paddle.y):
            return True
        return False


    def calculateNextCollisionPosition(self, paddle:Paddle):
        res = []
        if paddle.x < self.win_width // 2:
            res.append(-1)
        else:
            res.append(1)
        tempBall = copy.deepcopy(self)
        tempPaddle = copy.deepcopy(paddle)

        # Déplacement de la balle jusqu'à ce qu'elle atteigne la position x = paddle2_x
        while tempBall.check_collision(tempPaddle) == False and tempBall.x > 0 and tempBall.x < self.win_width:
            # Calcule la nouvelle position de la balle en ajoutant la vitesse de la balle à sa position actuelle
            tempBall.x = tempBall.x + tempBall.x_vel
            tempBall.y = tempBall.y + tempBall.y_vel
            tempPaddle.y = tempBall.y

            # Vérifie si la nouvelle position de la balle dépasse les bords du terrain
            if tempBall.y - tempBall.radius <= 0 or tempBall.y + tempBall.radius >= self.win_height:
                tempBall.y_vel = -tempBall.y_vel

        tempBall.y += random.uniform(-(paddle.height * 0.9 // 2), (paddle.height * 0.9 // 2))
        res.append(tempBall.y)
        return res # Retourne la position y correspondant


    def serialize(self, game):
        res:dict = {}
        res["x"] = self.x / game.width
        res["y"] = self.y / game.height
        res["speed"] = math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) / self.max_speed
        res["lastTouch"] = self.lastTouch
        res["touchedWall"] = self.touchedWall
        res["rounded_angle"] = round((math.atan2(self.y_vel, self.x_vel)), 2)
        # logging.info(f"rad by ball: {math.atan2(self.y_vel, self.x_vel)}")
        # logging.info(f"rounded_angle by game: {res['rounded_angle']}")
        res["rounded_angle"] = round(math.atan2(self.y_vel, self.x_vel) * 2) / 2
        res["next_collision"] = self.calculateNextCollisionPosition(game.paddle2)
        self.touchedWall = None

        return res
    def friction(self):
        if time.time() - self.frictionTimestamp > 0.4 and math.sqrt(self.x_vel ** 2 + self.y_vel ** 2) > self.max_speed / 5:
            self.frictionTimestamp = time.time()
            self.x_vel = self.x_vel * 0.93
            self.y_vel = self.y_vel * 0.93


