#!/usr/bin/python
#
# Copyright (C) 2008
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Chris Lumens <clumens@redhat.com>

# This yum plugin handles the whiteout file.  The whiteout is a repo-specific
# metadata file that is used to break loops in dependencies.
from yum.plugins import TYPE_CORE
import rpm

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree

iterparse = cElementTree.iterparse

requires_api_version = '2.6'
plugin_type = (TYPE_CORE, )

def postreposetup_hook(conduit):
    whiteout = ""
    lst = []

    # Merge the whiteout from all enabled repos together.
    for repo in conduit.getRepos().listEnabled():
        try:
            infile = repo.retrieveMD("group")
        except:
            continue

        for event, elem in iterparse(infile):
            if elem.tag == "whiteout":
                for child in elem.getchildren():
                    if child.tag != "ignoredep":
                        continue

                    lst.append("%s>%s" % (child.get("package"), child.get("requires")))

    whiteout = " ".join(lst)

    rpm.addMacro("_dependency_whiteout", whiteout)
