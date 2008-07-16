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

# This yum plugin handles the upgrade blacklist.  This is a repo-specific
# metadata file that tells us about packages that have been obsoleted by
# some other package and should therefore be removed on upgrade.  Usually
# packages themselves provide this information through Obsoletes:, but
# with multilib we can't always count on that.
from yum.plugins import TYPE_CORE

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree

iterparse = cElementTree.iterparse

requires_api_version = '2.6'
plugin_type = (TYPE_CORE, )

def exclude_hook(conduit):
    rpmdb = conduit.getRpmDB()
    tsinfo = conduit.getTsInfo()

    for repo in conduit.getRepos().listEnabled():
        try:
            infile = repo.retrieveMD("group")
        except:
            continue

        for event, elem in iterparse(infile):
            if elem.tag == "blacklist":
                for child in elem.getchildren():
                    if elem.tag != "package":
                        continue

                    name = elem.get("name")
                    try:
                        arch = elem.get("arch")
                    except:
                        arch = None

                    for po in rpmdb.searchNevra(name=name, arch=arch):
                        tsinfo.addErase(po)
