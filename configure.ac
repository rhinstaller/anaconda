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
#
# Author: David Cantrell <dcantrell@redhat.com>

m4_define(python_required_version, 2.5)

AC_PREREQ([2.63])
AC_INIT([anaconda], [21.48.22.37], [anaconda-devel-list@redhat.com])
AM_INIT_AUTOMAKE([foreign no-dist-gzip dist-bzip2 tar-ustar])

AC_CONFIG_HEADERS([config.h])
AC_CONFIG_MACRO_DIR([m4])

AC_DEFINE_UNQUOTED([BUILD_DATE], ["`date +%m%d%Y`"], [Date of anaconda build])
AM_SILENT_RULES([yes]) # make --enable-silent-rules the default.

# Checks for programs.
AC_PROG_AWK
AC_PROG_GREP
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_MAKE_SET
AC_PROG_LIBTOOL
AC_PROG_MKDIR_P

# Check for the intltool programs
# These checks and subsitutions are adapted IT_PROG_INTLTOOL provided in
# intltool.m4, but without the parts where it breaks gettext.
AC_PATH_PROG([INTLTOOL_EXTRACT], [intltool-extract])
AC_PATH_PROG([INTLTOOL_MERGE], [intltool-merge])
AS_IF([test -z "$INTLTOOL_EXTRACT" -o -z "$INTLTOOL_MERGE"],
      [AC_MSG_ERROR([*** intltool not found])])

# Add the bits for Makefile rules
INTLTOOL_V_MERGE='$(INTLTOOL__v_MERGE_$(V))'
INTLTOOL__v_MERGE_='$(INTLTOOL__v_MERGE_$(AM_DEFAULT_VERBOSITY))'
INTLTOOL__v_MERGE_0='@echo "  ITMRG " $@;'
INTLTOOL_V_MERGE_OPTIONS='$(intltool__v_merge_options_$(V))'
intltool__v_merge_options_='$(intltool__v_merge_options_$(AM_DEFAULT_VERBOSITY))'
intltool__v_merge_options_0='-q'
AC_SUBST(INTLTOOL_V_MERGE)
AC_SUBST(INTLTOOL__v_MERGE_)
AC_SUBST(INTLTOOL__v_MERGE_0)
AC_SUBST(INTLTOOL_V_MERGE_OPTIONS)
AC_SUBST(intltool__v_merge_options_)
AC_SUBST(intltool__v_merge_options_0)

INTLTOOL_DESKTOP_RULE='%.desktop:  %.desktop.in  $(INTLTOOL_MERGE) $(wildcard $(top_srcdir)/po/*.po) ; $(INTLTOOL_V_MERGE)LC_ALL=C $(INTLTOOL_MERGE) $(INTLTOOL_V_MERGE_OPTIONS) -d -u -c $(top_builddir)/po/.intltool-merge-cache $(top_srcdir)/po $< $@'
AC_SUBST(INTLTOOL_DESKTOP_RULE)

AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION([0.18.1])

# Checks for header files.
AC_PATH_X
AC_CHECK_HEADERS([fcntl.h stdlib.h string.h sys/time.h unistd.h],
                 [],
                 [AC_MSG_FAILURE([*** Header file $ac_header not found.])],
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
               [AC_MSG_FAILURE([*** Required function $ac_func not found.])])

AM_PATH_PYTHON(python_required_version)

# Check for the python extension paths
PKG_CHECK_MODULES([PYTHON], [python], [
    LIBS_save="$LIBS"
    LIBS="$LIBS $PYTHON_LIBS"
    AC_MSG_CHECKING([Python libraries])
    AC_TRY_LINK_FUNC([Py_Initialize], 
                     [AC_MSG_RESULT([yes])], 
                     [AC_MSG_RESULT([no])
                      AC_MSG_FAILURE([*** Unable to use python library])])
    LIBS="$LIBS_save"
    ],
    [AC_MSG_FAILURE([*** Unable to find python library])])

# Check for libraries we need that provide pkg-config scripts
PKG_PROG_PKG_CONFIG([0.23])
PKG_CHECK_MODULES([RPM], [rpm >= 4.10.0])
PKG_CHECK_MODULES([LIBARCHIVE], [libarchive >= 3.0.4])

# Set $RPM_OPT_FLAGS if we don't have it
if test -z $RPM_OPT_FLAGS ; then
    CFLAGS="$CFLAGS -g -pipe -Wp,-D_FORTIFY_SOURCE=2 -fexceptions"
else
    CFLAGS="$CFLAGS $RPM_OPT_FLAGS"
fi

# NFS support can, in theory, be enabled or disabled
AC_ARG_ENABLE(nfs,
    AC_HELP_STRING([--enable-nfs],
                   [enable NFS support (default is yes)]),
    [nfs=$enableval],
    [nfs=yes])

# IPv6 support can be enabled or disabled
AC_ARG_ENABLE(ipv6,
    AC_HELP_STRING([--enable-ipv6],
                   [enable IPv6 support (default is yes)]),
    [ipv6=$enableval],
    [ipv6=yes])
if test x$ipv6 = xyes ; then
    AC_SUBST(IPV6_CFLAGS, [-DENABLE_IPV6])
fi

# GCC likes to bomb out on some ridiculous warnings.  Add your favorites
# here.
SHUT_UP_GCC="-Wno-unused-result"

# Add remaining compiler flags we want to use
CFLAGS="$CFLAGS -Wall -Werror $SHUT_UP_GCC -D_GNU_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE"

# Filter CFLAGS (remove duplicate flags)
cflags_filter() {
    have=
    first=1
    for flag in $* ; do
        if test -z "`echo $have | grep -- $flag`" ; then
            if test x$first == x1 ; then
                first=2
            else
                echo -n " "
            fi
            echo -n $flag
            have="$have $flag"
        fi
    done
}
CFLAGS="`cflags_filter $CFLAGS`"

# Unset $(LIBS) because different programs and libraries will have different
# lists of libraries to link with, we don't want everything linking against
# all libraries we checked for.
LIBS=

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
                 data/help/Makefile
                 data/help/en-US/Makefile
                 po/Makefile.in
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
                 pyanaconda/ui/gui/tools/Makefile
                 pyanaconda/ui/gui/Makefile
                 pyanaconda/ui/tui/hubs/Makefile
                 pyanaconda/ui/tui/simpleline/Makefile
                 pyanaconda/ui/tui/spokes/Makefile
                 pyanaconda/ui/tui/tools/Makefile
                 pyanaconda/ui/tui/Makefile
                 data/post-scripts/Makefile
                 tests/Makefile
                 utils/Makefile
                 utils/dd/Makefile])
AC_OUTPUT
