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

# 1/22/16
# i18n.py
# Contains i18n code!


def _(message, *repls):
    """
    Performs string translations (i18n).
    Usage: _(message, replacementCode, replacementText, replacementCode2, replacementText2, ...)
    """

    # Perform any replacements
    for i in range(0, len(repls), 2):

        old = '{' + str(repls[i]) + '}'
        new = str(repls[i+1])

        message = message.replace(old, new)
        i += 2

    return message

