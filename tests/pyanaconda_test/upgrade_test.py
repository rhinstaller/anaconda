#!/usr/bin/python

import mock

class UpgradeTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(['_isys', 'block', 'parted', 'storage',
                           'pyanaconda.storage.formats', 'logging',
                           'ConfigParser'])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
                      
        import pyanaconda.upgrade
          
    def tearDown(self):
        self.tearDownModules()
    
    def query_upgrade_continue_1_test(self):
        import pyanaconda.upgrade
        DIR = 1
        pyanaconda.upgrade.DISPATCH_FORWARD
        anaconda = mock.Mock()
        anaconda.dir = DIR
        
        ret = pyanaconda.upgrade.queryUpgradeContinue(anaconda)
        self.assertEqual(None, ret)
    
    def query_upgrade_continue_2_test(self):
        import pyanaconda.upgrade
        DIR = 1
        pyanaconda.upgrade.DISPATCH_FORWARD
        anaconda = mock.Mock()
        anaconda.dir = DIR - 5
        anaconda.intf.messageWindow.return_value = 1
        
        ret = pyanaconda.upgrade.queryUpgradeContinue(anaconda)
        self.assertEqual(DIR, ret)
    
    def set_upgrade_root_1_test(self):
        import pyanaconda.upgrade
        DEV_NAME = 'device'
        DEV = mock.Mock()
        anaconda = mock.Mock()
        anaconda.ksdata.upgrade.root_device = None
        anaconda.rootParts = [(DEV, DEV_NAME)]
        pyanaconda.upgrade.setUpgradeRoot(anaconda)
        self.assertEqual(1, len(anaconda.upgradeRoot))
    
    def set_upgrade_root_2_test(self):
        import pyanaconda.upgrade
        DEV_NAME = 'device'
        DEV = mock.Mock()

        DEV2_NAME = 'device2'
        DEV2 = mock.Mock()
        DEV2.name = DEV2_NAME
        
        anaconda = mock.Mock()
        anaconda.ksdata.upgrade.root_device = DEV2_NAME
        anaconda.rootParts = [(DEV, DEV_NAME), (DEV2, DEV2_NAME)]
        pyanaconda.upgrade.setUpgradeRoot(anaconda)
        self.assertEqual(anaconda.upgradeRoot[0][1], DEV2_NAME)
    
    def find_root_parts_1_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.flags = mock.Mock()
        pyanaconda.upgrade.findExistingRoots = mock.Mock(
                            return_value=(None, [("info1", "info2", "info3")]))
        pyanaconda.upgrade.setUpgradeRoot = mock.Mock()
        
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.upgrade.DISPATCH_BACK + 2
        anaconda.rootParts = None
        anaconda.intf.messageWindow.return_value = 1
        
        pyanaconda.upgrade.findRootParts(anaconda)
        self.assertTrue(anaconda.intf.messageWindow.called)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('findinstall',), {'skip': 1}))
    
    def find_root_parts_2_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.setUpgradeRoot = mock.Mock()
        
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.upgrade.DISPATCH_BACK + 2
        anaconda.rootParts = ['rootpart']
        anaconda.intf.messageWindow.return_value = 1
        
        pyanaconda.upgrade.findRootParts(anaconda)
        self.assertFalse(anaconda.intf.messageWindow.called)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('findinstall',), {'skip': 0}))
    
    def find_existing_roots_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.findExistingRootDevices = mock.Mock()
        pyanaconda.upgrade.findExistingRoots(mock.Mock())
        self.assertTrue(pyanaconda.upgrade.findExistingRootDevices.called)
    
    def bind_mount_dev_directory_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.getFormat = mock.Mock()
        INST_PATH = "/tmp"
        pyanaconda.upgrade.bindMountDevDirectory(INST_PATH)
        self.assertEqual(pyanaconda.upgrade.getFormat().mount.call_args,
            ((), {'chroot': INST_PATH}))
    
    def upgrade_migrate_find_1_test(self):
        import pyanaconda.upgrade
        anaconda = mock.Mock()
        anaconda.storage.migratableDevices = []
        pyanaconda.upgrade.upgradeMigrateFind(anaconda)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('upgrademigratefs',), {}))
    
    def upgrade_migrate_find_2_test(self):
        import pyanaconda.upgrade
        anaconda = mock.Mock()
        anaconda.storage.migratableDevices = ['']
        pyanaconda.upgrade.upgradeMigrateFind(anaconda)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('upgrademigratefs',), {'skip': 0}))
    
    def copy_from_sysimage_1_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.access.return_value = False
        ROOT = "/tmp"
        FILE = "file"
        ret = pyanaconda.upgrade.copyFromSysimage(ROOT, FILE)
        self.assertFalse(ret)
    
    def copy_from_sysimage_2_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.access.return_value = True
        pyanaconda.upgrade.shutil = mock.Mock()
        pyanaconda.upgrade.shutil.copyfile.side_effect = OSError
        ROOT = "/tmp"
        FILE = "file"
        ret = pyanaconda.upgrade.copyFromSysimage(ROOT, FILE)
        self.assertTrue(pyanaconda.upgrade.os.remove.called)
        self.assertTrue(pyanaconda.upgrade.shutil.copyfile.called)
        self.assertFalse(ret)
    
    def copy_from_sysimage_3_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.access.return_value = True
        pyanaconda.upgrade.shutil = mock.Mock()
        ROOT = "/tmp"
        FILE = "file"
        ret = pyanaconda.upgrade.copyFromSysimage(ROOT, FILE)
        self.assertTrue(pyanaconda.upgrade.os.remove.called)
        self.assertTrue(pyanaconda.upgrade.shutil.copyfile.called)
        self.assertTrue(ret)
    
    def restore_time_1_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.environ = {'TZ': 'foo'}
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.upgrade.DISPATCH_BACK
        pyanaconda.upgrade.restoreTime(anaconda)
        self.assertTrue(pyanaconda.upgrade.os.environ.has_key('TZ'))
    
    def restore_time_2_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.copyFromSysimage = mock.Mock()
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.environ = {'TZ': 'foo'}
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.isS390.return_value = True
        
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.upgrade.DISPATCH_BACK + 1
        pyanaconda.upgrade.restoreTime(anaconda)
        self.assertFalse(pyanaconda.upgrade.os.environ.has_key('TZ'))
        self.assertTrue(pyanaconda.upgrade.copyFromSysimage.called)
        self.assertFalse(pyanaconda.upgrade.iutil.execWithRedirect.called)
    
    def restore_time_3_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.copyFromSysimage = mock.Mock()
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.environ = {'TZ': 'foo'}
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.isS390.return_value = False
        
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.upgrade.DISPATCH_BACK + 1
        pyanaconda.upgrade.restoreTime(anaconda)
        self.assertFalse(pyanaconda.upgrade.os.environ.has_key('TZ'))
        self.assertTrue(pyanaconda.upgrade.copyFromSysimage.called)
        self.assertTrue(pyanaconda.upgrade.iutil.execWithRedirect.called)
    
    def upgrade_swap_suggestion_1_test(self):
        """upgradeSwapSuggestion - 4GB RAM, 6GB SWAP"""
        import pyanaconda.upgrade
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.memInstalled.return_value = 4194304
        pyanaconda.upgrade.iutil.swapAmount.return_value = 6291456
        anaconda = mock.Mock()
        pyanaconda.upgrade.upgradeSwapSuggestion(anaconda)
        self.assertFalse(pyanaconda.upgrade.iutil.swapAmount.called)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('addswap', 1), {}))
    
    def upgrade_swap_suggestion_2_test(self):
        """upgradeSwapSuggestion - 128MB RAM and 256MB SWAP"""
        import pyanaconda.upgrade
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.memInstalled.return_value = 131072
        pyanaconda.upgrade.iutil.swapAmount.return_value = 262144
        anaconda = mock.Mock()
        pyanaconda.upgrade.upgradeSwapSuggestion(anaconda)
        self.assertTrue(pyanaconda.upgrade.iutil.swapAmount.called)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('addswap', 1), {}))
    
    def upgrade_swap_suggestion_3_test(self):
        """upgradeSwapSuggestion - 192MB RAM and 320MB SWAP"""
        import pyanaconda.upgrade
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.memInstalled.return_value = 196608
        pyanaconda.upgrade.iutil.swapAmount.return_value = 327680
        anaconda = mock.Mock()
        pyanaconda.upgrade.upgradeSwapSuggestion(anaconda)
        self.assertTrue(pyanaconda.upgrade.iutil.swapAmount.called)
        self.assertEqual(anaconda.dispatch.skipStep.call_args,
            (('addswap', 1), {}))
    
    def upgrade_swap_suggestion_4_test(self):
        """upgradeSwapSuggestion - 128MB RAM and 128MB SWAP"""
        import pyanaconda.upgrade
        DEV_SIZE = 256
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.memInstalled.return_value = 131072
        pyanaconda.upgrade.iutil.swapAmount.return_value = 131072
        pyanaconda.upgrade.isys = mock.Mock()
        pyanaconda.upgrade.isys.pathSpaceAvailable.return_value = DEV_SIZE
        DEVICE = mock.Mock()
        DEVICE.format.mountable = True
        DEVICE.format.linuxNative = True
        DEVICE.format.mountpoint = '/mnt'
        anaconda = mock.Mock()
        anaconda.rootPath = ''
        anaconda.storage.fsset.devices = [DEVICE]
        pyanaconda.upgrade.upgradeSwapSuggestion(anaconda)
        self.assertTrue(pyanaconda.upgrade.iutil.swapAmount.called)
        self.assertEqual(anaconda.upgradeSwapInfo,
            ([(DEVICE, DEV_SIZE)], 128, DEVICE))
        
    def upgrade_mount_filesystems_1_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.mountExistingSystem = mock.Mock()
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.islink.return_value = True
        pyanaconda.upgrade.os.readlink.return_value = 'a'
        pyanaconda.upgrade.os.path.exists.return_value = False
        
        anaconda = mock.Mock()
        anaconda.upgradeRoot = ['']
        anaconda.rootPath = ''
        pyanaconda.upgrade.upgradeMountFilesystems(anaconda)
        self.assertTrue(anaconda.storage.turnOnSwap.called)
        self.assertTrue(anaconda.storage.mkDevRoot.called)
    
    def upgrade_mount_filesystems_2_test(self):
        # This test include parts:
        # moving /etc/rpm/platform out of the way
        # disabling selinux
        import pyanaconda.upgrade
        pyanaconda.upgrade.mountExistingSystem = mock.Mock()
        pyanaconda.upgrade.os = mock.Mock()
        pyanaconda.upgrade.os.islink.return_value = True
        pyanaconda.upgrade.os.readlink.return_value = 'a'
        pyanaconda.upgrade.os.path.exists.return_value = True
        pyanaconda.upgrade.shutil = mock.Mock()
        pyanaconda.upgrade.selinux = mock.Mock()
        pyanaconda.upgrade.flags = mock.Mock()
        
        anaconda = mock.Mock()
        anaconda.upgradeRoot = ['']
        anaconda.rootPath = ''
        pyanaconda.upgrade.upgradeMountFilesystems(anaconda)
        self.assertTrue(anaconda.storage.turnOnSwap.called)
        self.assertTrue(anaconda.storage.mkDevRoot.called)
        self.assertEqual(pyanaconda.upgrade.shutil.move.call_args,
            (("/etc/rpm/platform", "/etc/rpm/platform.rpmsave"), {}))
        self.assertTrue(pyanaconda.upgrade.selinux.getfilecon.called)
    
    def set_steps_test(self):
        import pyanaconda.upgrade
        pyanaconda.upgrade.iutil = mock.Mock()
        pyanaconda.upgrade.iutil.isX86.return_value = False
        
        anaconda = mock.Mock()
        pyanaconda.upgrade.setSteps(anaconda)
        self.assertEqual(anaconda.dispatch.skipStep.call_args_list,
            [(('bootloader',), {}), (('upgbootloader',), {})])
    
