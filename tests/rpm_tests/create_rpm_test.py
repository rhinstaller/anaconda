import os

from tests.rpm_tests import RPMTestCase


class InstallRPMTestCase(RPMTestCase):

    def test_install(self):
        self.init_mock()

        mock_command = ["--install"]
        mock_command.extend(self.rpm_paths)
        self.run_mock(mock_command)


class InstalledFilesTestCase(RPMTestCase):

    ANACONDA_BUS_CONF = "anaconda-bus.conf"
    ANACONDA_GENERATOR = "anaconda-generator"

    def test_pyanaconda_installed_files(self):
        rpms = self._apply_filters([RPMFilters.debug_exclude,
                                    RPMFilters.anaconda_widgets_exclude],
                                   self.rpm_paths)
        rpm_files = self._get_rpms_content(rpms)

        rpm_files = filter(FileFilters.site_packages_only, rpm_files)
        rpm_files = map(ModifyingFilters.remove_site_packages_prefix, rpm_files)

        rpm_files = filter(FileFilters.pycache_exclude, rpm_files)
        rpm_files = filter(FileFilters.pyc_exclude, rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.pyanaconda_only,
                FileFilters.pycache_exclude,
                FileFilters.pyc_exclude,
                FileFilters.no_extension_exlude,
                FileFilters.makefiles_exclude,
                FileFilters.isys_exclude,
                FileFilters.glade_files_exclude,
                FileFilters.text_files_exclude
            ], self._get_source_files()
        )

        src_files = map(ModifyingFilters.rename_dot_in_files, src_files)

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_conf_installed_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_dbus_confs_only, rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_dbus_only,
                FileFilters.confs_only,
                lambda f: FileFilters.specific_file_exclude(self.ANACONDA_BUS_CONF, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_confs_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_main_conf_file(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(lambda f: FileFilters.specific_file_only(self.ANACONDA_BUS_CONF, f),
                           rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_dbus_only,
                FileFilters.confs_only,
                lambda f: FileFilters.specific_file_only(self.ANACONDA_BUS_CONF, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_dbus_service_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_dbus_services_only, rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._get_source_files()
        src_files = filter(FileFilters.src_dbus_only, src_files)
        src_files = filter(FileFilters.services_only, src_files)

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_dbus_prefix,
                ModifyingFilters.apply_services_prefix,
                ModifyingFilters.apply_dbus_prefix,
                ModifyingFilters.apply_share_anaconda_prefix
            ], src_files
        )

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_anaconda_service_files(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_systemd_only, rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_systemd_only,
                FileFilters.makefiles_exclude,
                lambda f: FileFilters.specific_file_exclude(self.ANACONDA_GENERATOR, f)
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_systemd_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/usr/lib/systemd/system", x)
            ], src_files
        )

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def test_anaconda_service_generator_file(self):
        rpm_files = self._get_core_rpm_content()

        rpm_files = filter(FileFilters.rpm_systemd_only, rpm_files)

        rpm_files = self._check_and_return_as_list(rpm_files)

        src_files = self._apply_filters(
            [
                FileFilters.src_systemd_only,
                FileFilters.makefiles_exclude,
                lambda f: FileFilters.specific_file_only(self.ANACONDA_GENERATOR, f),
            ], self._get_source_files()
        )

        src_files = self._apply_maps(
            [
                ModifyingFilters.remove_data_systemd_prefix,
                lambda x: ModifyingFilters.apply_rpm_prefix("/usr/lib/systemd/system-generators",
                                                            x),
            ], src_files
        )

        src_files = self._check_and_return_as_list(src_files)

        self._check_files_in_rpm(src_files, rpm_files)

    def _check_files_in_rpm(self, src_files, rpm_files):
        for f in src_files:
            self.assertIn(f, rpm_files, "File '{}' is not packaged in rpm".format(f))

    def _check_and_return_as_list(self, files_list):
        li = list(files_list)
        self.assertNotEqual(len(li), 0)

        return li

    def _get_source_files(self):
        ret = set()
        for root, _, files in os.walk(self.anaconda_root_path):
            files_with_path = self._join_relative_path_for_files(root, files)
            ret.update(files_with_path)

        return ret

    def _join_relative_path_for_files(self, root, files):
        out_files = set()
        new_root = os.path.relpath(root, self.anaconda_root_path)

        for f in files:
            new_path = os.path.join(new_root, f)
            out_files.add(new_path)

        return out_files

    def _get_core_rpm_content(self):
        rpms = filter(RPMFilters.debug_exclude, self.rpm_paths)
        rpms = filter(RPMFilters.anaconda_core_only, rpms)
        return self._get_rpms_content(rpms)

    def _get_rpms_content(self, rpms):
        content = set()

        for rpm in rpms:
            content.update(self._get_rpm_content(rpm))

        return content

    def _get_rpm_content(self, rpm):
        command = ["rpm", "-q", "-p", "-l", rpm]
        rpm_content = self.check_subprocess(command)

        return rpm_content.stdout.decode("utf-8").split('\n')

    @staticmethod
    def _apply_filters(filters, in_iter):
        for f in filters:
            in_iter = filter(f, in_iter)

        return in_iter

    @staticmethod
    def _apply_maps(maps, in_iter):
        for m in maps:
            in_iter = map(m, in_iter)

        return in_iter


class FileFilters(object):

    @staticmethod
    def makefiles_exclude(file):
        return "Makefile" not in file

    @staticmethod
    def isys_exclude(file):
        return "/isys/" not in file

    @staticmethod
    def pycache_exclude(file):
        return "__pycache__" not in file

    @staticmethod
    def pyc_exclude(file):
        return not file.endswith('.pyc')

    @staticmethod
    def pyanaconda_only(file):
        return "pyanaconda/" in file

    @staticmethod
    def site_packages_only(file):
        return "site-packages" in file

    @staticmethod
    def glade_files_exclude(file):
        return not file.endswith(".glade")

    @staticmethod
    def no_extension_exlude(file):
        return "." in file

    @staticmethod
    def text_files_exclude(file):
        return not file.endswith(".rst")

    @staticmethod
    def rpm_dbus_confs_only(file):
        return "/dbus" in file and file.endswith(".conf")

    @staticmethod
    def rpm_dbus_services_only(file):
        return "/dbus" in file and file.endswith(".service")

    @staticmethod
    def src_dbus_only(file):
        return "data/dbus" in file

    @staticmethod
    def confs_only(file):
        return file.endswith(".conf")

    @staticmethod
    def services_only(file):
        return file.endswith(".service")

    @staticmethod
    def rpm_systemd_only(file):
        return "/systemd/system" in file

    @staticmethod
    def src_systemd_only(file):
        return "systemd/" in file

    @staticmethod
    def specific_file_only(name, file):
        return file.endswith(name)

    @staticmethod
    def specific_file_exclude(name, file):
        return not FileFilters.specific_file_only(name, file)


class RPMFilters(object):

    @staticmethod
    def debug_exclude(rpm):
        return "debug" not in rpm

    @staticmethod
    def anaconda_widgets_exclude(rpm):
        return "anaconda-widgets" not in rpm

    @staticmethod
    def anaconda_core_only(rpm):
        # includes debug package
        return "anaconda-core" in rpm


class ModifyingFilters(object):

    @staticmethod
    def rename_dot_in_files(file):
        if file.endswith(".in"):
            return file[:-3]

        return file

    @staticmethod
    def remove_site_packages_prefix(file):
        if FileFilters.site_packages_only(file):
            _, suffix = file.split("site-packages/")
            return suffix

        return file

    @staticmethod
    def remove_data_dbus_prefix(file):
        if file.startswith("data/dbus/"):
            return file[10:]

        return file

    @staticmethod
    def remove_data_systemd_prefix(file):
        if file.startswith("data/systemd/"):
            return file[13:]

        return file

    @staticmethod
    def apply_rpm_prefix(prefix, file):
        return os.path.join(prefix, file)

    @staticmethod
    def apply_share_anaconda_prefix(file):
        return ModifyingFilters.apply_rpm_prefix("/usr/share/anaconda/", file)

    @staticmethod
    def apply_confs_prefix(file):
        return ModifyingFilters.apply_rpm_prefix("confs/", file)

    @staticmethod
    def apply_services_prefix(file):
        return ModifyingFilters.apply_rpm_prefix("services/", file)

    @staticmethod
    def apply_dbus_prefix(file):
        return ModifyingFilters.apply_rpm_prefix("dbus/", file)
