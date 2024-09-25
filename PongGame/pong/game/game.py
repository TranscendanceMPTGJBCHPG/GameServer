
from .paddle import Paddle
from .ball import Ball
import math
import time
import json
import pygame
import random
from .pong_ql import QL_AI
import asyncio


class Game:

    def __init__(self):
        self.width = 1500
        self.height = 1000
        self.white = (255, 255, 255)
        self.black = (0, 0, 0)

        # CLI and rendering options
        self.display = False
        self.CLI_controls = False
        if self.display == True or self.CLI_controls == True:
            pygame.init()
            if self.display == True:
                self.win = pygame.display.set_mode((self.width, self.height))
                pygame.display.set_caption("Pong")

        # Init objects
        self.ball: Ball = Ball(self.width // 2, self.height // 2, self.height // 100, self.width, self.height, self.display)
        self.paddle1: Paddle = Paddle(self.width // 30, self.height // 2 - (self.height // 6), self.height // 150, self.height // 6, self.width, self.height)
        self.paddle2: Paddle = Paddle(self.width - self.width // 30, self.height // 2 - (self.height // 6), self.height // 150, self.height // 6, self.width, self.height)
        # self.ai = QL_AI(self.width, self.height, self.paddle2.width, self.paddle2.height)
        # self.state = self.getGameState()

        # AI settings
        self.RUNNING_AI = True
        self.DIFFICULTY = 3
        self.SAVING = True
        self.TRAINING = True
        self.TRAININGPARTNER = False
        self.LOADING = True
        self.testing = True
        self.lastDump = 0
        # self.ai.training = self.TRAINING
        self.gameOver = False

        # self.init_ai()

        # game related variables
        self.scoreLimit = 100
        self.run = True
        self.pause = False
        self.goal1 = False
        self.goal2 = False
        self.currentTs = time.time()
        self.NewCalculusNeeded = True
        self.pauseCoolDown = self.currentTs
        self.lastSentInfos = 0
        self.gameState = {}
        self.are_args_set = False
        self.last_frame_time = 0
        self.state = self.getGameState()

        self.speed_multiplier = 2
        self.ball.max_speed *= self.speed_multiplier
        self.paddle1.vel *= self.speed_multiplier
        self.paddle2.vel *= self.speed_multiplier

        self.p1_successive_inputs = []
        self.p2_successive_inputs = []


    def init_display(self):
        self.display = True
        self.CLI_controls = True
        pygame.init()
        self.win = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pong")


    def handleArguments(self, event):
        print(event)
        # handling the argumemnts ->31504 if OK ->
        self.are_args_set = True


    def handlePauseResetQuit(self):
        for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                    self.gameOver = True
                    self.run = False
        self.keys = pygame.key.get_pressed()
        keys = self.keys
        if keys[pygame.K_r]:
            self.ball.reset(1)
        if keys[pygame.K_ESCAPE]:
            self.gameOver = True
        if keys[pygame.K_SPACE]:
            if self.gameState["goal"] == "None":
                self.currentTs = time.time()
                if self.currentTs - 0.2 > self.pauseCoolDown:
                    self.pauseCoolDown = self.currentTs
                    if self.pause == True:
                        self.pause = False
                    else:
                        self.pause = True
    

    def handlePlayer1Inputs(self):
        keys = self.keys

        if keys[pygame.K_w] and self.paddle1.canMove == True:
            self.paddle1.move(self.height, up=True)
        if keys[pygame.K_s] and self.paddle1.canMove == True:
            self.paddle1.move(self.height, up=False)

    
    def handlePlayer2Inputs(self):
        keys = self.keys

        if keys[pygame.K_UP] and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=True)
        if keys[pygame.K_DOWN] and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=False)


    def save_qtable(self):
        ai = self.ai

        if self.testing == True:
            ai.save('testing')
        if self.DIFFICULTY == 3:
            ai.save('hard')
        elif self.DIFFICULTY == 2:
            ai.save('medium')
        elif self.DIFFICULTY == 1:
            ai.save('easy')


    def handle_inputs(self):
        if self.TRAININGPARTNER == False:
            if self.display == True:
                self.handlePlayer1Inputs()
        else:
            self.paddle1.y = self.nextCollision[1] - self.paddle1.height // 2
        if not self.RUNNING_AI:
            if self.CLI_controls == True:
                self.handlePlayer2Inputs()
        # else:
        #     self.interactWithAI()


    def handle_collisions_on_paddle(self):
        # Gestion des collisions avec les raquettes
        if self.ball.check_collision(self.paddle1):
            self.ball.updateTrajectoryP1(self.paddle1)
            self.NewCalculusNeeded = True
        if self.ball.check_collision(self.paddle2):
            # print(f"onpaddle2, px: {paddle2.x}, py: [{paddle2.y}, {paddle2.y + paddle2.height}]\n")
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
            # self.state = self.getGameState()
            self.pause = True
            # self.ball.reset(self.ball.x)
            self.last_frame_time = 0

        if self.ball.x >= self.width:
            self.goal1 = True
            self.paddle1.score += 1
            self.paddle1.canMove = True
            self.paddle2.canMove = True
            self.NewCalculusNeeded = True
            # self.state = self.getGameState()
            self.pause = True
            # self.ball.reset(self.ball.x)
            self.last_frame_time = 0


    async def rungame(self):
        ball = self.ball
        paddle1 = self.paddle1
        paddle2 = self.paddle2

        while self.run:
            # print("is running")
            current_time = time.time()

            if self.NewCalculusNeeded == True:
                if ball.x_vel < 0:
                    self.nextCollision = ball.calculateNextCollisionPosition(paddle1)
                else:
                    self.nextCollision = ball.calculateNextCollisionPosition(paddle2)
                if self.TRAININGPARTNER == True:
                    half_height = paddle2.height // 2
                    paddle1.y = self.nextCollision[1] + random.uniform(-half_height, half_height) - half_height
                self.NewCalculusNeeded = False

            pygame.time.delay(1)

            if self.CLI_controls == True:
                self.handlePauseResetQuit()

            if not self.pause:

                self.handle_inputs()
                ball.move()
                ball.friction()
                self.handle_collisions_on_paddle()
                self.handle_collisions_on_border()
                self.handle_scores()

                if self.display == True:
                    self.redraw_window()

            # send JSON game state
            if current_time - self.last_frame_time >= 1/60 or self.isgameover() == True:
                self.serialize()
                self.last_frame_time = current_time
                # print(f"game state: {self.gameState}")
                yield json.dumps(self.gameState)


    def quit(self):
        if self.SAVING == True:
            self.save_qtable()
        if self.display == True or self.CLI_controls:
            pygame.quit()


    def redraw_window(self):
        self.win.fill(self.black)
        self.paddle1.draw(self.win)
        self.paddle2.draw(self.win)
        self.ball.draw(self.win)
        pygame.display.update()


    def resetPaddles(self):
        self.paddle1.y = self.height // 2
        self.paddle2.y = self.height // 2


    def init_ai(self):
        if self.LOADING == True:
            self.ai.epsilon = 0
            # print("LOADING")
            if self.testing == True:
                self.ai.load('AI_testing.pkl')
            elif self.DIFFICULTY == 3:
                self.ai.load("AI_hard.pkl")
                print("hard AI loaded")
            elif self.DIFFICULTY == 2:
                self.ai.load("AI_medium.pkl")
            elif self.DIFFICULTY == 1:
                self.ai.load("AI_easy.pkl")


    def getGameState(self):
        res = []

        # res.append(int(self.ball.x / 50))
        # res.append(int(self.ball.y / 50))
        # res.append(int(math.atan2(self.ball.y_vel, self.ball.x_vel)))
        # res.append(int((self.paddle2.y + self.paddle2.height / 2) / 50))
        res.append(int(self.ball.x / 75))
        res.append(int(self.ball.y / 75))
        res.append(round(math.atan2(self.ball.y_vel, self.ball.x_vel), 1))
        res.append(int((self.paddle2.y + self.paddle2.height / 2) / 75))
        # res.append(self.ball.calculateNextCollisionPosition(self.paddle2))
        # print(f"return getGamestate: {res}")

        return res


    def interactWithAI(self):
        newTS = time.time()
        if self.TRAINING == False:
            if (newTS - self.lastSentInfos >= 1):
                self.lastSentInfos = newTS
                self.state = self.getGameState()
        else:
            self.state = self.getGameState()
        res = self.ai.getAction(repr(self.state))

        prevY = self.paddle2.y
        # to nerf the AI:
#         if random.choice([1, 2, 3, 4, 5]) != 1:
#             res = 0
        if res == 0:
            pass
        if res == 1 and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=True)
        if res == 2 and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=False)
        nextState = self.getGameState()
        reward = self.ai.getReward(self.nextCollision, res, prevY, self.DIFFICULTY)
        self.ai.upadateQTable(repr(self.state), res, reward, repr(nextState))
        self.state[3] = (int((self.paddle2.y + self.paddle2.height / 2) / 50))


    def isgameover(self):
        if self.TRAINING == False:
            if self.paddle1.score >= self.scoreLimit or self.paddle2.score >= self.scoreLimit:
                self.gameOver = True
                return True
        if self.gameOver == True:
            return True
        return False


    def serialize(self):
        self.gameState["type"] = "None"
        if self.goal1 == True:
            self.gameState["goal"] = "1"
            # self.goal1 = False
        elif self.goal2 == True:
            self.gameState["goal"] = "2"
            # self.goal2 = False
        else:
            self.gameState["goal"] = "None"
        # if self.pause == False:
        self.gameState["game"] = self.gameSerialize()
        self.gameState["ball"] = self.ball.serialize(self)
        self.gameState["paddle1"] = self.paddle1.serialize(self)
        self.gameState["paddle2"] = self.paddle2.serialize(self)
        if self.isgameover():
            self.gameState["gameover"] = "Score"
        else:
            self.gameState["gameover"] = None
    

    def gameSerialize(self):
        res:dict = {}
        res["scoreLimit"] = self.scoreLimit
        res["pause"] = self.pause
        res['ai_data'] = self.getGameState()
        res['ai_data'].append(self.nextCollision)
        res['ai_data'].append(self.paddle2.y)
        return res


    async def resume_on_goal(self):
        # print("resume")
        self.ball.reset(self.ball.x)
        self.goal1 = False
        self.goal2 = False
        # if self.RUNNING_AI is True:
        #     self.paddle2.reset_position()
        # self.state = self.getGameState()
        self.lastSentInfos = time.time() - 0.25
        self.pause = False
    
