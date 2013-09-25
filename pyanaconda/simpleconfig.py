#
# simpleconifg.py - representation of a simple configuration file (sh-like)
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Will Woods <wwoods@redhat.com>
# Brian C. Lane <bcl@redhat.com>
#
# Copyright 1999-2012 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import os
import shutil
import shlex
from pipes import _safechars
import tempfile
from pyanaconda.iutil import upperASCII

def unquote(s):
    return ' '.join(shlex.split(s))

def quote(s, always=False):
    """ If always is set it returns a quoted value
    """
    if not always:
        for c in s:
            if c not in _safechars:
                break
        else:
            return s
    return '"'+s.replace('"', '\\"')+'"'

class SimpleConfigFile(object):
    """ Edit values in a configuration file without changing comments.
        Supports KEY=VALUE lines and ignores everything else.
        Supports adding new keys.
        Supports deleting keys.
        Preserves comment, blank lines and comments on KEY lines
        Does not support duplicate key entries.
    """
    def __init__(self, filename=None, read_unquote=True, write_quote=True,
                 always_quote=False):
        self.filename = filename
        self.read_unquote = read_unquote
        self.write_quote = write_quote
        self.always_quote = always_quote
        self.reset()

    def reset(self):
        self._lines = []
        self.info = {}

    def read(self, filename=None):
        """ passing filename will override the filename passed to init.

            save the lines into self._lines and the key/value pairs into
            self.info
        """
        filename = filename or self.filename
        with open(filename) as f:
            for line in f:
                self._lines.append(line)
                key, value = self._parseline(line)
                if key:
                    self.info[key] = value

    def write(self, filename=None, use_tmp=True):
        """ passing filename will override the filename passed to init.
        """
        filename = filename or self.filename
        if not filename:
            return None

        if use_tmp:
            tmpf = tempfile.NamedTemporaryFile(mode="w", delete=False)
            tmpf.write(str(self))
            tmpf.close()

            # Move the temporary file (with 0600 permissions) over the top of the
            # original and preserve the original's permissions
            filename = os.path.realpath(filename)
            if os.path.exists(filename):
                m = os.stat(filename).st_mode
            else:
                m = int('0100644', 8)
            shutil.move(tmpf.name, filename)
            os.chmod(filename, m)
        else:
            # write directly to the file
            with open(filename, "w") as fobj:
                fobj.write(str(self))

    def set(self, *args):
        for key, value in args:
            self.info[upperASCII(key)] = value

    def unset(self, *keys):
        for key in (upperASCII(k) for k in keys):
            if key in self.info:
                del self.info[key]

    def get(self, key):
        return self.info.get(upperASCII(key), "")

    def _parseline(self, line):
        """ parse a line into a key, value pair
            Handle comments and optionally unquote quoted strings
            Returns (key, value) or (None, None)
            key is always UPPERCASE
        """
        s = line.strip()
        if '#' in s:
            s = s[:s.find('#')] # remove from comment to EOL
            s = s.strip()       # and any unnecessary whitespace
        key, eq, val = s.partition('=')
        if self.read_unquote:
            val = unquote(val)
        if key != '' and eq == '=':
            return (upperASCII(key), val)
        else:
            return (None, None)

    def _kvpair(self, key, comment=""):
        value = self.info[key]
        if self.write_quote or self.always_quote:
            value = quote(value, self.always_quote)
        return key + '=' + value + comment + "\n"

    def __str__(self):
        """ Return the file that was read, replacing existing keys with new values
            removing keys that have been deleted and adding new keys.
        """
        oldkeys = []
        s = ""
        for line in self._lines:
            key = self._parseline(line)[0]
            if key is None:
                s += line
            else:
                if key not in self.info:
                    continue
                oldkeys.append(key)
                if "#" in line:
                    comment = " " + line[line.find("#"):]
                else:
                    comment = ""
                s += self._kvpair(key, comment)

        # Add new keys
        for key in self.info:
            if key not in oldkeys:
                s += self._kvpair(key)

        return s


