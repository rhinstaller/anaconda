#!/usr/bin/python

import mock

class BackendTest(mock.TestCase):

    def setUp(self):
        import pykickstart.commands

        self.setupModules(["_isys", "block", 'parted', 'storage',
                    'pyanaconda.storage.formats', 'logging',
                    'logging.config',
                    'ConfigParser', 'pyanaconda.anaconda_log',
                    'pyanaconda.storage.storage_log',
                    'pyanaconda.yuminstall'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

        import logging
        self.logger = mock.Mock()
        logging.getLogger.return_value = self.logger

        self.DD_EXTRACTED = '/tmp/DD'

        import pyanaconda.backend
        pyanaconda.backend.os = mock.Mock()
        pyanaconda.backend.DD_EXTRACTED = self.DD_EXTRACTED
        pyanaconda.backend.glob = mock.Mock()
        pyanaconda.backend.shutil = mock.Mock()

        self.logger.reset_mock()

    def tearDown(self):
        self.tearDownModules()

    def anaconda_backend_copy_firmware_test(self):
        import pyanaconda.backend
        FILE = 'foo'
        pyanaconda.backend.glob.glob.return_value = [FILE]

        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.copyFirmware()
        self.assertEqual(pyanaconda.backend.shutil.copyfile.call_args[0][0], FILE)

    def anaconda_backend_do_post_install_test(self):
        import pyanaconda.backend
        from pyanaconda.constants import ROOT_PATH
        FILE = 'foo'
        A = 'a'
        B = 'b'
        C = 'c'
        pyanaconda.backend.AnacondaBackend.copyFirmware = mock.Mock()
        pyanaconda.backend.AnacondaBackend.kernelVersionList = mock.Mock(
            return_value=[(A, B, C)])
        pyanaconda.backend.packages = mock.Mock()
        pyanaconda.backend.glob.glob.return_value = [FILE]

        pyanaconda.backend.os.path.exists.return_value=True
        pyanaconda.backend.os.path.basename.return_value=""

        pyanaconda.backend.storage = mock.Mock()
        pyanaconda.backend.sys = mock.Mock()

        anaconda = mock.Mock()
        anaconda.extraModules = True

        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.doPostInstall(anaconda)

        self.assertEqual(pyanaconda.backend.packages.method_calls[0],
            ('recreateInitrd', (A, ROOT_PATH), {}))
        self.assertEqual(pyanaconda.backend.shutil.method_calls[0],
            ('copytree', (FILE, ROOT_PATH + '/root/'), {}))
        self.assertEqual(pyanaconda.backend.shutil.method_calls[1],
            ('copytree', (self.DD_EXTRACTED, ROOT_PATH + '/root/DD'), {}))
        self.assertTrue(pyanaconda.backend.storage.writeEscrowPackets.called)

    def anaconda_backend_do_install_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        self.assertRaises(NotImplementedError, ab.doInstall, anaconda)

    def anaconda_backend_kernel_version_list_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ret = ab.kernelVersionList()
        self.assertEqual([], ret)

    def anaconda_backend_get_minimum_size_mb_test(self):
        import pyanaconda.backend
        PART = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ret = ab.getMinimumSizeMB(PART)
        self.assertEqual(0, ret)

    def anaconda_backend_do_backend_setup_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.doBackendSetup(anaconda)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_group_exists_test(self):
        import pyanaconda.backend
        GROUP = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.groupExists(GROUP)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_select_group_test(self):
        import pyanaconda.backend
        GROUP = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.selectGroup(GROUP)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_deselect_group_test(self):
        import pyanaconda.backend
        GROUP = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.deselectGroup(GROUP)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_package_exists_test(self):
        import pyanaconda.backend
        PKG = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.packageExists(PKG)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_select_package_test(self):
        import pyanaconda.backend
        PKG = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.selectPackage(PKG)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_deselect_package_test(self):
        import pyanaconda.backend
        PKG = mock.Mock()
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.deselectPackage(PKG)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_get_default_groups_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.getDefaultGroups(anaconda)
        self.assertTrue(self.logger.warning.called)

    def anaconda_backend_write_configuration_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        ab = pyanaconda.backend.AnacondaBackend(anaconda)
        ab.writeConfiguration()
        self.assertTrue(self.logger.warning.called)

    def do_backend_setup_1_test(self):
        import pyanaconda.backend
        RET = -1
        pyanaconda.backend.DISPATCH_BACK = RET
        anaconda = mock.Mock()
        anaconda.backend.doBackendSetup.return_value = RET
        ret = pyanaconda.backend.doBackendSetup(anaconda)
        self.assertEqual(RET, ret)

    def do_post_selection_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        pyanaconda.backend.doPostSelection(anaconda)
        self.assertTrue(anaconda.backend.doPostSelection.called)

    def do_pre_install_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        pyanaconda.backend.doPreInstall(anaconda)
        self.assertTrue(anaconda.backend.doPreInstall.called)

    def do_post_install_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        pyanaconda.backend.doPostInstall(anaconda)
        self.assertTrue(anaconda.backend.doPostInstall.called)

    def do_install_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        pyanaconda.backend.doInstall(anaconda)
        self.assertTrue(anaconda.backend.doInstall.called)

    def do_base_package_select_1_test(self):
        import pyanaconda.backend
        pyanaconda.backend.kickstart = mock.Mock()
        anaconda = mock.Mock()
        anaconda.ksdata = True

        pyanaconda.backend.doBasePackageSelect(anaconda)
        self.assertTrue(anaconda.backend.resetPackageSelections.called)

    def do_base_package_select_2_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        anaconda.ksdata = False

        pyanaconda.backend.doBasePackageSelect(anaconda)
        self.assertTrue(anaconda.backend.resetPackageSelections.called)
        self.assertTrue(anaconda.instClass.setPackageSelection.called)
        self.assertTrue(anaconda.instClass.setGroupSelection.called)

    def write_configuration_test(self):
        import pyanaconda.backend
        anaconda = mock.Mock()
        pyanaconda.backend.writeConfiguration(anaconda)
        self.assertTrue(anaconda.write.called)
        self.assertTrue(anaconda.backend.writeConfiguration)
