#!/usr/bin/python

import mock

class RescueTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(['_isys', 'block', 'parted', 'storage',
                        'pyanaconda.storage.formats', 'logging', 
                        'add_drive_text', 'ConfigParser', 
                        'pyanaconda.storage.storage_log'])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
        
        import pyanaconda.rescue
        pyanaconda.rescue.open = self.fs.open
          
    def tearDown(self):
        self.tearDownModules()
    
    #
    # RescueInterface class tests
    #
    
    def rescueinterface_waitwindow_test(self):
        import pyanaconda.rescue
        RET = 'foo1'
        pyanaconda.rescue.WaitWindow = mock.Mock(return_value=RET)
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.waitWindow(TITLE, TEXT)
        self.assertEqual(ret, RET)
    
    def rescueinterface_progresswindow_test(self):
        import pyanaconda.rescue
        RET = 'foo2'
        pyanaconda.rescue.ProgressWindow = mock.Mock(return_value=RET)
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        TOTAL = 100
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.progressWindow(TITLE, TEXT, TOTAL)
        self.assertEqual(ret, RET)
    
    def rescueinterface_detailedmessagewindow_test(self):
        import pyanaconda.rescue
        RET = 'foo3'
        pyanaconda.rescue.RescueInterface.messageWindow = mock.Mock(return_value=RET)
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.detailedMessageWindow(TITLE, TEXT)
        self.assertEqual(ret, RET)
    
    def rescueinterface_messagewindow_1_test(self):
        import pyanaconda.rescue
        pyanaconda.rescue.ButtonChoiceWindow = mock.Mock()
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        TYPE = 'ok'
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ri.detailedMessageWindow(TITLE, TEXT, TYPE)
        self.assertTrue(pyanaconda.rescue.ButtonChoiceWindow.called)
    
    def rescueinterface_messagewindow_2_test(self):
        import pyanaconda.rescue
        RET='yes'
        pyanaconda.rescue.ButtonChoiceWindow = mock.Mock(return_value=RET)
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        TYPE = 'yesno'
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.messageWindow(TITLE, TEXT, TYPE)
        self.assertEqual(ret, 1)
        
    def rescueinterface_messagewindow_3_test(self):
        import pyanaconda.rescue
        RET = 'barfoo'
        pyanaconda.rescue.ButtonChoiceWindow = mock.Mock(return_value=RET)
        SCREEN = 0
        TITLE = 'title'
        TEXT = 'text'
        TYPE = 'custom'
        CUSTOM_BUTT = ['foo_bar', 'bar_foo']
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.messageWindow(TITLE, TEXT, TYPE, custom_buttons=CUSTOM_BUTT)
        self.assertEqual(ret, 1)
    
    def rescueinterface_messagewindow_4_test(self):
        import pyanaconda.rescue
        RET = 'foo4'
        SCREEN = 0
        pyanaconda.rescue.OkCancelWindow = mock.Mock(return_value=RET)
        TITLE = 'title'
        TEXT = 'text'
        TYPE = 'otherfoo'
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.messageWindow(TITLE, TEXT, TYPE)
        self.assertEqual(ret, RET)
    
    def rescueinterface_enablenetwork_1_test(self):
        import pyanaconda.rescue
        anaconda = mock.Mock()
        anaconda.network.netdevices = {}
        SCREEN = 0
        
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.enableNetwork(anaconda)
        self.assertFalse(ret)
    
    def rescueinterface_enablenetwork_2_test(self):
        import pyanaconda.rescue
        import pyanaconda.textw.netconfig_text
        pyanaconda.rescue.INSTALL_BACK = -1
        pyanaconda.textw.netconfig_text.NetworkConfiguratorText = mock.Mock()
        pyanaconda.textw.netconfig_text.NetworkConfiguratorText().run.return_value =\
            "foo"
        anaconda = mock.Mock()
        anaconda.network.netdevices = {'foo': 'as'}
        SCREEN = 0
        
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.enableNetwork(anaconda)
        self.assertTrue(ret)
        
    def rescueinterface_enablenetwork_3_test(self):
        import pyanaconda.rescue
        import pyanaconda.textw.netconfig_text
        pyanaconda.rescue.INSTALL_BACK = "foo"
        pyanaconda.textw.netconfig_text.NetworkConfiguratorText = mock.Mock()
        pyanaconda.textw.netconfig_text.NetworkConfiguratorText().run.return_value =\
            pyanaconda.rescue.INSTALL_BACK
        anaconda = mock.Mock()
        anaconda.network.netdevices = {'bar': 'asdf'}
        SCREEN = 0
        
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.enableNetwork(anaconda)
        self.assertFalse(ret)
    
    def rescueinterface_passphraseentrywindow_test(self):
        import pyanaconda.rescue
        RET = ('secret', False)
        pyanaconda.rescue.PassphraseEntryWindow = mock.Mock()
        pyanaconda.rescue.PassphraseEntryWindow().run.return_value = RET
        SCREEN = 0
        DEVICE = 'dev'
        
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.passphraseEntryWindow(DEVICE)
        self.assertEqual(ret, RET)
        self.assertTrue(pyanaconda.rescue.PassphraseEntryWindow().pop.called)
    
    def rescueinterface_resetinitializediskquestion_test(self):
        import pyanaconda.rescue
        SCREEN = 0
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ri._initLabelAnswers = {'foo': 'bar'}
        ri.resetInitializeDiskQuestion()
    
    def rescueinterface_resetreinitinconsistentlvmquestion_test(self):
        import pyanaconda.rescue
        SCREEN = 0
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ri._inconsistentLVMAnswers = {'foo': 'bar'}
        ri.resetReinitInconsistentLVMQuestion()
        self.assertEqual(ri._inconsistentLVMAnswers, {})
    
    def rescueinterface_questioninitializedisk_test(self):
        import pyanaconda.rescue
        SCREEN = 0
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.questionInitializeDisk('/', '', 0)
        self.assertFalse(ret)
    
    def rescueinterface_questionreinitinconsistentlvm_test(self):
        import pyanaconda.rescue
        SCREEN = 0
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.questionReinitInconsistentLVM()
        self.assertFalse(ret)
    
    def rescueinterface_questioninitializedasd_test(self):
        import pyanaconda.rescue
        SCREEN = 0
        ri = pyanaconda.rescue.RescueInterface(SCREEN)
        ret = ri.questionInitializeDASD('', '')
        self.assertEqual(ret, 1)
    
    #
    # module function tests
    #
    
    def makemtab_test(self):
        import pyanaconda.rescue
        MTAB = "proc /proc proc rw 0 0"
        INSTPATH = '/tmp'
        STORAGE = mock.Mock()
        STORAGE.mtab = MTAB
        
        ret = pyanaconda.rescue.makeMtab(INSTPATH, STORAGE)
        self.assertEqual(self.fs['%s/etc/mtab' % INSTPATH], MTAB)
    
    def makefstab_test(self):
        import pyanaconda.rescue
        INSTPATH = '/tmp'
        FSTAB = 'rootfs / rootfs rw 0 0'
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.access.return_value = True
        self.fs.open('/proc/mounts', 'w').write(FSTAB)
        self.fs.open('%s/etc/fstab' % INSTPATH, 'w')
        
        ret = pyanaconda.rescue.makeFStab(INSTPATH)
        self.assertEqual(self.fs['%s/etc/fstab' % INSTPATH], FSTAB)
    
    def makeresolvconf_1_test(self):
        import pyanaconda.rescue
        INSTPATH = '/tmp'
        RESOLV = "nameserver 10.0.0.1"
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.access.return_value = False
        pyanaconda.rescue.shutil = mock.Mock()
        
        pyanaconda.rescue.makeResolvConf(INSTPATH)
        self.assertFalse(pyanaconda.rescue.shutil.copyfile.called)
    
    def makeresolvconf_2_test(self):
        import pyanaconda.rescue
        INSTPATH = '/tmp'
        RESOLV = "nameserver 10.0.0.1"
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.access.return_value = True
        pyanaconda.rescue.shutil = mock.Mock()
        self.fs.open('%s/etc/resolv.conf' % INSTPATH, 'w').write(RESOLV)
        
        pyanaconda.rescue.makeResolvConf(INSTPATH)
        self.assertFalse(pyanaconda.rescue.shutil.copyfile.called)
    
    def makeresolvconf_3_test(self):
        import pyanaconda.rescue
        INSTPATH = '/tmp'
        RESOLV = "nameserver 10.0.0.1"
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.access.return_value = True
        pyanaconda.rescue.shutil = mock.Mock()
        self.fs.open('%s/etc/resolv.conf' % INSTPATH, 'w').write('')
        self.fs.open('/etc/resolv.conf', 'w').write('')
        
        pyanaconda.rescue.makeResolvConf(INSTPATH)
        self.assertFalse(pyanaconda.rescue.shutil.copyfile.called)
        self.assertEqual(self.fs['%s/etc/resolv.conf' % INSTPATH], '')
    
    def makeresolvconf_4_test(self):
        import pyanaconda.rescue
        INSTPATH = '/tmp'
        RESOLV = "nameserver 10.0.0.1"
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.access.return_value = True
        pyanaconda.rescue.shutil = mock.Mock()
        self.fs.open('%s/etc/resolv.conf' % INSTPATH, 'w').write('')
        self.fs.open('/etc/resolv.conf', 'w').write(RESOLV)
        
        pyanaconda.rescue.makeResolvConf(INSTPATH)
        self.assertTrue(pyanaconda.rescue.shutil.copyfile.called)
        self.assertEqual(self.fs['%s/etc/resolv.conf' % INSTPATH], 
            'nameserver 10.0.0.1')
    
    def startnetworking_test(self):
        import pyanaconda.rescue
        NETWORK = mock.Mock()
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.startNetworking(NETWORK, '')
        self.assertEqual(pyanaconda.rescue.os.system.call_args,
            (('/usr/sbin/ifconfig lo 127.0.0.1',), {}))
        self.assertTrue(NETWORK.bringUp.called)
        
    def runshell_1_test(self):
        import pyanaconda.rescue
        import sys
        TMPFILE = '/tmp/abc'
        MSG = "foo bar"
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.path.exists.return_value = True
        pyanaconda.rescue.subprocess = mock.Mock()
        proc = mock.Mock()
        proc.returncode = 0
        pyanaconda.rescue.subprocess.Popen.return_value = proc
        
        stdout = sys.stdout
        sys.stdout = self.fs.open(TMPFILE, 'w')
        pyanaconda.rescue.runShell(msg=MSG)
        sys.stdout.close()
        sys.stdout = stdout
        
        self.assertTrue(MSG in self.fs[TMPFILE])
        self.assertEqual(pyanaconda.rescue.subprocess.Popen.call_args, 
            ((['/usr/bin/firstaidkit-qs'],), {}))
    
    def runshell_2_test(self):
        import pyanaconda.rescue
        import sys
        TMPFILE = '/tmp/abc'
        MSG = "foo bar"
        
        def fake_f(filename, _=""):
            return filename == "/bin/bash"
        
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.path.exists = fake_f
        pyanaconda.rescue.iutil = mock.Mock()
        proc = mock.Mock()
        proc.returncode = 0
        pyanaconda.rescue.subprocess.Popen.return_value = proc
        
        stdout = sys.stdout
        sys.stdout = self.fs.open(TMPFILE, 'w')
        pyanaconda.rescue.runShell(msg=MSG)
        sys.stdout.close()
        sys.stdout = stdout
        
        self.assertTrue(MSG in self.fs[TMPFILE])
        self.assertTrue(pyanaconda.rescue.iutil.execConsole.called)
    
    def runshell_3_test(self):
        import pyanaconda.rescue
        import sys
        TMPFILE = '/tmp/abc'
        SCREEN = mock.Mock()
        pyanaconda.rescue.os = mock.Mock()
        pyanaconda.rescue.os.path.exists.return_value = True
        pyanaconda.rescue.subprocess = mock.Mock()
        proc = mock.Mock()
        proc.returncode = 0
        pyanaconda.rescue.subprocess.Popen.return_value = proc
        
        pyanaconda.rescue.runShell(screen=SCREEN)

        self.assertTrue(SCREEN.suspend.called)
        self.assertTrue(SCREEN.finish.called)
    
    #def runrescue_test(self):
    #    pass
