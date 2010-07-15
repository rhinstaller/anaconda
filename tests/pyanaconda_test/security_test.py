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
        
    def write_ks_1_test(self):
        """Simulate writing security to kickstart (1)"""
        import pyanaconda.security 
                   
        scrt = pyanaconda.security.Security()
        f = self.fs.open('/tmp/security_ks1', 'w')
        scrt.writeKS(f)
        f.close()
        
        self.assertEqual(self.fs['/tmp/security_ks1'], 
            'selinux --enforcing\nauthconfig --enableshadow --passalgo=sha512 --enablefingerprint\n')
            
    def write_ks_2_test(self):
        """Simulate writing security to kickstart (2)"""
        import pyanaconda.security 
                   
        scrt = pyanaconda.security.Security()
        scrt.selinux = pyanaconda.security.SELINUX_DISABLED
        f = self.fs.open('/tmp/security_ks2', 'w')
        scrt.writeKS(f)
        f.close()
        
        self.assertEqual(self.fs['/tmp/security_ks2'], 
            'selinux --disabled\nauthconfig --enableshadow --passalgo=sha512 --enablefingerprint\n')
            
    def write_test(self):
        """Simulate writing security (simulate executing lokkit and authconfig)"""
        import pyanaconda.security 
                   
        scrt = pyanaconda.security.Security()
        scrt.write('/tmp/security')    
        
        self.assertEqual(pyanaconda.security.iutil.method_calls, 
            [('execWithRedirect', 
                ('/usr/sbin/lokkit', ['--selinux=enforcing']), 
                {'root': '/tmp/security', 'stderr': '/dev/null', 'stdout': '/dev/null'}
             ), 
             ('execWithRedirect', 
                ('/usr/sbin/authconfig', 
                    ['--update', '--nostart', '--enableshadow', '--passalgo=sha512', '--enablefingerprint']
                ), 
                {'root': '/tmp/security', 'stderr': '/dev/tty5', 'stdout': '/dev/tty5'}
             )
            ]
        )    
        
