#!/usr/bin/python
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Author: David Shea <dshea@redhat.com>

import sys
import argparse
import re
import os.path
import copy

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_accelerators.py")
    sys.exit(1)

accel_re = re.compile(r'_(?P<accel>.)')

success = True
def add_check_accel(glade_filename, accels, label):
    """Check whether an accelerator conflicts with existing accelerators.
       and add it to the current accelerator context.
    """
    global success

    match = accel_re.search(label.text)
    if match:
        accel = match.group('accel').lower()
        if accel in accels:
            # Check for an exception comment
            prev = label.getprevious()
            if (prev is not None) and (prev.tag == etree.Comment) and \
                    prev.text.strip().startswith('check_accelerators:'):
                return

            print("Accelerator collision for key %s in %s\n    line %d: %s\n    line %d: %s" %\
                    (accel, os.path.normpath(glade_filename),
                        accels[accel].sourceline, accels[accel].text,
                        label.sourceline, label.text))
            success = False
        else:
            accels[accel] = label

def combine_accels(glade_filename, list_a, list_b):
    if not list_a:
        return list_b
    if not list_b:
        return list_a

    newlist = []
    for accels_a in list_a:
        for accels_b in list_b:
            new_accels = copy.copy(accels_a)
            for accel in accels_b.keys():
                add_check_accel(glade_filename, new_accels, accels_b[accel])
            newlist.append(new_accels)
    return newlist

# GtkNotebook widgets define several child widgets, not all of which are active
# at the same time. To further complicate things, an object can have more than
# one GtkNotebook child, and a GtkNotebook can have GtkNotebook children.
#
# To handle this, GtkNotebook objects are processed separately.
# process_object returns a list of possible accelerator dictionaries, and each of
# these is compared against the list of accelerators returned for the object's
# other GtkNotebook children.

def process_object(glade_filename, interface_object):
    """Process keyboard shortcuts for a given glade object.

       The return value from this function is a list of accelerator
       dictionaries, with each consiting of accelerator shortcut characters
       as keys and the corresponding <object> Element objects as values. Each
       dictionary represents a set of accelerators that could be active at any
       given time.
    """
    # Start with an empty context for things that are always active
    accels = [{}]

    # Add everything that isn't a child of a GtkNotebook
    for label in interface_object.xpath(".//property[@name='label' and ../property[@name='use_underline']/text() = 'True' and not(ancestor::object[@class='GtkNotebook'])]"):
        add_check_accel(glade_filename, accels[0], label)

    # For each GtkNotebook tab that is not a child of another notebook,
    # add the tab to the top-level context
    for notebook_label in interface_object.xpath(".//object[@class='GtkNotebook' and not(ancestor::object[@class='GtkNotebook'])]/child[@type='tab']//property[@name='label' and ../property[@name='use_underline']/text() = 'True']"):
        add_check_accel(glade_filename, accels[0], notebook_label)

    # Now process each non-tab object in each Gtknotebook that is not a child
    # of another notebook. For each Gtk notebook, each non-tab child represents
    # a separate potentially-active context. Since each list returned by
    # process_object for a GtkNotebook child is independent of each other
    # GtkNotebook child, we can just combine all of them into a single list.
    # For example, say there's a notebook with two panes. The first pane
    # contains another notebook with two panes. Let's call the main pane
    # A, and the panes in the child GtkNotebook A_1 and A_2. A contains an
    # accelerator for 'a', A_1 contains accelerators for 'b' and 'c', and A_2
    # contains accelerators for 'b' and 'c'. The list returned would look like:
    #   [{'a': label1, 'b': label2, 'c': label3},
    #    {'a': label1, 'b': label4, 'c': label5}]
    # Then when we process the other pane in the outermost Notebook (let's call
    # it B), we find acclerators for 'a' and 'b':
    #   [{'a': label6, 'b': label7}].
    # None of these dictionaries are active at the same time. Because
    # process_object on A combined the accelerators that are in the top-level
    # of A with each of the accelerators in the Notebook children of A, we can
    # treat A as if it were actually two panes at the same-level of B and just
    # create a list of three dictionaries for the whole notebook.
    #
    # A deepcopy of each object is taken so that the object can be treated as a
    # separate XML document so that the ancestor axis stuff works.

    for notebook in interface_object.xpath(".//object[@class='GtkNotebook' and not(ancestor::object[@class='GtkNotebook'])]"):
        # Create the list of dictionaries for the notebook
        notebook_list = []
        for child in notebook.xpath("./child[not(@type='tab')]"):
            notebook_list.extend(process_object(glade_filename, copy.deepcopy(child)))

        # Now combine this with our list of accelerators
        accels = combine_accels(glade_filename, accels, notebook_list)

    return accels

def check_glade(glade_filename):
    with open(glade_filename) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Treat each top-level object as a separate context
        for interface_object in glade_tree.xpath("/interface/object"):
            process_object(glade_filename, interface_object)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser("Check for duplicated accelerators")
    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=argv)

    for glade_file in args.glade_files:
        check_glade(glade_file)

if __name__ == "__main__":
    main(sys.argv[1:])

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
