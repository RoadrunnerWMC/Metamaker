#!/usr/bin/python
# -*- coding: latin-1 -*-

# Metamaker - A low-level Super Mario Maker course editor
# Version 0.1.0
# Copyright (C) 2009-2019 Treeki, Tempus, angelsl, JasonP27, Kamek64,
# MalStar1000, RoadrunnerWMC, AboodXD

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


# 1/9/16
# Metamodifier: Modify SMM sprite parameters!
# By RRWMC

import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets
Qt = QtCore.Qt

from i18n import _
import params


# hm.
# - View -> "Friendly" Names (on by default) (needs a better name)
# Starting screen:
# .----. .---------.
# |    | |         | xxx:
# |    | |         | ____
# |    | |         |
# |    | |         |
# '----' '---------'
# |=||=| |===| |===|
#     - Left: list of .packs (from folder, from .pack/sarc, or from a folder if you so choose)
#         - If a .params is opened directly, this is cleared and disabled
#         - "Export" and "Import" buttons are there, too (though disabled if we're displaying a folder)
#     - Right: current .params file options
#         - QTreeView to properly display the hierarchy
#         - Add/Delete buttons are there; also
#         - Reordering isn't really an issue
#     - Far right: current option
#         - Don't forget that option-lists are a thing!
# - directly


METAMODIFIER_ID = 'Metamodifier by RoadrunnerWMC'
METAMODIFIER_VERSION = '0.1.0'



class MetamodifierWindow(QtWidgets.QMainWindow):
    """
    Main window for Metamodifier
    """
    def __init__(self, *args):
        """
        Initialize the window
        """
        super().__init__(*args)
        self.setWindowTitle(_('Metamodifier {version}', 'version', METAMODIFIER_VERSION))


def main():
    """
    Main function
    """
    global mw, app
    app = QtWidgets.QApplication(sys.argv)
    mw = MetamodifierWindow()
    mw.show()
    app.exec_()


if __name__ == '__main__': main()
