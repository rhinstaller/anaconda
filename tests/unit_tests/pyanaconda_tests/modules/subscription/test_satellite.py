#
# Copyright (C) 2021  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>

import unittest
from unittest.mock import patch

from requests import RequestException

from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT, USER_AGENT
from pyanaconda.modules.subscription.satellite import (
    PROVISIONING_SCRIPT_SUB_PATH,
    download_satellite_provisioning_script,
    run_satellite_provisioning_script,
)


class SatelliteLibraryTestCase(unittest.TestCase):
    """Test the Satellite provisioning code."""
    # this code at the moment basically just downloads the Satellite provisioning
    # script from the Satellite instance with one method, then runs it with the other

    @patch("pyanaconda.core.util.requests_session")
    def test_script_download_no_prefix(self, get_session):
        """Test the download_satellite_provisioning_script function - no prefix."""
        # mock the Python Request session
        session = get_session.return_value.__enter__.return_value
        result = session.get.return_value
        result.ok = True
        result.text = "foo script text"
        # run the download method
        script_text = download_satellite_provisioning_script("satellite.example.com")
        # check script text was returned
        assert "foo script text" == script_text
        # check the session was called correctly
        session.get.assert_called_once_with(
            'http://satellite.example.com' + PROVISIONING_SCRIPT_SUB_PATH,
            headers={"user-agent": USER_AGENT},
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )
        result.close.assert_called_once()

    @patch("pyanaconda.core.util.requests_session")
    def test_script_download_http(self, get_session):
        """Test the download_satellite_provisioning_script function - http prefix."""
        # mock the Python Request session
        session = get_session.return_value.__enter__.return_value
        result = session.get.return_value
        result.ok = True
        result.text = "foo script text"
        # run the download method
        script_text = download_satellite_provisioning_script("http://satellite.example.com")
        # check script text was returned
        assert "foo script text" == script_text
        # check the session was called correctly
        session.get.assert_called_once_with(
            'http://satellite.example.com' + PROVISIONING_SCRIPT_SUB_PATH,
            headers={"user-agent": USER_AGENT},
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )
        result.close.assert_called_once()

    @patch("pyanaconda.core.util.requests_session")
    def test_script_download_https(self, get_session):
        """Test the download_satellite_provisioning_script function - https prefix."""
        # mock the Python Request session
        session = get_session.return_value.__enter__.return_value
        result = session.get.return_value
        result.ok = True
        result.text = "foo script text"
        # run the download method
        script_text = download_satellite_provisioning_script("https://satellite.example.com")
        # check script text was returned
        assert "foo script text" == script_text
        # check the session was called correctly
        session.get.assert_called_once_with(
            'https://satellite.example.com' + PROVISIONING_SCRIPT_SUB_PATH,
            headers={"user-agent": USER_AGENT},
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )
        result.close.assert_called_once()

    @patch("pyanaconda.core.util.requests_session")
    def test_script_download_not_ok(self, get_session):
        """Test the download_satellite_provisioning_script function - result not ok."""
        # mock the Python Request session
        session = get_session.return_value.__enter__.return_value
        result = session.get.return_value
        result.ok = False
        result.text = "foo script text"
        # run the download method
        script_text = download_satellite_provisioning_script("satellite.example.com")
        # if result has ok == False, None should be returned instead of script text
        assert script_text is None
        # check the session was called correctly
        session.get.assert_called_once_with(
            'http://satellite.example.com' + PROVISIONING_SCRIPT_SUB_PATH,
            headers={"user-agent": USER_AGENT},
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )
        result.close.assert_called_once()

    @patch("pyanaconda.core.util.requests_session")
    def test_script_download_exception(self, get_session):
        """Test the download_satellite_provisioning_script function - exception."""
        # mock the Python Request session
        session = get_session.return_value.__enter__.return_value
        session.get.side_effect = RequestException()
        # run the download method
        script_text = download_satellite_provisioning_script("satellite.example.com")
        # if requests throw an exception, None should be returned instead of script text
        assert script_text is None
        # check the session was called correctly
        session.get.assert_called_once_with(
            'http://satellite.example.com' + PROVISIONING_SCRIPT_SUB_PATH,
            headers={"user-agent": USER_AGENT},
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )

    def test_run_satellite_provisioning_script_no_script(self):
        """Test the run_satellite_provisioning_script function - no script."""
        # if no script is provided, False should be returned
        assert run_satellite_provisioning_script(provisioning_script=None) is False

    @patch('pyanaconda.modules.subscription.satellite.util.mkdirChain')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pyanaconda.core.util.execWithRedirect')
    def test_run_satellite_provisioning_script_success(self, exec_with_redirect,
                                                       named_tempfile, mkdirChain):
        """Test the run_satellite_provisioning_script function - success."""
        # simulate successful script run
        exec_with_redirect.return_value = 0
        # get the actual file object
        file_object = named_tempfile.return_value.__enter__.return_value
        # fake a random name
        file_object.name = "totally_random_name"
        file_object = named_tempfile.return_value.__enter__.return_value
        # successful run should return True
        assert run_satellite_provisioning_script(provisioning_script="foo script") is True
        # check temp directory was created successfully
        mkdirChain.assert_called_once_with("/tmp")
        # check the tempfile was created correctly
        named_tempfile.assert_called_once_with(mode='w+t', dir='/tmp', prefix='satellite-')
        # check the temp file was written out
        file_object.write.assert_called_once_with("foo script")
        # test the script was executed properly
        exec_with_redirect.assert_called_once_with('bash',
                                                   argv=['/tmp/totally_random_name'],
                                                   root='/')

    @patch("pyanaconda.modules.subscription.satellite.conf")
    @patch('pyanaconda.modules.subscription.satellite.util.mkdirChain')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pyanaconda.core.util.execWithRedirect')
    def test_run_satellite_provisioning_script_success_chroot(self,
                                                              exec_with_redirect,
                                                              named_tempfile,
                                                              mkdirChain,
                                                              patched_conf):
        """Test the run_satellite_provisioning_script function - success in chroot."""
        # mock sysroot
        patched_conf.target.system_root = "/foo/sysroot"
        # simulate successful script run
        exec_with_redirect.return_value = 0
        # get the actual file object
        file_object = named_tempfile.return_value.__enter__.return_value
        # fake a random name
        file_object.name = "totally_random_name"
        file_object = named_tempfile.return_value.__enter__.return_value
        # successful run should return True
        assert run_satellite_provisioning_script(provisioning_script="foo script",
                                                 run_on_target_system=True) is True
        # check temp directory was created successfully
        mkdirChain.assert_called_once_with("/foo/sysroot/tmp")
        # check the tempfile was created correctly
        named_tempfile.assert_called_once_with(mode='w+t',
                                               dir='/foo/sysroot/tmp',
                                               prefix='satellite-')
        # check the temp file was written out
        file_object.write.assert_called_once_with("foo script")
        # test the script was executed properly
        exec_with_redirect.assert_called_once_with('bash',
                                                   argv=['/tmp/totally_random_name'],
                                                   root='/foo/sysroot')

    @patch('pyanaconda.modules.subscription.satellite.util.mkdirChain')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pyanaconda.core.util.execWithRedirect')
    def test_run_satellite_provisioning_script_failure(self, exec_with_redirect,
                                                       named_tempfile, mkdirChain):
        """Test the run_satellite_provisioning_script function - failure."""
        # simulate unsuccessful script run
        exec_with_redirect.return_value = 1
        # get the actual file object
        file_object = named_tempfile.return_value.__enter__.return_value
        # fake a random name
        file_object.name = "totally_random_name"
        file_object = named_tempfile.return_value.__enter__.return_value
        # failed run should return False
        assert run_satellite_provisioning_script(provisioning_script="foo script") is False
        # check temp directory was created successfully
        mkdirChain.assert_called_once_with("/tmp")
        # check the tempfile was created correctly
        named_tempfile.assert_called_once_with(mode='w+t', dir='/tmp', prefix='satellite-')
        # check the temp file was written out
        file_object.write.assert_called_once_with("foo script")
        # test the script was executed properly
        exec_with_redirect.assert_called_once_with('bash',
                                                   argv=['/tmp/totally_random_name'],
                                                   root='/')
