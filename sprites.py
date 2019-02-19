#!/usr/bin/python
# -*- coding: latin-1 -*-

# Metamaker - A low-level Super Mario Maker course editor
# Version 0.1.0
# Copyright (C) 2009-2019 Treeki, Tempus, angelsl, JasonP27, Kamek64,
# MalStar1000, RoadrunnerWMC

# This file is part of Metamaker.

# Metamaker is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Metamaker is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Metamaker.  If not, see <http://www.gnu.org/licenses/>.



# sprites.py
# Contains code to render Super Mario Maker sprite images


################################################################
################################################################

# Imports

from PyQt5 import QtCore, QtGui
Qt = QtCore.Qt


import spritelib as SLib

M1, M3, MW, WU = 0, 1, 2, 3
OVERWORLD, UNDERGROUND, CASTLE, AIRSHIP, UNDERWATER, GHOST_HOUSE = 0, 1, 2, 3, 4, 5


################################################################
################################################################

class SpriteImage_Block(SLib.SpriteImage):
    blockX = 0
    blockY = 0
    def __init__(self, parent, scale=None):
        super().__init__(parent, scale)
        self.spritebox.shown = False

    @classmethod
    def subspriteIcon(cls, sprdata):
        return SLib.GetTile(cls.blockX, cls.blockY)

    def paint(self, painter):
        super().paint(painter)

        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        tile = SLib.GetTile(self.blockX, self.blockY)
        if tile is None:
            self.spritebox.shown = True
        else:
            painter.drawPixmap(0, 0, tile)



class SpriteImage_BrickBlock(SpriteImage_Block): # 4
    blockX = 1



class SpriteImage_QuestionBlock(SpriteImage_Block): # 5
    blockX = 2



class SpriteImage_WoodenBlock(SpriteImage_Block): # 6
    blockX = 6



class SpriteImage_GroundTile(SpriteImage_Block): # 7
    blockX = 8
    blockY = 11

    # We don't need to redefine subspriteIcon because the tile number
    # is stored in the second half of the spritedata -- thus, for
    # subsprite 7, it will always be 0 and default to the tile at
    # (8, 12).

    def dataChanged(self):
        tileNum = self.parent.spritedata[7]
        self.blockX = (tileNum + 8) % 16
        self.blockY = (tileNum + 184) // 16



class SpriteImage_Coin(SpriteImage_Block): # 8
    blockX = 7



# 9 - Pipe:
# These are stored in the tilesets; HOWEVER, we still need to find the
# values for things like Direction and Length before the image can
# be made.


# 14 - Mushroom Platform:
# These are stored in the tilesets; HOWEVER, we still need to find the
# values for Style and Length before the image can be made.


class SpriteImage_SemisolidPlatform(SLib.SpriteImage): # 16
    def __init__(self, parent, scale=1.5):
        super().__init__(parent, scale)
        self.spritebox.shown = False

    @classmethod
    def subspriteIcon(cls, sprdata):
        pix = QtGui.QPixmap(180, 180)
        pix.fill(Qt.transparent)
        painter = QtGui.QPainter(pix)
        cls.paintSsP(painter, sprdata + b'\0\0\0\0', 3, 3)
        del painter
        return pix

    def paint(self, painter):
        super().paint(painter)

        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if not self.paintSsP(painter, self.parent.spritedata, self.parent.width, self.parent.height):
            self.spritebox.shown = True


    @staticmethod
    def paintSsP(painter, spritedata, w, h):

        offX = 7
        if (spritedata[1] >> 2) & 1:
            offX += 3
        elif (spritedata[1] >> 3) & 1:
            offX += 6
        # If both flags are set......? That still needs to be tested.

        # Draw corners
        t = SLib.GetTile(offX, 3)
        if t is None: return False
        painter.drawPixmap(0, 0, t)

        t = SLib.GetTile(offX + 2, 3)
        if t is None: return False
        painter.drawPixmap(w * 60 - 60, 0, t)

        t = SLib.GetTile(offX, 6)
        if t is None: return False
        painter.drawPixmap(0, h * 60 - 60, t)

        t = SLib.GetTile(offX + 2, 6)
        if t is None: return False
        painter.drawPixmap(w * 60 - 60, h * 60 - 60, t)

        # Draw the top and bottom
        for x in range(w - 2):
            t = SLib.GetTile(offX + 1, 3)
            if t is None: return False
            painter.drawPixmap(60 + x * 60, 0, t)

            t = SLib.GetTile(offX + 1, 6)
            if t is None: return False
            painter.drawPixmap(60 + x * 60, h * 60 - 60, t)

        # Draw the left and right sides
        for y in range(h - 2):
            i = (h - y) % 2 # from the bottom up, starting with the bottom tile

            t = SLib.GetTile(offX, 4 + i)
            if t is None: return False
            painter.drawPixmap(0, 60 + y * 60, t)

            t = SLib.GetTile(offX + 2, 4 + i)
            if t is None: return False
            painter.drawPixmap(w * 60 - 60, 60 + y * 60, t)

        # Draw the center
        for x in range(w - 2):
            for y in range(h - 2):
                i = (h - y + x) % 2 # from the bottom-left, starting with the bottom tile

                t = SLib.GetTile(offX + 1, 4 + i)
                if t is None: return False
                painter.drawPixmap(60 + x * 60, 60 + y * 60, t)


# 17 - Bridge
# These are stored in the tilesets; HOWEVER, we still need to find the
# value for Length before the image can be made.


class SpriteImage_DonutLift(SpriteImage_Block): # 21
    blockY = 4



class SpriteImage_CloudBlock(SpriteImage_Block): # 22
    blockX = 6
    blockY = 6



class SpriteImage_NoteBlock(SpriteImage_Block): # 23
    blockX = 4



class SpriteImage_InvisibleBlock(SpriteImage_Block): # 29
    blockX = 3



class SpriteImage_SpikeBlock(SpriteImage_Block): # 43
    blockX = 2
    blockY = 4



class SpriteImage_IceBlock(SpriteImage_Block): # 63
    blockX = 8
    blockY = 7



################################################################
################################################################


ImageClasses = {
    4: SpriteImage_BrickBlock,
    5: SpriteImage_QuestionBlock,
    6: SpriteImage_WoodenBlock,
    7: SpriteImage_GroundTile,
    8: SpriteImage_Coin,
    16: SpriteImage_SemisolidPlatform,
    21: SpriteImage_DonutLift,
    22: SpriteImage_CloudBlock,
    23: SpriteImage_NoteBlock,
    29: SpriteImage_InvisibleBlock,
    43: SpriteImage_SpikeBlock,
    63: SpriteImage_IceBlock,
    }
