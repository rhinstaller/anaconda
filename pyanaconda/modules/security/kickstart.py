#
# Kickstart handler for date and time settings.
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
from pykickstart.version import F28
from pykickstart.commands.realm import F19_Realm
from pykickstart.commands.authconfig import F28_Authconfig
from pykickstart.commands.authselect import F28_Authselect
from pykickstart.commands.selinux import FC3_SELinux
from pyanaconda.core.kickstart import KickstartSpecification


class SecurityKickstartSpecification(KickstartSpecification):

    version = F28

    commands = {
        "auth": F28_Authconfig,
        "authconfig": F28_Authconfig,
        "authselect": F28_Authselect,
        "selinux": FC3_SELinux,
        "realm": F19_Realm
    }
