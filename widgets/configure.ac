# configure.ac for anaconda widgets
#
# Copyright (C) 2011  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

AC_PREREQ([2.63])
AC_INIT([AnacondaWidgets], [2.0], [clumens@redhat.com])
AM_INIT_AUTOMAKE([foreign])
AM_SILENT_RULES([yes])

AM_PATH_PYTHON

AC_CONFIG_SRCDIR([src/BaseWindow.c])
AC_CONFIG_HEADERS([config.h])

AC_CONFIG_MACRO_DIR([m4])

AC_PROG_CC
AC_PROG_CXX
AC_PROG_LIBTOOL
AC_PROG_LN_S

AM_GNU_GETTEXT([external])

dnl Make sure that autoconf fails if the gobject-introspection macro
dnl is not expanded.
m4_pattern_forbid([GOBJECT_INTROSPECTION_CHECK])dnl
GOBJECT_INTROSPECTION_CHECK([0.6.7])
 
# Fail if introspection was not enabled
AS_IF([test "x$found_introspection" = xyes], [:],
      [AC_MSG_ERROR([*** GObject introspection must be enabled])])

dnl A missing GTK_DOC_CHECK should fail in autogen.sh running gtkdocize, but
dnl might as well check it here too
m4_pattern_forbid([GTK_DOC_CHECK])dnl
GTK_DOC_CHECK([1.14], [--flavour no-tmpl])

PKG_CHECK_MODULES([GLADEUI], [gladeui-2.0 >= 3.10])
PKG_CHECK_MODULES([GTK], [gtk+-x11-3.0 >= 3.0])
PKG_CHECK_MODULES([GLIB], [glib-2.0])
PKG_CHECK_MODULES([LIBXKLAVIER], [libxklavier >= 5.2.1])
PKG_CHECK_EXISTS([gobject-introspection-1.0 >= 1.30])

AC_CHECK_HEADERS([libintl.h string.h])

AC_CONFIG_FILES([Makefile
                 doc/Makefile
                 glade/Makefile
                 src/Makefile
                 python/Makefile
                 data/Makefile
                 data/tzmapdata/Makefile])
AC_OUTPUT
