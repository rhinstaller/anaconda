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
import collections
import locale

try:
    from lxml import etree
except ImportError:
    print("You need to install the python-lxml package to use check_accelerators.py")
    sys.exit(1)

accel_re = re.compile(r'_(?P<accel>.)')
success = True

# Only used when --translate is requested.
class PODict(collections.Mapping):
    def __init__(self, filename):
        try:
            import polib
        except ImportError:
            print("You need to install the python-polib package to check translations")
            sys.exit(1)

        self._dict = {}

        pofile = polib.pofile(filename)
        self.metadata = pofile.metadata
        for entry in pofile.translated_entries():
            # If this is a plural entry, take the first option and hope that
            # the accelerator is the same for all options.
            # Add dictionary entries for both the singular and plural IDs so
            # that glade placeholders can contain either form.
            if entry.msgstr_plural:
                self._dict[entry.msgid] = entry.msgstr_plural['0']
                self._dict[entry.msgid_plural] = entry.msgstr_plural['0']
            else:
                self._dict[entry.msgid] = entry.msgstr

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return len(self._dict)

def is_exception(node, conflicting_node, language=None):
    # Check for a comment of the form
    # <!-- check_accelerators: <conflicting-node-id> -->
    # The node passed in is the label property of the widget rather than the
    # <object> node itself, so we actually want the id attribute of the parent node.
    for comment in node.xpath("./preceding-sibling::comment()[contains(., 'check_accelerators:')]"):
        if comment.text.split(":")[1].strip() == conflicting_node.getparent().attrib['id']:
            return True

    return False

def add_check_accel(glade_filename, accels, label, po_map):
    """Check whether an accelerator conflicts with existing accelerators.
       and add it to the current accelerator context.
    """
    global success

    if po_map:
        if label.text not in po_map:
            return
        label.text = po_map[label.text]
        lang_str = " for language %s" % po_map.metadata['Language']
    else:
        lang_str = ""

    match = accel_re.search(label.text)
    if match:
        accel = match.group('accel').lower()
        if accel in accels:
            # Check for an exception comment
            if is_exception(label, accels[accel]):
                return

            print(("Accelerator collision for key %s in %s%s\n    line %d: %s\n    line %d: %s" %\
                    (accel, os.path.normpath(glade_filename), lang_str,
                        accels[accel].sourceline, accels[accel].text,
                        label.sourceline, label.text)).encode("utf-8"))
            success = False
        else:
            accels[accel] = label
    else:
        print(("No accelerator defined for %s in %s%s: line %d" %\
                (label.text, os.path.normpath(glade_filename), lang_str,
                    label.sourceline)).encode("utf-8"))
        success = False

def combine_accels(glade_filename, list_a, list_b, po_map):
    if not list_a:
        return list_b
    if not list_b:
        return list_a

    newlist = []
    for accels_a in list_a:
        for accels_b in list_b:
            new_accels = copy.copy(accels_a)
            for accel in accels_b.keys():
                add_check_accel(glade_filename, new_accels, accels_b[accel], po_map)
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

def process_object(glade_filename, interface_object, po_map):
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
    for label in interface_object.xpath(".//property[@name='label' and ../property[@name='use_underline']/text() = 'True' and not(ancestor::object[@class='GtkNotebook']) and not(../property[@name='use_stock']/text() = 'True')]"):
        add_check_accel(glade_filename, accels[0], label, po_map)

    # For each GtkNotebook tab that is not a child of another notebook,
    # add the tab to the top-level context
    for notebook_label in interface_object.xpath(".//object[@class='GtkNotebook' and not(ancestor::object[@class='GtkNotebook'])]/child[@type='tab']//property[@name='label' and ../property[@name='use_underline']/text() = 'True' and not(../property[@name='use_stock']/text() = 'True')]"):
        add_check_accel(glade_filename, accels[0], notebook_label, po_map)

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
            notebook_list.extend(process_object(glade_filename, copy.deepcopy(child), po_map))

        # Now combine this with our list of accelerators
        accels = combine_accels(glade_filename, accels, notebook_list, po_map)

    return accels

def check_glade(glade_filename, po_map=None):
    with open(glade_filename) as glade_file:
        # Parse the XML
        glade_tree = etree.parse(glade_file)

        # Treat each top-level object as a separate context
        for interface_object in glade_tree.xpath("/interface/object"):
            process_object(glade_filename, interface_object, po_map)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = argparse.ArgumentParser("Check for duplicated accelerators")
    parser.add_argument("-t", "--translate", action='store_true',
            help="Check translated strings")
    parser.add_argument("-p", "--podir", action='store', type=str,
            metavar='PODIR', help='Directory containing po files', default='./po')
    parser.add_argument("glade_files", nargs="+", metavar="GLADE-FILE",
            help='The glade file to check')
    args = parser.parse_args(args=argv)

    # First check the untranslated strings in each file
    for glade_file in args.glade_files:
        check_glade(glade_file)

    # Now loop over all of the translations
    if args.translate:
        import langtable

        with open(os.path.join(args.podir, 'LINGUAS')) as linguas:
            for line in linguas.readlines():
                if re.match(r'^#', line):
                    continue

                for lang in line.strip().split(" "):
                    # Reset the locale to C before parsing the po file because
                    # polib has erroneous uses of lower().
                    # See https://bitbucket.org/izi/polib/issue/54/pofile-parsing-crashes-in-turkish-locale
                    locale.setlocale(locale.LC_ALL, 'C')
                    po_map = PODict(os.path.join(args.podir, lang + ".po"))

                    # Set the locale so that we can use lower() on accelerator keys.
                    # If the language is of the form xx_XX, use that as the
                    # locale name. Otherwise use the first locale that
                    # langtable returns for the language. If that doesn't work,
                    # just use C and hope for the best.
                    if '_' in lang:
                        locale.setlocale(locale.LC_ALL, lang)
                    else:
                        locale_list = langtable.list_locales(languageId=lang)
                        if locale_list:
                            try:
                                locale.setlocale(locale.LC_ALL, locale_list[0])
                            except locale.Error:
                                print("No such locale %s, using C" % locale_list[0])
                                locale.setlocale(locale.LC_ALL, 'C')
                        else:
                            locale.setlocale(locale.LC_ALL, 'C')

                    for glade_file in args.glade_files:
                        check_glade(glade_file, po_map)

if __name__ == "__main__":
    main(sys.argv[1:])

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
