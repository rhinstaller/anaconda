#
# statusline_text.py: text mode status line management functions
#
# Copyright (C) 2000, 2001  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# XXX this file appears to be unused.

import string
import copy

class CleanStatusLine:

    def centerLabel(self, str, space):
        return string.center(str, space)

    def formatStatusLine(self, args):
        if len(args) == 1:
            return self.centerLabel(args[0], self.width)

        nonspaces = 0
        for i in args:
            nonspaces = nonspaces + len(i)

        spaceEach = (self.width-nonspaces)/len(args)
        outstr = ""

        j = 0
        for i in args:
            str = self.centerLabel(i, len(i) + spaceEach)
            outstr = outstr + str
            j = j + 1
            if j != len(args):
                outstr = outstr + "|"

        return outstr

    def setdefaultStatusLine(self, rargs, largs):
        self.rargs = rargs
        self.largs = largs
        

#    def defaultStatusLine(self):
#    def __str__(self):
#        args = copy.deepcopy(self.largs)
#        args.extend(self.rargs)
#        return self.formatStatusLine(args)
        
#    def customStatusLine(self, optargs):
    def __str__(self):
        args = copy.deepcopy(self.largs)
        if self.optargs != None:
            args.extend(self.optargs)
        args.extend(self.rargs)
        return self.formatStatusLine(args)


    def __init__(self, args, optargs=None):
#        self.largs = ["<Tab>/<Alt-Tab> between elements"]
#        self.rargs = ["<F12> next screen"]
        (self.largs, self.rargs) = args
        self.optargs = optargs
            
        self.width = 80
        
