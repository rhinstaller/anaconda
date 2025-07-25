#
# Kickstart handler for runtime settings.
#
# Copyright (C) 2023 Red Hat, Inc.
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
from pykickstart.sections import (
    OnErrorScriptSection,
    PostScriptSection,
    PreInstallScriptSection,
    TracebackScriptSection,
)

from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.core.kickstart import commands as COMMANDS
from pyanaconda.kickstart import AnacondaKSScript


class RuntimeKickstartSpecification(KickstartSpecification):
    """Kickstart specification of the runtime module."""

    commands = {
        "driverdisk": COMMANDS.DriverDisk,
        "mediacheck": COMMANDS.MediaCheck,
        "sshpw": COMMANDS.SshPw,
        "updates": COMMANDS.Updates,
        "logging": COMMANDS.Logging,
        "rescue": COMMANDS.Rescue,
        "eula": COMMANDS.Eula,
        "graphical": COMMANDS.DisplayMode,
        "text": COMMANDS.DisplayMode,
        "cmdline": COMMANDS.DisplayMode,
        "vnc": COMMANDS.Vnc,
        "rdp": COMMANDS.RDP,
        "reboot": COMMANDS.Reboot,
        "poweroff": COMMANDS.Reboot,
        "shutdown": COMMANDS.Reboot,
        "halt": COMMANDS.Reboot
    }

    commands_data = {
        "DriverDiskData": COMMANDS.DriverDiskData,
        "SshPwData": COMMANDS.SshPwData,
    }

    sections = {
        "pre-install": lambda handler: PreInstallScriptSection(handler, dataObj=AnacondaKSScript),
        "post": lambda handler: PostScriptSection(handler, dataObj=AnacondaKSScript),
        "onerror": lambda handler: OnErrorScriptSection(handler, dataObj=AnacondaKSScript),
        "traceback": lambda handler: TracebackScriptSection(handler, dataObj=AnacondaKSScript),
    }
