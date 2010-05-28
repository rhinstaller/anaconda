#
# simpleconifg.py - representation of a simple configuration file (sh-like)
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import os
import tempfile
import shutil

# use our own ASCII only uppercase function to avoid locale issues
# not going to be fast but not important
def uppercase_ASCII_string(str):
    newstr = ""
    for i in range(0,len(str)):
	if str[i] in string.lowercase:
	    newstr += chr(ord(str[i])-32)
	else:
	    newstr += str[i]

    return newstr

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

    def write(self, file):
        f = open(file, "w")
        f.write(self.__str__())
        f.close()

    def read(self, file):
        if not os.access(file, os.R_OK):
            return

        f = open(file, "r")
        lines = f.readlines()
        f.close()

        for line in lines:
            fields = line[:-1].split('=', 2)
            if len(fields) < 2:
                # how am I supposed to know what to do here?
                continue
            key = uppercase_ASCII_string(fields[0])
            value = fields[1]
            # XXX hack
            value = value.replace('"', '')
            value = value.replace("'", '')
            self.info[key] = value

    def set (self, *args):
        for (key, data) in args:
            self.info[uppercase_ASCII_string(key)] = data

    def unset (self, *keys):
        for key in keys:
            key = uppercase_ASCII_string(key)
            if self.info.has_key (key):
               del self.info[key]

    def get (self, key):
        key = uppercase_ASCII_string(key)
        return self.info.get(key, "")


class IfcfgFile(SimpleConfigFile):

    def __init__(self, dir, iface):
        SimpleConfigFile.__init__(self)
        self.iface = iface
        self.dir = dir

    @property
    def path(self):
        return os.path.join(self.dir, "ifcfg-%s" % self.iface)

    def clear(self):
        self.info = {}

    def read(self):
        """Reads values from ifcfg file.

        returns: number of values read
        """
        f = open(self.path, "r")
        lines = f.readlines()
        f.close()

        for line in lines:
            line = line.strip()
            if line.startswith("#") or line == '':
                continue
            fields = line.split('=', 1)
            key = uppercase_ASCII_string(fields[0])
            value = fields[1]
            # XXX hack
            value = value.replace('"', '')
            value = value.replace("'", '')
            self.info[key] = value

        return len(self.info)

    # This method has to write file in a particular
    # way so that ifcfg-rh's inotify mechanism triggeres
    # TODORV: check that it is still true.
    def write(self, dir=None):
        """Writes values into ifcfg file."""

        if not dir:
            path = self.path
        else:
            path = os.path.join(dir, os.path.basename(self.path))

        fd, newifcfg = tempfile.mkstemp(prefix="ifcfg-%s" % self.iface, text=False)
        os.write(fd, self.__str__())
        os.close(fd)

        os.chmod(newifcfg, 0644)
        try:
            os.remove(path)
        except OSError, e:
            if e.errno != 2:
                raise
        shutil.move(newifcfg, path)

