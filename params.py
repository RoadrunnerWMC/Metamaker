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



# params.py
# A library exposing functions for reading and writing Nintendo .params files.


import collections



def decode(filedata):
    """
    Parse a .params file: string -> dict
    """
    # A parameters file is essentially a set of nested dictionaries.
    #
    # In general, what can make parsing parameter files confusing is that a
    # single set of delimiters ("{" and "}") has two very different meanings
    # depending on context. They can be used to contain a dictionary, or to
    # contain a dictionary entry.
    #
    # Thus, "{" alternates meanings: dictionary, entry, dictionary, entry, ...

    # Break the filedata string into lines, and remove indentation and trailing whitespace.
    # The other parser functions assume that this has already been done.
    lines = [line.strip() for line in filedata.split('\n')]
    lines = [L for L in lines if len(L) > 0 and not L.startswith('#')]

    # Sanity check
    if lines[0] != '{':
        raise ValueError('This doesn\'t seem to be a Parameters file.')

    # The entire parameters file is just a dictionary. Parse it and return it.
    # (We can discard any leftover data; there shouldn't be any.)
    return _decodeDict(lines)[0]


def _decodeDict(lines):
    """
    Parse a dictionary:
    {
        {
            key
            value
        }
        {
            key
            value
        }
    }
    (Extra data here, after the end of the dictionary, is allowed.)

    The first two lines must both be '{'.
    Returns: the assembled dictionary, and whatever file data is left over
    afterward (or [] if there is none).
    """

    # Sanity checks, and remove the leading '{'
    assert lines[0] == '{' and lines[1] == '{'
    lines = lines[1:]

    # This is the dictionary we'll be building
    retdict = collections.OrderedDict()

    # Keep going until we hit the end of the list.
    while len(lines) > 0 and lines[0] != '}':

        # Parse this entry, and keep whatever file data is left
        # over
        key, val, lines = _decodeEntry(lines)

        # Add it to the dictionary we're building
        retdict[key] = val

    # Oh, we're done! We hit the end of the dictionary. Return it
    # along with whatever we didn't parse (excluding the final '}').
    return retdict, lines[1:]


def _decodeEntry(lines):
    """
    Parse a dictionary key/val pair:
    {
        key (atomic)
        value (could be an atomic or a dict)
    }
    Must begin with a '{'.
    Returns: the key, the value, and the rest of the file data afterward.
    """
    # Sanity checks, and remove the leading '{'
    assert lines[0] == '{' and lines[1] != '{'
    lines = lines[1:]

    # The key cannot be a dict. Parse and remove it.
    key = _decodeAtomic(lines[0])
    lines = lines[1:]

    # The value might be a dict, though. Parase and it, too.
    if lines[0] == '{':
        value, lines = _decodeDict(lines)
    else:
        value = _decodeAtomic(lines[0])
        lines = lines[1:]

    # Ensure that we end with a }, and remove that, too.
    assert lines[0] == '}'
    lines = lines[1:]

    # Return the key, value, and file data sans this entire key/value pair.
    return key, value, lines



def _decodeAtomic(line):
    """
    Parse an atomic parameter into a value.
    There are four types of atomic parameters:
    - integer (preceded by "-" if negative)
    - float (same as above)
    - string (delimited by '"'s)
    - list (a ' '-separated list of other atomics)
    """
    # This EAFP approach is nice and bulletproof.

    try:
        # It's an int!
        return int(line)
    except ValueError:
        try:
            # No, it's a float!
            return float(line)
        except ValueError:
            # No, it must be a string or list.
            if line.count('"') == 2 and line[0] + line[-1] == '""':
                # It's a string.
                return line[1:-1]
            else:
                # Must be a list!

                retval = []
                for val in line.split(' '):
                    if val == '': continue # yes, this does fix crashes (Splatoon/Enm_TakolienSpeedUp.params)
                    retval.append(_decodeAtomic(val))
                return retval


def encode(filedata):
    """
    Generate a parameters file: dict -> string
    Try to match Nintendo's output as closely as possible, including
    random oddities.
    """
    # We need to remove one of the trailing \n's, hence the [:-1].
    return _encodeDict(filedata, 0)[:-1]


def _encodeDict(dictdata, indent):
    """
    Render a parameters dictionary.
    """
    first = '\t' * indent + '{\n'
    last = '\t' * indent + '}\n\n' # Yes, there is a stray \n there.
    middle = ''
    for key, value in dictdata.items():
        middle += _encodeEntry(key, value, indent + 1)
    return first + middle + last


def _encodeEntry(key, value, indent):
    """
    Render a parameters dictionary entry.
    """
    first = '\t' * indent + '{\n'
    last = '\t' * indent + '}\n'
    keystr = _encodeAtomicLine(key, indent + 1)
    if isinstance(value, dict):
        valstr = _encodeDict(value, indent + 1)
    else:
        valstr = _encodeAtomicLine(value, indent + 1)

    return first + keystr + valstr + last


def _encodeAtomicLine(value, indent):
    """
    Render a parameters atomic value as a string representing the
    entire line at the indentation level given.
    """
    return '\t' * indent + _encodeAtomic(value) + ' \n' # Yes, that space is supposed to be there.


def _encodeAtomic(value):
    """
    Render a parameters atomic value as a string
    """
    if isinstance(value, str):
        return '"' + value + '"'
    elif isinstance(value, float):
        return '%.8F' % value # force exactly 8 decimal places
    elif isinstance(value, list) or isinstance(value, tuple):
        return ' '.join(_encodeAtomic(item) for item in value)
    else:
        return str(value)
