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

from math import ceil
from PyQt5.QtGui import QImage

import addrlib
import bcn
from bfres_structs import struct, GX2Surface, empty

try:
    import pyximport
    pyximport.install()

    import gx2FormConv_cy as formConv

except ImportError:
    import gx2FormConv as formConv


formats = {
    0x00000001: 'GX2_SURFACE_FORMAT_TC_R8_UNORM',
    0x00000002: 'GX2_SURFACE_FORMAT_TC_R4_G4_UNORM',
    0x00000007: 'GX2_SURFACE_FORMAT_TC_R8_G8_UNORM',
    0x00000008: 'GX2_SURFACE_FORMAT_TCS_R5_G6_B5_UNORM',
    0x0000000a: 'GX2_SURFACE_FORMAT_TC_R5_G5_B5_A1_UNORM',
    0x0000000b: 'GX2_SURFACE_FORMAT_TC_R4_G4_B4_A4_UNORM',
    0x00000019: 'GX2_SURFACE_FORMAT_TCS_R10_G10_B10_A2_UNORM',
    0x0000001a: 'GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_UNORM',
    0x0000041a: 'GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_SRGB',
    0x00000031: 'GX2_SURFACE_FORMAT_T_BC1_UNORM',
    0x00000431: 'GX2_SURFACE_FORMAT_T_BC1_SRGB',
    0x00000032: 'GX2_SURFACE_FORMAT_T_BC2_UNORM',
    0x00000432: 'GX2_SURFACE_FORMAT_T_BC2_SRGB',
    0x00000033: 'GX2_SURFACE_FORMAT_T_BC3_UNORM',
    0x00000433: 'GX2_SURFACE_FORMAT_T_BC3_SRGB',
    0x00000034: 'GX2_SURFACE_FORMAT_T_BC4_UNORM',
    0x00000234: 'GX2_SURFACE_FORMAT_T_BC4_SNORM',
    0x00000035: 'GX2_SURFACE_FORMAT_T_BC5_UNORM',
    0x00000235: 'GX2_SURFACE_FORMAT_T_BC5_SNORM',
}


BCn_formats = [
    0x31, 0x431, 0x32, 0x432,
    0x33, 0x433, 0x34, 0x234,
    0x35, 0x235,
]


def bytes_to_string(data, pos=0, end=0):
    if not end:
        end = data.find(b'\0', pos)
        if end == -1:
            return data[pos:].decode('utf-8')

    return data[pos:end].decode('utf-8')


def read(bfresData):
    assert bfresData[:4] == b"FRES" and bfresData[4:8] != b'    '

    version = bfresData[4]
    assert version in [3, 4]

    group = empty()
    group.pos = struct.unpack(">i", bfresData[0x24:0x28])[0]

    if group.pos == 0:
        return False

    group.pos += 0x28
    group.count = struct.unpack(">i", bfresData[group.pos:group.pos + 4])[0]
    group.pos += 20

    textures = []

    for i in range(group.count):
        nameAddr = struct.unpack(">i", bfresData[group.pos + 16 * i + 8:group.pos + 16 * i + 12])[0]
        nameAddr += group.pos + 16 * i + 8

        name = bytes_to_string(bfresData, nameAddr)

        pos = struct.unpack(">i", bfresData[group.pos + 16 * i + 12:group.pos + 16 * i + 16])[0]
        pos += group.pos + 16 * i + 12

        ftex = empty()
        ftex.headAddr = pos

        pos += 4

        surface = GX2Surface()
        surface.data(bfresData, pos)
        pos += surface.size

        if version == 4:
            surface.numMips = 1

        elif surface.numMips > 14:
            continue

        mipOffsets = []
        for j in range(13):
            mipOffsets.append(
                bfresData[j * 4 + pos] << 24
                | bfresData[j * 4 + 1 + pos] << 16
                | bfresData[j * 4 + 2 + pos] << 8
                | bfresData[j * 4 + 3 + pos]
            )

        pos += 68

        compSel = []
        compSel2 = []
        for j in range(4):
            comp = bfresData[pos + j]
            compSel2.append(comp)
            if comp == 4:  # Sorry, but this is unsupported.
                comp = j

            compSel.append(comp)

        pos += 24

        ftex.name = name
        ftex.dim = surface.dim
        ftex.width = surface.width
        ftex.height = surface.height
        ftex.depth = surface.depth
        ftex.numMips = surface.numMips
        ftex.format = surface.format_
        ftex.aa = surface.aa
        ftex.use = surface.use
        ftex.imageSize = surface.imageSize
        ftex.imagePtr = surface.imagePtr
        ftex.mipSize = surface.mipSize
        ftex.mipPtr = surface.mipPtr
        ftex.tileMode = surface.tileMode
        ftex.swizzle = surface.swizzle
        ftex.alignment = surface.alignment
        ftex.pitch = surface.pitch
        ftex.compSel = compSel
        ftex.compSel2 = compSel2
        ftex.mipOffsets = mipOffsets

        ftex.surfInfo = addrlib.getSurfaceInfo(ftex.format, ftex.width, ftex.height, ftex.depth, ftex.dim, ftex.tileMode, ftex.aa, 0)

        if ftex.format in BCn_formats:
            ftex.blkWidth, ftex.blkHeight = 4, 4

        else:
            ftex.blkWidth, ftex.blkHeight = 1, 1

        ftex.bpp = addrlib.surfaceGetBitsPerPixel(surface.format_) // 8

        dataAddr = struct.unpack(">i", bfresData[ftex.headAddr + 0xB0:ftex.headAddr + 0xB4])[0]
        dataAddr += ftex.headAddr + 0xB0

        ftex.dataAddr = dataAddr
        ftex.data = bfresData[dataAddr:dataAddr + ftex.imageSize]

        mipAddr = struct.unpack(">i", bfresData[ftex.headAddr + 0xB4:ftex.headAddr + 0xB8])[0]
        if mipAddr and ftex.mipSize:
            mipAddr += ftex.headAddr + 0xB4
            ftex.mipData = bfresData[mipAddr:mipAddr + ftex.mipSize]

        else:
            ftex.mipData = b''

        textures.append((name, ftex))

    return textures


def untileTex(tex):
    surfInfo = tex.surfInfo
    data = tex.data[:surfInfo.surfSize]

    result = []
    for mipLevel in range(tex.numMips):
        width = max(1, tex.width >> mipLevel)
        height = max(1, tex.height >> mipLevel)

        size = ceil(width / tex.blkWidth) * ceil(height / tex.blkHeight) * tex.bpp

        if mipLevel != 0:
            mipOffset = tex.mipOffsets[mipLevel - 1]
            if mipLevel == 1:
                mipOffset -= surfInfo.surfSize

            surfInfo = addrlib.getSurfaceInfo(tex.format, tex.width, tex.height, tex.depth, tex.dim, tex.tileMode, tex.aa, mipLevel)
            data = tex.mipData[mipOffset:mipOffset + surfInfo.surfSize]

        result_ = addrlib.deswizzle(
            width, height, surfInfo.height, tex.format, surfInfo.tileMode,
            tex.swizzle, surfInfo.pitch, surfInfo.bpp, data,
        )

        result.append(result_[:size])

    return result


def texToQImage(tex):
    assert tex.format in formats
    result = untileTex(tex)

    if tex.format == 0x1:
        data = result[0]

        format_ = 'l8'
        bpp = 1

    elif tex.format == 0x2:
        data = result[0]

        format_ = 'la4'
        bpp = 1

    elif tex.format == 0x7:
        data = result[0]

        format_ = 'la8'
        bpp = 2

    elif tex.format == 0x8:
        data = result[0]

        format_ = 'rgb565'
        bpp = 2

    elif tex.format == 0xa:
        data = result[0]

        format_ = 'rgb5a1'
        bpp = 2

    elif tex.format == 0xb:
        data = result[0]

        format_ = 'rgba4'
        bpp = 2

    elif tex.format == 0x19:
        data = result[0]

        format_ = 'bgr10a2'
        bpp = 4

    elif (tex.format & 0x3F) == 0x1a:
        data = result[0]

        format_ = 'rgba8'
        bpp = 4

    elif (tex.format & 0x3F) == 0x31:
        data = bcn.decompressDXT1(result[0], tex.width, tex.height)

        format_ = 'rgba8'
        bpp = 4

    elif (tex.format & 0x3F) == 0x32:
        data = bcn.decompressDXT3(result[0], tex.width, tex.height)

        format_ = 'rgba8'
        bpp = 4

    elif (tex.format & 0x3F) == 0x33:
        data = bcn.decompressDXT5(result[0], tex.width, tex.height)

        format_ = 'rgba8'
        bpp = 4

    elif (tex.format & 0x3F) == 0x34:
        data = bcn.decompressBC4(result[0], tex.width, tex.height, tex.format >> 8)

        format_ = 'rgba8'
        bpp = 4

    else:
        data = bcn.decompressBC5(result[0], tex.width, tex.height, tex.format >> 8)

        format_ = 'rgba8'
        bpp = 4

    data = formConv.torgba8(tex.width, tex.height, bytearray(data), format_, bpp, tex.compSel2)
    return QImage(data, tex.width, tex.height, QImage.Format_RGBA8888)
