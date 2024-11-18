import logging

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
        self.paddle1: Paddle = Paddle(self.width // 30, self.height // 2 - (self.height // 6 // 2), self.height // 150, self.height // 6, self.width, self.height)
        self.paddle2: Paddle = Paddle(self.width - self.width // 30, self.height // 2 - (self.height // 6 // 2), self.height // 150, self.height // 6, self.width, self.height)
        # self.ai = QL_AI(self.width, self.height, self.paddle2.width, self.paddle2.height)
        # self.state = self.getGameState()

        # AI settings
        self.RUNNING_AI = True
        self.DIFFICULTY = 3
        self.SAVING = False
        self.TRAINING = False
        self.LOADING = False
        self.testing = True
        self.lastDump = 0
        # self.ai.training = self.TRAINING
        self.TRAININGPARTNER = False
        self.partner_side = "left"

        self.gameOver = False

        # self.init_ai()

        # game related variables
        self.scoreLimit = 2
        self.run = True
        self.pause = False
        self.goal1 = False
        self.goal2 = False
        self.currentTs = time.time()
        self.NewCalculusNeeded = True
        self.pauseCoolDown = self.currentTs
        self.CLI_cooldown = 0
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
        current_ts = time.time()
        if current_ts - self.CLI_cooldown < 0.5:
            return
        self.CLI_cooldown = current_ts

        pygame.init()
        pygame.display.set_caption("Pong")
        self.display = True
        self.CLI_controls = True
        self.ball.update_speed_on_CLI(self.display)
        self.win = pygame.display.set_mode((self.width, self.height))
        logging.info("Display initialized")

    def deactivate_CLI(self):
        current_ts = time.time()
        if current_ts - self.CLI_cooldown < 0.5:
            return
        self.CLI_cooldown = current_ts

        self.CLI_controls = False
        self.display = False
        pygame.quit()
        logging.info("CLI deactivated")


    def handleArguments(self, event):
        print(event)
        # handling the argumemnts ->31504 if OK ->
        self.are_args_set = True


    def handlePauseResetQuit(self):
        if self.display == True:
            for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.deactivate_CLI()
                        return
                        # self.gameOver = True
                        # self.run = False
        self.keys = pygame.key.get_pressed()
        keys = self.keys
        if keys[pygame.K_r]:
            self.ball.reset(1, self.display)
        if keys[pygame.K_ESCAPE]:
            if self.gameState["goal"] == "None":
                self.currentTs = time.time()
                if self.currentTs - 0.2 > self.pauseCoolDown:
                    self.pauseCoolDown = self.currentTs
                    if self.pause == True:
                        self.pause = False
                    else:
                        self.pause = True
        # if keys[pygame.K_SPACE]:
        #     if self.gameState["goal"] == "None":
        #         self.currentTs = time.time()
        #         if self.currentTs - 0.2 > self.pauseCoolDown:
        #             self.pauseCoolDown = self.currentTs
        #             if self.pause == True:
        #                 self.pause = False
        #             else:
        #                 self.pause = True
    

    def handlePlayer1Inputs(self):
        event = pygame.event.get()
        keys = self.keys

        if keys[pygame.K_w] and self.paddle1.canMove == True:
            self.paddle1.move(self.height, up=True)
        elif keys[pygame.K_s] and self.paddle1.canMove == True:
            self.paddle1.move(self.height, up=False)
        # check c key keyup event

        elif keys[pygame.K_c]:
            logging.info("c key pressed")
            # current_ts = time.time()
            # logging.info(f"current_ts: {current_ts}, CLI_cooldown: {self.CLI_cooldown}")
            # if current_ts - self.CLI_cooldown > 0.5:
            #     self.CLI_cooldown = current_ts
            #     self.deactivate_CLI()
            self.deactivate_CLI()

    
    def handlePlayer2Inputs(self):
        keys = self.keys

        if keys[pygame.K_UP] and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=True)
        if keys[pygame.K_DOWN] and self.paddle2.canMove == True:
            self.paddle2.move(self.height, up=False)


    def handle_inputs(self):
        if self.TRAININGPARTNER == False:
            if self.display == True:
                self.handlePlayer1Inputs()
        else:
            if self.partner_side == "left":
                self.paddle1.y = self.nextCollision[1] + random.uniform(-(self.paddle1.height * 0.9 // 2), (self.paddle1.height * 0.9 // 2)) - self.paddle1.height // 2

            else:
                self.paddle2.y = self.nextCollision[1] + random.uniform(-(self.paddle1.height * 0.9 // 2), (self.paddle1.height * 0.9 // 2)) - self.paddle1.height // 2
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
                if self.TRAININGPARTNER is True:
                    half_height = paddle2.height // 2
                    if self.partner_side == "right":
                        paddle2.y = self.nextCollision[1] + random.uniform(-half_height, half_height) - half_height
                    else:
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
            if current_time - self.last_frame_time >= 1/60 or self.isgameover() == True and self.display == False:
                self.serialize()
                self.last_frame_time = current_time
                # print(f"game state: {self.gameState}")
                # if self.gameState["gameover"] != None:
                    # logging.info("Game Over SENT \n\n\n\n")
                yield json.dumps(self.gameState)


    def quit(self):
        if self.display == True or self.CLI_controls:
            pygame.quit()


    def redraw_window(self):
        self.win.fill(self.black)
        self.paddle1.draw(self.win)
        self.paddle2.draw(self.win)
        self.ball.draw(self.win)

        #draw a line in the middle of the screen
        pygame.draw.line(self.win, self.white, (self.width // 2, 0), (self.width // 2, self.height), 5)
        #draw the score
        font = pygame.font.SysFont(None, 100)
        text = font.render(str(self.paddle1.score), 1, self.white)
        self.win.blit(text, (self.width // 4, 50))
        text = font.render(str(self.paddle2.score), 1, self.white)
        self.win.blit(text, (self.width // 4 * 3, 50))

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

    def isgameover(self):
        if self.TRAINING == False:
            if self.paddle1.score >= self.scoreLimit or self.paddle2.score >= self.scoreLimit:
                self.gameOver = True
                self.pause = True
                return True
        if self.gameOver == True:
            self.pause = True
            return True
        return False


    def serialize(self):
        self.gameState["type"] = "None"
        self.gameState["playing"] = self.goal1 is False and self.goal2 is False
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
            self.gameState["winner"] = "1" if self.paddle1.score >= self.scoreLimit else "2"
            # logging.info("Game Over on data\n\n\n")
        else:
            self.gameState["gameover"] = None
            self.gameState["winner"] = None
    

    def gameSerialize(self):
        res:dict = {}
        res["scoreLimit"] = self.scoreLimit
        res["pause"] = self.pause
        res['ai_data'] = self.getGameState()
        res['ai_data'].append(self.nextCollision)
        # res['ai_data'].append(self.paddle1.y)
        res['ai_data'].append(self.paddle2.y)

        return res


    async def resume_on_goal(self):
        # print("resume")
        self.ball.reset(self.ball.x, self.display)
        self.goal1 = False
        self.goal2 = False
        # if self.RUNNING_AI is True:
        #     self.paddle2.reset_position()
        # self.state = self.getGameState()
        self.lastSentInfos = time.time() - 0.25
        self.pause = False
    
