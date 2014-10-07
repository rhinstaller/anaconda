# Makefile.am for anaconda widgets
#
# Copyright (C) 2011-2012  Red Hat, Inc.
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

-include $(INTROSPECTION_MAKEFILE)

ACLOCAL_AMFLAGS = -I m4

DISTCHECK_CONFIGURE_FLAGS = --enable-introspection --enable-gtk-doc

GISOURCES = BaseWindow.c \
	 DiskOverview.c \
	 HubWindow.c \
	 MountpointSelector.c \
	 SpokeSelector.c \
	 SpokeWindow.c \
	 StandaloneWindow.c \
	 LayoutIndicator.c \
	 BaseStandalone.c \
	 widgets-common.c

GIHDRS = BaseWindow.h \
	 DiskOverview.h \
	 HubWindow.h \
	 MountpointSelector.h \
	 SpokeSelector.h \
	 SpokeWindow.h \
	 StandaloneWindow.h \
	 LayoutIndicator.h \
	 BaseStandalone.h \
	 widgets-common.h

NONGISOURCES =

NONGIHDRS =

SOURCES = $(GISOURCES) $(NONGISOURCES)

HDRS = $(GIHDRS) $(NONGIHDRS)

WIDGETSDATA = '"$(datadir)/anaconda"'

noinst_HEADERS = gettext.h intl.h

lib_LTLIBRARIES = libAnacondaWidgets.la
libAnacondaWidgets_la_CFLAGS = $(GTK_CFLAGS) $(GLADEUI_CFLAGS) $(LIBXKLAVIER_CFLAGS) -Wall -g\
			       -DWIDGETS_DATADIR=$(WIDGETSDATA)
libAnacondaWidgets_la_LIBADD = $(GTK_LIBS) $(GLADEUI_LIBS) $(LIBXKLAVIER_LIBS)
libAnacondaWidgets_la_LDFLAGS = $(LTLIBINTL) -version-info 3:0:1
libAnacondaWidgets_la_SOURCES = $(SOURCES) $(HDRS) \
	  glade-adaptor.c

lib_includedir=$(includedir)/AnacondaWidgets
lib_include_HEADERS = $(HDRS)

MAINTAINERCLEANFILES = gettext.h

if HAVE_INTROSPECTION
AnacondaWidgets-3.0.gir: libAnacondaWidgets.la

AnacondaWidgets_3_0_gir_FILES = $(GISOURCES) $(GIHDRS)
AnacondaWidgets_3_0_gir_LIBS = libAnacondaWidgets.la
AnacondaWidgets_3_0_gir_SCANNERFLAGS = --warn-all --identifier-prefix=Anaconda --symbol-prefix=anaconda
AnacondaWidgets_3_0_gir_INCLUDES = Gtk-3.0 Xkl-1.0

INTROSPECTION_GIRS = AnacondaWidgets-3.0.gir

typelibdir = $(libdir)/girepository-1.0
typelib_DATA = $(INTROSPECTION_GIRS:.gir=.typelib)

CLEANFILES = AnacondaWidgets-3.0.gir $(typelib_DATA)
MAINTAINERCLEANFILES += Makefile.in
endif
