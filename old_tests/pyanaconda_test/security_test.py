#!/usr/bin/python

import mock
import sys

class SecurityTest(mock.TestCase):
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])

        self.fs = mock.DiskIO()

        import pyanaconda.security
        pyanaconda.security.log = mock.Mock()
        pyanaconda.security.open = self.fs.open
        pyanaconda.security.iutil = mock.Mock()

        import pyanaconda.flags
        pyanaconda.flags.flags.selinux = 1

    def tearDown(self):
        self.tearDownModules()

    def set_get_selinux_test(self):
        import pyanaconda.security

        states = pyanaconda.security.selinux_states
        scrt = pyanaconda.security.Security()

        for state in states:
            scrt.setSELinux(state)
            self.assertEqual(scrt.getSELinux(), state)

    def set_get_selinux_bad_sate_test(self):
        import pyanaconda.security

        states = pyanaconda.security.selinux_states
        scrt = pyanaconda.security.Security()
        scrt.setSELinux('bad_state')
        self.assertTrue(scrt.getSELinux() in states)

    def write_test(self):
        """Simulate writing security (simulate executing lokkit and authconfig)"""
        import pyanaconda.security

        scrt = pyanaconda.security.Security()
        pyanaconda.security.ROOT_PATH = "/tmp/security"
        scrt.write()

        self.assertEqual(pyanaconda.security.iutil.method_calls,
            [('execWithRedirect',
                ('/usr/sbin/lokkit', ['--selinux=enforcing']),
                {'root': '/tmp/security', 'stderr': '/dev/null', 'stdout': '/dev/null'}
             ),
             ('resetRpmDb', (), {}),
             ('execWithRedirect',
                ('/usr/sbin/authconfig',
                    ['--update', '--nostart', '--enableshadow', '--passalgo=sha512']
                ),
                {'root': '/tmp/security', 'stderr': '/dev/tty5', 'stdout': '/dev/tty5'}
             )
            ]
        )
