
import glob
import os
import subprocess
from unittest import TestCase

RPM_BUILD_DIR_ENV = "RPM_PATH"
ROOT_DIR_ENV = "ROOT_ANACONDA_PATH"


class RPMTestCase(TestCase):

    def check_subprocess(self, cmd, cwd=None):
        """Call external command and verify return result.

        :param cmd: list of parameters to specify command to run
        :type cmd: list
        :param cwd: path to directory where to run this command. If nothing specified it will
                    run command in actual directory.
        :type cwd: str
        """
        process_result = self.call_subprocess(cmd, cwd)

        assert process_result.returncode == 0, """
        Bad return code when running:
        {}""".format(cmd)

        return process_result

    def call_subprocess(self, cmd, cwd=None):
        """Call external command and return result."""
        print("Running command \"{}\"".format(" ".join(cmd)))
        # pylint: disable=subprocess-run-check
        return subprocess.run(cmd, stdout=subprocess.PIPE, cwd=cwd)

    @property
    def anaconda_root_path(self):
        """Root directory of tested anaconda from Makefile"""
        return os.environ[ROOT_DIR_ENV]

    @property
    def rpm_paths(self):
        """Paths pointing to RPM files

        This expects files in a place where `make rpms` or `make mock-rpms` will place them.
        """
        rpm_path = os.environ[RPM_BUILD_DIR_ENV]
        return glob.glob(rpm_path + os.path.sep + "*[0-9].rpm")
