#
# Copyright (C) 2026  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from unittest.mock import patch

import pytest
from pykickstart.constants import KS_SCRIPT_PRE

from pyanaconda.kickstart import AnacondaKSScript


class AnacondaKSScriptTestCase:

    @patch("pyanaconda.kickstart.util.ipmi_abort")
    @patch("pyanaconda.kickstart.errorHandler")
    @patch("pyanaconda.kickstart.run_script")
    def test_fatal_pre_script_error_exits_nonzero(self, run_script, error_handler,
                                                   ipmi_abort, tmp_path):
        """A fatal (errorOnFail) %pre script failure must exit with a non-zero
        status -- exiting 0 here would report a failed installation as a
        success.
        """
        log_file = tmp_path / "ks-script.log"
        log_file.write_text("the script blew up\n")
        run_script.return_value = (1, str(log_file))

        script = AnacondaKSScript(
            "exit 1\n",
            type=KS_SCRIPT_PRE,
            errorOnFail=True,
            lineno=1,
        )

        with pytest.raises(SystemExit) as exc_info:
            script.run("/")

        assert exc_info.value.code == 1
        error_handler.cb.assert_called_once()
        ipmi_abort.assert_called_once()
