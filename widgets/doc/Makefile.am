# Makefile.am for anaconda widget documentation
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

## Process this file with automake to produce Makefile.in

# The name of the module.
DOC_MODULE=AnacondaWidgets

# The top-level SGML file.
DOC_MAIN_SGML_FILE=$(DOC_MODULE)-docs.xml

# Directories containing the source code.
DOC_SOURCE_DIR=$(top_srcdir)

# Header files to ignore while scanning.
IGNORE_HFILES = config.h \
	gettext.h \
	intl.h

# Extra options to supply to gtkdoc-scan.
SCAN_OPTIONS=--rebuild-types

# Extra options to supply to gtkdoc-mkdb
MKDB_OPTIONS=--sgml-mode

# Only needed if you are using gtkdoc-scangobj to dynamically query widget
# signals and properties (which we are).
GTKDOC_CFLAGS=$(GLIB_CFLAGS) $(GTK_CFLAGS)
GTKDOC_LIBS=$(GLIB_LIBS) $(GTK_LIBS) $(top_builddir)/src/libAnacondaWidgets.la

include $(top_srcdir)/gtk-doc.make

if ENABLE_GTK_DOC
TESTS_ENVIRONMENT = cd $(srcdir) && \
  DOC_MODULE=$(DOC_MODULE) DOC_MAIN_SGML_FILE=$(DOC_MAIN_SGML_FILE) \
  SRCDIR=$(abs_srcdir) BUILDDIR=$(abs_builddir)
#TESTS = $(GTKDOC_CHECK)
endif

MAINTAINERCLEANFILES = AnacondaWidgets-overrides.txt AnacondaWidgets-sections.txt \
	AnacondaWidgets.types Makefile.in
