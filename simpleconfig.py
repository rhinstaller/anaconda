#
# simpleconifg.py - representation of a simple configuration file (sh-like)
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 1999-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string

class SimpleConfigFile:
    def __str__ (self):
        s = ""
        keys = self.info.keys ()
        keys.sort ()
        for key in keys:
            # FIXME - use proper escaping
            if type (self.info[key]) == type(""):
                s = s + key + "=\"" + self.info[key] + "\"\n"
        return s
            
    def __init__ (self):
        self.info = {}

    def set (self, *args):
        for (key, data) in args:
            self.info[string.upper (key)] = data

    def unset (self, *keys):
        for key in keys:
            key = string.upper (key)
            if self.info.has_key (key):
               del self.info[key] 

    def get (self, key):
        key = string.upper (key)
        if self.info.has_key (key):
            return self.info[key]
        else:
            return ""


