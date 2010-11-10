#!/usr/bin/python
import unittest
import re
import traceback


class ProxyRegexTestCase(unittest.TestCase):
    def testProxy(self):
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


        # This is from yumupdate.py and needs to be updated when it changes
        pattern = re.compile("([A-Za-z]+://)?(([A-Za-z0-9]+)(:[^:@]+)?@)?([^:/]+)(:[0-9]+)?(/.*)?")

        got_error = False
        for proxy, result in tests:
            try:
                self.assertEqual(pattern.match(proxy).groups(), result)
            except AssertionError as error:
                got_error = True
                print error

        if got_error:
            self.fail()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ProxyRegexTestCase)


if __name__ == "__main__":
    unittest.main()

