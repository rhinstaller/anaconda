

from tests.rpm_tests import RPMTestCase


class InstallRPMTestCase(RPMTestCase):

    def test_install(self):
        self.init_mock()

        mock_command = ["--install"]
        mock_command.extend(self.rpm_paths)
        self.run_mock(mock_command)
