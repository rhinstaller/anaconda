
import os
import subprocess
import glob

from unittest import TestCase


MOCK_NAME_ENV = "MOCKCHROOT"
MOCK_EXTRA_ARGS_ENV = "MOCK_EXTRA_ARGS"
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

        self.assertEqual(process_result.returncode, 0, msg="""
        Bad return code when running:
        {}""".format(cmd))

        return process_result

    def call_subprocess(self, cmd, cwd=None):
        """Call external command and return result."""
        print("Running command \"{}\"".format(" ".join(cmd)))
        return subprocess.run(cmd, stdout=subprocess.PIPE, cwd=cwd)

    @property
    def mock_name(self):
        """Name of the mock from Makefile"""
        return os.environ[MOCK_NAME_ENV]

    @property
    def mock_extra_args(self):
        """Extra arguments for mock from Makefile"""
        return os.environ[MOCK_EXTRA_ARGS_ENV]

    @property
    def anaconda_root_path(self):
        """Root directory of tested anaconda from Makefile"""
        return os.environ[ROOT_DIR_ENV]

    @property
    def rpm_paths(self):
        """Paths pointing to RPM files

        This expects files in a place where make rc-release will place them.
        """
        rpm_path = os.environ[RPM_BUILD_DIR_ENV]
        return glob.glob(rpm_path + os.path.sep + "*[0-9].rpm")

    def run_mock(self, cmd):
        """Run commands in mock

        Mock name and extra arguments are passed here from Makefile.
        """
        mock_command = self._create_mock_command()
        mock_command.extend(cmd)
        self.check_subprocess(mock_command)

    def _create_mock_command(self):
        output_cmd = ["mock", "-r", self.mock_name]

        if self.mock_extra_args:
            output_cmd.append(self.mock_extra_args)

        return output_cmd

    def init_mock(self):
        """Init mock before using it for tests."""
        self.run_mock(["--init"])
