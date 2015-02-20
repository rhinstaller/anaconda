#
# Copyright (C) 2010-2013  Red Hat, Inc.
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
# Red Hat Author(s): Brian C. Lane <bcl@redhat.com>
#                    David Shea <dshea@redhat.com>
#

import unittest

from regexcheck import regex_group
from pyanaconda.regexes import URL_PARSE

class URLRegexTestCase(unittest.TestCase):
    def url_regex_test(self):
        """
        Run a list of possible URL values through the regex and check for
        correct results.

        tests are in the form of: (URL string, match.groups() tuple)
        """
        tests = [ ( "proxy.host",
                      (None, None, None, 'proxy.host', None, None, None, None) ),

                  ( "proxy.host:3128",
                      (None, None, None, 'proxy.host', '3128', None, None, None) ),

                  ( "user:password@proxy.host",
                      (None, 'user', 'password', 'proxy.host', None, None, None, None) ),

                  ( "user@proxy.host",
                      (None, 'user', None, 'proxy.host', None, None, None, None) ),

                  ( "user:password@proxy.host:3128",
                      (None, 'user', 'password', 'proxy.host', '3128', None, None, None) ),

                  ( "user@proxy.host:3128",
                      (None, 'user', None, 'proxy.host', '3128', None, None, None) ),

                  ( "proxy.host/blah/blah",
                      (None, None, None, 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "proxy.host:3128/blah/blah",
                      (None, None, None, 'proxy.host', '3128', '/blah/blah', None, None) ),

                  ( "user:password@proxy.host/blah/blah",
                      (None, 'user', 'password', 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "user@proxy.host/blah/blah",
                      (None, 'user', None, 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "user:password@proxy.host:3128/blah/blah",
                      (None, 'user', 'password', 'proxy.host', '3128', "/blah/blah", None, None) ),

                  ( "user@proxy.host:3128/blah/blah",
                      (None, 'user', None, 'proxy.host', '3128', "/blah/blah", None, None) ),



                  ( "http://proxy.host",
                      ('http://', None, None, 'proxy.host', None, None, None, None) ),

                  ( "http://proxy.host:3128",
                      ('http://', None, None, 'proxy.host', '3128', None, None, None) ),

                  ( "http://user:password@proxy.host",
                      ('http://', 'user', 'password', 'proxy.host', None, None, None, None) ),

                  ( "http://user@proxy.host",
                      ('http://', 'user', None, 'proxy.host', None, None, None, None) ),

                  ( "http://user:password@proxy.host:3128",
                      ('http://', 'user', 'password', 'proxy.host', '3128', None, None, None) ),

                  ( "http://user@proxy.host:3128",
                      ('http://', 'user', None, 'proxy.host', '3128', None, None, None) ),

                  ( "http://proxy.host/blah/blah",
                      ('http://', None, None, 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "http://proxy.host:3128/blah/blah",
                      ('http://', None, None, 'proxy.host', '3128', '/blah/blah', None, None) ),

                  ( "http://user:password@proxy.host/blah/blah",
                      ("http://", 'user', 'password', 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "http://%75ser:password@proxy.host/blah/blah",
                      ("http://", '%75ser', 'password', 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "http://user:%70assword@proxy.host/blah/blah",
                      ("http://", 'user', '%70assword', 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "http://user@proxy.host/blah/blah",
                      ("http://", 'user', None, 'proxy.host', None, '/blah/blah', None, None) ),

                  ( "http://user@proxy.host/blah/bla%68",
                      ("http://", 'user', None, 'proxy.host', None, '/blah/bla%68', None, None) ),

                  ( "http://user:password@proxy.host:3128/blah/blah",
                      ("http://", 'user', 'password', 'proxy.host', '3128', '/blah/blah', None, None) ),

                  ( "http://user@proxy.host:3128/blah/blah",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', None, None) ),

                  ( "http://user@proxy.host:3128/blah/blah?query",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "query", None) ),

                  ( "http://user@proxy.host:3128/blah/blah?query?",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "query?", None) ),

                  ( "http://user@proxy.host:3128/blah/blah?query=whatever",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "query=whatever", None) ),

                  ( "http://user@proxy.host:3128/blah/blah?query=whate%76er",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "query=whate%76er", None) ),

                  ( "http://user@proxy.host:3128/blah/blah?",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "", None) ),

                  ( "http://user@proxy.host:3128/blah/blah#fragment",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', None, "fragment") ),

                  ( "http://user@proxy.host:3128/blah/blah#",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', None, "") ),

                  ( "http://user@proxy.host:3128/blah/blah#fragm%65nt",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', None, "fragm%65nt") ),

                  ( "http://user@proxy.host:3128/blah/blah?query=whatever#fragment",
                      ("http://", 'user', None, 'proxy.host', '3128', '/blah/blah', "query=whatever", "fragment") ),

                  # Invalid schemes
                  ( "0http://proxy.host/", None),
                  ( "h~ttp://proxy.host/", None),

                  # Invalid usernames and passwords
                  ( "http://%x5ser@proxy.host/", None),
                  ( "http://*ser@proxy.host/", None),
                  ( "http://user:p%xxssword@proxy.host/", None),
                  ( "http://user:p@ssword@proxy.host/", None),

                  # Invalid paths
                  ( "http://user:password@proxy.host/%xxlah/blah", None),
                  ( "http://user:password@proxy.host/[]lah/blah", None),

                  # Invalid queries
                  ( "http://proxy.host/blah/blah?quer%xx", None),
                  ( "http://proxy.host/blah/blah?que[]y", None),

                  # Invalid fragments
                  ( "http://proxy.host/blah/blah#fragment#", None),
                  ( "http://proxy.host/blah/blah#%xxragment", None),
                ]


        if not regex_group(URL_PARSE, tests):
            self.fail()
