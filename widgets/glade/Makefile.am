# Makefile.am for anaconda widget glade catalog
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

gladedir	= $(datadir)/glade/catalogs
dist_glade_DATA	= AnacondaWidgets.xml

glade_moduledir = $(libdir)/glade/modules
glade_module_LTLIBRARIES = libAnacondaWidgets.la

# Create a glade plugin containing the adaptor file that links
# to the regular libAnacondaWidgets
libAnacondaWidgets_la_SOURCES = glade-adaptor.c
libAnacondaWidgets_la_CFLAGS  = $(GLADEUI_CFLAGS) \
				-I$(top_srcdir)/src
libAnacondaWidgets_la_LDFLAGS = -module -avoid-version
libAnacondaWidgets_la_LIBADD  = $(GLADEUI_LIBS) \
				$(top_builddir)/src/libAnacondaWidgets.la

MAINTAINERCLEANFILES = Makefile.in
