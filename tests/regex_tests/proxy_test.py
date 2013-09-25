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
#

import unittest

from pyanaconda.regexes import PROXY_URL_PARSE

class ProxyRegexTestCase(unittest.TestCase):
    def proxy_regex_test(self):
        """
        Run a list of possible proxy= values through the regex and check for
        correct results.

        tests are in the form of: (proxy string, match.groups() tuple)
        """
        tests = [ ( "proxy.host",
                      (None, None, None, None, 'proxy.host', None, None) ),

                  ( "proxy.host:3128",
                      (None, None, None, None, 'proxy.host', ':3128', None) ),

                  ( "user:password@proxy.host",
                      (None, 'user:password@', 'user', ':password', 'proxy.host', None, None) ),

                  ( "user@proxy.host",
                      (None, 'user@', 'user', None, 'proxy.host', None, None) ),

                  ( "user:password@proxy.host:3128",
                      (None, 'user:password@', 'user', ':password', 'proxy.host', ':3128', None) ),

                  ( "user@proxy.host:3128",
                      (None, 'user@', 'user', None, 'proxy.host', ':3128', None) ),

                  ( "proxy.host/blah/blah",
                      (None, None, None, None, 'proxy.host', None, '/blah/blah') ),

                  ( "proxy.host:3128/blah/blah",
                      (None, None, None, None, 'proxy.host', ':3128', '/blah/blah') ),

                  ( "user:password@proxy.host/blah/blah",
                      (None, 'user:password@', 'user', ':password', 'proxy.host', None, '/blah/blah') ),

                  ( "user@proxy.host/blah/blah",
                      (None, 'user@', 'user', None, 'proxy.host', None, '/blah/blah') ),

                  ( "user:password@proxy.host:3128/blah/blah",
                      (None, 'user:password@', 'user', ':password', 'proxy.host', ':3128', "/blah/blah") ),

                  ( "user@proxy.host:3128/blah/blah",
                      (None, 'user@', 'user', None, 'proxy.host', ':3128', "/blah/blah") ),



                  ( "http://proxy.host",
                      ('http://', None, None, None, 'proxy.host', None, None) ),

                  ( "http://proxy.host:3128",
                      ('http://', None, None, None, 'proxy.host', ':3128', None) ),

                  ( "http://user:password@proxy.host",
                      ('http://', 'user:password@', 'user', ':password', 'proxy.host', None, None) ),

                  ( "http://user@proxy.host",
                      ('http://', 'user@', 'user', None, 'proxy.host', None, None) ),

                  ( "http://user:password@proxy.host:3128",
                      ('http://', 'user:password@', 'user', ':password', 'proxy.host', ':3128', None) ),

                  ( "http://user@proxy.host:3128",
                      ('http://', 'user@', 'user', None, 'proxy.host', ':3128', None) ),

                  ( "http://proxy.host/blah/blah",
                      ('http://', None, None, None, 'proxy.host', None, '/blah/blah') ),

                  ( "http://proxy.host:3128/blah/blah",
                      ('http://', None, None, None, 'proxy.host', ':3128', '/blah/blah') ),

                  ( "http://user:password@proxy.host/blah/blah",
                      ("http://", 'user:password@', 'user', ':password', 'proxy.host', None, '/blah/blah') ),

                  ( "http://user@proxy.host/blah/blah",
                      ("http://", 'user@', 'user', None, 'proxy.host', None, '/blah/blah') ),

                  ( "http://user:password@proxy.host:3128/blah/blah",
                      ("http://", 'user:password@', 'user', ':password', 'proxy.host', ':3128', '/blah/blah') ),

                  ( "http://user@proxy.host:3128/blah/blah",
                      ("http://", 'user@', 'user', None, 'proxy.host', ':3128', '/blah/blah') ),

                ]


        got_error = False
        for proxy, result in tests:
            try:
                self.assertEqual(PROXY_URL_PARSE.match(proxy).groups(), result)
            except AssertionError:
                got_error = True
                print("Proxy parse error: `%s' did not parse as `%s'" % (proxy, result))

        if got_error:
            self.fail()
