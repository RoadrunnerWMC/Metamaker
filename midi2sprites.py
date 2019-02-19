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


# 1/24/16
# RRWMC
# If this test works, it'll be added as a feature of Metamaker... or maybe a library or something?

import io

import mido

from i18n import _
from metamaker import DEFAULT_SPRITEDATA, X_MIN, X_MAX, Y_MIN, Y_MAX, SMM_X_MIN, SMM_X_MAX, SMM_Y_MIN, SMM_Y_MAX


NOTE_BLOCK_TYPE = 23

# We need to enable flag 4 to get the shaken version of the note block
NOTE_BLOCK_DATA = DEFAULT_SPRITEDATA[:3]
NOTE_BLOCK_DATA += bytes([DEFAULT_SPRITEDATA[3] | 4])
NOTE_BLOCK_DATA += DEFAULT_SPRITEDATA[4:]


class MidiConversionParams:
    """
    Allows you to define some values for the MIDI -> CDT conversion process.
    """
    def __init__(self, midoObj):
        self.trackNum = 0 # The track to import
        self.spriteNum = 0 # The sprite that will jump on the note blocks
        self.spriteData = DEFAULT_SPRITEDATA # The sprite data that those sprites will have
        self.toneOffset = -60 # Use to move the tone up or down. -60 puts middle C at the bottom of the course.
        self.xStartPos = 512 # Roughly a good default
        self.xUnitsPerBeat = 64 # 64 x-units = 4 tiles, which is about right if Mario runs across the bottom of the level



def isValidPos(x, y):
    """
    Is this a valid position for an object in SMM?
    """
    return X_MIN * 16 < x < X_MAX * 16 and Y_MIN * 16 < y < Y_MAX * 16


def findTicksPerBeat(midoObj):
    """
    Find the Ticks per Beat for this song.
    """
    for track in midoObj.tracks:
        for message in track:
            if isinstance(message, mido.MetaMessage) and message.type == 'time_signature':
                return message.clocks_per_click

    # 480 is mido.DEFAULT_TICKS_PER_BEAT, an undocumented constant
    return 480


def convertToSprPosList(midoObj, conversionParams):
    """
    Convert a Mido object to a list of sprite types and positions:
    [(type, x, y, data), (type, x, y, data), (type, x, y, data), (type, x, y, data), ...]
    """
    sprList = []

    # Find ticksPerBeat for this song
    tpb = findTicksPerBeat(midoObj)

    # Shorthand
    tn, sn, sd, to, xsp, xupb = \
        conversionParams.trackNum, conversionParams.spriteNum, \
        conversionParams.spriteData, conversionParams.toneOffset, \
        conversionParams.xStartPos, conversionParams.xUnitsPerBeat
    timeCoefficient = xupb / tpb # (x-units/beat) / (ticks/beat) = (x-units/tick)

    track = midoObj.tracks[tn]
    time = 0

    # Iterate over the messages in this track
    for message in track:
        if not isinstance(message, mido.MetaMessage):
            time += message.time
            if message.type == 'note_on':

                # Both sprites should be at the same x-position
                x = int(xsp + time * timeCoefficient)

                # Place the note block
                noteblockY = (message.note + to) * 16
                if isValidPos(x, noteblockY):
                    sprList.append((NOTE_BLOCK_TYPE, x, noteblockY, NOTE_BLOCK_DATA))

                # Place the sprite that will jump on the music block, just above it
                jumpsprY = noteblockY + 16
                if isValidPos(x, jumpsprY):
                    sprList.append((sn, x, jumpsprY, sd))

    return sprList


def percentageFit(midoObj, conversionParams):
    """
    What percentage (0 < pct < 1) of the midi will fit into
    the level, with the conversion parameters given?
    """
    time = 0
    for message in midoObj.tracks[conversionParams.trackNum]:
        if not isinstance(message, mido.MetaMessage):
            time += message.time

    # Calculate horizontal percentage
    maxWidth = int(time * conversionParams.xUnitsPerBeat / findTicksPerBeat(midoObj))
    if maxWidth > 0:
        levelWidth = SMM_X_MAX * 16 - conversionParams.xStartPos
        pctX = min(levelWidth / maxWidth, 1) # don't return > 100%
    else:
        # If we didn't have this if-else, we'd get a DivisionByZero error
        # because the song is 0-length... but that means we can fit it all,
        # so let's return 100%
        pctX = 1

    return pctX


def getSongObj(fp):
    """
    Returns a (MIDO) song object for the file at path fp.
    """
    try:
        return mido.MidiFile(fp)
    except Exception:
        return None


def getTracks(midoObj):
    """
    Returns a list of tracks in the (MIDO) song object.
    """
    L = []
    for i, track in enumerate(midoObj.tracks):
        if track.name:
            L.append(_('{num}: {name}', 'num', i + 1, 'name', track.name))
        else:
            L.append(str(i + 1))
    return L
