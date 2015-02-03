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
AC_INIT([AnacondaWidgets], [3.1], [clumens@redhat.com])
AM_INIT_AUTOMAKE([foreign])
AM_SILENT_RULES([yes])

AM_PATH_PYTHON

AC_CONFIG_SRCDIR([src/BaseWindow.c])
AC_CONFIG_HEADERS([config.h])

AC_CONFIG_MACRO_DIR([m4])

AC_TYPE_SIZE_T

AC_PROG_CC
AC_PROG_LIBTOOL

AM_GNU_GETTEXT([external])

dnl Make sure that autoconf fails if the gobject-introspection macro
dnl is not expanded.
m4_ifdef([GOBJECT_INTROSPECTION_CHECK],
[GOBJECT_INTROSPECTION_CHECK([0.6.7])],
[found_introspection=no
AM_CONDITIONAL(HAVE_INTROSPECTION, false)])
 
# Complain if introspection was not enabled
AS_IF([test "x$found_introspection" = xyes], [:],
      [ANACONDA_SOFT_FAILURE([GObject introspection must be enabled])])

# Add gtk-doc's html-dir option without pulling in the rest of gtk-doc
AC_ARG_WITH([html-dir],
            AS_HELP_STRING([--with-html-dir=PATH], [path to installed docs]),,
            [with_html_dir='${datadir}/gtk-doc/html'])
HTML_DIR="$with_html_dir"
AC_SUBST([HTML_DIR])

ANACONDA_PKG_CHECK_MODULES([GLADEUI], [gladeui-2.0 >= 3.10])
ANACONDA_PKG_CHECK_MODULES([GTK], [gtk+-x11-3.0 >= 3.11.3])
ANACONDA_PKG_CHECK_MODULES([LIBXKLAVIER], [libxklavier >= 5.2.1])
ANACONDA_PKG_CHECK_EXISTS([gobject-introspection-1.0 >= 1.30])

AC_CHECK_HEADERS([libintl.h stdlib.h string.h unistd.h locale.h],
                 [],
                 [ANACONDA_SOFT_FAILURE([Header file $ac_header not found.])],
                 [])

AC_CHECK_FUNCS([setlocale],
               [],
               [ANACONDA_SOFT_FAILURE([Function $ac_func not found.])])

AC_CONFIG_FILES([Makefile
                 doc/Makefile
                 glade/Makefile
                 src/Makefile
                 python/Makefile
                 data/Makefile
                 data/pixmaps/Makefile])
AC_OUTPUT

# Gently advise the user about the build failures they are about to encounter
ANACONDA_FAILURES
