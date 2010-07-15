#!/usr/bin/python

import mock
import sys

class CmdLineTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", 'parted', 'storage',
                            'pyanaconda.storage.formats', 'logging', 
                            'ConfigParser'])
        
        self.fs = mock.DiskIO()
        self.stdout = sys.stdout
        self.TMP_STDOUT = '/tmp/stdout'
        import pyanaconda.cmdline
        
    def tearDown(self):
        sys.stdout = self.stdout
        self.tearDownModules()

    def waitwindow_test(self):
        import pyanaconda.cmdline
        TITLE = 'TITLE'
        TEXT = 'text'
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        win = pyanaconda.cmdline.WaitWindow(TITLE, TEXT)
        sys.stdout.close()
        self.assertEqual(self.fs[self.TMP_STDOUT], '%s\n' % TEXT)
    
    def progresswindow_1_test(self):
        import pyanaconda.cmdline
        TITLE = 'TITLE'
        TEXT = 'text'
        TOTAL = 100
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        win = pyanaconda.cmdline.ProgressWindow(TITLE, TEXT, TOTAL)
        sys.stdout.close()
        self.assertTrue(TEXT in self.fs[self.TMP_STDOUT])
    
    def progresswindow_2_test(self):
        import pyanaconda.cmdline
        TITLE = 'TITLE'
        TEXT = 'text'
        TOTAL = 100
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        win = pyanaconda.cmdline.ProgressWindow(TITLE, TEXT, TOTAL)
        win.set(50)
        sys.stdout.close()
        self.assertTrue(TEXT in self.fs[self.TMP_STDOUT])
    
    def progresswindow_3_test(self):
        import pyanaconda.cmdline
        TITLE = 'TITLE'
        TEXT = 'text'
        TOTAL = 100
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        win = pyanaconda.cmdline.ProgressWindow(TITLE, TEXT, TOTAL)
        win.set(100)
        sys.stdout.close()
        self.assertTrue(TEXT in self.fs[self.TMP_STDOUT])
    
    def installinterface_progresswindow_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.ProgressWindow = mock.Mock(return_value='foo')
        
        intf = pyanaconda.cmdline.InstallInterface()
        ret = intf.progressWindow(0, 0, 0)
        self.assertEqual(ret, 'foo')
    
    def installinterface_kickstarterrorwindow_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        TEXT = 'foobar text'
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        intf = pyanaconda.cmdline.InstallInterface()
        try: intf.kickstartErrorWindow(TEXT)
        except: pass
        sys.stdout.close()
        self.assertTrue(TEXT in self.fs[self.TMP_STDOUT])
    
    def installinterface_messagewindow_1_test(self):
        import pyanaconda.cmdline
        TITLE = 'TITLE'
        TEXT = 'foobar text'
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        intf = pyanaconda.cmdline.InstallInterface()
        intf.messageWindow(TITLE, TEXT)
        sys.stdout.close()
        self.assertEqual(self.fs[self.TMP_STDOUT], '%s\n' % TEXT)
    
    def installinterface_messagewindow_2_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        TITLE = 'TITLE'
        TEXT = 'foobar text'
        TYPE = 'abc'
        CUSTOM_BUTTONS = ['BUT1', 'BUT2']
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        intf = pyanaconda.cmdline.InstallInterface()
        try: intf.messageWindow(TITLE, TEXT, TYPE, custom_buttons=CUSTOM_BUTTONS)
        except: pass
        sys.stdout.close()
        self.assertTrue(TITLE in self.fs[self.TMP_STDOUT])
        self.assertTrue(TEXT in self.fs[self.TMP_STDOUT])
        for but in CUSTOM_BUTTONS:
            self.assertTrue(but in self.fs[self.TMP_STDOUT])
    
    def installinterface_detailedmessagewindow_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.InstallInterface.messageWindow = mock.Mock()
        TITLE = 'TITLE'
        TEXT = 'foobar text'
        LONGTEXT = 'very very very (wait for it) long text.'
        
        intf = pyanaconda.cmdline.InstallInterface()
        intf.detailedMessageWindow(TITLE, TEXT, LONGTEXT)
        self.assertTrue(
            TEXT in pyanaconda.cmdline.InstallInterface.messageWindow.call_args[0][1])
        self.assertTrue(
            LONGTEXT in pyanaconda.cmdline.InstallInterface.messageWindow.call_args[0][1])
    
    def installinterface_passhraseentrywindow_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        DEVICE = 'foodevice'
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        intf = pyanaconda.cmdline.InstallInterface()
        self.assertRaises(Exception, intf.passphraseEntryWindow, DEVICE)
        sys.stdout.close()
        self.assertTrue(DEVICE in self.fs[self.TMP_STDOUT])
        
    def installinterface_getlukspassphrase_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        
        intf = pyanaconda.cmdline.InstallInterface()
        self.assertRaises(Exception, intf.getLUKSPassphrase, 'foo')
    
    def installinterface_enablenetwork_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        
        intf = pyanaconda.cmdline.InstallInterface()
        self.assertRaises(Exception, intf.enableNetwork)
    
    def installinterface_questioninitialize_dasd_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.time.sleep = mock.Mock(side_effect=Exception)
        
        intf = pyanaconda.cmdline.InstallInterface()
        self.assertRaises(Exception, intf.questionInitializeDASD, 'foo', 'bar')
    
    def installinterface_mainexceptionwindow_test(self):
        import pyanaconda.cmdline
        SHORT_TEXT = "short text"
        LONG_TEXT = "long text"
        
        sys.stdout = self.fs.open(self.TMP_STDOUT, 'w')
        intf = pyanaconda.cmdline.InstallInterface()
        intf.mainExceptionWindow(SHORT_TEXT, LONG_TEXT)
        sys.stdout.close()
        self.assertTrue(SHORT_TEXT in self.fs[self.TMP_STDOUT])
    
    def installinterface_waitwindow_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.WaitWindow = mock.Mock()
        TITLE = 'TITLE'
        TEXT = 'text'
        
        intf = pyanaconda.cmdline.InstallInterface()
        intf.waitWindow(TITLE, TEXT)
        self.assertTrue(pyanaconda.cmdline.WaitWindow.called)
        self.assertEqual(pyanaconda.cmdline.WaitWindow.call_args,
            (('TITLE', 'text'), {}))
    
    #def installinterface_run_test(self):
    #    pass
    
    def installinterface_setinstallprogressclass_test(self):
        import pyanaconda.cmdline
        CLASS = 65
        intf = pyanaconda.cmdline.InstallInterface()
        intf.setInstallProgressClass(CLASS)
        self.assertEqual(intf.instProgress, CLASS)
        
    def progressdisplay_get_fraction_test(self):
        import pyanaconda.cmdline
        PCT = 44
        pd = pyanaconda.cmdline.progressDisplay()
        pd.pct = PCT
        ret = pd.get_fraction()
        self.assertEqual(ret, PCT)
    
    def progressdisplay_set_fraction_test(self):
        import pyanaconda.cmdline
        PCT = 52
        pd = pyanaconda.cmdline.progressDisplay()
        pd.set_fraction(52)
        self.assertEqual(pd.pct, PCT)
    
    def progressdisplay_set_label_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.strip_markup = mock.Mock(return_value="foo")
        TEXT = 'text'
        
        pd = pyanaconda.cmdline.progressDisplay()
        pd.set_label(TEXT)
        self.assertEqual(pd.display, "foo")
    
    def setupprogressdisplay_1_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.DISPATCH_BACK = -1
        pyanaconda.cmdline.DISPATCH_FORWARD = 1
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.cmdline.DISPATCH_BACK
        
        ret = pyanaconda.cmdline.setupProgressDisplay(anaconda)
        self.assertEqual(ret, pyanaconda.cmdline.DISPATCH_BACK)
        self.assertTrue(anaconda.intf.setInstallProgressClass.called)
        
    def setupprogressdisplay_2_test(self):
        import pyanaconda.cmdline
        pyanaconda.cmdline.DISPATCH_BACK = -1
        pyanaconda.cmdline.DISPATCH_FORWARD = 1
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.cmdline.DISPATCH_FORWARD
        
        ret = pyanaconda.cmdline.setupProgressDisplay(anaconda)
        self.assertEqual(ret, pyanaconda.cmdline.DISPATCH_FORWARD)
        self.assertTrue(anaconda.intf.setInstallProgressClass.called)
    
