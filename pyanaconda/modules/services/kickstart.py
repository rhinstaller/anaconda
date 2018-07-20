#
# Kickstart handler for the services.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pykickstart.commands.firstboot import FC3_Firstboot
from pykickstart.commands.services import FC6_Services
from pykickstart.commands.skipx import FC3_SkipX
from pykickstart.commands.xconfig import F14_XConfig
from pykickstart.version import RHEL8
from pyanaconda.core.kickstart import KickstartSpecification


class ServicesKickstartSpecification(KickstartSpecification):

    version = RHEL8
    commands = {
        "firstboot": FC3_Firstboot,
        "services": FC6_Services,
        "skipx": FC3_SkipX,
        "xconfig": F14_XConfig,
    }
