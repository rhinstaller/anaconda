#!/bin/sh -e
# Generate HTML documentation
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>
#

# Using make to run tools with multiple outputs is a recipe for disaster, so
# use make to run this instead. It's not like any of it can be parallelized
# anyway, and if anything changes we more than likely have to start at the
# beginning. This script will run all of the various gtkdoc programs and create
# a single output file, $DOC_OUTPUT_DIR/gtkdoc.stamp

# ---- ENVIRONMENT VARIABLES -----
# DOC_MODULE: the name of the module
# DOC_MAIN_SGML_FILE: the top-level SGML file
# DOC_SOURCE_DIR: directories containing the source code
# IGNORE_HFILES: header files to ignore while scanning
# SCAN_OPTIONS: Extra options to supply to gtkdoc-scan
# MKDB_OPTIONS: Extra options to supply to gtkdoc-mkdb
# HTML_DIR: The gtk-doc html directory
# GTKDOC_CC: compiler to use with gtkdoc-scangobj (e.g., $(LTCOMPILE))
# GTKDOC_LD: linker to use with gtkdoc-scangobj (e.g., $(LINK))
# GTKDOC_RUN: Wrapper to run whatever gtdkco-scangobj made (e.g., $(LIBTOOL) --mode=execute)
# GTKDOC_CFLAGS: CFLAGS to pass to gtkdoc-scangobj (e.g., $(GTK_CFLAGS))
# GTKDOC_LIBS: LIBS to pass to gtkdoc-scangobj (e.g., $(GTK_LIB) plus the .la file to scan)

# Everything will be output in the current directory because these tools are
# awful at communicating paths to each other, and all of the paths in
# $DOC_MAIN_SGML_FILE need to be relative to the output directory. Which
# also means that $DOC_MAIN_SGML_FILE needs to be copied into $builddir.

# This script should be run any time the source files or the main SGML file
# change.

if [ -n "$V" ]; then
    set -x
fi

# Remove the old stamp file
rm -f gtkdoc.stamp

# Generate --source-dir args for gtkdoc-scan and gtkdoc-mkdb
# Use realpath to convert to absolute paths because whoever wrote gtkdoc-mkdb
# couldn't imagine a world in which input file aren't in the current directory
_source_dir=
for d in $DOC_SOURCE_DIR ; do
    _source_dir="${_source_dir} --source-dir=$(realpath $d)"
done

# Convert DOC_MAIN_SGML_FILE to an absolute path because gtkdoc-mkhtml can't
# specify an output directory
DOC_MAIN_SGML_FILE=$(realpath ${DOC_MAIN_SGML_FILE})

# Clean up files from gtkdoc-scan and run
rm -f ${DOC_MODULE}-decl-list.txt ${DOC_MODULE}-decl.txt ${DOC_MODULE}-overrides.txt \
      ${DOC_MODULE}-sections.txt ${DOC_MODULE}.types

gtkdoc-scan \
    --module=${DOC_MODULE} \
    --ignore-headers="${IGNORE_HFILES}" ${_source_dir} \
    --output-dir=. \
    ${SCAN_OPTIONS}

# Clean up files from gtkdoc-scangobj and run
rm -f ${DOC_MODULE}.args ${DOC_MODULE}.hierarchy ${DOC_MODULE}.interfaces \
      ${DOC_MODULE}.prerequisites ${DOC_MODULE}.signals

gtkdoc-scangobj \
    --module=${DOC_MODULE} \
    --types=${DOC_MODULE}.types \
    --output-dir=. \
    --cc="${GTKDOC_CC}" \
    --run="${GTKDOC_RUN}" \
    --ld="${GTKDOC_LD}" \
    --cflags="${GTKDOC_CFLAGS}" \
    --ldflags="${GTKDOC_LIBS}"

# Clean up files from gtkdoc-mkdb and run
rm -rf ${DOC_MODULE}-doc.bottom ${DOC_MODULE}-doc.top \
       ${DOC_MODULE}-undeclared.txt ${DOC_MODULE}-undocumented.txt \
       ${DOC_MODULE}-unused.txt sgml.stamp xml

gtkdoc-mkdb --module=${DOC_MODULE} \
            --source-suffixes=c,h \
            --ignore-files="${IGNORE_HFILES}" \
            --output-dir=xml \
            --main-sgml-file=${DOC_MAIN_SGML_FILE} \
            --output-format=xml \
            ${_source_dir} \
            ${MKDB_OPTIONS}

# We almost have something useful! gtkdoc-mkhtml is next
rm -rf html
mkdir html
( cd html && gtkdoc-mkhtml ${DOC_MODULE} ${DOC_MAIN_SGML_FILE} )

gtkdoc-fixxref --module=${DOC_MODULE} --module-dir=html --html-dir=${HTML_DIR}

# All done, new stamp file
touch gtkdoc.stamp
