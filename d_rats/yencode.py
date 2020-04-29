#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
import sys

DEFAULT_BANNED = "\x11\x13\x1A\00\xFD\xFE\xFF"
OFFSET = 64

def yencode_buffer(buf, banned=None):
    if not banned:
        banned = DEFAULT_BANNED

    banned += "="
    out = ""
        
    for char in buf:
        if char in banned:
            out += "=" + chr((ord(char) + OFFSET) % 256)
        else:
            out += char

    return out

def ydecode_buffer(buf):
    out = ""
    
    i = 0
    while i < len(buf):
        char = buf[i]
        if char == "=":
            i += 1
            v = ord(buf[i]) - OFFSET
            if v < 0:
                v += 256
            out += chr(v)
        else:
            out += char

        i += 1

    return out

if __name__=="__main__":
    import sys

    f = open(sys.argv[2])
    inbuf = f.read()

    if sys.argv[1] == "-e":
        sys.stdout.write(yencode_buffer(inbuf))
    else:
        sys.stdout.write(ydecode_buffer(inbuf))

    f.close()
