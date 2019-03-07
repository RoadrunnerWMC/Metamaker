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



# metamaker.py
# This is the main executable for Metamaker.


################################################################
################################################################

# Python version sanity check
MIN_PY_VER = 3.4
import sys
currentRunningVersion = sys.version_info.major + (sys.version_info.minor / 10)
if currentRunningVersion < MIN_PY_VER:
    # Let's not raise an exception, because that's almost mean
    print('You are running Metamaker with Python ' + sys.version[:5] +
        ', yet the lowest officially-supported version is ' + str(MIN_PY_VER) +
        '. Please consider updating Python.')

# Stdlib imports
import base64
import binascii
from math import floor as math_floor
import os.path
import struct
import subprocess
import threading
import time
import urllib.request
from xml.etree import ElementTree as etree
import zipfile

from PyQt5 import QtCore, QtGui, QtWidgets
Qt = QtCore.Qt

# Local imports
import bfres as BFRES
from i18n import _
HAS_MIDO = True
try:
    import midi2sprites
except ImportError:
    HAS_MIDO = False
import sarc as SarcLib
import spritelib as SLib
import sprites
import yaz0

METAMAKER_ID = 'Metamaker by RoadrunnerWMC (Based on Reggie by Treeki and Tempus)'
METAMAKER_VERSION = '0.1.0'
UPDATE_URL = ''

TILE_WIDTH = 60

DEFAULT_SPRITEDATA = b'\x06\0\x08@\0\0\0\0'
DEFAULT_SUBSPRITEDATA = b'\x06\0\x08@'
DEFAULT_EFFECT = b'\xFF\xFF\0\xFF\xFF\0\0\0'

# These are the min/max positions -- <i>not</i> the same as the scene boundaries!
X_MIN = -1
X_MAX = 239
Y_MIN = -1
Y_MAX = 26

# These are used for regenerate-ground, so <i>never</i> change them!
SMM_X_MIN = 0
SMM_X_MAX = 239
SMM_Y_MIN = 0
SMM_Y_MAX = 26


if not hasattr(QtWidgets.QGraphicsItem, 'ItemSendsGeometryChanges'):
    # enables itemChange being called on QGraphicsItem
    QtWidgets.QGraphicsItem.ItemSendsGeometryChanges = QtWidgets.QGraphicsItem.GraphicsItemFlag(0x800)


# Globals
app = None
mainWindow = None
settings = None


def _c(*args): return theme.color(*args)


def checkSplashEnabled():
    """
    Checks to see if the splash screen is enabled
    """
    global prefs
    if setting('SplashEnabled') is None:
        return True
    elif setting('SplashEnabled'):
        return True
    else:
        return False

def loadSplash():
    """
    If called, this will show the splash screen until removeSplash is called
    """
    splashpixmap = QtGui.QPixmap('metamakerdata/splash.png')
    app.splashscrn = QtWidgets.QSplashScreen(splashpixmap)
    app.splashscrn.show()
    app.processEvents()

def updateSplash(message, progress):
    """
    This will update the splashscreen with the given message and progressval
    """
    font = QtGui.QFont()
    font.setPointSize(10)

    message = _('{current} (Stage {stage})', 'current', message, 'stage', progress)
    splashtextpixmap = QtGui.QPixmap('metamakerdata/splash.png')
    splashtextpixmappainter = QtGui.QPainter(splashtextpixmap)
    splashtextpixmappainter.setFont(font)
    splashtextpixmappainter.drawText(220, 195, message)
    app.splashscrn.setPixmap(splashtextpixmap)
    splashtextpixmappainter = None
    app.processEvents()

def removeSplash():
    """
    This will delete the splash screen, if it exists
    """
    if app.splashscrn is not None:
        app.splashscrn.close()
        app.splashscrn = None
        splashpixmap = None
        splashtextpixmap = None


defaultStyle = None
defaultPalette = None
def GetDefaultStyle():
    """
    Stores a copy of the default app style upon launch, which can then be accessed later
    """
    global defaultStyle, defaultPalette, app
    if (defaultStyle, defaultPalette) != (None, None): return
    defaultStyle = app.style()
    defaultPalette = QtGui.QPalette(app.palette())

def setting(name, default=None):
    """
    Thin wrapper around QSettings, fixes the type=bool bug
    """
    result = settings.value(name, default)
    if result == 'false': return False
    elif result == 'true': return True
    elif result == 'none': return None
    else: return result

def setSetting(name, value):
    """
    Thin wrapper around QSettings
    """
    return settings.setValue(name, value)

def module_path():
    """
    This will get us the program's directory, even if we are frozen using cx_Freeze
    """
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    if __name__ == '__main__':
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return None

compressed = False
def checkContent(data):
    if not data.startswith(b'SARC'):
        return False

    required = (b'course/', b'course1.bin')
    for r in required:
        if r not in data:
            return False

    return True


def isValidCourse(filename):
    """
    Does some basic checks to see if this filename can possibly
    be a valid SMM course. Just sanity checks -- this can return
    True for a completely invalid level.
    """
    if not os.path.isfile(filename): return False

    with open(filename, 'rb') as f:
        return isValidCourseData(f.read())


def isValidCourseData(data):
    """
    You can call this if you have raw CDT data instead of a file path.
    """

    if data[:4] == b'Yaz0': return True
    elif data[:4] == b'SARC': return True

    # Check some basic things and padding areas
    if len(data) != 0x15000: return False
    if data[:8] != b'\0\0\0\0\0\0\0\x0B': return False
    if data[12:16] != b'\0\0\0\0': return False
    if data[0xE0:0xEC] != b'\0' * 12: return False
    if data[0x14F50:0x15000] != b'\0' * 0xB0: return False

    return True


def FilesAreMissing():
    """
    Checks to see if any of the required files for Metamaker are missing
    """

    if not os.path.isdir('metamakerdata'):
        QtWidgets.QMessageBox.warning(None, _('Error'), _('Sorry, you seem to be missing the required data files for Metamaker to work. Please redownload your copy of the editor.'))
        return True

    required = ['icon.png', 'samplecoursenames.xml', 'overrides.png',
                'spritedata.xml', 'about.png', 'spritecategories.xml']

    missing = []

    for check in required:
        if not os.path.isfile('metamakerdata/' + check):
            missing.append(check)

    if len(missing) > 0:
        QtWidgets.QMessageBox.warning(None, _('Error'), _('Sorry, you seem to be missing some of the required data files for Metamaker to work. Please redownload your copy of the editor. These are the files you are missing: {files}', 'files', ', '.join(missing)))
        return True

    return False


def GetIcon(name, big=False):
    """
    Helper function to grab a specific icon
    """
    return theme.GetIcon(name, big)



CourseNames = None
def LoadCourseNames():
    """
    Ensures that the course name info is loaded
    """
    global CourseNames

    # Parse the file
    tree = etree.parse('metamakerdata/samplecoursenames.xml')
    root = tree.getroot()

    # Parse the nodes (root acts like a large category)
    CourseNames = LoadCourseNames_Category(root)


def LoadCourseNames_Category(node):
    """
    Loads a CourseNames XML category
    """
    cat = []
    for child in node:
        if child.tag.lower() == 'category':
            cat.append((str(child.attrib['name']), LoadCourseNames_Category(child)))
        elif child.tag.lower() == 'course':
            cat.append((str(child.attrib['name']), str(child.attrib['file'])))
    return tuple(cat)



def LoadConstantLists():
    """
    Loads some lists of constants
    """
    global Sprites
    global SpriteCategories

    Sprites = None
    SpriteListData = None


class SpriteDefinition():
    """
    Stores and manages the data info for a specific sprite
    """

    class ListPropertyModel(QtCore.QAbstractListModel):
        """
        Contains all the possible values for a list property on a sprite
        """

        def __init__(self, entries, existingLookup, max):
            """
            Constructor
            """
            super().__init__()
            self.entries = entries
            self.existingLookup = existingLookup
            self.max = max

        def rowCount(self, parent=None):
            """
            Required by Qt
            """
            #return self.max
            return len(self.entries)

        def data(self, index, role=Qt.DisplayRole):
            """
            Get what we have for a specific row
            """
            if not index.isValid(): return None
            n = index.row()
            if n < 0: return None
            #if n >= self.max: return None
            if n >= len(self.entries): return None

            if role == Qt.DisplayRole:
                #entries = self.entries
                #if n in entries:
                #    return '%d: %s' % (n, entries[n])
                #else:
                #    return '%d: <unknown/unused>' % n
                return '%d: %s' % self.entries[n]

            return None


    def loadFrom(self, elem):
        """
        Loads in all the field data from an XML node
        """
        self.fields = []
        fields = self.fields

        for field in elem:
            if field.tag not in ['checkbox', 'list', 'value', 'bitfield']: continue

            attribs = field.attrib

            if 'comment' in attribs:
                comment = _('<b>{name}</b>: {note}', 'name', attribs['title'], 'note', attribs['comment'])
            else:
                comment = None

            if field.tag == 'checkbox':
                # parameters: title, nybble, mask, comment
                snybble = attribs['nybble']
                if '-' not in snybble:
                    nybble = int(snybble) - 1
                else:
                    getit = snybble.split('-')
                    nybble = (int(getit[0]) - 1, int(getit[1]))

                fields.append((0, attribs['title'], nybble, int(attribs['mask']) if 'mask' in attribs else 1, comment))
            elif field.tag == 'list':
                # parameters: title, nybble, model, comment
                snybble = attribs['nybble']
                if '-' not in snybble:
                    nybble = int(snybble) - 1
                    max = 16
                else:
                    getit = snybble.split('-')
                    nybble = (int(getit[0]) - 1, int(getit[1]))
                    max = (16 << ((nybble[1] - nybble[0] - 1) * 4))

                entries = []
                existing = [None for i in range(max)]
                for e in field:
                    if e.tag != 'entry': continue

                    i = int(e.attrib['value'])
                    entries.append((i, e.text))
                    existing[i] = True

                fields.append((1, attribs['title'], nybble, SpriteDefinition.ListPropertyModel(entries, existing, max), comment))
            elif field.tag == 'value':
                # parameters: title, nybble, max, comment
                snybble = attribs['nybble']

                # if it's 5-12 skip it
                # fixes tobias's crashy 'unknown values'
                if snybble == '5-12': continue

                if '-' not in snybble:
                    nybble = int(snybble) - 1
                    max = 16
                else:
                    getit = snybble.split('-')
                    nybble = (int(getit[0]) - 1, int(getit[1]))
                    max = (16 << ((nybble[1] - nybble[0] - 1) * 4))

                fields.append((2, attribs['title'], nybble, max, comment))
            elif field.tag == 'bitfield':
                # parameters: title, startbit, bitnum, comment
                startbit = int(attribs['startbit'])
                bitnum = int(attribs['bitnum'])

                fields.append((3, attribs['title'], startbit, bitnum, comment))


def LoadSpriteData():
    """
    Ensures that the sprite data info is loaded
    """
    global Sprites

    Sprites = [None] * 70
    errors = []
    errortext = []

    spritenames = []
    with open('metamakerdata/spritenames.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'): continue

            # Parse inline [comment text] comments
            # {Text} sections delimit extra names from original games;
            # right now we treat those as comments, too
            L = ''
            adding = True
            for char in line:
                if char in '[{':
                    adding = False
                    continue
                elif char in ']}':
                    adding = True
                    continue
                if adding: L += char

            # Those comments might leave double-spaces: text [comment] text -> text  text
            while '  ' in L: L = L.replace('  ', ' ')
            # And spaces at the end of the line: text [comment]\n -> text \n
            L = L.replace(' \n', '\n')
            spritenames.append(L[:-1]) # cut off the \n

    paths = [['metamakerdata/spritedata.xml', None]]

    for sdpath, snpath in paths:

        # Add XML sprite data, if there is any
        if sdpath not in (None, ''):
            path = sdpath if isinstance(sdpath, str) else sdpath.path
            tree = etree.parse(path)
            root = tree.getroot()

            for sprite in root:
                if sprite.tag.lower() != 'sprite': continue

                try: spriteid = int(sprite.attrib['id'])
                except ValueError: continue
                spritename = spritenames[spriteid] # formerly sprite.attrib['name']
                notes = None

                if 'notes' in sprite.attrib:
                    notes = _('<b>Sprite Notes:</b> {notes}', 'notes', sprite.attrib['notes'])

                sdef = SpriteDefinition()
                sdef.id = spriteid
                sdef.name = spritename
                sdef.notes = notes

                try:
                    sdef.loadFrom(sprite)
                except Exception as e:
                    errors.append(str(spriteid))
                    errortext.append(str(e))

                Sprites[spriteid] = sdef

        # Add TXT sprite names, if there are any
        # This code is only ever run when a custom
        # gamedef is loaded, because spritenames.txt
        # is a file only ever used by custom gamedefs.
        if (snpath is not None) and (snpath.path is not None):
            snfile = open(snpath.path)
            data = snfile.read()
            snfile.close()
            del snfile

            # Split the data
            data = data.split('\n')
            for i, line in enumerate(data): data[i] = line.split(':')

            # Apply it
            for spriteid, name in data:
                Sprites[int(spriteid)].name = name

    # Warn the user if errors occurred
    if len(errors) > 0:
        QtWidgets.QMessageBox.warning(None, _('Warning'), _("The sprite data file didn't load correctly. The following sprites have incorrect and/or broken data in them, and may not be editable correctly in the editor: {sprites}", 'sprites', ', '.join(errors)), QtWidgets.QMessageBox.Ok)
        QtWidgets.QMessageBox.warning(None, _('Errors'), repr(errortext))

SpriteCategories = None
def LoadSpriteCategories(reload_=False):
    """
    Ensures that the sprite category info is loaded
    """
    global Sprites, SpriteCategories
    if (SpriteCategories is not None) and not reload_: return

    paths = ['metamakerdata/spritecategories.xml']

    SpriteCategories = []
    for path in paths:
        tree = etree.parse(path)
        root = tree.getroot()

        CurrentView = None
        for view in root:
            if view.tag.lower() != 'view': continue

            viewname = view.attrib['name']

            # See if it's in there already
            CurrentView = []
            for potentialview in SpriteCategories:
                if potentialview[0] == viewname: CurrentView = potentialview[1]
            if CurrentView == []: SpriteCategories.append((viewname, CurrentView, []))

            CurrentCategory = None
            for category in view:
                if category.tag.lower() != 'category': continue

                catname = category.attrib['name']

                # See if it's in there already
                CurrentCategory = []
                for potentialcat in CurrentView:
                    if potentialcat[0] == catname: CurrentCategory = potentialcat[1]
                if CurrentCategory == []: CurrentView.append((catname, CurrentCategory))

                for attach in category:
                    if attach.tag.lower() != 'attach': continue

                    sprite = attach.attrib['sprite']
                    if '-' not in sprite:
                        if int(sprite) not in CurrentCategory:
                            CurrentCategory.append(int(sprite))
                    else:
                        x = sprite.split('-')
                        for i in range(int(x[0]), int(x[1])+1):
                            if i not in CurrentCategory:
                                CurrentCategory.append(i)

    # Add a Search category
    SpriteCategories.append((_('Search'), [(_('Search Results'), list(range(70)))], []))
    SpriteCategories[-1][1][0][1].append(9999) # 'no results' special case



class ChooseCourseNameDialog(QtWidgets.QDialog):
    """
    Dialog which lets you choose a course from a list
    """
    def __init__(self):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Choose Course'))
        self.setWindowIcon(GetIcon('open'))
        LoadCourseNames()
        self.currentcourse = None

        # create the tree
        tree = QtWidgets.QTreeWidget()
        tree.setColumnCount(1)
        tree.setHeaderHidden(True)
        tree.setIndentation(16)
        tree.currentItemChanged.connect(self.HandleItemChange)
        tree.itemActivated.connect(self.HandleItemActivated)

        # add items (CourseNames is effectively a big category)
        tree.addTopLevelItems(self.ParseCategory(CourseNames))

        # assign it to self.coursetree
        self.coursetree = tree

        # create the buttons
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # create the layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.coursetree)
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)
        self.layout = layout

        self.setMinimumWidth(320) # big enough to fit "World 5: Freezeflame Volcano/Freezeflame Glacier"
        self.setMinimumHeight(384)

    def ParseCategory(self, items):
        """
        Parses a XML category
        """
        nodes = []
        for item in items:
            node = QtWidgets.QTreeWidgetItem()
            node.setText(0, item[0])
            # see if it's a category or a course
            if isinstance(item[1], str):
                # it's a course
                node.setData(0, Qt.UserRole, item[1])
                node.setToolTip(0, item[1] + '.cdt')
            else:
                # it's a category
                children = self.ParseCategory(item[1])
                for cnode in children:
                    node.addChild(cnode)
                node.setToolTip(0, item[0])
            nodes.append(node)
        return tuple(nodes)

    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, QtWidgets.QTreeWidgetItem)
    def HandleItemChange(self, current, previous):
        """
        Catch the selected course and enable/disable OK button as needed
        """
        self.currentcourse = current.data(0, Qt.UserRole)
        if self.currentcourse is None:
            self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
        else:
            self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(True)
            self.currentcourse = str(self.currentcourse)


    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def HandleItemActivated(self, item, column):
        """
        Handle a doubleclick on a course
        """
        self.currentcourse = item.data(0, Qt.UserRole)
        if self.currentcourse is not None:
            self.currentcourse = str(self.currentcourse)
            self.accept()


def SetAppStyle():
    """
    Set the application window color
    """
    global app
    global theme

    # Change the color if applicable
    #if _c('ui') is not None: app.setPalette(QtGui.QPalette(_c('ui')))

    # Change the style
    styleKey = setting('uiStyle')
    style = QtWidgets.QStyleFactory.create(styleKey)
    app.setStyle(style)


Course = None
Dirty = False
DirtyOverride = 0
AutoSaveDirty = False
OverrideSnapping = False
SpritesShown = True
SpriteImagesShown = True
RealViewEnabled = False
SpritesFrozen = False
NumberFont = None
GridType = None
RestoredFromAutoSave = False
AutoSavePath = ''
AutoSaveData = b''
AutoOpenScriptEnabled = False

def createHorzLine():
    f = QtWidgets.QFrame()
    f.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
    return f

def createVertLine():
    f = QtWidgets.QFrame()
    f.setFrameStyle(QtWidgets.QFrame.VLine | QtWidgets.QFrame.Sunken)
    return f

def LoadNumberFont():
    """
    Creates a valid font we can use to display the item numbers
    """
    global NumberFont
    if NumberFont is not None: return

    # this is a really crappy method, but I can't think of any other way
    # normal Qt defines Q_WS_WIN and Q_WS_MAC but we don't have that here
    s = QtCore.QSysInfo()
    if hasattr(s, 'WindowsVersion'):
        NumberFont = QtGui.QFont('Tahoma', (7/24) * TILE_WIDTH)
    elif hasattr(s, 'MacintoshVersion'):
        NumberFont = QtGui.QFont('Lucida Grande', (9/24) * TILE_WIDTH)
    else:
        NumberFont = QtGui.QFont('Sans', (8/24) * TILE_WIDTH)

def SetDirty(noautosave=False):
    global Dirty, DirtyOverride, AutoSaveDirty
    if DirtyOverride > 0: return

    if not noautosave: AutoSaveDirty = True
    if Dirty: return

    Dirty = True
    try:
        mainWindow.UpdateTitle()
    except Exception:
        pass



class AssetsClass:
    """
    An object that lets you access any assets from the SMM Model folder.
    Provides readable syntax and very nice caching optimizations!
    """
    def __init__(self, modelpath, packpath):
        """
        Initializes Assets
        """
        self.modelpath = modelpath
        self.packpath = packpath
        self.pathsverified = self.verifyPaths()

        self.loadedModels = set()
        self.loadedPacks = set()
        self.ftexCacheRaw = {}
        self.ftexCacheRendered = {}


    def verifyPaths(self):
        """
        Return True if self.modelpath and self.packpath appear to be
        proper SMM Model/ and Pack/ folders, respectively.
        """

        # TODO: check the Model/ and Pack/ folders for the existence of a few select files

        return True


    def __getitem__(self, key):
        """
        Returns the specified texture from the Model or Pack folder.
        Format is as follows:
        Model/filename/texturename    OR
        Pack/packname/folder.folder.szsname/texturename
        File extensions must not be included, since they can vary
        depending on various things.
        None is a perfectly possible return value (if the user doesn't
        choose a Model folder, for example, *any* call to this will result
        in None), so make sure to account for that when indexing the
        AssetsClass instance!
        """
        print('AssetsClass[\'' + key + '\']')
        # Quick short-circuit
        if key in self.ftexCacheRendered:
            print('    Short-circuiting.')
            return self.ftexCacheRendered[key]

        if key.startswith('Model/'):
            print('    Loading a model/ .')
            if key.count('/') != 2:
                raise ValueError('Invalid key format.')

            # Make sure the SZS/SARC/BFRES is loaded
            bfresName = key.split('/')[1]
            print('    ... called %s' % bfresName)
            self.loadModelItemIntoCache(bfresName)

        elif key.startswith('Pack/'):
            print('    Loading a pack/ .')
            if key.count('/') != 3:
                raise ValueError('Invalid key format.')

            # Make sure the Pack file is loaded
            packName = key.split('/')[1]
            print('    ... called %s' % packName)
            self.loadPackIntoCache(packName)

        else:
            raise ValueError('Invalid key format.')

        print('    Model loading done... theoretically')

        # Sanity check
        if key not in self.ftexCacheRaw and key not in self.ftexCacheRendered:
            raise ValueError('Key not found.')

        # Now return the rendered texture
        img = self.loadFtex(key)
        print('    Returning this thing: ' + repr(img))
        if img is None:
            return None
        else:
            print('    Here\'s its dimensions: %d, %d' % (img.width(), img.height()))
            return None if img.isNull() else img


    def loadModelItemIntoCache(self, modelName):
        """
        Load something from the Model folder ([Yaz0 -> ] SARC -> BFRES)
        into self.ftexCache.
        """
        print('    loadModelItemIntoCache(%s)' % modelName)
        # Prevent the same file from being loaded multiple times
        if modelName in self.loadedModels: return
        self.loadedModels.add(modelName)
        print('        Added that to self.loadedModels')

        # Find the file to open, and if it's compressed or not
        fp = os.path.join(self.modelpath, modelName + '.sarc')
        print('        Trying "' + fp + '"')
        compressed = False
        if not os.path.isfile(fp):
            fp = os.path.join(self.modelpath, modelName + '.szs')
            print('        Didn\'t exist; assuming "' + fp + '"...')
            compressed = True

        # Get the data
        print('        Opening that.')
        if not compressed:
            with open(fp, 'rb') as f:
                sarcData = f.read()
        else:
            sarcData = yaz0.decompress_opt(fp)
        print('        Got a sarc?: ' + repr(sarcData[:8]))

        # The sarc always contains exactly one file -- the BFRES
        assert sarcData[:4] == b'SARC'
        sarc = SarcLib.SARC_Archive()
        sarc.load(sarcData)
        (sarcFile,) = sarc.contents # http://stackoverflow.com/a/1619539/4718769
        bfresData = sarcFile.data

        print('        Got a BFRES?: ' + repr(bfresData[:8]))

        # Load it
        print('        Loading that bfres into the cache, prefixed with "Model/' + modelName + '"...')
        self.loadBfresIntoCache('Model/' + modelName, bfresData)


    def loadPackItemIntoCache(self, packName):
        """
        Load something from the Pack folder (SARC -> (Yaz0 -> SARC -> BFRES) * N) into self.ftexCache.
        This will load the raw contents of ALL of the BFRESs in the requested Pack. (They won't all be
        rendered, of course.)
        """
        # Prevent the same file from being loaded multiple times
        if packName in self.loadedPacks: return
        self.loadedPacks.add(packName)


    def loadBfresIntoCache(self, prefix, bfresData):
        """
        Load a [Yaz0 -> ] SARC -> BFRES, and store its FTEX's into self.ftexCache
        """
        print('        loadBfresIntoCache(%s, %s...)' % (prefix, repr(bfresData[:8])))
        textures = BFRES.read(bfresData)
        for name, tex in textures:
            self.ftexCacheRaw[prefix + '/' + name] = tex

        print('            FTEX reading done.')


    def loadFtex(self, key):
        """
        Returns the FTEX specified as a QImage, using a cached copy if
        possible.
        """
        print('    loadFtex(\'' + key + '\')')
        # Return the rendered copy if possible
        if key in self.ftexCacheRendered:
            print('        Short-circuiting')
            return self.ftexCacheRendered[key]

        # Render it
        img = BFRES.texToQImage(self.ftexCacheRaw[key])

        # Cache it
        self.ftexCacheRendered[key] = img

        # Return it
        return img



class CourseClass:
    """
    Class for a course from Super Mario Maker
    """
    def __init__(self):
        """
        Initializes the course with default settings
        """
        super().__init__()

        self.headerStruct = struct.Struct('>QI4xH6BQB7x66s2s4BHBBI96sII12xI')
        self.sprStruct = struct.Struct('>IIhbb4s4s4sbbhhbb')
        self.effectStruct = struct.Struct('>5bxxx')

    def load(self, data, progress=None):
        """
        Loads a Super Mario Maker course from bytes data.
        """

        header = self.headerStruct.unpack_from(data, 0)

        def parseStyle(raw):
            vals = [b'M1', b'M3', b'MW', b'WU']
            return vals.index(raw) if raw in vals else 0

        courseVer = header[0]; assert courseVer == 0xB
        # header[1] is the CRC32 hash; we don't need to load this
        self.creationYear = header[2]
        self.creationMonth = header[3]
        self.creationDay = header[4]
        self.creationHour = header[5]
        self.creationMinute = header[6]
        self.unk16 = header[7]
        self.unk17 = header[8]
        self.unk181F = header[9]
        self.unk20 = header[10]
        self.courseName = header[11].rstrip(b'\0').decode('utf-16be')
        self.style = parseStyle(header[12])
        self.unk6C = header[13]
        self.theme = header[14] % 6
        self.unk6E = header[15]
        self.unk6F = header[16]
        self.timeLimit = header[17]
        self.autoscroll = header[18]
        self.unk73 = header[19]
        self.unk7475 = header[20]
        self.unk76D7 = header[21] # this reeeeeally needs to be figured out ASAP
        self.unkD8DB = header[22]
        self.unkDCDF = header[23]
        numItems = header[24]


        effects = []
        for i in range(300):
            effinfo = self.effectStruct.unpack_from(data, 0x145F0 + 8 * i)
            eff = Effect(*effinfo)
            effects.append(eff)


        self.sprites = []
        for i in range(numItems):
            sprinfo = list(self.sprStruct.unpack_from(data, 0xF0 + 32 * i))

            # Replace the effect index with the Effect object itself
            eff = None if sprinfo[11] == -1 else effects[sprinfo[11] % 300]
            sprinfo[11] = eff

            # Fix up the positions
            sprinfo[0] = sprinfo[0] // 10 - 8
            sprinfo[1] = sprinfo[1] // 10
            sprinfo[2] = sprinfo[2] // 10 - 8

            spr = SpriteItem(*sprinfo)
            self.sprites.append(spr)

            spr.UpdateListItem()
            spr.UpdateDynamicSizing()


        # Success return value
        return True


    def save(self):
        """
        Save the course back to a file
        """
        header = self.headerStruct.pack(
            0x0B,
            0, # we can't calculate the hash yet; we fill it in later
            self.creationYear,
            self.creationMonth,
            self.creationDay,
            self.creationHour,
            self.creationMinute,
            self.unk16,
            self.unk17,
            self.unk181F,
            self.unk20,
            self.courseName.encode('utf-16be').ljust(66, b'\0'),
            [b'M1', b'M3', b'MW', b'WU'][self.style % 4],
            self.unk6C,
            self.theme,
            self.unk6E,
            self.unk6F,
            self.timeLimit,
            self.autoscroll,
            self.unk73,
            self.unk7475,
            self.unk76D7,
            self.unkD8DB,
            self.unkDCDF,
            len(self.sprites),
            )


        effects = []
        sprdata = b''
        for spr in self.sprites:

            if spr.effect is None:
                b = None
            else:
                b = self.effectStruct.pack(
                    spr.effect.unk00,
                    spr.effect.unk01,
                    spr.effect.unk02,
                    spr.effect.unk03,
                    spr.effect.unk04,
                    )

            if b is None:
                thisEffIdx = -1
            elif b in effects:
                thisEffIdx = effects.index(b)
            else:
                effects.append(b)
                thisEffIdx = len(effects) - 1

            sprdata += self.sprStruct.pack(
                spr.objx * 10 + 80,
                spr.objz * 10,
                spr.objy * 10 + 80,
                spr.width,
                spr.height,
                spr.spritedata[:4],
                spr.spritedata_sub,
                spr.spritedata[4:],
                spr.type,
                spr.type_sub,
                spr.linkingID,
                thisEffIdx,
                spr.costumeID,
                spr.costumeID_sub,
                )

        sprdata = sprdata.ljust(0x14500, b'\0')

        while len(effects) < 300: effects.append(DEFAULT_EFFECT)
        effdata = b''.join(effects)

        cdt = bytearray(header + sprdata + effdata + b'\0' * 0xB0)

        hash = binascii.crc32(cdt[16:]) & 0xFFFFFFFF
        # Shamelessly splice this into the cdt
        cdt[0x8] = hash >> 24
        cdt[0x9] = (hash >> 16) & 0xFF
        cdt[0xA] = (hash >> 8) & 0xFF
        cdt[0xB] = hash & 0xFF

        return bytes(cdt)


    # Python hax: automatically notify SLib whenever the style or theme changes!
    @property
    def style(self):
        return self._style
    @style.setter
    def style(self, value):
        SLib.Style = value
        self._style = value
    @property
    def theme(self):
        return self._theme
    @theme.setter
    def theme(self, value):
        SLib.Theme = value
        self._theme = value


    # The following insanely long constant was written by hand by RoadrunnerWMC.
    TERRAIN_EDGES = (24, 24, 28, 28, 24, 24, 28, 28, 25, 25, 34, 0, 25, 25, 34, 0, 27, 27, 33, 33, 27, 27, 1, 1, 6, 6, 36, 44, 6, 6, 45, 9, 24, 24, 28, 28, 24, 24, 28, 28, 25, 25, 34, 0, 25, 25, 34, 0, 27, 27, 33, 33, 27, 27, 1, 1, 6, 6, 36, 44, 6, 6, 45, 9, 30, 30, 29, 29, 30, 30, 29, 29, 32, 32, 38, 40, 32, 32, 38, 40, 31, 31, 37, 37, 31, 31, 41, 41, 35, 35, 39, 48, 49, 35, 49, 52, 30, 30, 29, 29, 30, 30, 29, 29, 4, 4, 42, 2, 4, 4, 42, 2, 31, 31, 37, 37, 31, 31, 41, 41, 46, 46, 50, 54, 46, 46, 57, 67, 24, 24, 28, 28, 24, 24, 28, 28, 25, 25, 34, 0, 25, 25, 34, 0, 27, 27, 33, 33, 27, 27, 1, 1, 6, 6, 36, 44, 6, 6, 45, 9, 24, 24, 28, 28, 24, 24, 28, 28, 25, 25, 34, 0, 25, 25, 34, 0, 27, 27, 33, 33, 27, 27, 1, 1, 6, 6, 36, 44, 6, 6, 45, 9, 30, 30, 29, 29, 30, 30, 29, 29, 32, 32, 38, 40, 32, 32, 38, 40, 5, 5, 43, 43, 5, 5, 3, 3, 47, 47, 51, 56, 47, 47, 55, 68, 30, 30, 29, 29, 30, 30, 29, 29, 4, 4, 42, 2, 4, 4, 42, 2, 5, 5, 43, 43, 5, 5, 3, 3, 15, 15, 53, 69, 15, 15, 70, 12)

    def regenerateGround(self, groundsprites):
        """
        Recalculate edge pieces for selected ground sprites (sprite 7)
        """
        # Make a list of all ground sprites in the level
        allGroundSprites = []
        for spr in self.sprites:
            if spr.type != 7: continue
            allGroundSprites.append(spr)

        for this in groundsprites:
            if not isinstance(this, SpriteItem): continue
            if this.type != 7: continue

            # Make a bitfield showing which edges are touching another
            # ground sprite:
            # 1 2 3
            # 4   5
            # 6 7 8
            edges = 0
            for other in allGroundSprites:

                xAlign, yAlign = 0, 0

                if this.objx - 16 <= other.objx < this.objx:
                    # To the left
                    xAlign = 1
                elif this.objx == other.objx:
                    # Horizontally-aligned
                    xAlign = 2
                elif this.objx < other.objx <= this.objx + 16:
                    # To the right
                    xAlign = 3

                if this.objy - 16 <= other.objy < this.objy:
                    # Below
                    yAlign = 3
                elif this.objy == other.objy:
                    # Vertically-aligned
                    yAlign = 2
                elif this.objy < other.objy <= this.objy + 16:
                    # Above
                    yAlign = 1

                # Depending on where the other tile is relative to this one,
                # OR-in a bit, flagging where it is
                if (xAlign, yAlign) == (1, 1): edges |= 128
                elif (xAlign, yAlign) == (2, 1): edges |= 64
                elif (xAlign, yAlign) == (3, 1): edges |= 32
                elif (xAlign, yAlign) == (1, 2): edges |= 16
                elif (xAlign, yAlign) == (3, 2): edges |= 8
                elif (xAlign, yAlign) == (1, 3): edges |= 4
                elif (xAlign, yAlign) == (2, 3): edges |= 2
                elif (xAlign, yAlign) == (3, 3): edges |= 1

            # Edges of the stage also count for ground edge-detection
            if this.objx <= SMM_X_MIN * 16:
                edges |= 0x94
            elif this.objx >= SMM_X_MAX * 16:
                edges |= 0x29
            if this.objy <= SMM_Y_MIN * 16:
                edges |= 0x07
            elif this.objy >= SMM_Y_MAX * 16:
                edges |= 0xE0

            # Splice the correct value into the sprite data
            this.spritedata = this.spritedata[:7] + bytes([self.TERRAIN_EDGES[edges]])

            # Update stuff
            this.UpdateDynamicSizing()
            this.UpdateListItem()
        SetDirty()




class ListWidgetItem_SortsByOther(QtWidgets.QListWidgetItem):
    """
    A ListWidgetItem that defers sorting to another object.
    """
    def __init__(self, reference, text=''):
        super().__init__(text)
        self.reference = reference
    def __lt__(self, other):
        return self.reference < other.reference


class Effect:
    """
    An effect you can place in your level.
    """
    def __init__(self, unk00, unk01, unk02, unk03, unk04):
        """
        Initializes the effect with the parameters given
        """
        self.unk00 = unk00
        self.unk01 = unk01
        self.unk02 = unk02
        self.unk03 = unk03
        self.unk04 = unk04


class CourseEditorItem(QtWidgets.QGraphicsItem):
    """
    Class for any type of item that can show up in the course editor control
    """
    positionChanged = None # Callback: positionChanged(CourseEditorItem obj, int oldx, int oldy, int x, int y)
    autoPosChange = False
    dragoffsetx = 0
    dragoffsety = 0

    def __init__(self):
        """
        Generic constructor for course editor items
        """
        super().__init__()
        self.setFlag(self.ItemSendsGeometryChanges, True)


    def __lt__(self, other):
        return (self.objx * 100000 + self.objy) < (other.objx * 100000 + other.objy)


    def getFullRect(self):
        """
        Basic implementation that returns self.BoundingRect
        """
        return self.BoundingRect.translated(self.pos())


    def UpdateListItem(self, updateTooltipPreview=False):
        """
        Updates the list item
        """
        if not hasattr(self, 'listitem'): return
        if self.listitem is None: return

        if updateTooltipPreview:
            # It's just like Qt to make this overly complicated. XP
            img = self.renderInCourseIcon()
            byteArray = QtCore.QByteArray()
            buf = QtCore.QBuffer(byteArray)
            img.save(buf, 'PNG')
            byteObj = bytes(byteArray)
            b64 = base64.b64encode(byteObj).decode('utf-8')

            self.listitem.setToolTip('<img src="data:image/png;base64,' + b64 + '" />')

        self.listitem.setText(self.ListString())


    def renderInCourseIcon(self):
        """
        Renders an icon of this item as it appears in the course
        """
        # Constants:
        # Maximum size of the preview (it will be shrunk if it exceeds this)
        maxSize = QtCore.QSize(256, 256)
        # Percentage of the size to use for margins
        marginPct = 0.75
        # Maximum margin (24 = 1 block)
        maxMargin = 96

        # Get the full bounding rectangle
        br = self.getFullRect()

        # Expand the rect to add extra margins around the edges
        marginX = br.width() * marginPct
        marginY = br.height() * marginPct
        marginX = min(marginX, maxMargin)
        marginY = min(marginY, maxMargin)
        br.setX(br.x() - marginX)
        br.setY(br.y() - marginY)
        br.setWidth(br.width() + marginX)
        br.setHeight(br.height() + marginY)

        # Take the screenshot
        ScreenshotImage = QtGui.QImage(br.width(), br.height(), QtGui.QImage.Format_ARGB32)
        ScreenshotImage.fill(Qt.transparent)

        RenderPainter = QtGui.QPainter(ScreenshotImage)
        mainWindow.scene.render(
            RenderPainter,
            QtCore.QRectF(0, 0, br.width(), br.height()),
            br,
            )
        RenderPainter.end()

        # Shrink it if it's too big
        final = ScreenshotImage
        if ScreenshotImage.width() > maxSize.width() or ScreenshotImage.height() > maxSize.height():
            final = ScreenshotImage.scaled(
                maxSize,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
                )

        return final

    def boundingRect(self):
        """
        Required for Qt
        """
        return self.BoundingRect


class SpriteItem(CourseEditorItem):
    """
    Course editor item that represents a sprite
    """
    BoundingRect = QtCore.QRectF(0, 0, TILE_WIDTH, TILE_WIDTH)
    SelectionRect = QtCore.QRectF(0, 0, TILE_WIDTH - 1, TILE_WIDTH - 1)
    ChangingPos = False

    # Default argument values are the ones the game uses
    def __init__(self,
        x=0, z=0, y=0,
        w=1, h=1,
        sprdata=DEFAULT_SPRITEDATA[:4], subsprdata=DEFAULT_SUBSPRITEDATA, sprdata2=DEFAULT_SPRITEDATA[4:],
        type_=0, subtype=-1,
        linkingid=-1, eff=None, costumeid=-1, subcostumeid=-1,
        ):
        """
        Create a sprite with specific data
        """
        super().__init__()
        self.setZValue(26000)

        self.objx = x
        self.objy = y
        self.objz = z
        self.width = w
        self.height = h
        self.spritedata = sprdata + sprdata2
        self.spritedata_sub = subsprdata
        self.type = type_
        self.type_sub = subtype
        self.linkingID = linkingid
        self.effect = eff
        self.costumeID = costumeid
        self.costumeID_sub = subcostumeid

        self.font = NumberFont
        self.listitem = None
        self.CourseRect = QtCore.QRectF(self.objx / 16, self.objy / 16, TILE_WIDTH / 16, TILE_WIDTH / 16)
        self.ChangingPos = False

        SLib.SpriteImage.loadImages()
        self.ImageObj = SLib.SpriteImage(self)

        try:
            sname = Sprites[type_].name
            self.name = sname
        except:
            self.name = 'UNKNOWN'

        self.InitializeSprite()

        self.setFlag(self.ItemIsMovable, not SpritesFrozen)
        self.setFlag(self.ItemIsSelectable, not SpritesFrozen)

        global DirtyOverride
        DirtyOverride += 1
        self.resetPos()
        DirtyOverride -= 1

    def SetType(self, type):
        """
        Sets the type of the sprite
        """
        self.type = type
        self.InitializeSprite()

    def ListString(self):
        """
        Returns a string that can be used to describe the sprite in a list
        """
        baseString = _('{name} (at {x}, {y})', 'name', self.name, 'x', self.objx, 'y', self.objy)
        return baseString

    def __lt__(self, other):
        # Sort by objx, then objy, then sprite type
        return (self.objx * 100000 + self.objy) * 1000 + self.type < (other.objx * 100000 + other.objy) * 1000 + other.type


    def InitializeSprite(self):
        """
        Initializes sprite and creates any auxiliary objects needed
        """
        global prefs

        type = self.type

        if type > len(Sprites): return

        self.name = Sprites[type].name
        self.setToolTip(_('<b>Sprite {type}:</b><br>{name}', 'type', self.type, 'name', self.name))
        self.UpdateListItem()

        imgs = sprites.ImageClasses
        if type in imgs:
            self.setImageObj(imgs[type])

    def setImageObj(self, obj):
        """
        Sets a new sprite image object for this SpriteItem
        """
        yorig = self.y()
        for auxObj in self.ImageObj.aux:
            if auxObj.scene() is None: continue
            auxObj.scene().removeItem(auxObj)

        self.setZValue(26000)
        self.resetTransform()

        if (self.type in sprites.ImageClasses) and (self.type not in SLib.SpriteImagesLoaded):
            sprites.ImageClasses[self.type].loadImages()
            SLib.SpriteImagesLoaded.add(self.type)

        self.ImageObj = obj(self)

        self.UpdateDynamicSizing()
        self.UpdateRects()
        self.ChangingPos = True
        self.resetPos()
        self.ChangingPos = False
        if self.scene() is not None: self.scene().update()

    def UpdateDynamicSizing(self):
        """
        Updates the sizes for dynamically sized sprites
        """
        CurrentRect = QtCore.QRectF(self.x(), self.y(), self.BoundingRect.width(), self.BoundingRect.height())
        CurrentAuxRects = []
        for auxObj in self.ImageObj.aux:
            CurrentAuxRects.append(QtCore.QRectF(
                auxObj.x() + self.x(),
                auxObj.y() + self.y(),
                auxObj.BoundingRect.width(),
                auxObj.BoundingRect.height(),
                ))

        self.ImageObj.dataChanged()
        self.ImageObj.sizeChanged()
        self.UpdateRects()

        self.ChangingPos = True
        self.resetPos()
        self.ChangingPos = False

        if self.scene() is not None:
            self.scene().update(CurrentRect)
            self.scene().update(self.x(), self.y(), self.BoundingRect.width(), self.BoundingRect.height())
            for auxUpdateRect in CurrentAuxRects:
                self.scene().update(auxUpdateRect)


    def UpdateRects(self):
        """
        Creates all the rectangles for the sprite
        """
        type = self.type

        self.prepareGeometryChange()

        # Get rects
        imgRect = QtCore.QRectF(
            0, 0,
            self.ImageObj.width * TILE_WIDTH / 16,
            self.ImageObj.height * TILE_WIDTH / 16,
            )
        spriteboxRect = QtCore.QRectF(
            0, 0,
            self.ImageObj.spritebox.BoundingRect.width(),
            self.ImageObj.spritebox.BoundingRect.height(),
            )
        imgOffsetRect = imgRect.translated(
            (self.objx + self.ImageObj.xOffset) * (TILE_WIDTH / 16),
            (self.objy + self.ImageObj.yOffset) * (TILE_WIDTH / 16),
            )
        spriteboxOffsetRect = spriteboxRect.translated(
            (self.objx * (TILE_WIDTH / 16)) + self.ImageObj.spritebox.BoundingRect.topLeft().x(),
            (self.objy * (TILE_WIDTH / 16)) + self.ImageObj.spritebox.BoundingRect.topLeft().y(),
            )

        if SpriteImagesShown:
            unitedRect = imgRect.united(spriteboxRect)
            unitedOffsetRect = imgOffsetRect.united(spriteboxOffsetRect)

            # SelectionRect: Used to determine the size of the
            # "this sprite is selected" translucent white box that
            # appears when a sprite with an image is selected.
            self.SelectionRect = QtCore.QRectF(
                0, 0,
                imgRect.width() - 1,
                imgRect.height() - 1,
                )

            # CourseRect: Used by the Course Overview to determine
            # the size and position of the sprite in the course.
            # Measured in blocks.
            self.CourseRect = QtCore.QRectF(
                unitedOffsetRect.topLeft().x() / TILE_WIDTH,
                unitedOffsetRect.topLeft().y() / TILE_WIDTH,
                unitedOffsetRect.width() / TILE_WIDTH,
                unitedOffsetRect.height() / TILE_WIDTH,
                )

            # BoundingRect: The sprite can only paint within
            # this area.
            self.BoundingRect = unitedRect.translated(
                self.ImageObj.spritebox.BoundingRect.topLeft().x(),
                self.ImageObj.spritebox.BoundingRect.topLeft().y(),
                )

        else:
            self.SelectionRect = QtCore.QRectF(0, 0, TILE_WIDTH, TILE_WIDTH)

            self.CourseRect = QtCore.QRectF(
                spriteboxOffsetRect.topLeft().x() / TILE_WIDTH,
                spriteboxOffsetRect.topLeft().y() / TILE_WIDTH,
                spriteboxOffsetRect.width() / TILE_WIDTH,
                spriteboxOffsetRect.height() / TILE_WIDTH,
                )

            # BoundingRect: The sprite can only paint within
            # this course.
            self.BoundingRect = spriteboxRect.translated(
                self.ImageObj.spritebox.BoundingRect.topLeft().x(),
                self.ImageObj.spritebox.BoundingRect.topLeft().y(),
                )


    def getFullRect(self):
        """
        Returns a rectangle that contains the sprite and all
        auxiliary objects.
        """
        self.UpdateRects()

        br = self.BoundingRect.translated(
            self.x(),
            self.y(),
            )
        for aux in self.ImageObj.aux:
            br = br.united(
                aux.BoundingRect.translated(
                    aux.x() + self.x(),
                    aux.y() + self.y(),
                    )
                )

        return br


    def setStdPos(self, x, y):
        """
        Sets objx and objy to x and y, and then updates the sprite's position in the scene
        """
        self.objx, self.objy = x, y
        self.resetPos()


    def resetPos(self):
        """
        Resets the Qt position of this sprite
        """
        x, y = self.objx, self.objy
        if SpriteImagesShown:
            x += self.ImageObj.xOffset
            y += self.ImageObj.yOffset

        h = self.ImageObj.height if SpriteImagesShown else 16

        self.setPos(
            int(x * TILE_WIDTH / 16),
            -int((y + h) * TILE_WIDTH / 16),
        )


    def itemChange(self, change, value):
        """
        Makes sure positions don't go out of bounds and updates them as necessary.
        This HAS TO TAKE positions in Qt form! Because Qt calls it automatically!
        This means:
        - Y position should usually be negative
        - Y position must map to the TOP of the sprite
        """
        tileWidthMult = TILE_WIDTH / 16
        if change == QtWidgets.QGraphicsItem.ItemPositionChange:
            if self.scene() is None: return value
            if self.ChangingPos: return value

            # Convert Qt-style Y coord to SMM-style
            y = value.y()
            y = -y
            h = self.ImageObj.height * TILE_WIDTH / 16 if SpriteImagesShown else TILE_WIDTH
            y -= h
            value.setY(y)

            if SpriteImagesShown:
                xOffset, xOffsetAdjusted = self.ImageObj.xOffset, self.ImageObj.xOffset * tileWidthMult
                yOffset, yOffsetAdjusted = self.ImageObj.yOffset, self.ImageObj.yOffset * tileWidthMult
            else:
                xOffset, xOffsetAdjusted = 0, 0
                yOffset, yOffsetAdjusted = 0, 0

            # snap to 24x24
            newpos = value

            # snap even further if Shift isn't held
            # but -only- if OverrideSnapping is off
            if not OverrideSnapping:
                if QtWidgets.QApplication.keyboardModifiers() == Qt.AltModifier:
                    # Alt is held; don't snap
                    newpos.setX((int((newpos.x() + 0.75) / tileWidthMult) * tileWidthMult))
                    newpos.setY((int((newpos.y() + 0.75) / tileWidthMult) * tileWidthMult))
                else:
                    # Snap to 8x8
                    newpos.setX(int(int((newpos.x() + (TILE_WIDTH / 4) - xOffsetAdjusted) / (TILE_WIDTH / 2)) * (TILE_WIDTH / 2) + xOffsetAdjusted))
                    newpos.setY(int(int((newpos.y() + (TILE_WIDTH / 4) - yOffsetAdjusted) / (TILE_WIDTH / 2)) * (TILE_WIDTH / 2) + yOffsetAdjusted))

            x = newpos.x()
            y = newpos.y()

            # don't let it get out of the boundaries
            if x < X_MIN * TILE_WIDTH: newpos.setX(X_MIN * TILE_WIDTH)
            if x > X_MAX * TILE_WIDTH: newpos.setX(X_MAX * TILE_WIDTH)
            if y < Y_MIN * TILE_WIDTH: newpos.setY(Y_MIN * TILE_WIDTH)
            if y > Y_MAX * TILE_WIDTH: newpos.setY(Y_MAX * TILE_WIDTH)

            # update the data
            x = int(newpos.x() / tileWidthMult - xOffset)
            y = int(newpos.y() / tileWidthMult - yOffset)

            if x != self.objx or y != self.objy:
                updRect = QtCore.QRectF(self.x(), self.y(), self.BoundingRect.width(), self.BoundingRect.height())
                self.scene().update(updRect)

                self.CourseRect.moveTo((x + xOffset) / 16, (y + yOffset) / 16)

                for auxObj in self.ImageObj.aux:
                    auxUpdRect = QtCore.QRectF(
                        self.x() + auxObj.x(),
                        self.y() + auxObj.y(),
                        auxObj.BoundingRect.width(),
                        auxObj.BoundingRect.height(),
                        )
                    self.scene().update(auxUpdRect)

                self.scene().update(
                    self.x() + self.ImageObj.spritebox.BoundingRect.topLeft().x(),
                    self.y() + self.ImageObj.spritebox.BoundingRect.topLeft().y(),
                    self.ImageObj.spritebox.BoundingRect.width(),
                    self.ImageObj.spritebox.BoundingRect.height(),
                    )

                oldx = self.objx
                oldy = self.objy
                self.objx = x
                self.objy = y
                if self.positionChanged is not None:
                    self.positionChanged(self, oldx, oldy, x, y)

                self.ImageObj.positionChanged()

                SetDirty()

            # And now convert SMM-style Y coord back to Qt-style
            y = newpos.y()
            y += h
            y = -y
            newpos.setY(y)

            return newpos

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Overrides mouse pressing events if needed for cloning
        """
        if event.button() == Qt.LeftButton:
            if QtWidgets.QApplication.keyboardModifiers() == Qt.ControlModifier:
                if self.effect is not None:
                    neweff = Effect(
                        self.effect.unk00,
                        self.effect.unk01,
                        self.effect.unk02,
                        self.effect.unk03,
                        self.effect.unk04,
                        )
                newitem = SpriteItem(
                    self.objz, self.objx, self.objy,
                    self.width, self.height,
                    self.spritedata[:4], self.spritedata_sub, self.spritedata[4:],
                    self.type, self.type_sub,
                    self.linkingID, neweff if self.effect is not None else None,
                    self.costumeID, self.costumeID_sub,
                    )
                newitem.listitem = ListWidgetItem_SortsByOther(newitem, newitem.ListString())
                mainWindow.spriteList.addItem(newitem.listitem)
                Course.sprites.append(newitem)
                mainWindow.scene.addItem(newitem)
                mainWindow.scene.clearSelection()
                self.setSelected(True)
                newitem.UpdateListItem()
                SetDirty()
                return

        super().mousePressEvent(event)


    def updateScene(self):
        """
        Calls self.scene().update()
        """
        # Some of the more advanced painters need to update the whole scene
        # and this is a convenient way to do it:
        # self.parent.updateScene()
        if self.scene() is not None: self.scene().update()


    def paint(self, painter, option=None, widget=None, overrideGlobals=False):
        """
        Paints the sprite
        """

        # Setup stuff
        if option is not None:
            painter.setClipRect(option.exposedRect)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Turn aux things on or off
        for aux in self.ImageObj.aux:
            aux.setVisible(SpriteImagesShown)

        # Default spritebox
        drawSpritebox = True
        spriteboxRect = QtCore.QRectF(0, 0, TILE_WIDTH, TILE_WIDTH)

        if SpriteImagesShown or overrideGlobals:
            self.ImageObj.paint(painter)

            drawSpritebox = self.ImageObj.spritebox.shown

            # Determine the spritebox position
            if drawSpritebox:
                spriteboxRect = self.ImageObj.spritebox.RoundedRect

            # Let the image object paint a little icon for a subsprite, if necessary
            self.ImageObj.paintSub(painter, spriteboxRect if drawSpritebox else self.SelectionRect)

            # Draw the selected-sprite-image overlay box
            if self.isSelected() and (not drawSpritebox or self.ImageObj.size != (16, 16)):
                painter.setPen(QtGui.QPen(_c('sprite_lines_s'), 1, Qt.DotLine))
                painter.drawRect(self.SelectionRect)
                painter.fillRect(self.SelectionRect, _c('sprite_fill_s'))



        # Draw the spritebox if applicable
        if drawSpritebox:
            if self.isSelected():
                painter.setBrush(QtGui.QBrush(_c('spritebox_fill_s')))
                painter.setPen(QtGui.QPen(_c('spritebox_lines_s'), 1 / 24 * TILE_WIDTH))
            else:
                painter.setBrush(QtGui.QBrush(_c('spritebox_fill')))
                painter.setPen(QtGui.QPen(_c('spritebox_lines'), 1 / 24 * TILE_WIDTH))
            painter.drawRect(spriteboxRect)

            painter.setFont(self.font)
            painter.drawText(spriteboxRect, Qt.AlignCenter, str(self.type))


    def scene(self):
        """
        Solves a small bug
        """
        return mainWindow.scene

    def delete(self):
        """
        Delete the sprite from the course
        """
        sprlist = mainWindow.spriteList
        mainWindow.UpdateFlag = True
        sprlist.takeItem(sprlist.row(self.listitem))
        mainWindow.UpdateFlag = False
        sprlist.selectionModel().clearSelection()
        Course.sprites.remove(self)



class CourseOverviewWidget(QtWidgets.QWidget):
    """
    Widget that shows an overview of the course and can be clicked to move the view
    """
    moveIt = QtCore.pyqtSignal(int, int)

    def __init__(self):
        """
        Constructor for the course overview widget
        """
        super().__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding))

        self.bgbrush = QtGui.QBrush(_c('bg'))
        self.spritebrush = QtGui.QBrush(_c('overview_sprite'))

        self.scale = 0.375
        self.maxX = 1
        self.maxY = 1
        self.Rescale()

        self.Xposlocator = 0
        self.Yposlocator = 0
        self.Hlocator = 50
        self.Wlocator = 80
        self.mainWindowScale = 1

    def mouseMoveEvent(self, event):
        """
        Handles mouse movement over the widget
        """
        super().mouseMoveEvent(event)

        if event.buttons() == Qt.LeftButton:
            self.moveIt.emit(event.pos().x() * self.posmult, event.pos().y() * self.posmult - Y_MAX * TILE_WIDTH)

    def mousePressEvent(self, event):
        """
        Handles mouse pressing events over the widget
        """
        super().mousePressEvent(event)

        if event.button() == Qt.LeftButton:
            self.moveIt.emit(event.pos().x() * self.posmult, event.pos().y() * self.posmult - Y_MAX * TILE_WIDTH)

    def paintEvent(self, event):
        """
        Paints the course overview widget
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Hax: Draw complete background, draw OOB highlight, redraw background for in-bounds course :D

        # Draw BG and out-of-bounds highlight
        painter.fillRect(event.rect(), self.bgbrush)
        painter.fillRect(event.rect(), QtGui.QBrush(_c('outofbounds')))

        # Rescale
        self.Rescale()
        painter.scale(self.scale, self.scale)

        # Redraw the in-bounds course
        painter.fillRect(QtCore.QRect(0, 0, X_MAX + 1, Y_MAX - Y_MIN + 1), self.bgbrush)

        # Draw sprites
        for sprite in Course.sprites:
            r = QtCore.QRectF(sprite.CourseRect)
            r.moveTo(r.x(), Y_MAX - (r.y() + r.height()))
            painter.fillRect(r, self.spritebrush)

        # Draw grid
        painter.setPen(QtGui.QPen(_c('grid'), 0.3))
        for y in range(0, Y_MAX + 1, 8):
            painter.drawLine(X_MIN, Y_MAX - y, X_MAX + 1, Y_MAX - y)
        for x in range(X_MIN, X_MAX + 1, 8):
            painter.drawLine(x, 0, x, Y_MAX - Y_MIN + 1)

        # Draw viewbox
        painter.setPen(QtGui.QPen(_c('overview_viewbox'), 1))
        painter.drawRect(
            self.Xposlocator/TILE_WIDTH/self.mainWindowScale,
            Y_MAX - (self.Yposlocator/TILE_WIDTH/self.mainWindowScale),
            self.Wlocator/TILE_WIDTH/self.mainWindowScale,
            self.Hlocator/TILE_WIDTH/self.mainWindowScale,
            )


    def Rescale(self):
        """
        Recalculates the proper scale and position multiplier
        """
        Xscale = self.width() / float(X_MAX - X_MIN + 1)
        Yscale = self.height() / float(Y_MAX - Y_MIN + 1)

        self.scale = min([Xscale, Yscale])

        self.posmult = TILE_WIDTH / self.scale


class SpritePickerWidget(QtWidgets.QTreeWidget):
    """
    Widget that shows a list of available sprites
    """
    def __init__(self):
        """
        Initializes the widget
        """
        super().__init__()
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.currentItemChanged.connect(self.HandleItemChange)

        LoadSpriteData()
        LoadSpriteCategories()
        self.LoadItems()

    def LoadItems(self):
        """
        Loads tree widget items
        """
        self.clear()

        for viewname, view, nodelist in SpriteCategories:
            for n in nodelist: nodelist.remove(n)
            for catname, category in view:
                cnode = QtWidgets.QTreeWidgetItem()
                cnode.setText(0, catname)
                cnode.setData(0, Qt.UserRole, -1)

                isSearch = (catname == _('Search Results'))
                if isSearch:
                    self.SearchResultsCategory = cnode
                    SearchableItems = []

                for id in category:
                    snode = QtWidgets.QTreeWidgetItem()
                    if id == 9999:
                        snode.setText(0, _('No sprites found'))
                        snode.setData(0, Qt.UserRole, -2)
                        self.NoSpritesFound = snode
                    else:
                        snode.setText(0, _('{id}: {name}', 'id', id, 'name', Sprites[id].name))
                        snode.setData(0, Qt.UserRole, id)

                    if isSearch:
                        SearchableItems.append(snode)

                    cnode.addChild(snode)

                self.addTopLevelItem(cnode)
                cnode.setHidden(True)
                nodelist.append(cnode)

        self.ShownSearchResults = SearchableItems
        self.NoSpritesFound.setHidden(True)

        self.itemClicked.connect(self.HandleSprReplace)


    def SwitchView(self, view):
        """
        Changes the selected sprite view
        """
        for i in range(self.topLevelItemCount()):
            self.topLevelItem(i).setHidden(True)

        for node in view[2]:
            node.setHidden(False)


    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, QtWidgets.QTreeWidgetItem)
    def HandleItemChange(self, current, previous):
        """
        Throws a signal when the selected sprite changed
        """
        if current is None: return
        id = current.data(0, Qt.UserRole)
        if id != -1:
            self.SpriteChanged.emit(id)


    def SetSearchString(self, searchfor):
        """
        Shows the items containing that string
        """
        check = self.SearchResultsCategory

        rawresults = self.findItems(searchfor, Qt.MatchContains | Qt.MatchRecursive)
        results = list(filter((lambda x: x.parent() == check), rawresults))

        for x in self.ShownSearchResults: x.setHidden(True)
        for x in results: x.setHidden(False)
        self.ShownSearchResults = results

        self.NoSpritesFound.setHidden((len(results) != 0))
        self.SearchResultsCategory.setExpanded(True)


    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def HandleSprReplace(self, item, column):
        """
        Throws a signal when the selected sprite is used as a replacement
        """
        if QtWidgets.QApplication.keyboardModifiers() == Qt.AltModifier:
            id = item.data(0, Qt.UserRole)
            if id != -1:
                self.SpriteReplace.emit(id)

    SpriteChanged = QtCore.pyqtSignal(int)
    SpriteReplace = QtCore.pyqtSignal(int)



class RawDataEditorWidget(QtWidgets.QLineEdit):
    """
    Widget for editing raw sprite data
    """
    dataChanged = QtCore.pyqtSignal('PyQt_PyObject')

    def __init__(self, len, *args):
        """
        len is the length of the sprite data, in bytes (nybbles * 2)
        """
        super().__init__(*args)
        self.len = len
        self.textEdited.connect(self._handleTextChange)
        self.data = b'\0' * len

        self.setText(self.getFmtStr() % ((0,) * len))

    def getFmtStr(self):
        return ('%02x%02x ' * (self.len // 2))[:-1] + ('%02x' * (self.len % 2))

    def updateContents(self, newdata):
        vals = [val for val in newdata]
        self.setText(self.getFmtStr() % tuple(vals))
        self.setStyleSheet('')
        self.data = newdata
        self.dataChanged.emit(newdata)

    def _handleTextChange(self):
        raw = self.text().replace(' ', '')
        valid = False

        if len(raw) == self.len * 2:
            try:
                data = []
                for r in range(0, len(raw), 2):
                    data.append(int(raw[r:r+2], 16))
                data = bytes(data)
                valid = True
            except Exception: pass

        # if it's valid, let it go
        if valid:
            self.data = data

            self.setStyleSheet('')

            self.dataChanged.emit(data)
        else:
            self.setStyleSheet('QLineEdit { background-color: #ffd2d2; }')



class SpriteEditorWidget(QtWidgets.QWidget):
    """
    Widget for editing sprite data
    """
    DataUpdate = QtCore.pyqtSignal('PyQt_PyObject')

    data = DEFAULT_SPRITEDATA
    subdata = DEFAULT_SUBSPRITEDATA
    width = 1
    height = 1
    linkingId = -1
    useEff = False
    effUnk00 = -1
    effUnk01 = -1
    effUnk02 = 0
    effUnk03 = -1
    effUnk04 = -1
    costumeId = -1
    costumeId_sub = -1

    def __init__(self, defaultmode=False):
        """
        Constructor
        """
        super().__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed))

        # Create the raw editors
        font = QtGui.QFont()
        font.setPointSize(8)

        editbox = QtWidgets.QLabel(_('Modify Raw Data:'))
        editbox.setFont(font)
        edit = RawDataEditorWidget(8)
        edit.dataChanged.connect(lambda x: self.HandleRawDataEdited(x, False))
        self.raweditor = edit

        editboxlayout = QtWidgets.QHBoxLayout()
        editboxlayout.addWidget(editbox)
        editboxlayout.addWidget(edit)
        editboxlayout.setStretch(1, 1)

        # 'Editing Sprite #' label
        self.spriteLabel = QtWidgets.QLabel('-')
        self.spriteLabel.setWordWrap(True)

        self.noteButton = QtWidgets.QToolButton()
        self.noteButton.setIcon(GetIcon('note'))
        self.noteButton.setText(_('Notes'))
        self.noteButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.noteButton.setAutoRaise(True)
        self.noteButton.clicked.connect(self.ShowNoteTooltip)

        topLayout = QtWidgets.QHBoxLayout()
        topLayout.addWidget(self.spriteLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(self.noteButton)

        subLayout = QtWidgets.QVBoxLayout()
        subLayout.setContentsMargins(0, 0, 0, 0)

        # Non-specific sprite options

        self.widthEdit = QtWidgets.QSpinBox()
        self.widthEdit.setMinimum(-128)
        self.widthEdit.setMaximum(127)
        self.widthEdit.valueChanged.connect(self.HandleOptionsChanged)

        self.heightEdit = QtWidgets.QSpinBox()
        self.heightEdit.setMinimum(-128)
        self.heightEdit.setMaximum(127)
        self.heightEdit.valueChanged.connect(self.HandleOptionsChanged)

        self.zPosEdit = QtWidgets.QSpinBox()
        self.zPosEdit.setMinimum(0)
        self.zPosEdit.setMaximum(0x7FFFFFFF) # really 0xFFFFFFFF, but Qt's maximum value is limited. See:
                                             # http://comments.gmane.org/gmane.comp.lib.qt.general/10012
        self.zPosEdit.valueChanged.connect(self.HandleOptionsChanged)

        self.linkingIdEdit = QtWidgets.QSpinBox()
        self.linkingIdEdit.setMinimum(-32768)
        self.linkingIdEdit.setMaximum(32767)
        self.linkingIdEdit.valueChanged.connect(self.HandleOptionsChanged)

        self.useEffEdit = QtWidgets.QCheckBox(_('Effect'))
        self.useEffEdit.clicked.connect(self.HandleOptionsChanged)
        self.effUnk00Edit = QtWidgets.QSpinBox()
        self.effUnk00Edit.setMinimum(-128)
        self.effUnk00Edit.setMaximum(127)
        self.effUnk00Edit.valueChanged.connect(self.HandleOptionsChanged)
        self.effUnk01Edit = QtWidgets.QSpinBox()
        self.effUnk01Edit.setMinimum(-128)
        self.effUnk01Edit.setMaximum(127)
        self.effUnk01Edit.valueChanged.connect(self.HandleOptionsChanged)
        self.effUnk02Edit = QtWidgets.QSpinBox()
        self.effUnk02Edit.setMinimum(-128)
        self.effUnk02Edit.setMaximum(127)
        self.effUnk02Edit.valueChanged.connect(self.HandleOptionsChanged)
        self.effUnk03Edit = QtWidgets.QSpinBox()
        self.effUnk03Edit.setMinimum(-128)
        self.effUnk03Edit.setMaximum(127)
        self.effUnk03Edit.valueChanged.connect(self.HandleOptionsChanged)
        self.effUnk04Edit = QtWidgets.QSpinBox()
        self.effUnk04Edit.setMinimum(-128)
        self.effUnk04Edit.setMaximum(127)
        self.effUnk04Edit.valueChanged.connect(self.HandleOptionsChanged)

        self.costumeIdEdit = QtWidgets.QSpinBox()
        self.costumeIdEdit.setMinimum(-128)
        self.costumeIdEdit.setMaximum(127)
        self.costumeIdEdit.valueChanged.connect(self.HandleOptionsChanged)

        optionsLayout1 = QtWidgets.QFormLayout()
        optionsLayout1.addRow(_('Width:'), self.widthEdit)
        optionsLayout1.addRow(_('Height:'), self.heightEdit)
        optionsLayout1.addRow(_('Z-position:'), self.zPosEdit)
        optionsLayout1.addRow(_('Linking ID:'), self.linkingIdEdit)
        optionsLayout1.addRow(_('Costume ID:'), self.costumeIdEdit)
        optionsLayout1.addWidget(self.useEffEdit)
        optionsLayout2 = QtWidgets.QFormLayout()
        optionsLayout2.addRow(_('Unknown Effect Value 0x00:'), self.effUnk00Edit)
        optionsLayout2.addRow(_('Unknown Effect Value 0x01:'), self.effUnk01Edit)
        optionsLayout2.addRow(_('Unknown Effect Value 0x02:'), self.effUnk02Edit)
        optionsLayout2.addRow(_('Unknown Effect Value 0x03:'), self.effUnk03Edit)
        optionsLayout2.addRow(_('Unknown Effect Value 0x04:'), self.effUnk04Edit)
        optionsLayout = QtWidgets.QHBoxLayout()
        optionsLayout.addLayout(optionsLayout1)
        optionsLayout.addLayout(optionsLayout2)

        # Subsprite stuff

        editbox_sub = QtWidgets.QLabel(_('Modify Raw Data:'))
        editbox_sub.setFont(font)
        edit_sub = RawDataEditorWidget(4)
        edit_sub.dataChanged.connect(lambda x: self.HandleRawDataEdited(x, True))
        self.raweditor_sub = edit_sub

        editboxlayout_sub = QtWidgets.QHBoxLayout()
        editboxlayout_sub.addWidget(editbox_sub)
        editboxlayout_sub.addWidget(edit_sub)
        editboxlayout_sub.setStretch(1, 1)

        self.spriteLabel_sub_1 = QtWidgets.QLabel(_('<b>Subsprite</b>'))
        self.spriteNum_sub = QtWidgets.QSpinBox()
        self.spriteNum_sub.setMinimum(-1)
        self.spriteNum_sub.setMaximum(len(Sprites) - 1)
        self.spriteNum_sub.valueChanged.connect(self.HandleOptionsChanged)
        self.spriteLabel_sub_2 = QtWidgets.QLabel(_('<b>: -</b>'))

        self.noteButton_sub = QtWidgets.QToolButton()
        self.noteButton_sub.setIcon(GetIcon('note'))
        self.noteButton_sub.setText(_('Notes'))
        self.noteButton_sub.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.noteButton_sub.setAutoRaise(True)
        self.noteButton_sub.clicked.connect(self.ShowNoteTooltip)

        topLayout_sub = QtWidgets.QHBoxLayout()
        topLayout_sub.addWidget(self.spriteLabel_sub_1)
        topLayout_sub.addWidget(self.spriteNum_sub)
        topLayout_sub.addWidget(self.spriteLabel_sub_2)
        topLayout_sub.addStretch(1)
        topLayout_sub.addWidget(self.noteButton_sub)

        subLayout_sub = QtWidgets.QVBoxLayout()
        subLayout_sub.setContentsMargins(0, 0, 0, 0)

        self.costumeIdEdit_sub = QtWidgets.QSpinBox()
        self.costumeIdEdit_sub.setMinimum(-128)
        self.costumeIdEdit_sub.setMaximum(127)
        self.costumeIdEdit_sub.valueChanged.connect(self.HandleOptionsChanged)

        optionsLayout_sub = QtWidgets.QFormLayout()
        optionsLayout_sub.addRow(_('Costume ID:'), self.costumeIdEdit_sub)

        # Layout stuff

        controlsLayout = QtWidgets.QGridLayout()
        self.editorlayout = controlsLayout

        subLayout.addLayout(optionsLayout)
        subLayout.addWidget(createHorzLine())
        subLayout.addLayout(controlsLayout)
        subLayout.addLayout(editboxlayout)

        controlsLayout_sub = QtWidgets.QGridLayout()
        self.editorlayout_sub = controlsLayout_sub
        subLayout_sub.addLayout(optionsLayout_sub)
        subLayout_sub.addWidget(createHorzLine())
        subLayout_sub.addLayout(controlsLayout_sub)
        subLayout_sub.addLayout(editboxlayout_sub)

        # create a layout
        mainLayout = QtWidgets.QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0)
        mainLayout.addLayout(subLayout, 1, 0)
        mainLayout.addWidget(createVertLine(), 0, 1, 2, 1)
        mainLayout.addLayout(topLayout_sub, 0, 2)
        mainLayout.addLayout(subLayout_sub, 1, 2)
        # Making this work better would be good:
        # mainLayoutL = QtWidgets.QVBoxLayout()
        # mainLayoutL.addLayout(topLayout)
        # mainLayoutL.addLayout(subLayout)
        # mainLayoutR = QtWidgets.QVBoxLayout()
        # mainLayoutR.addLayout(topLayout_sub)
        # mainLayoutR.addLayout(subLayout_sub)
        # mainLayout = QtWidgets.QHBoxLayout()
        # mainLayout.addLayout(mainLayoutL)
        # mainLayout.addWidget(createVertLine())
        # mainLayout.addLayout(mainLayoutR)

        self.setLayout(mainLayout)

        self.spritetype = -1
        self.data = DEFAULT_SPRITEDATA
        self.fields = []
        self.subspritetype = -1
        self.subdata = DEFAULT_SUBSPRITEDATA
        self.subfields = []
        self.UpdateFlag = False
        self.DefaultMode = defaultmode

        self.notes = None
        self.notes_sub = None


    class PropertyDecoder(QtCore.QObject):
        """
        Base class for all the sprite data decoder/encoders
        """
        updateData = QtCore.pyqtSignal('PyQt_PyObject')

        def __init__(self):
            """
            Generic constructor
            """
            super().__init__()

        def retrieve(self, data):
            """
            Extracts the value from the specified nybble(s)
            """
            nybble = self.nybble

            if isinstance(nybble, tuple):
                if nybble[1] == (nybble[0] + 2) and (nybble[0] | 1) == 0:
                    # optimize if it's just one byte
                    return data[nybble[0] >> 1]
                else:
                    # we have to calculate it sadly
                    # just do it by looping, shouldn't be that bad
                    value = 0
                    for n in range(nybble[0], nybble[1]):
                        value <<= 4
                        value |= (data[n >> 1] >> (0 if (n & 1) == 1 else 4)) & 15
                    return value
            else:
                # we just want one nybble
                if nybble >= (len(data) * 2): return 0
                return (data[nybble//2] >> (0 if (nybble & 1) == 1 else 4)) & 15


        def insertvalue(self, data, value):
            """
            Assigns a value to the specified nybble(s)
            """
            nybble = self.nybble
            sdata = list(data)

            if isinstance(nybble, tuple):
                if nybble[1] == (nybble[0] + 2) and (nybble[0] | 1) == 0:
                    # just one byte, this is easier
                    sdata[nybble[0] >> 1] = value & 255
                else:
                    # AAAAAAAAAAA
                    for n in reversed(range(nybble[0], nybble[1])):
                        cbyte = sdata[n >> 1]
                        if (n & 1) == 1:
                            cbyte = (cbyte & 240) | (value & 15)
                        else:
                            cbyte = ((value & 15) << 4) | (cbyte & 15)
                        sdata[n >> 1] = cbyte
                        value >>= 4
            else:
                # only overwrite one nybble
                cbyte = sdata[nybble >> 1]
                if (nybble & 1) == 1:
                    cbyte = (cbyte & 240) | (value & 15)
                else:
                    cbyte = ((value & 15) << 4) | (cbyte & 15)
                sdata[nybble >> 1] = cbyte

            return bytes(sdata)


    class CheckboxPropertyDecoder(PropertyDecoder):
        """
        Class that decodes/encodes sprite data to/from a checkbox
        """

        def __init__(self, title, nybble, mask, comment, layout, row):
            """
            Creates the widget
            """
            super().__init__()

            self.widget = QtWidgets.QCheckBox(title)
            if comment is not None: self.widget.setToolTip(comment)
            self.widget.clicked.connect(self.HandleClick)

            if isinstance(nybble, tuple):
                length = nybble[1] - nybble[0] + 1
            else:
                length = 1

            xormask = 0
            for i in range(length):
                xormask |= 0xF << (i * 4)

            self.nybble = nybble
            self.mask = mask
            self.xormask = xormask
            layout.addWidget(self.widget, row, 0, 1, 2)

        def update(self, data):
            """
            Updates the value shown by the widget
            """
            value = ((self.retrieve(data) & self.mask) == self.mask)
            self.widget.setChecked(value)

        def assign(self, data):
            """
            Assigns the selected value to the data
            """
            value = self.retrieve(data) & (self.mask ^ self.xormask)
            if self.widget.isChecked():
                value |= self.mask
            return self.insertvalue(data, value)

        @QtCore.pyqtSlot(bool)
        def HandleClick(self, clicked=False):
            """
            Handles clicks on the checkbox
            """
            self.updateData.emit(self)


    class ListPropertyDecoder(PropertyDecoder):
        """
        Class that decodes/encodes sprite data to/from a combobox
        """

        def __init__(self, title, nybble, model, comment, layout, row):
            """
            Creates the widget
            """
            super().__init__()

            self.model = model
            self.widget = QtWidgets.QComboBox()
            self.widget.setModel(model)
            if comment is not None: self.widget.setToolTip(comment)
            self.widget.currentIndexChanged.connect(self.HandleIndexChanged)

            self.nybble = nybble
            layout.addWidget(QtWidgets.QLabel(title+':'), row, 0, Qt.AlignRight)
            layout.addWidget(self.widget, row, 1)

        def update(self, data):
            """
            Updates the value shown by the widget
            """
            value = self.retrieve(data)
            if not self.model.existingLookup[value]:
                self.widget.setCurrentIndex(-1)
                return

            i = 0
            for x in self.model.entries:
                if x[0] == value:
                    self.widget.setCurrentIndex(i)
                    break
                i += 1

        def assign(self, data):
            """
            Assigns the selected value to the data
            """
            return self.insertvalue(data, self.model.entries[self.widget.currentIndex()][0])

        @QtCore.pyqtSlot(int)
        def HandleIndexChanged(self, index):
            """
            Handle the current index changing in the combobox
            """
            self.updateData.emit(self)


    class ValuePropertyDecoder(PropertyDecoder):
        """
        Class that decodes/encodes sprite data to/from a spinbox
        """

        def __init__(self, title, nybble, max, comment, layout, row):
            """
            Creates the widget
            """
            super().__init__()

            self.widget = QtWidgets.QSpinBox()
            self.widget.setRange(0, max - 1)
            if comment is not None: self.widget.setToolTip(comment)
            self.widget.valueChanged.connect(self.HandleValueChanged)

            self.nybble = nybble
            layout.addWidget(QtWidgets.QLabel(title + ':'), row, 0, Qt.AlignRight)
            layout.addWidget(self.widget, row, 1)

        def update(self, data):
            """
            Updates the value shown by the widget
            """
            value = self.retrieve(data)
            self.widget.setValue(value)

        def assign(self, data):
            """
            Assigns the selected value to the data
            """
            return self.insertvalue(data, self.widget.value())

        @QtCore.pyqtSlot(int)
        def HandleValueChanged(self, value):
            """
            Handle the value changing in the spinbox
            """
            self.updateData.emit(self)


    class BitfieldPropertyDecoder(PropertyDecoder):
        """
        Class that decodes/encodes sprite data to/from a bitfield
        """

        def __init__(self, title, startbit, bitnum, comment, layout, row):
            """
            Creates the widget
            """
            super().__init__()

            self.startbit = startbit
            self.bitnum = bitnum

            self.widgets = []
            CheckboxLayout = QtWidgets.QGridLayout()
            CheckboxLayout.setContentsMargins(0, 0, 0, 0)
            for i in range(bitnum):
                c = QtWidgets.QCheckBox()
                self.widgets.append(c)
                CheckboxLayout.addWidget(c, 0, i)
                if comment is not None: c.setToolTip(comment)
                c.toggled.connect(self.HandleValueChanged)

                L = QtWidgets.QLabel(str(i + 1))
                CheckboxLayout.addWidget(L, 1, i)
                CheckboxLayout.setAlignment(L, Qt.AlignHCenter)

            w = QtWidgets.QWidget()
            w.setLayout(CheckboxLayout)

            layout.addWidget(QtWidgets.QLabel(_('{title}:', 'title', title)), row, 0, Qt.AlignRight)
            layout.addWidget(w, row, 1)

        def update(self, data):
            """
            Updates the value shown by the widget
            """
            for bitIdx in range(self.bitnum):
                checkbox = self.widgets[bitIdx]

                adjustedIdx = bitIdx + self.startbit
                byteNum = adjustedIdx // 8
                bitNum = adjustedIdx % 8
                checkbox.setChecked((data[byteNum] >> (7 - bitNum) & 1))

        def assign(self, data):
            """
            Assigns the checkbox states to the data
            """
            data = bytearray(data)

            for idx in range(self.bitnum):
                checkbox = self.widgets[idx]

                adjustedIdx = idx + self.startbit
                byteIdx = adjustedIdx // 8
                bitIdx = adjustedIdx % 8

                origByte = data[byteIdx]
                origBit = (origByte >> (7 - bitIdx)) & 1
                newBit = 1 if checkbox.isChecked() else 0

                if origBit == newBit: continue
                if origBit == 0 and newBit == 1:
                    # Turn the byte on by OR-ing it in
                    newByte = (origByte | (1 << (7 - bitIdx))) & 0xFF
                else:
                    # Turn it off by:
                    # inverting it
                    # OR-ing in the new byte
                    # inverting it back
                    newByte = ~origByte & 0xFF
                    newByte = newByte | (1 << (7 - bitIdx))
                    newByte = ~newByte & 0xFF

                data[byteIdx] = newByte

            return bytes(data)

        @QtCore.pyqtSlot(int)
        def HandleValueChanged(self, value):
            """
            Handle any checkbox being changed
            """
            self.updateData.emit(self)


    def setSprite(self, type, subtype, reset=False):
        """
        Change the sprite type used by the data editor
        """
        if (self.spritetype == type) and (self.subspritetype == subtype) and not reset: return

        self.UpdateFlag = True

        self.spritetype = type
        self.subspritetype = subtype
        if type != 1000:
            sprite = Sprites[type]
        else:
            sprite = None
        if subtype != 1000:
            subsprite = Sprites[subtype]
        else:
            subsprite = None

        # remove all the existing widgets in the layouts
        for layout in (self.editorlayout, self.editorlayout_sub):
            for row in range(2, layout.rowCount()):
                for column in range(0, layout.columnCount()):
                    w = layout.itemAtPosition(row, column)
                    if w is not None:
                        widget = w.widget()
                        layout.removeWidget(widget)
                        widget.setParent(None)

        if sprite is None:
            self.spriteLabel.setText(_('<b>Unidentified/Unknown Sprite ({id})</b>', 'id', type))
            self.noteButton.setVisible(False)

            # use the raw editor if nothing is there
            self.raweditor.setVisible(True)
            if len(self.fields) > 0: self.fields = []

        else:
            self.spriteLabel.setText(_('<b>Sprite {id}: {name}</b>', 'id', type, 'name', sprite.name))

            self.noteButton.setVisible(sprite.notes is not None)
            self.notes = sprite.notes

            # create all the new fields
            fields = []
            row = 2

            for f in sprite.fields:
                if f[0] == 0:
                    nf = self.CheckboxPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout, row)
                elif f[0] == 1:
                    nf = self.ListPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout, row)
                elif f[0] == 2:
                    nf = self.ValuePropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout, row)
                elif f[0] == 3:
                    nf = self.BitfieldPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout, row)

                nf.updateData.connect(lambda x: self.HandleFieldUpdate(x, False))
                fields.append(nf)
                row += 1

            self.fields = fields


        if subsprite is None or subtype == -1:
            # Clear stuff
            self.spriteLabel_sub_2.setText(_('<b>: <i>None</i></b>'))
            self.noteButton_sub.setVisible(False)
            if len(self.subfields) > 0: self.subfields = []

        else:
            self.spriteLabel_sub_2.setText(_('<b>: {name}</b>', 'name', subsprite.name))
            self.spriteNum_sub.setValue(subtype)

            self.noteButton_sub.setVisible(subsprite.notes is not None)
            self.notes_sub = subsprite.notes


            # create all the new fields
            fields = []
            row = 2

            for f in subsprite.fields:
                if f[0] == 0:
                    nf = self.CheckboxPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout_sub, row)
                elif f[0] == 1:
                    nf = self.ListPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout_sub, row)
                elif f[0] == 2:
                    nf = self.ValuePropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout_sub, row)
                elif f[0] == 3:
                    nf = self.BitfieldPropertyDecoder(f[1], f[2], f[3], f[4], self.editorlayout_sub, row)

                nf.updateData.connect(lambda x: self.HandleFieldUpdate(x, True))
                fields.append(nf)
                row += 1

            self.subfields = fields

        # Update all the fields
        for f in self.fields:
            f.update(self.data)
        for f in self.subfields:
            f.update(self.subdata)

        self.UpdateFlag = False


    def update(self):
        """
        Updates all the fields to display the appropriate info
        """
        self.UpdateFlag = True

        self.raweditor.updateContents(self.data)
        self.raweditor_sub.updateContents(self.subdata)

        self.widthEdit.setValue(self.width)
        self.heightEdit.setValue(self.height)
        self.zPosEdit.setValue(self.zPos)
        self.linkingIdEdit.setValue(self.linkingId)
        self.useEffEdit.setChecked(self.useEff)
        self.effUnk00Edit.setValue(self.effUnk00)
        self.effUnk01Edit.setValue(self.effUnk01)
        self.effUnk02Edit.setValue(self.effUnk02)
        self.effUnk03Edit.setValue(self.effUnk03)
        self.effUnk04Edit.setValue(self.effUnk04)
        self.effUnk00Edit.setEnabled(self.useEff)
        self.effUnk01Edit.setEnabled(self.useEff)
        self.effUnk02Edit.setEnabled(self.useEff)
        self.effUnk03Edit.setEnabled(self.useEff)
        self.effUnk04Edit.setEnabled(self.useEff)
        self.costumeIdEdit.setValue(self.costumeId)
        self.costumeIdEdit_sub.setValue(self.costumeId_sub)
        self.spriteNum_sub.setValue(self.subspritetype)

        # Go through all the data
        for f in self.fields:
            f.update(self.data)
        for f in self.subfields:
            f.update(self.subdata)

        self.UpdateFlag = False


    @QtCore.pyqtSlot()
    def ShowNoteTooltip(self):
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.notes, self)


    @QtCore.pyqtSlot('PyQt_PyObject')
    def HandleFieldUpdate(self, field, issub):
        """
        Triggered when a field's data is updated
        """
        if self.UpdateFlag: return

        if issub:
            d = self.subdata
            self.subdata = field.assign(d)

            self.raweditor_sub.updateContents(self.subdata)
            for f in self.subfields:
                if f != field: f.update(self.subdata)
        else:
            d = self.data
            self.data = field.assign(d)

            self.raweditor.updateContents(self.data)
            for f in self.fields:
                if f != field: f.update(self.data)

        self.DataUpdate.emit(self)


    @QtCore.pyqtSlot(str)
    def HandleRawDataEdited(self, data, issub):
        """
        Triggered when either raw data textbox is edited
        """
        if self.UpdateFlag: return

        if issub:
            self.subdata = self.raweditor_sub.data

            self.UpdateFlag = True
            for f in self.subfields: f.update(self.subdata)
            self.UpdateFlag = False
        else:
            self.data = self.raweditor.data

            self.UpdateFlag = True
            for f in self.fields: f.update(self.data)
            self.UpdateFlag = False

        self.DataUpdate.emit(self)


    def HandleOptionsChanged(self):
        """
        Handle any of the options changing
        """
        if self.UpdateFlag: return

        self.width = self.widthEdit.value()
        self.height = self.heightEdit.value()
        self.zPos = self.zPosEdit.value()
        self.linkingId = self.linkingIdEdit.value()
        self.useEff = self.useEffEdit.isChecked()
        self.effUnk00 = self.effUnk00Edit.value()
        self.effUnk01 = self.effUnk01Edit.value()
        self.effUnk02 = self.effUnk02Edit.value()
        self.effUnk03 = self.effUnk03Edit.value()
        self.effUnk04 = self.effUnk04Edit.value()
        self.costumeId = self.costumeIdEdit.value()
        self.costumeId_sub = self.costumeIdEdit_sub.value()

        if self.subspritetype != self.spriteNum_sub.value():
            self.setSprite(self.spritetype, self.spriteNum_sub.value())

        self.effUnk00Edit.setEnabled(self.useEff)
        self.effUnk01Edit.setEnabled(self.useEff)
        self.effUnk02Edit.setEnabled(self.useEff)
        self.effUnk03Edit.setEnabled(self.useEff)
        self.effUnk04Edit.setEnabled(self.useEff)

        self.DataUpdate.emit(self)

    def HandleSubspriteTypeChanging(self):
        """
        Handle the subsprite type changing. We need to do extra stuff.
        """
        self.subspritetype = self.spriteNum_sub.value()



def LoadTheme():
    """
    Loads the theme
    """
    global theme

    id = setting('Theme')
    if id is None: id = 'Classic'
    if id != 'Classic':

        path = str('metamakerdata\\themes\\'+id).replace('\\', '/')
        with open(path, 'rb') as f:
            theme = MetamakerTheme(f)

    else: theme = MetamakerTheme()


class MetamakerTheme():
    """
    Class that represents a Metamaker theme
    """
    def __init__(self, file=None):
        """
        Initializes the theme
        """
        self.initAsClassic()
        if file is not None: self.initFromFile(file)


    def initAsClassic(self):
        """
        Initializes the theme as the hardcoded Classic theme
        """
        self.fileName = 'Classic'
        self.formatver = 1.0
        self.version = 1.0
        self.themeName = _('Classic')
        self.creator = _('Treeki, Tempus')
        self.description = _('The default Metamaker theme.')
        self.iconCacheSm = {}
        self.iconCacheLg = {}
        self.style = None

        # Add the colors                                               # Descriptions:
        self.colors = {
            'bg':                      QtGui.QColor(119,136,153),     # Main scene background fill
            'grid':                    QtGui.QColor(255,255,255,100), # Grid
            'overview_sprite':         QtGui.QColor(0,92,196),        # Overview sprite fill
            'smi':                     QtGui.QColor(255,255,255,80),  # Sprite movement indicator
            'sprite_fill_s':           QtGui.QColor(255,255,255,64),  # Selected sprite w/ image fill
            'sprite_lines_s':          QtGui.QColor(255,255,255),     # Selected sprite w/ image lines
            'spritebox_fill':          QtGui.QColor(0,92,196,120),    # Unselected sprite w/o image fill
            'spritebox_fill_s':        QtGui.QColor(0,92,196,240),    # Selected sprite w/o image fill
            'spritebox_lines':         QtGui.QColor(0,0,0),           # Unselected sprite w/o image fill
            'spritebox_lines_s':       QtGui.QColor(255,255,255),     # Selected sprite w/o image fill
            'overview_viewbox':        QtGui.QColor(0,0,255),         # Overview background fill
            'outofbounds':             QtGui.QColor.fromRgb(255,0,0,20) # Out-of-Bounds Highlight
            }

    def initFromFile(self, file):
        """
        Initializes the theme from the file
        """
        try:
            zipf = zipfile.ZipFile(file, 'r')
            zipfList = zipf.namelist()
        except Exception:
            # Can't load the data for some reason
            return
        try:
            mainxmlfile = zipf.open('main.xml')
        except KeyError:
            # There's no main.xml in the file
            return

        # Create a XML ElementTree
        try: maintree = etree.parse(mainxmlfile)
        except Exception: return
        root = maintree.getroot()

        # Parse the attributes of the <theme> tag
        if not self.parseMainXMLHead(root):
            # The attributes are messed up
            return

        # Parse the other nodes
        for node in root:
            if node.tag.lower() == 'colors':
                if 'file' not in node.attrib: continue

                # Load the colors XML
                try:
                    self.loadColorsXml(zipf.open(node.attrib['file']))
                except Exception: continue

            elif node.tag.lower() == 'stylesheet':
                if 'file' not in node.attrib: continue

                # Load the stylesheet
                try:
                    self.loadStylesheet(zipf.open(node.attrib['file']))
                except Exception: continue

            elif node.tag.lower() == 'icons':
                if not all(thing in node.attrib for thing in ['size', 'folder']): continue

                foldername = node.attrib['folder']
                big = node.attrib['size'].lower()[:2] == 'lg'
                cache = self.iconCacheLg if big else self.iconCacheSm

                # Load the icons
                for iconfilename in zipfList:
                    iconname = iconfilename
                    if not iconname.startswith(foldername + '/'): continue
                    iconname = iconname[len(foldername)+1:]
                    if len(iconname) <= len('icon-.png'): continue
                    if not iconname.startswith('icon-') or not iconname.endswith('.png'): continue
                    iconname = iconname[len('icon-'): -len('.png')]

                    icodata = zipf.open(iconfilename).read()
                    pix = QtGui.QPixmap()
                    if not pix.loadFromData(icodata): continue
                    ico = QtGui.QIcon(pix)

                    cache[iconname] = ico


    def parseMainXMLHead(self, root):
        """
        Parses the main attributes of main.xml
        """
        MaxSupportedXMLVersion = 1.0

        # Check for required attributes
        if root.tag.lower() != 'theme': return False
        if 'format' in root.attrib:
            formatver = root.attrib['format']
            try: self.formatver = float(formatver)
            except ValueError: return False
        else: return False

        if self.formatver > MaxSupportedXMLVersion: return False
        if 'name' in root.attrib: self.themeName = root.attrib['name']
        else: return False

        # Check for optional attributes
        self.creator = _('</i>(unknown)</i>')
        self.description = _('</i>No description</i>')
        self.style = None
        self.version = 1.0
        if 'creator'     in root.attrib: self.creator = root.attrib['creator']
        if 'description' in root.attrib: self.description = root.attrib['description']
        if 'style'       in root.attrib: self.style = root.attrib['style']
        if 'version'     in root.attrib:
            try: self.version = float(root.attrib['style'])
            except ValueError: pass

        return True

    def loadColorsXml(self, file):
        """
        Loads a colors.xml file
        """
        try: tree = etree.parse(file)
        except Exception: return

        root = tree.getroot()
        if root.tag.lower() != 'colors': return False

        colorDict = {}
        for colorNode in root:
            if colorNode.tag.lower() != 'color': continue
            if not all(thing in colorNode.attrib for thing in ['id', 'value']): continue

            colorval = colorNode.attrib['value']
            if colorval.startswith('#'): colorval = colorval[1:]
            a = 255
            try:
                if len(colorval) == 3:
                    # RGB
                    r = int(colorval[0], 16)
                    g = int(colorval[1], 16)
                    b = int(colorval[2], 16)
                elif len(colorval) == 4:
                    # RGBA
                    r = int(colorval[0], 16)
                    g = int(colorval[1], 16)
                    b = int(colorval[2], 16)
                    a = int(colorval[3], 16)
                elif len(colorval) == 6:
                    # RRGGBB
                    r = int(colorval[0:2], 16)
                    g = int(colorval[2:4], 16)
                    b = int(colorval[4:6], 16)
                elif len(colorval) == 8:
                    # RRGGBBAA
                    r = int(colorval[0:2], 16)
                    g = int(colorval[2:4], 16)
                    b = int(colorval[4:6], 16)
                    a = int(colorval[6:8], 16)
            except ValueError: continue
            colorobj = QtGui.QColor(r, g, b, a)
            colorDict[colorNode.attrib['id']] = colorobj

        # Merge dictionaries
        self.colors.update(colorDict)


    def loadStylesheet(self, file):
        """
        Loads a stylesheet
        """
        print(file)

    def color(self, name):
        """
        Returns a color
        """
        return self.colors[name]

    def GetIcon(self, name, big=False):
        """
        Returns an icon
        """

        cache = self.iconCacheLg if big else self.iconCacheSm

        if name not in cache:
            path = 'metamakerdata/ico/lg/icon-' if big else 'metamakerdata/ico/sm/icon-'
            path += name
            cache[name] = QtGui.QIcon(path)

        return cache[name]

    def ui(self):
        """
        Returns the UI style
        """
        return self.uiStyle


# Related function
def toQColor(*args):
    """
    Usage: toQColor(r, g, b[, a]) OR toQColor((r, g, b[, a]))
    """
    if len(args) == 1: args = args[0]
    r = args[0]
    g = args[1]
    b = args[2]
    a = args[3] if len(args) == 4 else 255
    return QtGui.QColor(r, g, b, a)



class CourseScene(QtWidgets.QGraphicsScene):
    """
    GraphicsScene subclass for the course scene
    """
    def __init__(self, *args):
        self.bgbrush = QtGui.QBrush(_c('bg'))
        super().__init__(*args)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, self.bgbrush)

        # Give out-of-bounds regions a red-tinted background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QBrush(_c('outofbounds')))
        painter.drawRect(X_MIN * TILE_WIDTH, -(Y_MAX + 1) * TILE_WIDTH, -X_MIN * TILE_WIDTH, (Y_MAX + 1) * TILE_WIDTH) # left edge
        painter.drawRect(X_MIN * TILE_WIDTH, 0, -X_MIN * TILE_WIDTH, -Y_MIN * TILE_WIDTH) # bottom-left corner
        painter.drawRect(0, 0, (X_MAX + 1) * TILE_WIDTH, -Y_MIN * TILE_WIDTH) # bottom edge


class CourseViewWidget(QtWidgets.QGraphicsView):
    """
    QGraphicsView subclass for the course view
    """
    PositionHover = QtCore.pyqtSignal(int, int)
    FrameSize = QtCore.pyqtSignal(int, int)
    repaint = QtCore.pyqtSignal()

    def __init__(self, scene, parent):
        """
        Constructor
        """
        super().__init__(scene, parent)

        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        #self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(119,136,153)))
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        #self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setMouseTracking(True)
        #self.setOptimizationFlags(QtWidgets.QGraphicsView.IndirectPainting)
        self.YScrollBar = QtWidgets.QScrollBar(Qt.Vertical, parent)
        self.XScrollBar = QtWidgets.QScrollBar(Qt.Horizontal, parent)
        self.setVerticalScrollBar(self.YScrollBar)
        self.setHorizontalScrollBar(self.XScrollBar)

        self.currentobj = None

        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)

    def mousePressEvent(self, event):
        """
        Overrides mouse pressing events if needed
        """
        if event.button() == Qt.RightButton:
            if CurrentPaintType == 1 and CurrentSprite != -1:
                # paint a sprite
                clicked = mainWindow.view.mapToScene(event.x(), event.y())
                if clicked.x() < 0: clicked.setX(0)

                if CurrentSprite >= 0:

                    # paint a sprite
                    clickedx = int(clicked.x() // TILE_WIDTH) * 16
                    clickedy = -int(clicked.y() // TILE_WIDTH) * 16 - 16

                    spr = SpriteItem(clickedx, 0, clickedy,
                        sprdata = mainWindow.defaultDataEditor.data[:4],
                        sprdata2 = mainWindow.defaultDataEditor.data[4:],
                        subsprdata = mainWindow.defaultDataEditor.subdata,
                        type_ = CurrentSprite,
                        )

                    mw = mainWindow
                    spr.positionChanged = mw.HandleSprPosChange
                    mw.scene.addItem(spr)

                    spr.listitem = ListWidgetItem_SortsByOther(spr)
                    mw.spriteList.addItem(spr.listitem)
                    Course.sprites.append(spr)

                    self.currentobj = spr
                    self.dragstartx = clickedx
                    self.dragstarty = clickedy

                    self.scene().update()

                    spr.UpdateListItem()

                SetDirty()

        elif (event.button() == Qt.LeftButton) and (QtWidgets.QApplication.keyboardModifiers() == Qt.ShiftModifier):
            mw = mainWindow

            pos = mw.view.mapToScene(event.x(), event.y())
            addsel = mw.scene.items(pos)
            for i in addsel:
                if (int(i.flags()) & i.ItemIsSelectable) != 0:
                    i.setSelected(not i.isSelected())
                    break

        else:
            QtWidgets.QGraphicsView.mousePressEvent(self, event)
        mainWindow.courseOverview.update()


    def resizeEvent(self, event):
        """
        Catches resize events
        """
        self.FrameSize.emit(event.size().width(), event.size().height())
        event.accept()
        QtWidgets.QGraphicsView.resizeEvent(self, event)


    def mouseMoveEvent(self, event):
        """
        Overrides mouse movement events if needed
        """

        pos = mainWindow.view.mapToScene(event.x(), event.y())
        self.PositionHover.emit(int(pos.x()), int(pos.y()))

        if event.buttons() == Qt.RightButton and self.currentobj is not None:

            # possibly a small optimization
            type_spr = SpriteItem

            # iterate through the objects if there's more than one
            if isinstance(self.currentobj, list) or isinstance(self.currentobj, tuple):
                objlist = self.currentobj
            else:
                objlist = (self.currentobj,)

            for obj in objlist:
                if isinstance(obj, type_spr):
                    # move the created sprite
                    clicked = mainWindow.view.mapToScene(event.x(), event.y())
                    if clicked.x() < 0: clicked.setX(0)
                    clickedx = int((clicked.x() - TILE_WIDTH / 2) / TILE_WIDTH * 16)
                    clickedy = int((clicked.y() - TILE_WIDTH / 2) / TILE_WIDTH * 16)

                    if obj.objx != clickedx or obj.objy != clickedy:
                        obj.setStdPos(clickedx, -clickedy)

        else:
            QtWidgets.QGraphicsView.mouseMoveEvent(self, event)


    def mouseReleaseEvent(self, event):
        """
        Overrides mouse release events if needed
        """
        if event.button() == Qt.RightButton:
            self.currentobj = None
            event.accept()
        else:
            QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)


    def paintEvent(self, e):
        """
        Handles paint events and fires a signal
        """
        self.repaint.emit()
        QtWidgets.QGraphicsView.paintEvent(self, e)


    def drawForeground(self, painter, rect):
        """
        Draws a foreground grid
        """
        if GridType is None: return

        Zoom = mainWindow.ZoomLevel
        drawLine = painter.drawLine
        GridColor = _c('grid')

        if GridType == 'grid': # draw a classic grid
            startx = rect.x()
            startx -= (startx % TILE_WIDTH)
            endx = startx + rect.width() + TILE_WIDTH

            starty = rect.y()
            starty -= (starty % TILE_WIDTH)
            endy = starty + rect.height() + TILE_WIDTH

            x = startx - TILE_WIDTH
            while x <= endx:
                x += TILE_WIDTH
                if x % (TILE_WIDTH * 8) == 0:
                    painter.setPen(QtGui.QPen(GridColor, 2 * TILE_WIDTH / 24, Qt.DashLine))
                    drawLine(x, starty, x, endy)
                elif x % (TILE_WIDTH * 4) == 0:
                    if Zoom < 25: continue
                    painter.setPen(QtGui.QPen(GridColor, 1 * TILE_WIDTH / 24, Qt.DashLine))
                    drawLine(x, starty, x, endy)
                else:
                    if Zoom < 50: continue
                    painter.setPen(QtGui.QPen(GridColor, 1 * TILE_WIDTH / 24, Qt.DotLine))
                    drawLine(x, starty, x, endy)

            y = starty - TILE_WIDTH
            while y <= endy:
                y += TILE_WIDTH
                if y % (TILE_WIDTH * 8) == 0:
                    painter.setPen(QtGui.QPen(GridColor, 2 * TILE_WIDTH / 24, Qt.DashLine))
                    drawLine(startx, y, endx, y)
                elif y % (TILE_WIDTH * 4) == 0 and Zoom >= 25:
                    painter.setPen(QtGui.QPen(GridColor, 1 * TILE_WIDTH / 24, Qt.DashLine))
                    drawLine(startx, y, endx, y)
                elif Zoom >= 50:
                    painter.setPen(QtGui.QPen(GridColor, 1 * TILE_WIDTH / 24, Qt.DotLine))
                    drawLine(startx, y, endx, y)

        else: # draw a checkerboard
            L = 0.2
            D = 0.1     # Change these values to change the checkerboard opacity

            Light = QtGui.QColor(GridColor)
            Dark = QtGui.QColor(GridColor)
            Light.setAlpha(Light.alpha()*L)
            Dark.setAlpha(Dark.alpha()*D)

            size = TILE_WIDTH if Zoom >= 50 else TILE_WIDTH * 8

            board = QtGui.QPixmap(8*size, 8*size)
            board.fill(QtGui.QColor(0,0,0,0))
            p = QtGui.QPainter(board)
            p.setPen(Qt.NoPen)

            p.setBrush(QtGui.QBrush(Light))
            for x, y in ((0, size), (size, 0)):
                p.drawRect(x+(4*size), y,          size, size)
                p.drawRect(x+(4*size), y+(2*size), size, size)
                p.drawRect(x+(6*size), y,          size, size)
                p.drawRect(x+(6*size), y+(2*size), size, size)

                p.drawRect(x,          y+(4*size), size, size)
                p.drawRect(x,          y+(6*size), size, size)
                p.drawRect(x+(2*size), y+(4*size), size, size)
                p.drawRect(x+(2*size), y+(6*size), size, size)
            p.setBrush(QtGui.QBrush(Dark))
            for x, y in ((0, 0), (size, size)):
                p.drawRect(x,          y,          size, size)
                p.drawRect(x,          y+(2*size), size, size)
                p.drawRect(x+(2*size), y,          size, size)
                p.drawRect(x+(2*size), y+(2*size), size, size)

                p.drawRect(x,          y+(4*size), size, size)
                p.drawRect(x,          y+(6*size), size, size)
                p.drawRect(x+(2*size), y+(4*size), size, size)
                p.drawRect(x+(2*size), y+(6*size), size, size)

                p.drawRect(x+(4*size), y,          size, size)
                p.drawRect(x+(4*size), y+(2*size), size, size)
                p.drawRect(x+(6*size), y,          size, size)
                p.drawRect(x+(6*size), y+(2*size), size, size)

                p.drawRect(x+(4*size), y+(4*size), size, size)
                p.drawRect(x+(4*size), y+(6*size), size, size)
                p.drawRect(x+(6*size), y+(4*size), size, size)
                p.drawRect(x+(6*size), y+(6*size), size, size)


            del p

            painter.drawTiledPixmap(rect, board, QtCore.QPointF(rect.x(), rect.y()))




####################################################################
####################################################################
####################################################################

class HexSpinBox(QtWidgets.QSpinBox):
    class HexValidator(QtGui.QValidator):
        def __init__(self, min, max):
            super().__init__()
            self.valid = set('0123456789abcdef')
            self.min = min
            self.max = max

        def validate(self, input, pos):
            try:
                input = str(input).lower()
            except Exception:
                return (self.Invalid, input, pos)
            valid = self.valid

            for char in input:
                if char not in valid:
                    return (self.Invalid, input, pos)

            try:
                value = int(input, 16)
            except ValueError:
                # If value == '' it raises ValueError
                return (self.Invalid, input, pos)

            if value < self.min or value > self.max:
                return (self.Intermediate, input, pos)

            return (self.Acceptable, input, pos)


    def __init__(self, format='%04X', *args):
        self.format = format
        super().__init__(*args)
        self.validator = self.HexValidator(self.minimum(), self.maximum())

    def setMinimum(self, value):
        self.validator.min = value
        QtWidgets.QSpinBox.setMinimum(self, value)

    def setMaximum(self, value):
        self.validator.max = value
        QtWidgets.QSpinBox.setMaximum(self, value)

    def setRange(self, min, max):
        self.validator.min = min
        self.validator.max = max
        QtWidgets.QSpinBox.setMinimum(self, min)
        QtWidgets.QSpinBox.setMaximum(self, max)

    def validate(self, text, pos):
        return self.validator.validate(text, pos)

    def textFromValue(self, value):
        return self.format % value

    def valueFromText(self, value):
        return int(str(value), 16)


class AboutDialog(QtWidgets.QDialog):
    """
    Shows the About info for Metamaker
    """
    def __init__(self):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('About Metamaker'))
        self.setWindowIcon(GetIcon('metamaker'))

        # Set the palette to the default
        # defaultPalette is a global
        self.setPalette(QtGui.QPalette(defaultPalette))

        # Open the readme file
        f = open('readme.md', 'r')
        readme = f.read()
        f.close()
        del f

        # Logo
        logo = QtGui.QPixmap('metamakerdata/about.png')
        logoLabel = QtWidgets.QLabel()
        logoLabel.setPixmap(logo)
        logoLabel.setContentsMargins(16, 4, 32, 4)

        # Description
        description =  '<html><head><style type=\'text/CSS\'>'
        description += 'body {font-family: Calibri}'
        description += '.main {font-size: 12px}'
        description += '</style></head><body>'
        description += '<center><h1><i>Metamaker</i> Course Editor</h1><div class=\'main\'>'
        description += '<i>Metamaker Course Editor</i> is an open-source project based upon the Reggie! Level Editor that lets you edit Super Mario Maker course files on your PC, without many of the arbitrary restrictions imposed by the official editor.<br>'
        description += '</div></center></body></html>'

        # Description label
        descLabel = QtWidgets.QLabel()
        descLabel.setText(description)
        descLabel.setMinimumWidth(512)
        descLabel.setWordWrap(True)

        # Readme.md viewer
        readmeView = QtWidgets.QPlainTextEdit()
        readmeView.setPlainText(readme)
        readmeView.setReadOnly(True)

        # Buttonbox
        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)

        # Main layout
        L = QtWidgets.QGridLayout()
        L.addWidget(logoLabel, 0, 0, 2, 1)
        L.addWidget(descLabel, 0, 1)
        L.addWidget(readmeView, 1, 1)
        L.addWidget(buttonBox, 2, 0, 1, 2)
        L.setRowStretch(1, 1)
        L.setColumnStretch(1, 1)
        self.setLayout(L)



# Sets up the Course Options Menu
class CourseOptionsDialog(QtWidgets.QDialog):
    """
    Dialog which lets you choose among various course options from tabs
    """
    def __init__(self):
        """
        Creates and initializes the tab dialog
        """
        super().__init__()
        self.setWindowTitle(_('Course Options'))

        self.creationTime = QtWidgets.QDateTimeEdit()
        self.creationTime.setMinimumDate(QtCore.QDate(1, 1, 1))
        self.creationTime.setMaximumDate(QtCore.QDate(0xFFFF, 12, 31))
        self.creationTime.setCalendarPopup(True)

        self.unk16 = QtWidgets.QSpinBox()
        self.unk16.setMinimum(0)
        self.unk16.setMaximum(0xFF)

        self.unk17 = QtWidgets.QSpinBox()
        self.unk17.setMinimum(0)
        self.unk17.setMaximum(0xFF)

        self.unk181F = QtWidgets.QSpinBox()
        self.unk181F.setMinimum(0)
        self.unk181F.setMaximum(0xFFFFF) # u64, but Qt glitches if you do that

        self.unk20 = QtWidgets.QSpinBox()
        self.unk20.setMinimum(0)
        self.unk20.setMaximum(0xFF)

        self.courseName = QtWidgets.QLineEdit()
        self.courseName.setMaxLength(32)

        self.courseStyle = QtWidgets.QComboBox()
        self.courseStyle.addItems([_('Super Mario Bros.'), _('Super Mario Bros. 3'), _('Super Mario World'), _('New Super Mario Bros. U')])

        self.unk6C = QtWidgets.QSpinBox()
        self.unk6C.setMinimum(0)
        self.unk6C.setMaximum(0xFF)

        self.courseTheme = QtWidgets.QComboBox()
        self.courseTheme.addItems([_('Overworld'), _('Underground'), _('Castle'), _('Airship'), _('Water'), _('Ghost house')])

        self.unk6E = QtWidgets.QSpinBox()
        self.unk6E.setMinimum(0)
        self.unk6E.setMaximum(0xFF)

        self.unk6F = QtWidgets.QSpinBox()
        self.unk6F.setMinimum(0)
        self.unk6F.setMaximum(0xFF)

        self.timeLimit = QtWidgets.QSpinBox()
        self.timeLimit.setMinimum(0)
        self.timeLimit.setMaximum(0xFFFF)

        self.autoscroll = QtWidgets.QSpinBox()
        self.autoscroll.setMinimum(0)
        self.autoscroll.setMaximum(0xFF)

        self.unk73 = QtWidgets.QSpinBox()
        self.unk73.setMinimum(0)
        self.unk73.setMaximum(0xFF)

        self.unk7475 = QtWidgets.QSpinBox()
        self.unk7475.setMinimum(0)
        self.unk7475.setMaximum(0xFFFF)

        # 76-D7? I don't even know

        self.unkD8DB = QtWidgets.QSpinBox()
        self.unkD8DB.setMinimum(0)
        self.unkD8DB.setMaximum(0xFFFF) # u32, but Qt glitches if you do that

        self.unkDCDF = QtWidgets.QSpinBox()
        self.unkDCDF.setMinimum(0)
        self.unkDCDF.setMaximum(0xFFFF) # u32, but Qt glitches if you do that

        settingsWidget = QtWidgets.QWidget()
        settingsLayout = QtWidgets.QFormLayout(settingsWidget)
        settingsLayout.addRow(_('Creation time:'), self.creationTime)
        settingsLayout.addRow(_('Unknown value 0x16:'), self.unk16)
        settingsLayout.addRow(_('Unknown value 0x17:'), self.unk17)
        settingsLayout.addRow(_('Unknown value 0x18-0x1F:'), self.unk181F)
        settingsLayout.addRow(_('Unknown value 0x20:'), self.unk20)
        settingsLayout.addRow(_('Course name:'), self.courseName)
        settingsLayout.addRow(_('Style:'), self.courseStyle)
        settingsLayout.addRow(_('Unknown value 0x6C:'), self.unk6C)
        settingsLayout.addRow(_('Theme:'), self.courseTheme)
        settingsLayout.addRow(_('Unknown value 0x6E:'), self.unk6E)
        settingsLayout.addRow(_('Unknown value 0x6F:'), self.unk6F)
        settingsLayout.addRow(_('Time limit:'), self.timeLimit)
        settingsLayout.addRow(_('Autoscroll speed:'), self.autoscroll)
        settingsLayout.addRow(_('Unknown value 0x73:'), self.unk73)
        settingsLayout.addRow(_('Unknown value 0x74-0x75:'), self.unk7475)
        settingsLayout.addRow(_('Unknown value 0xD8-0xDB:'), self.unkD8DB)
        settingsLayout.addRow(_('Unknown value 0xDC-0xDF:'), self.unkDCDF)

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(settingsWidget)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.populateFields()


    def populateFields(self):
        """
        Populate the fields based on properties of the global Course object
        """
        self.creationTime.setDate(QtCore.QDate(Course.creationYear, Course.creationMonth, Course.creationDay))
        self.creationTime.setTime(QtCore.QTime(Course.creationHour, Course.creationMinute))
        self.unk16.setValue(Course.unk16)
        self.unk17.setValue(Course.unk17)
        self.unk181F.setValue(Course.unk181F)
        self.unk20.setValue(Course.unk20)
        self.courseName.setText(Course.courseName)
        self.courseStyle.setCurrentIndex(Course.style)
        self.unk6C.setValue(Course.unk6C)
        self.courseTheme.setCurrentIndex(Course.theme)
        self.unk6E.setValue(Course.unk6E)
        self.unk6F.setValue(Course.unk6F)
        self.timeLimit.setValue(Course.timeLimit)
        self.autoscroll.setValue(Course.autoscroll)
        self.unk73.setValue(Course.unk73)
        self.unk7475.setValue(Course.unk7475)
        # ?????????
        self.unkD8DB.setValue(Course.unkD8DB)
        self.unkDCDF.setValue(Course.unkDCDF)


    def readOutFields(self):
        """
        Set properties of the Course object based on the field values
        """
        cDate = self.creationTime.dateTime().date()
        cTime = self.creationTime.dateTime().time()

        Course.creationYear = cDate.year()
        Course.creationMonth = cDate.month()
        Course.creationDay = cDate.day()
        Course.creationHour = cTime.hour()
        Course.creationMinute = cTime.minute()
        Course.unk16 = self.unk16.value()
        Course.unk17 = self.unk17.value()
        Course.unk181F = self.unk181F.value()
        Course.unk20 = self.unk20.value()
        Course.courseName = self.courseName.text()
        Course.style = self.courseStyle.currentIndex()
        Course.unk6C = self.unk6C.value()
        Course.theme = self.courseTheme.currentIndex()
        Course.unk6E = self.unk6E.value()
        Course.unk6F = self.unk6F.value()
        Course.timeLimit = self.timeLimit.value()
        Course.autoscroll = self.autoscroll.value()
        Course.unk73 = self.unk73.value()
        Course.unk7475 = self.unk7475.value()
        Course.unkD8DB = self.unkD8DB.value()
        Course.unkDCDF = self.unkDCDF.value()


# Sets up the Screen Cap Choice Dialog
class ScreenCapChoiceDialog(QtWidgets.QDialog):
    """
    Dialog which lets you choose which zone to take a pic of
    """
    def __init__(self):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Choose a Screenshot Source'))
        self.setWindowIcon(GetIcon('screenshot'))

        self.zoneCombo = QtWidgets.QComboBox()
        self.zoneCombo.addItem(_('Current Screen'))
        self.zoneCombo.addItem(_('Entire Course'))

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.zoneCombo)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)



class MidiImportDialog(QtWidgets.QDialog):
    """
    Dialog which lets you choose a MIDI to import, and some import options
    """
    paramsInfo = None
    updating = False
    def __init__(self):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Import MIDI'))
        self.setWindowIcon(GetIcon('screenshot'))

        self.openButton = QtWidgets.QPushButton(_('Open...'))
        self.openButton.clicked.connect(self.handleOpenBtnClicked)

        self.fileLabel = QtWidgets.QLabel()

        self.trackNum = QtWidgets.QComboBox()
        self.trackNum.setEnabled(False)

        self.spriteNum = QtWidgets.QSpinBox()
        self.spriteNum.setMinimum(0)
        self.spriteNum.setMaximum(69)
        self.spriteNum.valueChanged.connect(self.handleValueChanged)
        self.spriteNum.setEnabled(False)

        self.spriteData = RawDataEditorWidget(8)
        self.spriteData.dataChanged.connect(self.handleValueChanged)
        self.spriteData.setEnabled(False)

        self.toneOffset = QtWidgets.QSpinBox()
        self.toneOffset.setMinimum(-1000)
        self.toneOffset.setMaximum(1000)
        self.toneOffset.valueChanged.connect(self.handleValueChanged)
        self.toneOffset.setEnabled(False)

        self.xStartPos = QtWidgets.QSpinBox()
        self.xStartPos.setMinimum(X_MIN * 16)
        self.xStartPos.setMaximum(X_MAX * 16)
        self.xStartPos.valueChanged.connect(self.handleValueChanged)
        self.xStartPos.setEnabled(False)

        self.xUnitsPerBeat = QtWidgets.QSpinBox()
        self.xUnitsPerBeat.setMinimum(1)
        self.xUnitsPerBeat.setMaximum(1000)
        self.xUnitsPerBeat.valueChanged.connect(self.handleValueChanged)
        self.xUnitsPerBeat.setEnabled(False)

        self.percentLabel = QtWidgets.QLabel()

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        lyt = QtWidgets.QFormLayout(self)
        lyt.addRow(_('File:'), self.openButton)
        lyt.addWidget(self.fileLabel)
        lyt.addRow(_('Track:'), self.trackNum)
        lyt.addRow(_('Sprite type:'), self.spriteNum)
        lyt.addRow(_('Sprite data:'), self.spriteData)
        lyt.addRow(_('Tone offset:'), self.toneOffset)
        lyt.addRow(_('Initial X-position:'), self.xStartPos)
        lyt.addRow(_('X-units per beat:'), self.xUnitsPerBeat)
        lyt.addRow(_('Percentage of song that fits in the course:'), self.percentLabel)
        lyt.addRow(buttonBox)


    def handleOpenBtnClicked(self):
        """
        The Open... button was clicked
        """
        path = QtWidgets.QFileDialog.getOpenFileName(
            self, _('Choose a MIDI file'), '',
            _('MIDI files') + ' (*.midi, *.mid);;' + _('All files') + ' (*)',
            )[0]
        if not path: return

        self.midi = midi2sprites.getSongObj(path)
        if self.midi is None: return # invalid MIDI

        self.fileLabel.setText(os.path.basename(path))
        self.trackNum.setEnabled(True)
        self.spriteNum.setEnabled(True)
        self.spriteData.setEnabled(True)
        self.toneOffset.setEnabled(True)
        self.xStartPos.setEnabled(True)
        self.xUnitsPerBeat.setEnabled(True)

        paramsInfo = midi2sprites.MidiConversionParams(self.midi)

        self.updating = True
        self.trackNum.clear()
        self.trackNum.addItems(midi2sprites.getTracks(self.midi))
        self.trackNum.setCurrentIndex(paramsInfo.trackNum)
        self.spriteNum.setValue(paramsInfo.spriteNum)
        self.spriteData.updateContents(paramsInfo.spriteData)
        self.toneOffset.setValue(paramsInfo.toneOffset)
        self.xStartPos.setValue(paramsInfo.xStartPos)
        self.xUnitsPerBeat.setValue(paramsInfo.xUnitsPerBeat)
        self.updating = False

        self.paramsInfo = paramsInfo

        self.updatePercent()


    def handleValueChanged(self):
        """
        Putting these three handlers together because it's easier.
        """
        if self.updating or self.paramsInfo is None: return

        self.paramsInfo.trackNum = self.trackNum.currentIndex()
        self.paramsInfo.spriteNum = self.spriteNum.value()
        self.paramsInfo.spriteData = self.spriteData.data
        self.paramsInfo.toneOffset = self.toneOffset.value()
        self.paramsInfo.xStartPos = self.xStartPos.value()
        self.paramsInfo.xUnitsPerBeat = self.xUnitsPerBeat.value()

        self.updatePercent()


    def updatePercent(self):
        """
        Update the percentage label.
        """
        if self.paramsInfo is None: return

        self.percentLabel.setText(_('{value}%', 'value', 100 * midi2sprites.percentageFit(self.midi, self.paramsInfo)))



class AutoSavedInfoDialog(QtWidgets.QDialog):
    """
    Dialog which lets you know that an auto saved course exists
    """

    def __init__(self, filename):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Auto-saved backup found'))
        self.setWindowIcon(GetIcon('save'))

        mainlayout = QtWidgets.QVBoxLayout(self)

        hlayout = QtWidgets.QHBoxLayout()

        icon = QtWidgets.QLabel()
        hlayout.addWidget(icon)

        label = QtWidgets.QLabel(_("Metamaker has found some course data which wasn't saved - possibly due to a crash within the editor or by your computer. Do you want to restore this course?<br><br>If you pick No, the autosaved course data will be deleted and will no longer be accessible.<br><br>Original file path: {path}", 'path', filename))
        label.setWordWrap(True)
        hlayout.addWidget(label)
        hlayout.setStretch(1, 1)

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.No | QtWidgets.QDialogButtonBox.Yes)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        mainlayout.addLayout(hlayout)
        mainlayout.addWidget(buttonbox)


class CourseChoiceDialog(QtWidgets.QDialog):
    """
    Dialog which lets you choose an course
    """

    def __init__(self, coursecount):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Choose a Course'))
        self.setWindowIcon(GetIcon('courses'))

        self.courseCombo = QtWidgets.QComboBox()
        for i in range(coursecount):
            self.courseCombo.addItem(_('Course {num}', 'num', i+1))

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.courseCombo)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)


class ZoomWidget(QtWidgets.QWidget):
    """
    Widget that allows easy zoom level control
    """
    def __init__(self):
        """
        Creates and initializes the widget
        """
        super().__init__()
        maxwidth = 512-128
        maxheight = 20

        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.minLabel = QtWidgets.QPushButton()
        self.minusLabel = QtWidgets.QPushButton()
        self.plusLabel = QtWidgets.QPushButton()
        self.maxLabel = QtWidgets.QPushButton()

        self.slider.setMaximumHeight(maxheight)
        self.slider.setMinimum(0)
        self.slider.setMaximum(len(mainWindow.ZoomLevels)-1)
        self.slider.setTickInterval(2)
        self.slider.setTickPosition(self.slider.TicksAbove)
        self.slider.setPageStep(1)
        self.slider.setTracking(True)
        self.slider.setSliderPosition(self.findIndexOfLevel(100))
        self.slider.valueChanged.connect(self.sliderMoved)

        self.minLabel.setIcon(GetIcon('zoommin'))
        self.minusLabel.setIcon(GetIcon('zoomout'))
        self.plusLabel.setIcon(GetIcon('zoomin'))
        self.maxLabel.setIcon(GetIcon('zoommax'))
        self.minLabel.setFlat(True)
        self.minusLabel.setFlat(True)
        self.plusLabel.setFlat(True)
        self.maxLabel.setFlat(True)
        self.minLabel.clicked.connect(mainWindow.HandleZoomMin)
        self.minusLabel.clicked.connect(mainWindow.HandleZoomOut)
        self.plusLabel.clicked.connect(mainWindow.HandleZoomIn)
        self.maxLabel.clicked.connect(mainWindow.HandleZoomMax)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.minLabel,   0, 0)
        self.layout.addWidget(self.minusLabel, 0, 1)
        self.layout.addWidget(self.slider,     0, 2)
        self.layout.addWidget(self.plusLabel,  0, 3)
        self.layout.addWidget(self.maxLabel,   0, 4)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(0)
        self.layout.setContentsMargins(0,0,4,0)

        self.setLayout(self.layout)
        self.setMinimumWidth(maxwidth)
        self.setMaximumWidth(maxwidth)
        self.setMaximumHeight(maxheight)

    def sliderMoved(self):
        """
        Handle the slider being moved
        """
        mainWindow.ZoomTo(mainWindow.ZoomLevels[self.slider.value()])

    def setZoomLevel(self, newLevel):
        """
        Moves the slider to the zoom level given
        """
        self.slider.setSliderPosition(self.findIndexOfLevel(newLevel))

    def findIndexOfLevel(self, course):
        for i, maincourse in enumerate(mainWindow.ZoomLevels):
            if float(maincourse) == float(course): return i


class ZoomStatusWidget(QtWidgets.QWidget):
    """
    Shows the current zoom level, in percent
    """
    def __init__(self):
        """
        Creates and initializes the widget
        """
        super().__init__()
        self.label = QtWidgets.QPushButton('100%')
        self.label.setFlat(True)
        self.label.clicked.connect(mainWindow.HandleZoomActual)

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.setContentsMargins(4,0,8,0)
        self.setMaximumWidth(56)

        self.setLayout(self.layout)

    def setZoomLevel(self, zoomLevel):
        """
        Updates the widget
        """
        if float(int(zoomLevel)) == float(zoomLevel):
            self.label.setText(str(int(zoomLevel))+'%')
        else:
            self.label.setText(str(float(zoomLevel))+'%')


class PreferencesDialog(QtWidgets.QDialog):
    """
    Dialog which lets you customize Metamaker
    """
    def __init__(self):
        """
        Creates and initializes the dialog
        """
        super().__init__()
        self.setWindowTitle(_('Metamaker Preferences'))
        self.setWindowIcon(GetIcon('settings'))

        # Create the tab widget
        self.tabWidget = QtWidgets.QTabWidget()
        self.tabWidget.currentChanged.connect(self.tabChanged)

        # Create other widgets
        self.infoLabel = QtWidgets.QLabel()
        self.generalTab = self.getGeneralTab()
        self.toolbarTab = self.getToolbarTab()
        self.themesTab = self.getThemesTab()
        self.tabWidget.addTab(self.generalTab, _('General'))
        self.tabWidget.addTab(self.toolbarTab, _('Toolbar'))
        self.tabWidget.addTab(self.themesTab, _('Themes'))

        # Create the buttonbox
        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        # Create a main layout
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.infoLabel)
        mainLayout.addWidget(self.tabWidget)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        # Update it
        self.tabChanged()
        self.menuSettingChanged()

    def tabChanged(self):
        """
        Handles the current tab being changed
        """
        self.infoLabel.setText(self.tabWidget.currentWidget().info)

    def menuSettingChanged(self):
        """
        Handles the menu-style option being changed
        """
        self.tabWidget.setTabEnabled(1, self.generalTab.MenuM.isChecked())


    def getGeneralTab(self):
        """
        Returns the General Tab
        """

        class GeneralTab(QtWidgets.QWidget):
            """
            General Tab
            """
            info = _('<b>Metamaker Preferences</b><br>Customize Metamaker by changing these settings.<br>Use the tabs below to view even more settings.<br>Metamaker must be restarted before certain changes can take effect.')

            def __init__(self, menuHandler):
                """
                Initializes the General Tab
                """
                super().__init__()

                # Add the Splash Screen settings
                self.SplashR = QtWidgets.QRadioButton(_('If TPLLib cannot use a fast backend (recommended)'))
                self.SplashA = QtWidgets.QRadioButton(_('Always'))
                self.SplashN = QtWidgets.QRadioButton(_('Never'))
                self.SplashG = QtWidgets.QButtonGroup() # huge glitches if it's not assigned to self.something
                self.SplashG.setExclusive(True)
                self.SplashG.addButton(self.SplashR)
                self.SplashG.addButton(self.SplashA)
                self.SplashG.addButton(self.SplashN)
                SplashL = QtWidgets.QVBoxLayout()
                SplashL.addWidget(self.SplashR)
                SplashL.addWidget(self.SplashA)
                SplashL.addWidget(self.SplashN)

                # Add the Translation Language setting
                self.Trans = QtWidgets.QComboBox()
                self.Trans.setMaximumWidth(256)

                # Create the main layout
                L = QtWidgets.QFormLayout()
                L.addRow(_('Show the splash screen:'), SplashL)
                L.addRow(_('Language:'), self.Trans)
                self.setLayout(L)

                # Set the buttons
                self.Reset()


            def Reset(self):
                """
                Read the preferences and check the respective boxes
                """
                if str(setting('ShowSplash')): self.SplashA.setChecked(True)
                elif str(setting('ShowSplash')): self.SplashN.setChecked(True)
                else: self.SplashR.setChecked(True)

                self.Trans.addItem('English')
                self.Trans.setItemData(0, None, Qt.UserRole)
                self.Trans.setCurrentIndex(0)
                i = 1
                for trans in os.listdir('metamakerdata/translations'):
                    if trans.lower() == 'english': continue

                    fp = 'metamakerdata/translations/' + trans + '/main.xml'
                    if not os.path.isfile(fp): continue

                    transobj = MetamakerTranslation(trans)
                    name = transobj.name
                    self.Trans.addItem(name)
                    self.Trans.setItemData(i, trans, Qt.UserRole)
                    if trans == str(setting('Translation')):
                        self.Trans.setCurrentIndex(i)
                    i += 1


        return GeneralTab(self.menuSettingChanged)


    def getToolbarTab(self):
        """
        Returns the Toolbar Tab
        """

        class ToolbarTab(QtWidgets.QWidget):
            """
            Toolbar Tab
            """
            info = _('<b>Toolbar Preferences</b><br>Choose menu items you would like to appear on the toolbar.<br>Metamaker must be restarted before the toolbar can be updated.<br>')

            def __init__(self):
                """
                Initializes the Toolbar Tab
                """
                global FileActions
                global EditActions
                global ViewActions
                global SettingsActions
                global HelpActions

                super().__init__()

                # Determine which keys are activated
                if setting('ToolbarActs') in (None, 'None', 'none', '', 0):
                    # Get the default settings
                    toggled = {}
                    for List in (FileActions, EditActions, ViewActions, SettingsActions, HelpActions):
                        for name, activated, key in List:
                            toggled[key] = activated
                else: # Get the registry settings
                    toggled = setting('ToolbarActs')
                    newToggled = {} # here, I'm replacing QStrings w/ python strings
                    for key in toggled:
                        newToggled[str(key)] = toggled[key]
                    toggled = newToggled

                # Create some data
                self.FileBoxes = []
                self.EditBoxes = []
                self.ViewBoxes = []
                self.SettingsBoxes = []
                self.HelpBoxes = []
                FL = QtWidgets.QVBoxLayout()
                EL = QtWidgets.QVBoxLayout()
                VL = QtWidgets.QVBoxLayout()
                SL = QtWidgets.QVBoxLayout()
                HL = QtWidgets.QVBoxLayout()
                FB = QtWidgets.QGroupBox(_('&File'))
                EB = QtWidgets.QGroupBox(_('&Edit'))
                VB = QtWidgets.QGroupBox(_('&View'))
                SB = QtWidgets.QGroupBox(_('&Settings'))
                HB = QtWidgets.QGroupBox(_('&Help'))

                # Arrange this data so it can be iterated over
                menuItems = (
                    (FileActions, self.FileBoxes, FL, FB),
                    (EditActions, self.EditBoxes, EL, EB),
                    (ViewActions, self.ViewBoxes, VL, VB),
                    (SettingsActions, self.SettingsBoxes, SL, SB),
                    (HelpActions, self.HelpBoxes, HL, HB),
                )

                # Set up the menus by iterating over the above data
                for defaults, boxes, layout, group in menuItems:
                    for L, C, I in defaults:
                        box = QtWidgets.QCheckBox(L)
                        boxes.append(box)
                        layout.addWidget(box)
                        try: box.setChecked(toggled[I])
                        except KeyError: pass
                        box.InternalName = I # to save settings later
                    group.setLayout(layout)


                # Create the always-enabled Current Course checkbox
                CurrentCourse = QtWidgets.QCheckBox(_('Current Course'))
                CurrentCourse.setChecked(True)
                CurrentCourse.setEnabled(False)

                # Create the Reset button
                reset = QtWidgets.QPushButton(_('Reset'))
                reset.clicked.connect(self.reset)

                # Create the main layout
                L = QtWidgets.QGridLayout()
                L.addWidget(reset,       0, 0, 1, 1)
                L.addWidget(FB,          1, 0, 3, 1)
                L.addWidget(EB,          1, 1, 3, 1)
                L.addWidget(VB,          1, 2, 3, 1)
                L.addWidget(SB,          1, 3, 1, 1)
                L.addWidget(HB,          2, 3, 1, 1)
                L.addWidget(CurrentCourse, 3, 3, 1, 1)
                self.setLayout(L)

            def reset(self):
                """
                This is called when the Reset button is clicked
                """
                items = (
                    (self.FileBoxes, FileActions),
                    (self.EditBoxes, EditActions),
                    (self.ViewBoxes, ViewActions),
                    (self.SettingsBoxes, SettingsActions),
                    (self.HelpBoxes, HelpActions)
                )

                for boxes, defaults in items:
                    for box, default in zip(boxes, defaults):
                        box.setChecked(default[1])

        return ToolbarTab()


    def getThemesTab(self):
        """
        Returns the Themes Tab
        """

        class ThemesTab(QtWidgets.QWidget):
            """
            Themes Tab
            """
            info = _('<b>Metamaker Themes</b><br>Pick a theme below to change application colors and icons.<br>You can download more themes at {a href="rvlution.net"}rvlution.net{/a}.<br>Metamaker must be restarted before the theme can be changed.')

            def __init__(self):
                """
                Initializes the Themes Tab
                """
                super().__init__()

                # Get the current and available themes
                self.themeID = theme.themeName
                self.themes = self.getAvailableThemes()

                # Create the radiobuttons
                self.btns = []
                self.btnvals = {}
                for name, themeObj in self.themes:
                    displayname = name
                    if displayname.lower().endswith('.rt'): displayname = displayname[:-3]

                    btn = QtWidgets.QRadioButton(displayname)
                    if name == str(setting('Theme')): btn.setChecked(True)
                    btn.clicked.connect(self.UpdatePreview)

                    self.btns.append(btn)
                    self.btnvals[btn] = (name, themeObj)

                # Create the buttons group
                btnG = QtWidgets.QButtonGroup()
                btnG.setExclusive(True)
                for btn in self.btns:
                    btnG.addButton(btn)

                # Create the buttons groupbox
                L = QtWidgets.QGridLayout()
                for idx, button in enumerate(self.btns):
                    L.addWidget(btn, idx%12, int(idx/12))
                btnGB = QtWidgets.QGroupBox(_('Available Themes'))
                btnGB.setLayout(L)

                # Create the preview labels and groupbox
                self.preview = QtWidgets.QLabel()
                self.description = QtWidgets.QLabel()
                L = QtWidgets.QVBoxLayout()
                L.addWidget(self.preview)
                L.addWidget(self.description)
                L.addStretch(1)
                previewGB = QtWidgets.QGroupBox(_('Preview'))
                previewGB.setLayout(L)

                # Create the options box options
                keys = QtWidgets.QStyleFactory().keys()
                self.NonWinStyle = QtWidgets.QComboBox()
                self.NonWinStyle.setToolTip(_('<b>Use Nonstandard Window Style</b><br>If this is checkable, the selected theme specifies a<br>window style other than the default. In most cases, you<br>should leave this checked. Uncheck this if you dislike<br>the style this theme uses.'))
                self.NonWinStyle.addItems(keys)
                uistyle = setting('uiStyle')
                if uistyle is not None:
                    self.NonWinStyle.setCurrentIndex(keys.index(setting('uiStyle')))

                # Create the options groupbox
                L = QtWidgets.QVBoxLayout()
                L.addWidget(self.NonWinStyle)
                optionsGB = QtWidgets.QGroupBox(_('Options'))
                optionsGB.setLayout(L)

                # Create a main layout
                L = QtWidgets.QGridLayout()
                L.addWidget(btnGB, 0, 0, 2, 1)
                L.addWidget(optionsGB, 0, 1)
                L.addWidget(previewGB, 1, 1)
                L.setRowStretch(1, 1)
                self.setLayout(L)

                # Update the preview things
                self.UpdatePreview()


            def getAvailableThemes(self):
                """Searches the Themes folder and returns a list of theme filepaths.
                Automatically adds 'Classic' to the list."""
                themes = os.listdir('metamakerdata/themes')
                themeList = [('Classic', MetamakerTheme())]
                for themeName in themes:
                    try:
                        if themeName.split('.')[-1].lower() == 'rt':
                            data = open('metamakerdata/themes/' + themeName, 'rb').read()
                            theme = MetamakerTheme(data)
                            themeList.append((themeName, theme))
                    except Exception: pass

                return tuple(themeList)

            def UpdatePreview(self):
                """
                Updates the preview
                """
                for btn in self.btns:
                    if btn.isChecked():
                        t = self.btnvals[btn][1]
                        self.preview.setPixmap(self.drawPreview(t))
                        text = _('<b>{name}</b><br>By {creator}<br>{description}', 'name', t.themeName, 'creator', t.creator, 'description', t.description)
                        self.description.setText(text)

            def drawPreview(self, theme):
                """
                Returns a preview pixmap for the given theme
                """

                # Set up some things
                px = QtGui.QPixmap(350, 185)
                px.fill(_c('bg'))
                return px


                paint = QtGui.QPainter(px)

                UIColor = _c('ui')
                if UIColor is None: UIColor = toQColor(240, 240, 240) # close enough

                ice = QtGui.QPixmap('metamakerdata/sprites/ice_flow_7.png')

                font = QtGui.QFont(NumberFont) # need to make a new instance to avoid changing global settings
                font.setPointSize(6)
                paint.setFont(font)

                # Draw the spriteboxes
                paint.setPen(QtGui.QPen(_c('spritebox_lines'), 1))
                paint.setBrush(QtGui.QBrush(_c('spritebox_fill')))

                paint.drawRoundedRect(176, 64, 16, 16, 5, 5)
                paint.drawText(QtCore.QPointF(180, 75), '38')

                paint.drawRoundedRect(16, 96, 16, 16, 5, 5)
                paint.drawText(QtCore.QPointF(20, 107), '53')

                # Draw the grid
                paint.setPen(QtGui.QPen(_c('grid'), 1, Qt.DotLine))
                gridcoords = []
                i=0
                while i < 350:
                    gridcoords.append(i)
                    i=i+16
                for i in gridcoords:
                    paint.setPen(QtGui.QPen(_c('grid'), 0.75, Qt.DotLine))
                    paint.drawLine(i, 0, i, 185)
                    paint.drawLine(0, i, 350, i)
                    if (i/16)%4 == 0:
                        paint.setPen(QtGui.QPen(_c('grid'), 1.5, Qt.DotLine))
                        paint.drawLine(i, 0, i, 185)
                        paint.drawLine(0, i, 350, i)
                    if (i/16)%8 == 0:
                        paint.setPen(QtGui.QPen(_c('grid'), 2.25, Qt.DotLine))
                        paint.drawLine(i, 0, i, 185)
                        paint.drawLine(0, i, 350, i)

                # Draw the UI
                paint.setBrush(QtGui.QBrush(UIColor))
                paint.setPen(toQColor(0,0,0,0))
                paint.drawRect(0, 0, 350, 24)
                paint.drawRect(300, 24, 50, 165)

                # Delete the painter and return the pixmap
                del paint
                return px


        return ThemesTab()


class ListWidgetWithToolTipSignal(QtWidgets.QListWidget):
    """
    A QtWidgets.QListWidget that includes a signal that
    is emitted when a tooltip is about to be shown. Useful
    for making tooltips that update every time you show
    them.
    """
    toolTipAboutToShow = QtCore.pyqtSignal(QtWidgets.QListWidgetItem)

    def viewportEvent(self, e):
        """
        Handles viewport events
        """
        if e.type() == e.ToolTip:
            self.toolTipAboutToShow.emit(self.itemFromIndex(self.indexAt(e.pos())))

        return super().viewportEvent(e)



####################################################################
####################################################################
####################################################################



class MetamakerWindow(QtWidgets.QMainWindow):
    """
    Metamaker main course editor window
    """
    ZoomLevel = 100

    Filetypes = ''
    Filetypes += _('SMM Course Data Table') + ' (*.cdt);;'
    Filetypes += _('Archived SMM Course') + ' (*.sarc);;'
    Filetypes += _('Compressed SMM Course') + ' (*.szs);;'
    Filetypes += _('All files') + ' (*)'

    def CreateAction(self, shortname, function, icon, text, statustext, shortcut, toggle=False):
        """
        Helper function to create an action
        """

        if icon is not None:
            act = QtWidgets.QAction(icon, text, self)
        else:
            act = QtWidgets.QAction(text, self)

        if shortcut is not None: act.setShortcut(shortcut)
        if statustext is not None: act.setStatusTip(statustext)
        if toggle:
            act.setCheckable(True)
        if function is not None: act.triggered.connect(function)

        self.actions[shortname] = act


    def __init__(self):
        """
        Editor window constructor
        """
        super().__init__(None)
        global Initializing
        Initializing = True

        # Metamaker Version number goes below here. 64 char max (32 if non-ascii).
        self.MetamakerInfo = METAMAKER_ID

        self.ZoomLevels = [7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 85.0, 90.0, 95.0, 100.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 350.0, 400.0]

        self.AutosaveTimer = QtCore.QTimer()
        self.AutosaveTimer.timeout.connect(self.Autosave)
        self.AutosaveTimer.start(20000)

        # required variables
        self.UpdateFlag = False
        self.SelectionUpdateFlag = False
        self.selObj = None
        self.CurrentSelection = []


        # set up the window
        self.setWindowTitle(_('Metamaker {version}', 'version', METAMAKER_VERSION))
        self.setWindowIcon(QtGui.QIcon('metamakerdata/icon.png'))
        self.setIconSize(QtCore.QSize(16, 16))

        # create the course scene and view
        self.scene = CourseScene(
            X_MIN * TILE_WIDTH,
            - (Y_MAX + 1) * TILE_WIDTH,
            (X_MAX - X_MIN + 1) * TILE_WIDTH,
            (Y_MAX - Y_MIN + 1) * TILE_WIDTH,
            self)
        self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        self.scene.selectionChanged.connect(self.ChangeSelectionHandler)

        self.view = CourseViewWidget(self.scene, self)
        self.view.centerOn(0, 0) # this scrolls to the top left
        self.view.PositionHover.connect(self.PositionHovered)
        self.view.XScrollBar.valueChanged.connect(self.XScrollChange)
        self.view.YScrollBar.valueChanged.connect(self.YScrollChange)
        self.view.FrameSize.connect(self.HandleWindowSizeChange)

        # done creating the window!
        self.setCentralWidget(self.view)

        # set up the clipboard stuff
        self.clipboard = None
        self.systemClipboard = QtWidgets.QApplication.clipboard()
        self.systemClipboard.dataChanged.connect(self.TrackClipboardUpdates)

        # we might have something there already, activate Paste if so
        self.TrackClipboardUpdates()


    def __init2__(self):
        """
        Finishes initialization. (fixes bugs with some widgets calling mainWindow.something before it's fully init'ed)
        """
        # set up actions and menus
        self.SetupActionsAndMenus()

        # set up the status bar
        self.posLabel = QtWidgets.QLabel()
        self.selectionLabel = QtWidgets.QLabel()
        self.hoverLabel = QtWidgets.QLabel()
        self.statusBar().addWidget(self.posLabel)
        self.statusBar().addWidget(self.selectionLabel)
        self.statusBar().addWidget(self.hoverLabel)
        self.ZoomWidget = ZoomWidget()
        self.ZoomStatusWidget = ZoomStatusWidget()
        self.statusBar().addPermanentWidget(self.ZoomWidget)
        self.statusBar().addPermanentWidget(self.ZoomStatusWidget)

        # create the various panels
        self.SetupDocksAndPanels()

        # load something
        fn = QtWidgets.QFileDialog.getOpenFileName(self, _('Choose a course'), '', self.Filetypes)[0]
        if fn: # the rest are optional

            mfp = QtWidgets.QFileDialog.getExistingDirectory(self, _('Find SMM\'s Model folder'))
            pfp = QtWidgets.QFileDialog.getExistingDirectory(self, _('Find SMM\'s Pack folder'))

            self.SetupAssets(mfp, pfp)

            if not self.LoadCourse(fn, True, 1):
                self.close()

        else:
            raise Exception(_('You didn\'t pick a course file!'))

        QtCore.QTimer.singleShot(100, self.courseOverview.update)

        toggleHandlers = {
            self.HandleSpritesVisibility: SpritesShown,
            self.HandleSpriteImages: SpriteImagesShown,
            }
        for handler in toggleHandlers:
            handler(toggleHandlers[handler]) # call each toggle-button handler to set each feature correctly upon startup

        # let's restore the state and geometry
        # geometry: determines the main window position
        # state: determines positions of docks
        if settings.contains('MainWindowGeometry'):
            self.restoreGeometry(setting('MainWindowGeometry'))
        if settings.contains('MainWindowState'):
            self.restoreState(setting('MainWindowState'), 0)

        # Aaaaaand... initializing is done!
        Initializing = False


    def SetupActionsAndMenus(self):
        """
        Sets up Metamaker's actions, menus and toolbars
        """
        self.createMenubar()

    actions = {}
    def createMenubar(self):
        """
        Create actions, a menubar and a toolbar
        """

        # File
        self.CreateAction('newcourse', self.HandleNewCourse, GetIcon('new'), _('New Course'), _('Create a new, blank course'), QtGui.QKeySequence.New)
        self.CreateAction('openfromname', self.HandleOpenFromName, GetIcon('open'), _('Open Sample Course by Name...'), _('Open a sample course based on its name'), QtGui.QKeySequence.Open)
        self.CreateAction('openfromfile', self.HandleOpenFromFile, GetIcon('openfromfile'), _('Open Course by File...'), _('Open a course based on its filename'), QtGui.QKeySequence('Ctrl+Shift+O'))
        self.CreateAction('save', self.HandleSave, GetIcon('save'), _('Save Course'), _('Save the course back to the original file'), QtGui.QKeySequence.Save)
        self.CreateAction('saveas', self.HandleSaveAs, GetIcon('saveas'), _('Save Course As...'), _('Save the course to a new file'), QtGui.QKeySequence.SaveAs)
        self.CreateAction('screenshot', self.HandleScreenshot, GetIcon('screenshot'), _('Course Screenshot...'), _('Take a full size screenshot of your course for you to share'), QtGui.QKeySequence('Ctrl+Alt+S'))
        self.CreateAction('importmidi', self.HandleImportMIDI, GetIcon('spritesfreeze'), _('Import MIDI...'), _('Import a .midi song to convert into sprites for your level'), QtGui.QKeySequence('Ctrl+I'))
        self.CreateAction('preferences', self.HandlePreferences, GetIcon('settings'), _('Metamaker Preferences...'), _('Change important Metamaker settings'), QtGui.QKeySequence('Ctrl+Alt+P'))
        self.CreateAction('exit', self.HandleExit, GetIcon('delete'), _('Exit Metamaker'), _('Exit the editor'), QtGui.QKeySequence('Ctrl+Q'))

        # Edit
        self.CreateAction('selectall', self.SelectAll, GetIcon('selectall'), _('Select All'), _('Select all items in this course'), QtGui.QKeySequence.SelectAll)
        self.CreateAction('deselect', self.Deselect, GetIcon('deselect'), _('Deselect'), _('Deselect all currently selected items'), QtGui.QKeySequence('Ctrl+D'))
        self.CreateAction('cut', self.Cut, GetIcon('cut'), _('Cut'), _('Cut out the current selection to the clipboard'), QtGui.QKeySequence.Cut)
        self.CreateAction('copy', self.Copy, GetIcon('copy'), _('Copy'), _('Copy the current selection to the clipboard'), QtGui.QKeySequence.Copy)
        self.CreateAction('paste', self.Paste, GetIcon('paste'), _('Paste'), _('Paste items from the clipboard'), QtGui.QKeySequence.Paste)
        self.CreateAction('freezesprites', self.HandleSpritesFreeze, GetIcon('spritesfreeze'), _('Freeze Sprites'), _('Make sprites non-selectable'), QtGui.QKeySequence('Ctrl+Shift+2'), True)
        self.CreateAction('regenground', self.HandleRegenerateGround, GetIcon('spritesfreeze'), _('Regenerate Ground'), _('Recalculate ground edges for selected ground sprites (sprite type 7)'), QtGui.QKeySequence('Ctrl+R'))

        # View
        self.CreateAction('realview', self.HandleRealViewToggle, GetIcon('realview'), _('Real View'), _('Show special effects present in the course'), QtGui.QKeySequence('Ctrl+9'), True)
        self.CreateAction('showsprites', self.HandleSpritesVisibility, GetIcon('sprites'), _('Show Sprites'), _('Toggle viewing of sprites'), QtGui.QKeySequence('Ctrl+4'), True)
        self.CreateAction('showspriteimages', self.HandleSpriteImages, GetIcon('sprites'), _('Show Sprite Images'), _('Toggle viewing of sprite images'), QtGui.QKeySequence('Ctrl+6'), True)
        self.CreateAction('fullscreen', self.HandleFullscreen, GetIcon('fullscreen'), _('Show Fullscreen'), _('Display the main window with all available screen space'), QtGui.QKeySequence('Ctrl+U'), True)
        self.CreateAction('grid', self.HandleSwitchGrid, GetIcon('grid'), _('Switch Grid'), _('Cycle through available grid views'), QtGui.QKeySequence('Ctrl+G'), False)
        self.CreateAction('zoommax', self.HandleZoomMax, GetIcon('zoommax'), _('Zoom to Maximum'), _('Zoom in all the way'), QtGui.QKeySequence('Ctrl+PgDown'), False)
        self.CreateAction('zoomin', self.HandleZoomIn, GetIcon('zoomin'), _('Zoom In'), _('Zoom into the main course view'), QtGui.QKeySequence.ZoomIn, False)
        self.CreateAction('zoomactual', self.HandleZoomActual, GetIcon('zoomactual'), _('Zoom 100%'), _('Show the course at the default zoom'), QtGui.QKeySequence('Ctrl+0'), False)
        self.CreateAction('zoomout', self.HandleZoomOut, GetIcon('zoomout'), _('Zoom Out'), _('Zoom out of the main course view'), QtGui.QKeySequence.ZoomOut, False)
        self.CreateAction('zoommin', self.HandleZoomMin, GetIcon('zoommin'), _('Zoom to Minimum'), _('Zoom out all the way'), QtGui.QKeySequence('Ctrl+PgUp'), False)
        # Show Overview and Show Palette are added later

        # Help
        self.CreateAction('infobox', self.AboutBox, GetIcon('metamaker'), _('About Metamaker'), _('Info about the program, and the team behind it'), QtGui.QKeySequence('Ctrl+Shift+I'))
        self.CreateAction('helpbox', self.HelpBox, GetIcon('contents'), _('Help Contents...'), _('Help documentation for the needy newbie'), QtGui.QKeySequence('Ctrl+Shift+H'))
        self.CreateAction('tipbox', self.TipBox, GetIcon('tips'), _('Metamaker Tips...'), _('Tips and controls for beginners and power users'), QtGui.QKeySequence('Ctrl+Shift+T'))
        self.CreateAction('aboutqt', QtWidgets.qApp.aboutQt, GetIcon('qt'), _('About PyQt...'), _('About the Qt library Metamaker is based on'), QtGui.QKeySequence('Ctrl+Shift+Q'))

        # Settings
        self.CreateAction('courseoptions', self.HandleCourseOptions, GetIcon('course'), _('Course Settings...'), _('Control stage timer, etc'), QtGui.QKeySequence('Ctrl+Alt+A'))

        # Help actions are created later

        # Configure them
        self.actions['importmidi'].setEnabled(HAS_MIDO)

        self.actions['realview'].setChecked(RealViewEnabled)

        self.actions['showsprites'].setChecked(SpritesShown)
        self.actions['showspriteimages'].setChecked(SpriteImagesShown)

        self.actions['freezesprites'].setChecked(SpritesFrozen)

        self.actions['cut'].setEnabled(False)
        self.actions['copy'].setEnabled(False)
        self.actions['paste'].setEnabled(False)
        self.actions['deselect'].setEnabled(False)


        ####
        menubar = QtWidgets.QMenuBar()
        self.setMenuBar(menubar)


        fmenu = menubar.addMenu(_('&File'))
        fmenu.addAction(self.actions['newcourse'])
        fmenu.addAction(self.actions['openfromname'])
        fmenu.addAction(self.actions['openfromfile'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['save'])
        fmenu.addAction(self.actions['saveas'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['screenshot'])
        fmenu.addAction(self.actions['importmidi'])
        fmenu.addAction(self.actions['preferences'])
        fmenu.addSeparator()
        fmenu.addAction(self.actions['exit'])

        emenu = menubar.addMenu(_('&Edit'))
        emenu.addAction(self.actions['selectall'])
        emenu.addAction(self.actions['deselect'])
        emenu.addSeparator()
        emenu.addAction(self.actions['cut'])
        emenu.addAction(self.actions['copy'])
        emenu.addAction(self.actions['paste'])
        emenu.addSeparator()
        emenu.addAction(self.actions['freezesprites'])
        emenu.addSeparator()
        emenu.addAction(self.actions['regenground'])

        vmenu = menubar.addMenu(_('&View'))
        vmenu.addAction(self.actions['realview'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['showsprites'])
        vmenu.addAction(self.actions['showspriteimages'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['fullscreen'])
        vmenu.addAction(self.actions['grid'])
        vmenu.addSeparator()
        vmenu.addAction(self.actions['zoommax'])
        vmenu.addAction(self.actions['zoomin'])
        vmenu.addAction(self.actions['zoomactual'])
        vmenu.addAction(self.actions['zoomout'])
        vmenu.addAction(self.actions['zoommin'])
        vmenu.addSeparator()
        # self.courseOverviewDock.toggleViewAction() is added here later
        # so we assign it to self.vmenu
        self.vmenu = vmenu

        lmenu = menubar.addMenu(_('&Settings'))
        lmenu.addAction(self.actions['courseoptions'])

        hmenu = menubar.addMenu(_('&Help'))
        hmenu.addAction(self.actions['infobox'])
        hmenu.addAction(self.actions['helpbox'])
        hmenu.addAction(self.actions['tipbox'])
        hmenu.addSeparator()
        hmenu.addAction(self.actions['aboutqt'])

        # create a toolbar
        self.toolbar = self.addToolBar(_('Editor Toolbar'))
        self.toolbar.setObjectName('MainToolbar')



    def SetupDocksAndPanels(self):
        """
        Sets up the dock widgets and panels
        """
        # course overview
        dock = QtWidgets.QDockWidget(_('Overview'), self)
        dock.setFeatures(dock.features() | dock.DockWidgetVerticalTitleBar)
        dock.setObjectName('courseoverview') # needed for the state to save/restore correctly

        self.courseOverview = CourseOverviewWidget()
        self.courseOverview.moveIt.connect(self.HandleOverviewClick)
        self.courseOverviewDock = dock
        dock.setWidget(self.courseOverview)

        self.addDockWidget(Qt.TopDockWidgetArea, dock)
        dock.setVisible(True)
        act = dock.toggleViewAction()
        act.setShortcut(QtGui.QKeySequence('Ctrl+M'))
        act.setIcon(GetIcon('overview'))
        act.setStatusTip(_('Show or hide the Course Overview window'))
        self.vmenu.addAction(act)

        # create the sprite editor panel
        dock = QtWidgets.QDockWidget(_('Modify Selected Sprite Properties'), self)
        dock.setVisible(False)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('spriteeditor') #needed for the state to save/restore correctly

        self.spriteDataEditor = SpriteEditorWidget()
        self.spriteDataEditor.DataUpdate.connect(self.SpriteDataUpdated)
        dock.setWidget(self.spriteDataEditor)
        self.spriteEditorDock = dock

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)


        # create the palette
        dock = QtWidgets.QDockWidget(_('Palette'), self)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable | QtWidgets.QDockWidget.DockWidgetClosable)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setObjectName('palette') #needed for the state to save/restore correctly

        self.creationDock = dock
        act = dock.toggleViewAction()
        act.setShortcut(QtGui.QKeySequence('Ctrl+P'))
        act.setIcon(GetIcon('palette'))
        act.setStatusTip(_('Show or hide the Palette window'))
        self.vmenu.addAction(act)

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setVisible(True)


        # add tabs to it
        tabs = QtWidgets.QTabWidget()
        tabs.setIconSize(QtCore.QSize(16, 16))
        tabs.currentChanged.connect(self.CreationTabChanged)
        dock.setWidget(tabs)
        self.creationTabs = tabs

        # sprite tab: add
        self.sprPickerTab = QtWidgets.QWidget()
        tabs.addTab(self.sprPickerTab, GetIcon('spritesadd'), _('Add'))

        spl = QtWidgets.QVBoxLayout(self.sprPickerTab)
        self.sprPickerLayout = spl

        svpl = QtWidgets.QHBoxLayout()
        svpl.addWidget(QtWidgets.QLabel(_('View:')))

        sspl = QtWidgets.QHBoxLayout()
        sspl.addWidget(QtWidgets.QLabel(_('Search:')))

        LoadSpriteCategories()
        viewpicker = QtWidgets.QComboBox()
        for view in SpriteCategories:
            viewpicker.addItem(view[0])
        viewpicker.currentIndexChanged.connect(self.SelectNewSpriteView)

        self.spriteViewPicker = viewpicker
        svpl.addWidget(viewpicker, 1)

        self.spriteSearchTerm = QtWidgets.QLineEdit()
        self.spriteSearchTerm.textChanged.connect(self.NewSearchTerm)
        sspl.addWidget(self.spriteSearchTerm, 1)

        spl.addLayout(svpl)
        spl.addLayout(sspl)

        self.spriteSearchLayout = sspl
        sspl.itemAt(0).widget().setVisible(False)
        sspl.itemAt(1).widget().setVisible(False)

        self.sprPicker = SpritePickerWidget()
        self.sprPicker.SpriteChanged.connect(self.SpriteChoiceChanged)
        self.sprPicker.SpriteReplace.connect(self.SpriteReplace)
        self.sprPicker.SwitchView(SpriteCategories[0])
        spl.addWidget(self.sprPicker, 1)

        self.defaultPropButton = QtWidgets.QPushButton(_('Set Default Properties'))
        self.defaultPropButton.setEnabled(False)
        self.defaultPropButton.clicked.connect(self.ShowDefaultProps)

        sdpl = QtWidgets.QHBoxLayout()
        sdpl.addStretch(1)
        sdpl.addWidget(self.defaultPropButton)
        sdpl.addStretch(1)
        spl.addLayout(sdpl)

        # default sprite data editor
        ddock = QtWidgets.QDockWidget(_('Default Properties'), self)
        ddock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable | QtWidgets.QDockWidget.DockWidgetClosable)
        ddock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        ddock.setObjectName('defaultprops') #needed for the state to save/restore correctly

        self.defaultDataEditor = SpriteEditorWidget(True)
        self.defaultDataEditor.setVisible(False)
        ddock.setWidget(self.defaultDataEditor)

        self.addDockWidget(Qt.RightDockWidgetArea, ddock)
        ddock.setVisible(False)
        ddock.setFloating(True)
        self.defaultPropDock = ddock

        # sprite tab: current
        self.sprEditorTab = QtWidgets.QWidget()
        tabs.addTab(self.sprEditorTab, GetIcon('spritelist'), _('Current'))

        spel = QtWidgets.QVBoxLayout(self.sprEditorTab)
        self.sprEditorLayout = spel

        slabel = QtWidgets.QLabel(_('Sprites currently in this course:<br>(Double-click one to jump to it instantly)'))
        slabel.setWordWrap(True)
        self.spriteList = ListWidgetWithToolTipSignal()
        self.spriteList.itemActivated.connect(self.HandleSpriteSelectByList)
        self.spriteList.toolTipAboutToShow.connect(self.HandleSpriteToolTipAboutToShow)
        self.spriteList.setSortingEnabled(True)

        spel.addWidget(slabel)
        spel.addWidget(self.spriteList)


        # Set the current tab to the Sprites tab
        self.CreationTabChanged(0)


    @QtCore.pyqtSlot()
    def Autosave(self):
        """
        Auto saves the course
        """
        return
        global AutoSaveDirty
        if not AutoSaveDirty: return

        data = Course.save()
        setSetting('AutoSaveFilePath', self.fileSavePath)
        setSetting('AutoSaveFileData', QtCore.QByteArray(data))
        AutoSaveDirty = False


    @QtCore.pyqtSlot()
    def TrackClipboardUpdates(self):
        """
        Catches systemwide clipboard updates
        """
        if Initializing: return
        clip = self.systemClipboard.text()
        if clip is not None and clip != '':
            clip = str(clip).strip()

            if clip.startswith('MetamakerClip|') and clip.endswith('|%'):
                self.clipboard = clip.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
                self.actions['paste'].setEnabled(True)
            else:
                self.clipboard = None
                self.actions['paste'].setEnabled(False)


    @QtCore.pyqtSlot(int)
    def XScrollChange(self, pos):
        """
        Moves the Overview current position box based on X scroll bar value
        """
        self.courseOverview.Xposlocator = pos
        self.courseOverview.update()

    @QtCore.pyqtSlot(int)
    def YScrollChange(self, pos):
        """
        Moves the Overview current position box based on Y scroll bar value
        """
        self.courseOverview.Yposlocator = -pos
        self.courseOverview.update()

    @QtCore.pyqtSlot(int, int)
    def HandleWindowSizeChange(self, w, h):
        self.courseOverview.Hlocator = h
        self.courseOverview.Wlocator = w
        self.courseOverview.update()

    def UpdateTitle(self):
        """
        Sets the window title accordingly
        """
        self.setWindowTitle(_(
            'Metamaker {ver} - {title} {unsaved}',
            'ver', METAMAKER_VERSION,
            'title', self.fileTitle,
            'unsaved', _('(unsaved)') if Dirty else '',
        ))

    def CheckDirty(self):
        """
        Checks if the course is unsaved and asks for a confirmation if so - if it returns True, Cancel was picked
        """
        if not Dirty: return False

        msg = QtWidgets.QMessageBox()
        msg.setText(_('The course has unsaved changes in it.'))
        msg.setInformativeText(_('Do you want to save them?'))
        msg.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        msg.setDefaultButton(QtWidgets.QMessageBox.Save)
        ret = msg.exec_()

        if ret == QtWidgets.QMessageBox.Save:
            if not self.HandleSave():
                # save failed
                return True
            return False
        elif ret == QtWidgets.QMessageBox.Discard:
            return False
        elif ret == QtWidgets.QMessageBox.Cancel:
            return True



    @QtCore.pyqtSlot()
    def AboutBox(self):
        """
        Shows the about box
        """
        AboutDialog().exec_()


    @QtCore.pyqtSlot()
    def HelpBox(self):
        """
        Shows the help box
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.join(module_path(), 'metamakerdata', 'help', 'index.html')))


    @QtCore.pyqtSlot()
    def TipBox(self):
        """
        Metamaker Tips and Commands
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.join(module_path(), 'metamakerdata', 'help', 'tips.html')))


    @QtCore.pyqtSlot()
    def SelectAll(self):
        """
        Select all sprites in the current course
        """
        paintRect = QtGui.QPainterPath()
        x, y = X_MIN * TILE_WIDTH, -Y_MAX * TILE_WIDTH
        w, h = X_MAX * TILE_WIDTH - x, -Y_MIN * TILE_WIDTH - y
        paintRect.addRect(x, y, w, h)
        self.scene.setSelectionArea(paintRect)


    @QtCore.pyqtSlot()
    def Deselect(self):
        """
        Deselect all currently selected items
        """
        items = self.scene.selectedItems()
        for obj in items:
            obj.setSelected(False)


    @QtCore.pyqtSlot()
    def Cut(self):
        """
        Cuts the selected items
        """
        self.SelectionUpdateFlag = True
        selitems = self.scene.selectedItems()
        self.scene.clearSelection()

        if len(selitems) > 0:
            clipboard_s = []
            ii = isinstance
            type_spr = SpriteItem

            for obj in selitems:
                if ii(obj, type_spr):
                    obj.delete()
                    obj.setSelected(False)
                    self.scene.removeItem(obj)
                    clipboard_s.append(obj)

            if len(clipboard_o) > 0 or len(clipboard_s) > 0:
                SetDirty()
                self.actions['cut'].setEnabled(False)
                self.actions['paste'].setEnabled(True)
                self.clipboard = self.encodeObjects([], clipboard_s)
                self.systemClipboard.setText(self.clipboard)

        self.courseOverview.update()
        self.SelectionUpdateFlag = False
        self.ChangeSelectionHandler()

    @QtCore.pyqtSlot()
    def Copy(self):
        """
        Copies the selected items
        """
        selitems = self.scene.selectedItems()
        if len(selitems) > 0:
            clipboard_o = []
            clipboard_s = []
            ii = isinstance
            type_spr = SpriteItem

            for obj in selitems:
                if ii(obj, type_spr):
                    clipboard_s.append(obj)

            if len(clipboard_o) > 0 or len(clipboard_s) > 0:
                self.actions['paste'].setEnabled(True)
                self.clipboard = self.encodeObjects([], clipboard_s)
                self.systemClipboard.setText(self.clipboard)

    @QtCore.pyqtSlot()
    def Paste(self):
        """
        Paste the selected items
        """
        if self.clipboard is not None:
            self.placeEncodedObjects(self.clipboard)

    def encodeObjects(self, clipboard_o, clipboard_s):
        """
        Encode a set of objects and sprites into a string
        """
        convclip = ['MetamakerClip']

        # get sprites
        for item in clipboard_s:
            data = item.spritedata
            convclip.append('1:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d' % (item.type, item.objx, item.objy, data[0], data[1], data[2], data[3], data[4], data[5], data[7]))

        convclip.append('%')
        return '|'.join(convclip)

    def placeEncodedObjects(self, encoded, select=True, xOverride=None, yOverride=None):
        """
        Decode and place a set of objects
        """
        self.SelectionUpdateFlag = True
        self.scene.clearSelection()
        added = []

        x1 = X_MAX
        x2 = X_MIN
        y1 = Y_MAX
        y2 = Y_MIN

        global OverrideSnapping
        OverrideSnapping = True

        if not (encoded.startswith('MetamakerClip|') and encoded.endswith('|%')): return

        clip = encoded.split('|')[1:-1]

        if len(clip) > 300:
            result = QtWidgets.QMessageBox.warning(self, 'Metamaker', _("You're trying to paste over 300 items at once.<br>This may take a while (depending on your computer speed), are you sure you want to continue?"), QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.No: return

        sprites = self.getEncodedObjects(encoded)

        # Go through the sprites
        for spr in sprites:
            x = spr.objx / 16
            y = spr.objy / 16
            if x < x1: x1 = x
            if x > x2: x2 = x
            if y < y1: y1 = y
            if y > y2: y2 = y

            Course.sprites.append(spr)
            added.append(spr)
            self.scene.addItem(spr)

        # now center everything
        zoomscaler = (self.ZoomLevel / 100.0)
        width = x2 - x1 + 1
        height = y2 - y1 + 1
        viewportx = (self.view.XScrollBar.value() / zoomscaler) / TILE_WIDTH
        viewporty = (self.view.YScrollBar.value() / zoomscaler) / TILE_WIDTH
        viewportwidth = (self.view.width() / zoomscaler) / TILE_WIDTH
        viewportheight = (self.view.height() / zoomscaler) / TILE_WIDTH

        for item in added: item.setSelected(select)

        OverrideSnapping = False

        self.courseOverview.update()
        SetDirty()
        self.SelectionUpdateFlag = False
        self.ChangeSelectionHandler()

        return added

    def getEncodedObjects(self, encoded):
        """
        Create the objects from a MetamakerClip
        """

        sprites = []

        try:
            if not (encoded.startswith('MetamakerClip|') and encoded.endswith('|%')): return

            clip = encoded[11:-2].split('|')

            if len(clip) > 300:
                result = QtWidgets.QMessageBox.warning(self, 'Metamaker', _("You're trying to paste over 300 items at once.<br>This may take a while (depending on your computer speed), are you sure you want to continue?"), QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
                if result == QtWidgets.QMessageBox.No:
                    return

            for item in clip:
                # Check to see whether it's an object or sprite
                # and add it to the correct stack
                split = item.split(':')
                if split[0] == '0':
                    print('Those things no longer exist.')

                elif split[0] == '1':
                    # sprite
                    if len(split) != 11: continue

                    objx = int(split[2])
                    objy = int(split[3])
                    data = bytes(map(int, [split[4], split[5], split[6], split[7], split[8], split[9], '0', split[10], '0', '0', '0', '0', '0', '0']))

                    x = objx / 16
                    y = objy / 16

                    newitem = SpriteItem(int(split[1]), objx, objy, data)
                    sprites.append(newitem)

        except ValueError:
            # an int() probably failed somewhere
            pass

        return sprites


    @QtCore.pyqtSlot()
    def HandlePreferences(self):
        """
        Edit Metamaker preferences
        """

        # Show the dialog
        dlg = PreferencesDialog()
        if dlg.exec_() == QtWidgets.QDialog.Rejected:
            return


        # Get the splash screen setting
        if dlg.generalTab.SplashA.isChecked():
            setSetting('ShowSplash', True)
        elif dlg.generalTab.SplashN.isChecked():
            setSetting('ShowSplash', False)
        else:
            setSetting('ShowSplash', 'TPLLib')

        # Get the translation
        name = str(dlg.generalTab.Trans.itemData(dlg.generalTab.Trans.currentIndex(), Qt.UserRole))
        setSetting('Translation', name)

        # Get the Toolbar tab settings
        boxes = (dlg.toolbarTab.FileBoxes, dlg.toolbarTab.EditBoxes, dlg.toolbarTab.ViewBoxes, dlg.toolbarTab.SettingsBoxes, dlg.toolbarTab.HelpBoxes)
        ToolbarSettings = {}
        for boxList in boxes:
            for box in boxList:
                ToolbarSettings[box.InternalName] = box.isChecked()
        setSetting('ToolbarActs', ToolbarSettings)

        # Get the theme settings
        for btn in dlg.themesTab.btns:
            if btn.isChecked():
                setSetting('Theme', dlg.themesTab.btnvals[btn][0])
                break
        setSetting('uiStyle', dlg.themesTab.NonWinStyle.currentText())

        # Warn the user that they may need to restart
        QtWidgets.QMessageBox.warning(None, _('Metamaker Preferences'), _('You may need to restart Metamaker for changes to take effect.'))


    @QtCore.pyqtSlot()
    def HandleNewCourse(self):
        """
        Create a new course
        """
        if self.CheckDirty(): return
        self.LoadCourse(None, False, 1)


    @QtCore.pyqtSlot()
    def HandleOpenFromName(self):
        """
        Open a course using the course picker
        """
        if self.CheckDirty(): return

        LoadCourseNames()
        dlg = ChooseCourseNameDialog()
        if dlg.exec_() == dlg.Accepted:
            self.LoadCourse(dlg.currentcourse, False, 1)


    @QtCore.pyqtSlot()
    def HandleOpenFromFile(self):
        """
        Open a course using the filename
        """
        if self.CheckDirty(): return

        fn = QtWidgets.QFileDialog.getOpenFileName(self, _('Choose a course archive'), '', self.Filetypes)[0]
        if fn == '': return
        self.LoadCourse(str(fn), True, 1)


    @QtCore.pyqtSlot()
    def HandleSave(self):
        """
        Save a course back to the archive
        """
        if not mainWindow.fileSavePath:
            self.HandleSaveAs()
            return

        global Dirty, AutoSaveDirty
        data = Course.save()
        try:
            with open(self.fileSavePath, 'wb') as f:
                f.write(data)
        except IOError as e:
            QtWidgets.QMessageBox.warning(None, _('Error'), _('Error while Metamaker was trying to save the course:<br>(#{err1}) {err2}<br><br>(Your work has not been saved! Try saving it under a different filename or in a different folder.)', 'err1', e.args[0], 'err2', e.args[1]))
            return False

        Dirty = False
        AutoSaveDirty = False
        self.UpdateTitle()

        #setSetting('AutoSaveFilePath', self.fileSavePath)
        #setSetting('AutoSaveFileData', 'x')
        return True


    @QtCore.pyqtSlot()
    def HandleSaveAs(self):
        """
        Save a course back to the archive, with a new filename
        """
        fn = QtWidgets.QFileDialog.getSaveFileName(self, _('Choose a new filename'), '', self.Filetypes)[0]
        if fn == '': return
        fn = str(fn)

        global Dirty, AutoSaveDirty
        Dirty = False
        AutoSaveDirty = False
        Dirty = False

        self.fileSavePath = fn
        self.fileTitle = os.path.basename(fn)

        data = Course.save()
        with open(fn, 'wb') as f:
            f.write(data)

        #setSetting('AutoSaveFilePath', fn)
        #setSetting('AutoSaveFileData', 'x')

        self.UpdateTitle()


    def HandleImportMIDI(self):
        """
        Import a .midi song into the level
        """

        dlg = MidiImportDialog()

        if dlg.exec_() != dlg.Accepted: return

        for type_, x, y, data in midi2sprites.convertToSprPosList(dlg.midi, dlg.paramsInfo):
            newitem = SpriteItem(type_=type_, x=x, y=y, sprdata=data[:4], sprdata2=data[4:])

            newitem.listitem = ListWidgetItem_SortsByOther(newitem, newitem.ListString())
            mainWindow.spriteList.addItem(newitem.listitem)
            Course.sprites.append(newitem)
            mainWindow.scene.addItem(newitem)
            newitem.UpdateListItem()
            SetDirty()

        self.scene.update()
        self.courseOverview.update()


    @QtCore.pyqtSlot()
    def HandleExit(self):
        """
        Exit the editor. Why would you want to do this anyway?
        """
        self.close()


    @QtCore.pyqtSlot(bool)
    def HandleRealViewToggle(self, checked):
        """
        Handle toggling of Real View
        """
        global RealViewEnabled

        RealViewEnabled = checked
        SLib.RealViewEnabled = RealViewEnabled

        setSetting('RealViewEnabled', RealViewEnabled)
        self.scene.update()


    @QtCore.pyqtSlot(bool)
    def HandleSpritesVisibility(self, checked):
        """
        Handle toggling of sprite visibility
        """
        global SpritesShown

        SpritesShown = checked

        if Course is not None:
            for spr in Course.sprites:
                spr.setVisible(SpritesShown)

        setSetting('ShowSprites', SpritesShown)
        self.scene.update()


    @QtCore.pyqtSlot(bool)
    def HandleSpriteImages(self, checked):
        """
        Handle toggling of sprite images
        """
        global SpriteImagesShown

        SpriteImagesShown = checked

        setSetting('ShowSpriteImages', SpriteImagesShown)

        if Course is not None:
            for spr in Course.sprites:
                spr.UpdateRects()
                spr.resetPos()

        self.scene.update()


    @QtCore.pyqtSlot(bool)
    def HandleSpritesFreeze(self, checked):
        """
        Handle toggling of sprites being frozen
        """
        global SpritesFrozen

        SpritesFrozen = checked
        flag1 = QtWidgets.QGraphicsItem.ItemIsSelectable
        flag2 = QtWidgets.QGraphicsItem.ItemIsMovable

        if Course is not None:
            for spr in Course.sprites:
                spr.setFlag(flag1, not SpritesFrozen)
                spr.setFlag(flag2, not SpritesFrozen)

        setSetting('FreezeSprites', SpritesFrozen)
        self.scene.update()


    def HandleRegenerateGround(self):
        """
        Recalculate edge pieces for selected ground sprites (sprite 7)
        """
        selitems = self.scene.selectedItems()
        if len(selitems) == 0: return

        Course.regenerateGround(selitems)


    @QtCore.pyqtSlot(bool)
    def HandleFullscreen(self, checked):
        """
        Handle fullscreen mode
        """
        if checked:
            self.showFullScreen()
        else:
            self.showMaximized()


    @QtCore.pyqtSlot()
    def HandleSwitchGrid(self):
        """
        Handle switching of the grid view
        """
        global GridType

        if GridType is None: GridType = 'grid'
        elif GridType == 'grid': GridType = 'checker'
        else: GridType = None

        setSetting('GridType', GridType)
        self.scene.update()


    @QtCore.pyqtSlot()
    def HandleZoomIn(self):
        """
        Handle zooming in
        """
        z = self.ZoomLevel
        zi = self.ZoomLevels.index(z)
        zi += 1
        if zi < len(self.ZoomLevels):
            self.ZoomTo(self.ZoomLevels[zi])


    @QtCore.pyqtSlot()
    def HandleZoomOut(self):
        """
        Handle zooming out
        """
        z = self.ZoomLevel
        zi = self.ZoomLevels.index(z)
        zi -= 1
        if zi >= 0:
            self.ZoomTo(self.ZoomLevels[zi])


    @QtCore.pyqtSlot()
    def HandleZoomActual(self):
        """
        Handle zooming to the actual size
        """
        self.ZoomTo(100.0)

    @QtCore.pyqtSlot()
    def HandleZoomMin(self):
        """
        Handle zooming to the minimum size
        """
        self.ZoomTo(self.ZoomLevels[0])

    @QtCore.pyqtSlot()
    def HandleZoomMax(self):
        """
        Handle zooming to the maximum size
        """
        self.ZoomTo(self.ZoomLevels[len(self.ZoomLevels)-1])


    def ZoomTo(self, z):
        """
        Zoom to a specific level
        """
        zEffective = z / TILE_WIDTH * 24 # "100%" zoom level produces 24x24 level view
        tr = QtGui.QTransform()
        tr.scale(zEffective / 100.0, zEffective / 100.0)
        self.ZoomLevel = z
        self.view.setTransform(tr)
        self.courseOverview.mainWindowScale = zEffective / 100.0

        zi = self.ZoomLevels.index(z)
        self.actions['zoommax'].setEnabled(zi < len(self.ZoomLevels) - 1)
        self.actions['zoomin'] .setEnabled(zi < len(self.ZoomLevels) - 1)
        self.actions['zoomactual'].setEnabled(z != 100.0)
        self.actions['zoomout'].setEnabled(zi > 0)
        self.actions['zoommin'].setEnabled(zi > 0)

        self.ZoomWidget.setZoomLevel(z)
        self.ZoomStatusWidget.setZoomLevel(z)

        self.scene.update()


    @QtCore.pyqtSlot(int, int)
    def HandleOverviewClick(self, x, y):
        """
        Handle position changes from the course overview
        """
        self.view.centerOn(x, y)
        self.courseOverview.update()


    def closeEvent(self, event):
        """
        Handler for the main window close event
        """

        if self.CheckDirty():
            event.ignore()
        else:
            # save our state
            self.spriteEditorDock.setVisible(False)
            self.defaultPropDock.setVisible(False)

            # state: determines positions of docks
            # geometry: determines the main window position
            setSetting('MainWindowState', self.saveState(0))
            setSetting('MainWindowGeometry', self.saveGeometry())

            if hasattr(self, 'HelpBoxInstance'):
                self.HelpBoxInstance.close()

            if hasattr(self, 'TipsBoxInstance'):
                self.TipsBoxInstance.close()

            setSetting('AutoSaveFilePath', 'none')
            setSetting('AutoSaveFileData', 'x')

            event.accept()


    def SetupAssets(self, modelpath, packpath):
        """
        Sets up the Assets object
        """
        global Assets
        Assets = AssetsClass(modelpath, packpath)
        SLib.Assets = Assets


    def LoadCourse(self, name, isFullPath, courseNum):
        """
        Load a SMM course into the editor
        """
        global levName; levName=name.replace('\\', '/').split('/')[-1]

        bad = False
        if isFullPath and not isValidCourse(name):
            bad = True
        elif not isFullPath:
            QtWidgets.QMessageBox.warning(self, 'Metamaker', _("Open From Name isn't implemented yet. Sorry."), QtWidgets.QMessageBox.Ok)
            return

        if bad:
            QtWidgets.QMessageBox.warning(self, 'Metamaker', _("This file doesn't seem to be a valid course."), QtWidgets.QMessageBox.Ok)
            return False


        # Get the data
        global RestoredFromAutoSave
        if not RestoredFromAutoSave:

            # Check if there is a file by this name
            if not os.path.isfile(name):
                QtWidgets.QMessageBox.warning(None, _('Error'), _('Cannot find the required course file {file}.cdt. Check your Course folder and make sure it exists.', 'file', name))
                return False

            # Set the filepath variables
            self.fileSavePath = name
            self.fileTitle = os.path.basename(self.fileSavePath)

            # Open the file
            with open(self.fileSavePath, 'rb') as fileobj:
                courseData = fileobj.read()

        else:
            # Auto-saved course. Check if there's a path associated with it:

            if AutoSavePath == 'None':
                self.fileSavePath = None
                self.fileTitle = _('Untitled')
            else:
                self.fileSavePath = AutoSavePath
                self.fileTitle = os.path.basename(name)

            # Get the course data
            courseData = AutoSaveData
            SetDirty(noautosave=True)

            # Turn off the autosave flag
            RestoredFromAutoSave = False

        # Turn the dirty flag off, and keep it that way
        global Dirty, DirtyOverride
        Dirty = False
        DirtyOverride += 1

        # Decompress the level if needed
        if courseData[:4] == b'Yaz0':
            courseData = yaz0.decompress_opt(courseData)

        # Un-archive the level if needed
        if courseData[:4] == b'SARC':
            sarc = SarcLib.SARC_Archive()
            sarc.load(courseData)

            # This is a bad method that just grabs the first
            # .cdt it finds, but... we don't necessarily know
            # the filename to look for, so it would be hard
            # to do much better than this.
            for file in sarc.contents:
                if file.name.endswith('.cdt') and isValidCourseData(file.data):
                    courseData = file.data
                    break
            else:
                QtWidgets.QMessageBox.warning(self, 'Metamaker', _("This file doesn't seem to be a valid course."), QtWidgets.QMessageBox.Ok)
                return False


        if app.splashscrn is not None:
            progress = None
        else:
            progress = QtWidgets.QProgressDialog(self)

            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.setRange(0, 7)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle('Metamaker')

        # Here's how progress is tracked. (After the major refactor, it may be a bit messed up now.)
        # - 0: Loading course data
        # [Course.__init__ is entered here]
        # [Control is returned to LoadCourse_SMM]
        # - 6: Loading objects
        # - 7: Preparing editor

        # First, clear out the existing course.
        self.scene.clearSelection()
        self.CurrentSelection = []
        self.scene.clear()

        # Clear out sprite list
        self.spriteList.clear()
        self.spriteList.selectionModel().setCurrentIndex(QtCore.QModelIndex(), QtCore.QItemSelectionModel.Clear)


        # Prevent things from snapping when they're created
        global OverrideSnapping
        OverrideSnapping = True

        # Update progress
        if progress is not None:
            progress.setLabelText(_('Loading course data...'))
            progress.setValue(0)
        if app.splashscrn is not None:
            updateSplash(_('Loading course data...'), 0)

        # Load more stuff
        self.LoadCourse_SMM(courseData, progress)

        # Set the course overview settings
        mainWindow.courseOverview.maxX = 100
        mainWindow.courseOverview.maxY = 40

        self.courseOverview.update()

        self.view.centerOn(0, 0)
        self.ZoomTo(100.0)

        # Turn snapping back on
        OverrideSnapping = False

        # Turn the dirty flag off
        DirtyOverride -= 1
        self.UpdateTitle()

        # Update UI things
        self.scene.update()

        self.courseOverview.Rescale()
        self.courseOverview.update()
        QtCore.QTimer.singleShot(20, self.courseOverview.update)

        # Remove the splashscreen
        removeSplash()

        # If we got this far, everything worked! Return True.
        return True


    def LoadCourse_SMM(self, courseData, progress):
        """
        Performs all course-loading tasks specific to Super Mario Maker courses.
        Do not call this directly - use LoadCourse(...) instead!
        """

        # Create the new course object
        global Course
        Course = CourseClass()

        # Load it
        if not Course.load(courseData, progress):
            raise Exception

        if progress is not None:
            progress.setLabelText(_('Preparing editor...'))
            progress.setValue(7)
        if app.splashscrn is not None:
            updateSplash(_('Preparing editor...'), 7)


        # Add all things to the scene
        pcEvent = self.HandleSprPosChange
        for spr in Course.sprites:
            spr.positionChanged = pcEvent
            spr.listitem = ListWidgetItem_SortsByOther(spr)
            self.spriteList.addItem(spr.listitem)
            self.scene.addItem(spr)
            spr.UpdateListItem()


    @QtCore.pyqtSlot()
    def ChangeSelectionHandler(self):
        """
        Update the visible panels whenever the selection changes
        """
        if self.SelectionUpdateFlag: return

        try:
            selitems = self.scene.selectedItems()
        except RuntimeError:
            # must catch this error: if you close the app while something is selected,
            # you get a RuntimeError about the 'underlying C++ object being deleted'
            return

        # do this to avoid flicker
        showSpritePanel = False
        updateModeInfo = False

        # clear our variables
        self.selObj = None
        self.selObjs = None

        self.spriteList.setCurrentItem(None)

        # possibly a small optimization
        func_ii = isinstance
        type_spr = SpriteItem

        if len(selitems) == 0:
            # nothing is selected
            self.actions['cut'].setEnabled(False)
            self.actions['copy'].setEnabled(False)

        elif len(selitems) == 1:
            # only one item, check the type
            self.actions['cut'].setEnabled(True)
            self.actions['copy'].setEnabled(True)

            item = selitems[0]
            self.selObj = item
            if func_ii(item, type_spr):
                showSpritePanel = True
                updateModeInfo = True

        else:
            updateModeInfo = True

            # more than one item
            self.actions['cut'].setEnabled(True)
            self.actions['copy'].setEnabled(True)


        # count the # of each type, for the statusbar label

        # write the statusbar label text
        text = ''
        if len(selitems) > 0:
            singleitem = len(selitems) == 1
            if singleitem:
                text = _('- 1 sprite selected')  # 1 sprite selected
            else: # multiple things selected; see if they're all the same type
                text = _('- {x} sprites selected', 'x', len(selitems)) # x sprites selected
        self.selectionLabel.setText(text)

        self.CurrentSelection = selitems

        self.spriteEditorDock.setVisible(showSpritePanel)

        if len(self.CurrentSelection) > 0:
            self.actions['deselect'].setEnabled(True)
        else:
            self.actions['deselect'].setEnabled(False)

        if updateModeInfo: self.UpdateModeInfo()


    @QtCore.pyqtSlot(int)
    def CreationTabChanged(self, nt):
        """
        Handles the selected palette tab changing
        """
        idx = self.creationTabs.currentIndex()
        CPT = -1
        # 0 = sprites-add, 1 = sprite-list, 2 = ???
        if idx == 0: # sprites
            CPT = 1

        global CurrentPaintType
        CurrentPaintType = CPT


    @QtCore.pyqtSlot(int)
    def SpriteChoiceChanged(self, type):
        """
        Handles a new sprite being chosen
        """
        global CurrentSprite
        CurrentSprite = type
        if type != 1000 and type >= 0:
            self.defaultDataEditor.setSprite(type, -1)
            self.defaultDataEditor.data = DEFAULT_SPRITEDATA
            self.defaultDataEditor.subdata = DEFAULT_SUBSPRITEDATA
            self.defaultDataEditor.width = 1
            self.defaultDataEditor.height = 1
            self.defaultDataEditor.zPos = 1
            self.defaultDataEditor.linkingId = -1
            self.defaultDataEditor.effUnk00 = -1
            self.defaultDataEditor.effUnk01 = -1
            self.defaultDataEditor.effUnk02 = 0
            self.defaultDataEditor.effUnk03 = -1
            self.defaultDataEditor.effUnk04 = -1
            self.defaultDataEditor.costumeId = -1
            self.defaultDataEditor.costumeId_sub = -1
            self.defaultDataEditor.update()
            self.defaultPropButton.setEnabled(True)
        else:
            self.defaultPropButton.setEnabled(False)
            self.defaultPropDock.setVisible(False)
            self.defaultDataEditor.update()


    @QtCore.pyqtSlot(int)
    def SpriteReplace(self, type):
        """
        Handles a new sprite type being chosen to replace the selected sprites
        """
        items = self.scene.selectedItems()
        type_spr = SpriteItem
        changed = False

        for x in items:
            if isinstance(x, type_spr):
                x.spritedata = self.defaultDataEditor.data # change this first or else images get messed up
                x.SetType(type)
                x.update()
                changed = True

        if changed:
            SetDirty()

        self.ChangeSelectionHandler()


    @QtCore.pyqtSlot(int)
    def SelectNewSpriteView(self, type):
        """
        Handles a new sprite view being chosen
        """
        cat = SpriteCategories[type]
        self.sprPicker.SwitchView(cat)

        isSearch = (type == len(SpriteCategories) - 1)
        layout = self.spriteSearchLayout
        layout.itemAt(0).widget().setVisible(isSearch)
        layout.itemAt(1).widget().setVisible(isSearch)


    @QtCore.pyqtSlot(str)
    def NewSearchTerm(self, text):
        """
        Handles a new sprite search term being entered
        """
        self.sprPicker.SetSearchString(text)


    @QtCore.pyqtSlot()
    def ShowDefaultProps(self):
        """
        Handles the Show Default Properties button being clicked
        """
        self.defaultPropDock.setVisible(True)


    def HandleSprPosChange(self, obj, oldx, oldy, x, y):
        """
        Handle the sprite being dragged
        """
        if obj == self.selObj:
            if oldx == x and oldy == y: return
            obj.UpdateListItem()
            SetDirty()


    @QtCore.pyqtSlot('PyQt_PyObject')
    def SpriteDataUpdated(self, widget):
        """
        Handle the current sprite's data being updated
        """
        if self.spriteEditorDock.isVisible():
            obj = self.selObj

            obj.spritedata = widget.data
            obj.spritedata_sub = widget.subdata
            obj.width = widget.width
            obj.height = widget.height
            obj.objz = widget.zPos
            obj.linkingID = widget.linkingId
            if (widget.effUnk00, widget.effUnk01, widget.effUnk02, widget.effUnk03, widget.effUnk04) == (-1, -1, 0, -1, -1):
                obj.effect = None
            else:
                obj.effect = Effect(widget.effUnk00, widget.effUnk01, widget.effUnk02, widget.effUnk03, widget.effUnk04)
            obj.costumeID = widget.costumeId
            obj.costumeID_sub = widget.costumeId_sub
            obj.type_sub = widget.subspritetype

            obj.UpdateListItem()
            SetDirty()

            obj.UpdateDynamicSizing()

    @QtCore.pyqtSlot(QtWidgets.QListWidgetItem)
    def HandleSpriteSelectByList(self, item):
        """
        Handle a sprite being selected from the list
        """
        if self.UpdateFlag: return

        # can't really think of any other way to do this
        #item = self.spriteList.item(row)
        spr = None
        for check in Course.sprites:
            if check.listitem == item:
                spr = check
                break
        if spr is None: return

        spr.ensureVisible(QtCore.QRectF(), 192, 192)
        self.scene.clearSelection()
        spr.setSelected(True)

    @QtCore.pyqtSlot(QtWidgets.QListWidgetItem)
    def HandleSpriteToolTipAboutToShow(self, item):
        """
        Handle a sprite being hovered in the list
        """
        spr = None
        for check in Course.sprites:
            if check.listitem == item:
                spr = check
                break
        if spr is None: return

        spr.UpdateListItem(True)

    def UpdateModeInfo(self):
        """
        Change the info in the currently visible panel
        """
        self.UpdateFlag = True

        if self.spriteEditorDock.isVisible():
            obj = self.selObj

            self.spriteDataEditor.setSprite(obj.type, obj.type_sub)
            self.spriteDataEditor.data = obj.spritedata
            self.spriteDataEditor.subdata = obj.spritedata_sub
            self.spriteDataEditor.width = obj.width
            self.spriteDataEditor.height = obj.height
            self.spriteDataEditor.zPos = obj.objz
            self.spriteDataEditor.linkingId = obj.linkingID
            if obj.effect is None:
                self.spriteDataEditor.useEff = False
                self.spriteDataEditor.effUnk00 = -1
                self.spriteDataEditor.effUnk01 = -1
                self.spriteDataEditor.effUnk02 = 0
                self.spriteDataEditor.effUnk03 = -1
                self.spriteDataEditor.effUnk04 = -1
            else:
                self.spriteDataEditor.useEff = True
                self.spriteDataEditor.effUnk00 = obj.effect.unk00
                self.spriteDataEditor.effUnk01 = obj.effect.unk01
                self.spriteDataEditor.effUnk02 = obj.effect.unk02
                self.spriteDataEditor.effUnk03 = obj.effect.unk03
                self.spriteDataEditor.effUnk04 = obj.effect.unk04
            self.spriteDataEditor.costumeId = obj.costumeID
            self.spriteDataEditor.costumeId_sub = obj.costumeID_sub
            self.spriteDataEditor.subspritetype = obj.type_sub

            self.spriteDataEditor.update()

        self.UpdateFlag = False


    @QtCore.pyqtSlot(int, int)
    def PositionHovered(self, x, y):
        """
        Handle a position being hovered in the view
        """
        info = ''
        hovereditems = self.scene.items(QtCore.QPointF(x, y))
        hovered = None
        for item in hovereditems:
            hover = item.hover if hasattr(item, 'hover') else True
            hovered = item
            break

        if hovered is not None and isinstance(hovered, SpriteItem):
            info = _('- Sprite under mouse: {name} at {xpos}, {ypos}', 'name', hovered.name, 'xpos', hovered.objx, 'ypos', hovered.objy)

        self.posLabel.setText(_('({objx}, {objy}) - ({sprx}, {spry})', 'objx', x // TILE_WIDTH, 'objy', -y // TILE_WIDTH, 'sprx', x * 16 // TILE_WIDTH, 'spry', -y * 16 // TILE_WIDTH))
        self.hoverLabel.setText(info)


    def keyPressEvent(self, event):
        """
        Handles key press events for the main window if needed
        """
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            sel = self.scene.selectedItems()
            self.SelectionUpdateFlag = True
            if len(sel) > 0:
                for obj in sel:
                    obj.delete()
                    obj.setSelected(False)
                    self.scene.removeItem(obj)
                    self.courseOverview.update()
                SetDirty()
                event.accept()
                self.SelectionUpdateFlag = False
                self.ChangeSelectionHandler()
                return
        self.courseOverview.update()

        QtWidgets.QMainWindow.keyPressEvent(self, event)


    @QtCore.pyqtSlot()
    def HandleCourseOptions(self):
        """
        Pops up the options for Course Dialog
        """
        dlg = CourseOptionsDialog()
        if dlg.exec_() != dlg.Accepted: return

        SetDirty()
        dlg.readOutFields()

        self.scene.update()


    @QtCore.pyqtSlot()
    def HandleScreenshot(self):
        """
        Takes a screenshot of the entire course and saves it
        """

        dlg = ScreenCapChoiceDialog()
        if dlg.exec_() == dlg.Accepted:
            fn = QtWidgets.QFileDialog.getSaveFileName(mainWindow, _('Choose a new filename'), '/untitled.png', _('Portable Network Graphics') + ' (*.png)')[0]
            if fn == '': return
            fn = str(fn)

            if dlg.zoneCombo.currentIndex() == 0:
                ScreenshotImage = QtGui.QImage(mainWindow.view.width(), mainWindow.view.height(), QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                mainWindow.view.render(RenderPainter, QtCore.QRectF(0, 0, mainWindow.view.width(), mainWindow.view.height()), QtCore.QRect(QtCore.QPoint(0, 0), QtCore.QSize(mainWindow.view.width(), mainWindow.view.height())))
                RenderPainter.end()
            elif dlg.zoneCombo.currentIndex() == 1:
                maxX = maxY = 0
                minX = minY = 0x0ddba11
                for z in Course.zones:
                    if maxX < ((z.objx*(TILE_WIDTH/16)) + (z.width*(TILE_WIDTH/16))):
                        maxX = ((z.objx*(TILE_WIDTH/16)) + (z.width*(TILE_WIDTH/16)))
                    if maxY < ((z.objy*(TILE_WIDTH/16)) + (z.height*(TILE_WIDTH/16))):
                        maxY = ((z.objy*(TILE_WIDTH/16)) + (z.height*(TILE_WIDTH/16)))
                    if minX > z.objx*(TILE_WIDTH/16):
                        minX = z.objx*(TILE_WIDTH/16)
                    if minY > z.objy*(TILE_WIDTH/16):
                        minY = z.objy*(TILE_WIDTH/16)
                maxX = (X_MAX*TILE_WIDTH if X_MAX*TILE_WIDTH < maxX+40 else maxX+40)
                maxY = (Y_MAX*TILE_WIDTH if Y_MAX*TILE_WIDTH < maxY+40 else maxY+40)
                minX = (0 if 40 > minX else minX-40)
                minY = (40 if 40 > minY else minY-40)

                ScreenshotImage = QtGui.QImage(int(maxX - minX), int(maxY - minY), QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                mainWindow.scene.render(RenderPainter, QtCore.QRectF(0, 0, int(maxX - minX), int(maxY - minY)), QtCore.QRectF(int(minX), int(minY), int(maxX - minX), int(maxY - minY)))
                RenderPainter.end()


            else:
                i = dlg.zoneCombo.currentIndex() - 2
                ScreenshotImage = QtGui.QImage(Course.zones[i].width*TILE_WIDTH/16, Course.zones[i].height*TILE_WIDTH/16, QtGui.QImage.Format_ARGB32)
                ScreenshotImage.fill(Qt.transparent)

                RenderPainter = QtGui.QPainter(ScreenshotImage)
                mainWindow.scene.render(RenderPainter, QtCore.QRectF(0, 0, Course.zones[i].width*TILE_WIDTH/16, Course.zones[i].height*TILE_WIDTH/16), QtCore.QRectF(int(Course.zones[i].objx)*TILE_WIDTH/16, int(Course.zones[i].objy)*TILE_WIDTH/16, Course.zones[i].width*TILE_WIDTH/16, Course.zones[i].height*TILE_WIDTH/16))
                RenderPainter.end()

            ScreenshotImage.save(fn, 'PNG', 50)


def main():
    """
    Main startup function for Metamaker
    """

    global app, mainWindow, settings, METAMAKER_VERSION

    # create an application
    app = QtWidgets.QApplication(sys.argv)

    # load the settings
    settings = QtCore.QSettings('Metamaker', METAMAKER_VERSION)

    # load the style
    GetDefaultStyle()

    # go to the script path
    path = module_path()
    if path is not None:
        os.chdir(module_path())

    # check if required files are missing
    if FilesAreMissing():
        sys.exit(1)

    # load required stuff
    global Sprites
    global SpriteListData
    Sprites = None
    SpriteListData = None
    LoadTheme()
    LoadConstantLists()
    SetAppStyle()
    LoadSpriteData()
    LoadNumberFont()
    SLib.OutlineColor = _c('smi')
    SLib.main()

    # load the splashscreen
    app.splashscrn = None
    if checkSplashEnabled():
        loadSplash()

    global EnableAlpha, GridType, CollisionsShown, DepthShown, RealViewEnabled
    global SpritesFrozen
    global SpritesShown, SpriteImagesShown

    gt = setting('GridType')
    if gt == 'checker': GridType = 'checker'
    elif gt == 'grid': GridType = 'grid'
    else: GridType = None
    RealViewEnabled = setting('RealViewEnabled', False)
    SpritesFrozen = setting('FreezeSprites', False)
    SpritesShown = setting('ShowSprites', True)
    SpriteImagesShown = setting('ShowSpriteImages', True)
    SLib.RealViewEnabled = RealViewEnabled
    SLib.sprites = sprites

    # create and show the main window
    mainWindow = MetamakerWindow()
    mainWindow.__init2__() # fixes bugs
    mainWindow.show()
    exitcodesys = app.exec_()
    app.deleteLater()
    sys.exit(exitcodesys)

generateStringsXML = False
if '-generatestringsxml' in sys.argv:
    generateStringsXML = True

if __name__ == '__main__': main()
