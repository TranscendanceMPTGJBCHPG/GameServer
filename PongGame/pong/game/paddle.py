import pygame
import logging

white = (255, 255, 255)
black = (0, 0, 0)

class Paddle:
    
    def __init__(self, x, y, width, height, win_width, win_height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.win_width = win_width
        self.win_height = win_height
        self.vel = round(win_height / 333)
        self.lastTouch = 0
        self.canMove = True
        self.score = 0
        # logging.info(f"paddle width: {width}, height: {height}, vel: {self.vel}, win_height: {win_height}")
        # exit(0)

    def reset_position(self):
        up, down = False, False
        if self.y + self.height / 2 < self.win_height / 2:
            up = True
        else:
            down = True
        if up is True:
            while self.y + self.height / 2 < self.win_height / 2 + 10:
                self.move(self.win_height, up=False)
        else:
            while self.y + self.height / 2 > self.win_height / 2 - 10:
                self.move(self.win_height, up=True)
    

    def draw(self, win):
        pygame.draw.rect(win, white, (self.x, self.y, self.width, self.height))

    async def move(self, height, up=True):

        # logging.info(f"paddle move: height: {height}")
        temp = self.y
        if up:
            temp -= self.vel
            if temp < 0:
                temp = 0
        else:
            temp += self.vel
            if temp > height - self.height:
                temp = height - self.height
        self.y = temp

    def serialize(self, game):
        res:dict = {}
        res["x"] = self.x / game.width
        res["y"] = (self.y + self.height / 2) / game.height
        res["score"] = self.score

        return res