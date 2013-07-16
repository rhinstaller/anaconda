#!/usr/bin/python

import mock
import os

class VncTest(mock.TestCase):

    def setUp(self):
        self.setupModules(["_isys", "block", "logging", "ConfigParser"])
        self.fs = mock.DiskIO()

        self.anaconda = mock.Mock()
        self.anaconda.ksdata.vnc.password = ''

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

        self.OK = 22

        import pyanaconda.vnc
        pyanaconda.vnc.log = mock.Mock()
        pyanaconda.vnc.os = mock.Mock()
        pyanaconda.vnc.subprocess = mock.Mock()
        pyanaconda.vnc.subprocess.Popen().communicate.return_value = (1, 2)
        pyanaconda.vnc.subprocess.Popen().returncode = self.OK
        pyanaconda.vnc.open = self.fs.open

        self.ROOT = '/'
        self.DISPLAY = '2'
        self.DESKTOP = 'Desktop'
        self.PASS = ''
        self.LOG_FILE = '/tmp/vnc.log'
        self.PW_FILE = '/tmp/vncpassword'
        self.VNCCONNECTHOST = 'host'

    def tearDown(self):
        self.tearDownModules()

    def set_vnc_password_1_test(self):
        import pyanaconda.vnc
        server = pyanaconda.vnc.VncServer()
        server.anaconda = self.anaconda
        pyanaconda.vnc.iutil = mock.Mock()
        pyanaconda.vnc.os.pipe.return_value = (1, 2)

        server.setVNCPassword()
        self.assertEqual(
            pyanaconda.vnc.iutil.execWithRedirect.call_args_list,
            [(('vncpasswd', ['-f']), {'stdin': 1, 'stdout': '/tmp/vncpassword'})])

    def initialize_test(self):
        import pyanaconda.vnc

        IP = '192.168.0.21'
        HOSTNAME = 'desktop'

        dev = mock.Mock()
        dev.get.return_value = 'eth0'
        pyanaconda.vnc.network = mock.Mock()
        pyanaconda.vnc.network.Network().netdevices = [dev]
        pyanaconda.vnc.network.getActiveNetDevs.return_value = [0]
        pyanaconda.vnc.network.getDefaultHostname.return_value = HOSTNAME
        pyanaconda.vnc.isys = mock.Mock()
        pyanaconda.vnc.isys.getIPAddresses = mock.Mock(return_value=[IP])

        server = pyanaconda.vnc.VncServer(display=self.DISPLAY)
        server.initialize()
        expected = "%s:%s (%s)" % (HOSTNAME, self.DISPLAY, IP)
        self.assertEqual(server.connxinfo, expected)

    def openlogfile_test(self):
        import pyanaconda.vnc
        FILE = 'file'
        pyanaconda.vnc.os.O_RDWR = os.O_RDWR
        pyanaconda.vnc.os.O_CREAT = os.O_CREAT
        pyanaconda.vnc.os.open.return_value = FILE

        server = pyanaconda.vnc.VncServer(log_file=self.LOG_FILE)
        ret = server.openlogfile()
        self.assertEqual(ret, FILE)
        self.assertEqual(pyanaconda.vnc.os.open.call_args,
            ((self.LOG_FILE, os.O_RDWR | os.O_CREAT), {})
        )

    def connect_to_view_test(self):
        import pyanaconda.vnc
        pyanaconda.vnc.subprocess.Popen().communicate.return_value = (self.OK, '')

        server = pyanaconda.vnc.VncServer(vncconnecthost=self.VNCCONNECTHOST)
        ret = server.connectToView()
        self.assertTrue(ret)

        params = pyanaconda.vnc.subprocess.Popen.call_args[0][0]
        self.assertTrue(self.VNCCONNECTHOST in params)
        self.assertTrue(params[params.index(self.VNCCONNECTHOST)-1] == "-connect")

    def start_server_test(self):
        import pyanaconda.vnc
        pyanaconda.vnc.VncServer.initialize = mock.Mock()
        pyanaconda.vnc.VncServer.setVNCPassword = mock.Mock()
        pyanaconda.vnc.VncServer.VNCListen = mock.Mock()
        pyanaconda.vnc.subprocess.Popen().poll.return_value = None
        pyanaconda.vnc.os.environ = {}
        pyanaconda.vnc.time.sleep = mock.Mock()

        server = pyanaconda.vnc.VncServer(root=self.ROOT, display=self.DISPLAY,
            desktop=self.DESKTOP, password=self.PASS, vncconnecthost="")
        server.openlogfile = mock.Mock()
        server.startServer()

        params = pyanaconda.vnc.subprocess.Popen.call_args[0][0]
        self.assertTrue('desktop=%s'%self.DESKTOP  in params)
        self.assertTrue(':%s'%self.DISPLAY  in params)
        self.assertTrue(pyanaconda.vnc.VncServer.VNCListen.called)
        self.assertTrue("DISPLAY" in pyanaconda.vnc.os.environ)
        self.assertEqual(pyanaconda.vnc.os.environ['DISPLAY'], ":%s" % self.DISPLAY)
