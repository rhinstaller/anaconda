#
# simpleconifg.py - representation of a simple configuration file (sh-like)
#
# Copyright (C) 1999-2014 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Author(s): Matt Wilson <msw@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Will Woods <wwoods@redhat.com>
#            Brian C. Lane <bcl@redhat.com>
#
import os
import shutil
import shlex
from pipes import _safechars
import tempfile
from pyanaconda.iutil import upperASCII, eintr_retry_call

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

def find_comment(s):
    """ Look for a # comment outside of a quoted string.
        If there are no quotes, find the last # in the string.

        :param str s: string to check for comment and quotes
        :returns: index of comment or None
        :rtype: int or None

        Handles comments inside quotes and quotes inside quotes.
    """
    q = None
    for i in range(len(s)):
        if not q and s[i] == '#':
            return i

        # Ignore quotes inside other quotes
        if s[i] in "'\"":
            if s[i] == q:
                q = None
            elif q is None:
                q = s[i]
    return None


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
                key, value, _comment = self._parseline(line)
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
            eintr_retry_call(os.chmod, filename, m)
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
        """ parse a line into a key, value and comment

            :param str line: Line to be parsed
            :returns: Tuple of key, value, comment
            :rtype: tuple

            Handle comments and optionally unquote quoted strings
            Returns (key, value, comment) or (None, None, comment)
            key is always UPPERCASE and comment may by "" if none was found.
        """
        s = line.strip()
        # Look for a # outside any quotes
        comment = ""
        comment_index = find_comment(s)
        if comment_index is not None:
            comment = s[comment_index:]
            s = s[:comment_index]   # remove from comment to EOL

        key, eq, val = s.partition('=')
        key = key.strip()
        val = val.strip()
        if self.read_unquote:
            val = unquote(val)
        if key != '' and eq == '=':
            return (upperASCII(key), val, comment)
        else:
            return (None, None, comment)

    def _kvpair(self, key, comment=""):
        value = self.info[key]
        if self.write_quote or self.always_quote:
            value = quote(value, self.always_quote)
        if comment:
            comment = " " + comment
        return key + '=' + value + comment + "\n"

    def __str__(self):
        """ Return the file that was read, replacing existing keys with new values
            removing keys that have been deleted and adding new keys.
        """
        oldkeys = []
        s = ""
        for line in self._lines:
            key, _value, comment = self._parseline(line)
            if key is None:
                s += line
            else:
                if key not in self.info:
                    continue
                oldkeys.append(key)
                s += self._kvpair(key, comment)

        # Add new keys
        for key in self.info:
            if key not in oldkeys:
                s += self._kvpair(key)

        return s
