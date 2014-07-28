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
DOC_SOURCE_DIR=$(top_srcdir)/src

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
GTKDOC_CFLAGS=$(GTK_CFLAGS)
GTKDOC_LIBS=$(GTK_LIBS) $(top_builddir)/src/libAnacondaWidgets.la

# Extra junk copied from gtk-doc.make
GTKDOC_CC = $(LIBTOOL) --tag=CC --mode=compile $(CC) $(INCLUDES) $(GTKDOC_DEPS_CFLAGS) $(AM_CPPFLAGS) $(CPPFLAGS) $(AM_CFLAGS) $(CFLAGS)
GTKDOC_LD = $(LIBTOOL) --tag=CC --mode=link $(CC) $(GTKDOC_DEPS_LIBS) $(AM_CFLAGS) $(CFLAGS) $(AM_LDFLAGS) $(LDFLAGS)
GTKDOC_RUN = $(LIBTOOL) --mode=execute

# gtk-doc is terrible at integrating with autotools, so build things by hand.

# Copy the files we need into $builddir
SETUP_FILES = $(DOC_MAIN_SGML_FILE)
GTK_DOC_V_SETUP=$(GTK_DOC_V_SETUP_$(V))
GTK_DOC_V_SETUP_=$(GTK_DOC_V_SETUP_$(AM_DEFAULT_VERBOSITY))
GTK_DOC_V_SETUP_0=@echo "  DOC      Preparing build";

setup-build.stamp:
	$(GTK_DOC_V_SETUP)if test "$(abs_srcdir)" != "$(abs_builddir)" ; then \
	    test -d $(abs_builddir) || $(MKDIR_P) $(abs_builddir) ; \
            cp -pf $(abs_srcdir)/$(DOC_MAIN_SGML_FILE) $(abs_builddir)/$(DOC_MAIN_SGML_FILE) ; \
        fi
	$(AM_V_at)touch setup-build.stamp

GTK_DOC_V_BUILD=$(GTK_DOC_V_BUILD_$(V))
GTK_DOC_V_BUILD_=$(GTK_DOC_V_BUILD_$(AM_DEFAULT_VERBOSITY))
GTK_DOC_V_BUILD_0=@echo "  DOC      Building docs";

noinst_DATA = gtkdoc.stamp
dist_noinst_SCRIPTS = run-gtkdoc.sh
dist_noinst_DATA = AnacondaWidgets-docs.xml

# Copy a bunch of make variables to the environment and run the gtk-doc script
gtkdoc.stamp: run-gtkdoc.sh $(DOC_SOURCE_DIR)/*.c $(DOC_SOURCE_DIR)/*.h \
	      $(top_builddir)/src/libAnacondaWidgets.la \
	      $(DOC_MAIN_SGML_FILE) \
	      setup-build.stamp
	$(GTK_DOC_V_BUILD)DOC_MODULE="$(DOC_MODULE)" \
	DOC_MAIN_SGML_FILE="$(DOC_MAIN_SGML_FILE)" \
	DOC_SOURCE_DIR="$(DOC_SOURCE_DIR)" \
	IGNORE_HFILES="$(IGNORE_HFILES)" \
	SCAN_OPTIONS="$(SCAN_OPTIONS)" \
	MKDB_OPTIONS="$(MKDB_OPTIONS)" \
	HTML_DIR="$(HTML_DIR)" \
	GTKDOC_CC="$(GTKDOC_CC)" \
	GTKDOC_LD="$(GTKDOC_LD)" \
	GTKDOC_RUN="$(GTKDOC_RUN)" \
	GTKDOC_CFLAGS="$(GTKDOC_CFLAGS)" \
	GTKDOC_LIBS="$(GTKDOC_LIBS)" \
	V=$(V) \
	$(srcdir)/run-gtkdoc.sh

# install and uninstall targets adapted from gtk-doc.make
install-data-local: gtkdoc.stamp
	@installfiles=`echo $(builddir)/html/*`; \
        installdir="$(DESTDIR)$(HTML_DIR)/$(DOC_MODULE)" ; \
	$(mkinstalldirs) $${installdir} ; \
	for i in $$installfiles; do \
	  echo ' $(INSTALL_DATA) '$$i ; \
          $(INSTALL_DATA) $$i $${installdir}; \
        done ; \
	gtkdoc-rebase --relative --dest-dir=$(DESTDIR) --html-dir=$${installdir}

uninstall-local:
	@installdir="$(DESTDIR)$(HTML_DIR)/$(DOC_MODULE)" ; \
	rm -rf $${installdir}

# Clean up the mess
CLEANFILES = AnacondaWidgets-decl-list.txt AnacondaWidgets-decl.txt \
	     AnacondaWidgets-overrides.txt AnacondaWidgets-sections.txt \
	     AnacondaWidgets.types AnacondaWidgets.args AnacondaWidgets.hierarchy \
	     AnacondaWidgets.interfaces AnacondaWidgets.prerequisites AnacondaWidgets.signals \
	     AnacondaWidgets-doc.bottom AnacondaWidgets-doc.top AnacondaWidgets-undeclared.txt \
	     AnacondaWidgets-undocumented.txt AnacondaWidgets-unused.txt \
	     sgml.stamp html.stamp gtkdoc.stamp setup-build.stamp

clean-local:
	@rm -rf xml html
	@if test "$(abs_srcdir)" != "$(abs_builddir)" ; then \
		rm -f $(abs_builddir)/$(DOC_MAIN_SGML_FILE) ; \
	fi

MAINTAINERCLEANFILES = Makefile.in
