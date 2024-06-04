# configure.ac for anaconda
#
# Copyright (C) 2021  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

m4_define(python_required_version, 3.4)

AC_PREREQ([2.63])
AC_INIT([anaconda], [41.19], [anaconda-devel@lists.fedoraproject.org])

# make it possible to set build info at build time
# (patch only builds, modular builds, mass-rebuilds, etc.)
AC_ARG_VAR(ANACONDA_RELEASE, [])

# default release to 1 if not set by option
AS_IF([test $ANACONDA_RELEASE],
      [AC_SUBST(PACKAGE_RELEASE, $ANACONDA_RELEASE)],
      [AC_SUBST(PACKAGE_RELEASE, 1)])

# Disable building static libraries.
# This needs to be set before initializing automake
AC_DISABLE_STATIC

# UIDs in an openshift pod are bigger than what tar-ustar can handle
# tar-pax can deal with it though
# https://github.com/hpcng/singularity/issues/670#issuecomment-346104684
AM_INIT_AUTOMAKE([foreign no-dist-gzip dist-bzip2 tar-pax])

AC_CONFIG_HEADERS([config.h])
AC_CONFIG_MACRO_DIR([m4])

AC_DEFINE_UNQUOTED([BUILD_DATE], ["`date +%m%d%Y`"], [Date of anaconda build])
AM_SILENT_RULES([yes]) # make --enable-silent-rules the default.

AC_USE_SYSTEM_EXTENSIONS
AC_SYS_LARGEFILE

# Checks for programs.
AC_PROG_CC
AC_PROG_LN_S
AC_PROG_LIBTOOL
AC_PROG_MKDIR_P

# Check for the gettext programs
AC_PATH_PROG([XGETTEXT], [xgettext])
AC_PATH_PROG([MSGFMT], [msgfmt])
AC_PATH_PROG([MSGMERGE], [msgmerge])
AC_PATH_PROG([MSGCAT], [msgcat])
AS_IF([test -z "$XGETTEXT" -o -z "$MSGFMT" -o -z "$MSGMERGE" -o -z "$MSGCAT"],
      [ANACONDA_SOFT_FAILURE([gettext not found])])

# Checks for header files.
AC_CHECK_HEADERS([fcntl.h stdlib.h string.h sys/time.h unistd.h],
                 [],
                 [ANACONDA_SOFT_FAILURE([Header file $ac_header not found.])],
                 [])

# Checks for typedefs, structures, and compiler characteristics.
AC_TYPE_PID_T
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_TYPE_UINT32_T
AC_TYPE_INT64_T

# Checks for library functions.
AC_FUNC_FORK
AC_CHECK_FUNCS([getcwd mkdir strchr strdup],
               [],
               [ANACONDA_SOFT_FAILURE([Function $ac_func not found.])])

AM_PATH_PYTHON(python_required_version)

# Check for the python extension paths
PKG_CHECK_MODULES([PYTHON3], [python3], [], ANACONDA_SOFT_FAILURE([Unable to find python library]))

# Check for libraries we need that provide pkg-config scripts
ANACONDA_PKG_CHECK_MODULES([RPM], [rpm >= 4.10.0])
ANACONDA_PKG_CHECK_MODULES([LIBARCHIVE], [libarchive >= 3.0.4])

# Add remaining compiler flags we want to use
CFLAGS="$CFLAGS -Wall -Werror -fanalyzer"


# Perform arch related tests
AC_CANONICAL_BUILD
s_arch="`echo $build_cpu | sed -e s/i.86/i386/ -e s/powerpc.*/ppc/`"

AC_CONFIG_SUBDIRS([widgets])

AC_CONFIG_FILES([Makefile
                 anaconda.spec
                 data/Makefile
                 data/command-stubs/Makefile
                 docs/Makefile
                 dracut/Makefile
                 data/conf.d/Makefile
                 data/profile.d/Makefile
                 data/liveinst/Makefile
                 data/liveinst/gnome/Makefile
                 data/systemd/Makefile
                 data/dbus/Makefile
                 data/gtk-4.0/Makefile
                 data/window-manager/Makefile
                 data/window-manager/config/Makefile
                 po/Makefile
                 scripts/Makefile
                 pyanaconda/Makefile
                 pyanaconda/version.py
                 pyanaconda/core/Makefile
                 pyanaconda/core/kickstart/Makefile
                 pyanaconda/core/configuration/Makefile
                 pyanaconda/core/startup/Makefile
                 pyanaconda/payload/Makefile
                 pyanaconda/payload/dnf/Makefile
                 pyanaconda/payload/live/Makefile
                 pyanaconda/ui/Makefile
                 pyanaconda/ui/categories/Makefile
                 pyanaconda/ui/lib/Makefile
                 pyanaconda/ui/gui/hubs/Makefile
                 pyanaconda/ui/gui/spokes/Makefile
                 pyanaconda/ui/gui/spokes/advstorage/Makefile
                 pyanaconda/ui/gui/spokes/lib/Makefile
                 pyanaconda/ui/gui/Makefile
                 pyanaconda/ui/tui/hubs/Makefile
                 pyanaconda/ui/tui/spokes/Makefile
                 pyanaconda/ui/tui/Makefile
                 pyanaconda/ui/webui/Makefile
                 pyanaconda/modules/Makefile
                 pyanaconda/modules/common/Makefile
                 pyanaconda/modules/common/base/Makefile
                 pyanaconda/modules/common/task/Makefile
                 pyanaconda/modules/common/errors/Makefile
                 pyanaconda/modules/common/constants/Makefile
                 pyanaconda/modules/common/structures/Makefile
                 pyanaconda/modules/boss/Makefile
                 pyanaconda/modules/boss/install_manager/Makefile
                 pyanaconda/modules/boss/kickstart_manager/Makefile
                 pyanaconda/modules/boss/module_manager/Makefile
                 pyanaconda/modules/security/Makefile
                 pyanaconda/modules/timezone/Makefile
                 pyanaconda/modules/network/Makefile
                 pyanaconda/modules/network/firewall/Makefile
                 pyanaconda/modules/localization/Makefile
                 pyanaconda/modules/users/Makefile
                 pyanaconda/modules/payloads/Makefile
                 pyanaconda/modules/payloads/payload/Makefile
                 pyanaconda/modules/payloads/payload/dnf/Makefile
                 pyanaconda/modules/payloads/payload/live_os/Makefile
                 pyanaconda/modules/payloads/payload/live_image/Makefile
                 pyanaconda/modules/payloads/payload/rpm_ostree/Makefile
                 pyanaconda/modules/payloads/base/Makefile
                 pyanaconda/modules/payloads/source/Makefile
                 pyanaconda/modules/payloads/source/cdn/Makefile
                 pyanaconda/modules/payloads/source/cdrom/Makefile
                 pyanaconda/modules/payloads/source/closest_mirror/Makefile
                 pyanaconda/modules/payloads/source/flatpak/Makefile
                 pyanaconda/modules/payloads/source/harddrive/Makefile
                 pyanaconda/modules/payloads/source/hmc/Makefile
                 pyanaconda/modules/payloads/source/live_image/Makefile
                 pyanaconda/modules/payloads/source/live_os/Makefile
                 pyanaconda/modules/payloads/source/live_tar/Makefile
                 pyanaconda/modules/payloads/source/nfs/Makefile
                 pyanaconda/modules/payloads/source/repo_files/Makefile
                 pyanaconda/modules/payloads/source/repo_path/Makefile
                 pyanaconda/modules/payloads/source/rpm_ostree/Makefile
                 pyanaconda/modules/payloads/source/rpm_ostree_container/Makefile
                 pyanaconda/modules/payloads/source/url/Makefile
                 pyanaconda/modules/runtime/Makefile
                 pyanaconda/modules/runtime/dracut_commands/Makefile
                 pyanaconda/modules/runtime/user_interface/Makefile
                 pyanaconda/modules/storage/Makefile
                 pyanaconda/modules/storage/bootloader/Makefile
                 pyanaconda/modules/storage/checker/Makefile
                 pyanaconda/modules/storage/dasd/Makefile
                 pyanaconda/modules/storage/devicetree/Makefile
                 pyanaconda/modules/storage/disk_initialization/Makefile
                 pyanaconda/modules/storage/disk_selection/Makefile
                 pyanaconda/modules/storage/fcoe/Makefile
                 pyanaconda/modules/storage/iscsi/Makefile
                 pyanaconda/modules/storage/nvme/Makefile
                 pyanaconda/modules/storage/partitioning/Makefile
                 pyanaconda/modules/storage/partitioning/automatic/Makefile
                 pyanaconda/modules/storage/partitioning/blivet/Makefile
                 pyanaconda/modules/storage/partitioning/custom/Makefile
                 pyanaconda/modules/storage/partitioning/interactive/Makefile
                 pyanaconda/modules/storage/partitioning/manual/Makefile
                 pyanaconda/modules/storage/snapshot/Makefile
                 pyanaconda/modules/storage/zfcp/Makefile
                 pyanaconda/modules/services/Makefile
                 pyanaconda/modules/subscription/Makefile
                 data/pixmaps/Makefile
                 tests/Makefile
                 utils/Makefile
                 utils/dd/Makefile])

AC_OUTPUT

# Gently advise the user about the build failures they are about to encounter
ANACONDA_FAILURES
