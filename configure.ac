# configure.ac for anaconda
#
# Copyright (C) 2009  Red Hat, Inc.
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
AC_INIT([anaconda], [25.20.9], [anaconda-devel-list@redhat.com])

# Disable building static libraries.
# This needs to be set before initializing automake
AC_DISABLE_STATIC

AM_INIT_AUTOMAKE([foreign no-dist-gzip dist-bzip2 tar-ustar])

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
AC_CHECK_FUNCS([getcwd memset mkdir strchr strdup],
               [],
               [ANACONDA_SOFT_FAILURE([Function $ac_func not found.])])

AC_CHECK_LIB([audit], [audit_open], [:],
             [ANACONDA_SOFT_FAILURE([libaudit not found])])

AM_PATH_PYTHON(python_required_version)

# Check for the python extension paths
PKG_CHECK_MODULES([PYTHON3], [python3], [
    LIBS_save="$LIBS"
    LIBS="$LIBS $PYTHON3_LIBS"
    AC_MSG_CHECKING([Python libraries])
    AC_TRY_LINK_FUNC([Py_Initialize], 
                     [AC_MSG_RESULT([yes])], 
                     [AC_MSG_RESULT([no])
                      ANACONDA_SOFT_FAILURE([Unable to use python library])])
    LIBS="$LIBS_save"
    ],
    [ANACONDA_SOFT_FAILURE([Unable to find python library])])

# Check for libraries we need that provide pkg-config scripts
ANACONDA_PKG_CHECK_MODULES([RPM], [rpm >= 4.10.0])
ANACONDA_PKG_CHECK_MODULES([LIBARCHIVE], [libarchive >= 3.0.4])

# GCC likes to bomb out on some ridiculous warnings.  Add your favorites
# here.
SHUT_UP_GCC="-Wno-unused-result"

# Add remaining compiler flags we want to use
CFLAGS="$CFLAGS -Wall -Werror $SHUT_UP_GCC"

AC_SUBST(PACKAGE_RELEASE, [1])

# Perform arch related tests
AC_CANONICAL_BUILD
s_arch="`echo $build_cpu | sed -e s/i.86/i386/ -e s/powerpc.*/ppc/`"

AM_CONDITIONAL(IS_LIVEINST_ARCH,
  [test x$s_arch = xppc || test x$s_arch = xppc64 || test x$s_arch = xppc64le || test x$s_arch = xi386 || test x$s_arch = xx86_64])

AC_CONFIG_SUBDIRS([widgets])

AC_CONFIG_FILES([Makefile
                 anaconda.spec
                 data/Makefile
                 data/command-stubs/Makefile
                 docs/Makefile
                 dracut/Makefile
                 pyanaconda/installclasses/Makefile
                 data/liveinst/Makefile
                 data/liveinst/console.apps/Makefile
                 data/liveinst/gnome/Makefile
                 data/liveinst/pam.d/Makefile
                 data/systemd/Makefile
                 data/window-manager/Makefile
                 data/window-manager/config/Makefile
                 data/window-manager/theme/Makefile
                 po/Makefile
                 scripts/Makefile
                 pyanaconda/Makefile
                 pyanaconda/version.py
                 pyanaconda/isys/Makefile
                 pyanaconda/packaging/Makefile
                 pyanaconda/ui/Makefile
                 pyanaconda/ui/categories/Makefile
                 pyanaconda/ui/lib/Makefile
                 pyanaconda/ui/gui/hubs/Makefile
                 pyanaconda/ui/gui/spokes/Makefile
                 pyanaconda/ui/gui/spokes/advstorage/Makefile
                 pyanaconda/ui/gui/spokes/lib/Makefile
                 pyanaconda/ui/gui/Makefile
                 pyanaconda/ui/tui/hubs/Makefile
                 pyanaconda/ui/tui/simpleline/Makefile
                 pyanaconda/ui/tui/spokes/Makefile
                 pyanaconda/ui/tui/Makefile
                 data/post-scripts/Makefile
                 data/pixmaps/Makefile
                 tests/Makefile
                 utils/Makefile
                 utils/dd/Makefile])
AC_OUTPUT

# Gently advise the user about the build failures they are about to encounter
ANACONDA_FAILURES
