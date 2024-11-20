import logging

from .paddle import Paddle
from .ball import Ball
import math
import time
import json
import random
import asyncio


class Game:

    def __init__(self):
        self.width = 1500
        self.height = 1000
        self.white = (255, 255, 255)
        self.black = (0, 0, 0)

        # Init objects
        self.ball: Ball = Ball(self.width // 2, self.height // 2, self.height // 100, self.width, self.height)
        self.paddle1: Paddle = Paddle(self.width // 30, self.height // 2 - (self.height // 6 // 2), self.height // 150, self.height // 6, self.width, self.height)
        self.paddle2: Paddle = Paddle(self.width - self.width // 30, self.height // 2 - (self.height // 6 // 2), self.height // 150, self.height // 6, self.width, self.height)

        self.TRAININGPARTNER = False
        # self.partner_side = "right"
        self.partner_side = "left"

        self.gameOver = False

        # game related variables
        self.scoreLimit = 1
        self.run = True
        self.pause = False
        self.goal1 = False
        self.goal2 = False
        self.currentTs = time.time()
        self.NewCalculusNeeded = True
        self.pauseCoolDown = self.currentTs
        self.lastSentInfos = 0
        self.gameState = {}
        self.last_frame_time = 0
        self.state = self.getGameState()

        self.speed_multiplier = 3.5
        self.ball.max_speed *= self.speed_multiplier
        # self.paddle1.vel *= self.speed_multiplier
        # self.paddle2.vel *= self.speed_multiplier

        self.frame_rate = 60


    def handle_collisions_on_paddle(self):
        # Gestion des collisions avec les raquettes
        if self.ball.check_collision(self.paddle1):
            self.ball.updateTrajectoryP1(self.paddle1)
            self.NewCalculusNeeded = True
        if self.ball.check_collision(self.paddle2):
            self.ball.updateTrajectoryP2(self.paddle2)
            self.NewCalculusNeeded = True

    
    def handle_collisions_on_border(self):
        if self.ball.y - self.ball.radius <= 0 or self.ball.y + self.ball.radius >= self.height:
            if self.ball.y - self.ball.radius <= 0:
                self.ball.touchedWall = "top"
            else:
                self.ball.touchedWall = "bottom"
            self.ball.y_vel = -self.ball.y_vel


    def handle_scores(self):
        if self.ball.x <= 0:
            self.goal2 = True
            self.paddle2.score += 1
            self.paddle1.canMove = True
            self.paddle2.canMove = True
            self.NewCalculusNeeded = True
            self.pause = True
            self.last_frame_time = 0

        if self.ball.x >= self.width:
            self.goal1 = True
            self.paddle1.score += 1
            self.paddle1.canMove = True
            self.paddle2.canMove = True
            self.NewCalculusNeeded = True
            self.pause = True
            self.last_frame_time = 0


    async def rungame(self):
        ball = self.ball
        paddle1 = self.paddle1
        paddle2 = self.paddle2

        while self.run:
            current_time = time.time()

            if self.NewCalculusNeeded == True:
                if ball.x_vel < 0:
                    self.nextCollision = ball.calculateNextCollisionPosition(paddle1)
                else:
                    self.nextCollision = ball.calculateNextCollisionPosition(paddle2)
                if self.TRAININGPARTNER is True:
                    half_height = paddle2.height // 2
                    if self.partner_side == "right":
                        paddle2.y = self.nextCollision[1] + random.uniform(-half_height, half_height) - half_height
                    else:
                        paddle1.y = self.nextCollision[1] + random.uniform(-half_height, half_height) - half_height
                self.NewCalculusNeeded = False

            await asyncio.sleep(0.001)  

            if not self.pause:

                ball.move()
                ball.friction()
                self.handle_collisions_on_paddle()
                self.handle_collisions_on_border()
                self.handle_scores()

            # send JSON game state
            if current_time - self.last_frame_time >= 1/self.frame_rate or self.isgameover() == True:
                self.serialize()
                self.last_frame_time = current_time

                yield json.dumps(self.gameState)


    def resetPaddles(self):
        self.paddle1.y = self.height // 2
        self.paddle2.y = self.height // 2


    def getGameState(self):
        res = []

        res.append(int(self.ball.x / 75))
        res.append(int(self.ball.y / 75))
        res.append(round(math.atan2(self.ball.y_vel, self.ball.x_vel), 1))
        res.append(int((self.paddle2.y + self.paddle2.height / 2) / 75))

        return res


    def isgameover(self):
        if self.paddle1.score >= self.scoreLimit or self.paddle2.score >= self.scoreLimit or self.gameOver == True:
            self.gameOver = True
            self.pause = True
            return True
        return False


    def serialize(self):
        self.gameState["type"] = "None"
        self.gameState["playing"] = self.goal1 is False and self.goal2 is False
        if self.goal1 == True:
            self.gameState["goal"] = "1"
        elif self.goal2 == True:
            self.gameState["goal"] = "2"
        else:
            self.gameState["goal"] = "None"
        self.gameState["game"] = self.gameSerialize()
        self.gameState["ball"] = self.ball.serialize(self)
        self.gameState["paddle1"] = self.paddle1.serialize(self)
        self.gameState["paddle2"] = self.paddle2.serialize(self)
        if self.isgameover():
            self.gameState["gameover"] = "Score"
            self.gameState["winner"] = "1" if self.paddle1.score >= self.scoreLimit else "2"
        else:
            self.gameState["gameover"] = None
            self.gameState["winner"] = None
    

    def gameSerialize(self):
        res:dict = {}

        res["scoreLimit"] = self.scoreLimit
        res["pause"] = self.pause
        res['ai_data'] = self.getGameState()
        res['ai_data'].append(self.nextCollision)
        res['ai_data'].append(self.paddle2.y)

        return res


    async def resume_on_goal(self):
        self.ball.reset(self.ball.x)
        self.goal1 = False
        self.goal2 = False
        self.lastSentInfos = time.time() - 0.25
        self.pause = False
    
