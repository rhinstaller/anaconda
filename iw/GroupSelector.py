#!/usr/bin/python -tt
#
# Copyright 2005 Red Hat, Inc.
#
# Jeremy Katz <katzj@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 only
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import os,sys
import string

import gtk
import gtk.glade
import gobject

import yum
import yum.Errors
import repomd.mdErrors as mdErrors

from rhpl.translate import _, N_, getDefaultLangs

GLADE_FILE = "GroupSelector.glade"
I18N_DOMAIN = "anaconda"

# kind of lame caching of translations so we don't always have
# to do all the looping
strs = {}
def _xmltrans(base, thedict):
    if strs.has_key(base):
        return strs[base]
    
    langs = getDefaultLangs()
    for l in langs:
        if thedict.has_key(l):
            strs[base] = thedict[l]
            return strs[base]
    strs[base] = base
    return base

class OptionalPackageSelector:
    def __init__(self, yumobj, group, parent = None, getgladefunc = None):
        self.ayum = yumobj
        self.group = group

        if getgladefunc:
            xmlfn = getgladefunc(GLADE_FILE)
        else:
            xmlfn = GLADE_FILE

        self.xml = gtk.glade.XML(xmlfn, "groupDetailsDialog",
                                 domain=I18N_DOMAIN)

        self.window = self.xml.get_widget("groupDetailsDialog")
        if parent:
            self.window.set_transient_for(parent)
        self.window.set_title(_("Packages in %s") %
                               _xmltrans(group.name, group.translated_name))
        self._createStore()
        self._populate()

    def _createStore(self):
        self.pkgstore = gtk.TreeStore(gobject.TYPE_BOOLEAN,
                                      gobject.TYPE_STRING,
                                      gobject.TYPE_PYOBJECT)
        tree = self.xml.get_widget("packageList")
        tree.set_model(self.pkgstore)

        column = gtk.TreeViewColumn(None, None)
        cbr = gtk.CellRendererToggle()
        cbr.connect ("toggled", self._pkgToggled)
        column.pack_start(cbr, False)
        column.add_attribute(cbr, 'active', 0)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.add_attribute(renderer, 'markup', 1)
        tree.append_column(column)

        self.pkgstore.set_sort_column_id(1, gtk.SORT_ASCENDING)

    def __deselectPackage(self, pkg):
        # FIXME: this doesn't handle removing an installed package...
        grpid = self.group.groupid
        try:
            pkgs = self.ayum.pkgSack.returnNewestByName(pkg)
        except mdErrors.PackageSackError:
            self.ayum.log(4, "no such package %s from group %s" %
                     (pkg, self.group.groupid))
        if pkgs:
            pkgs = self.ayum.bestPackagesFromList(pkgs)
        for po in pkgs:
            txmbrs = self.ayum.tsInfo.getMembers(pkgtup = po.pkgtup)
            for txmbr in txmbrs:
                try:
                    txmbr.groups.remove(grpid)
                except ValueError:
                    self.ayum.log(4, "package %s was not marked in group %s" %(po, grpid))
                if len(txmbr.groups) == 0:
                    self.ayum.tsInfo.remove(po.pkgtup)

    def __selectPackage(self, pkg):
        grpid = self.group.groupid
        try:
            txmbrs = self.ayum.install(name = pkg)
        except yum.Errors.InstallError, e:
            self.ayum.log(3, "No package named %s available to "
                          "be installed: %s" %(pkg, e))
        else:
            map(lambda x: x.groups.append(grpid), txmbrs)

    def _pkgToggled(self, widget, path):
        i = self.pkgstore.get_iter_from_string(path)
        sel = self.pkgstore.get_value(i, 0)
        pkg = self.pkgstore.get_value(i, 2)
        if sel:
            self.__deselectPackage(pkg)
        else:
            self.__selectPackage(pkg)
        self.pkgstore.set_value(i, 0, not sel)
            

    def __getPackageDescription(self, pkgname):
        po = None
        if self.ayum.rpmdb.installed(name = pkgname):
            pkgtup = self.ayum.rpmdb.returnTupleByKeyword(name=pkgname)
            if len(pkgtup) > 0:
                po = self.ayum.getInstalledPackageObject(pkgtup[0])
        else:
            pos = self.ayum.pkgSack.searchNevra(name=pkgname)
            if len(pos) > 0:
                po = pos[0]
        if po:
            return po.returnSimple('summary').replace("\n", "")
        return None

    def _populate(self):
        pkgs = self.group.default_packages.keys() + \
               self.group.optional_packages.keys()
        for pkg in pkgs:
            desc = self.__getPackageDescription(pkg)
            if desc is not None:
                s = "<b>%s</b> - %s" %(pkg, desc)
            else:
                # if there's no description, it's not in the rpmdb or
                # the pkgsack, so showing it doesn't do much good...
                continue 
            self.pkgstore.append(None, [self.ayum.isPackageInstalled(pkg),
                                        s, pkg])

    def run(self):
        self.window.show_all()
        return self.window.run()

    def destroy(self):
        return self.window.destroy()

class GroupSelector:
    def __init__(self, yumobj, getgladefunc = None, framefunc = None):
        self.ayum = yumobj

        self.getgladefunc = getgladefunc
        self.framefunc = framefunc
        if getgladefunc:
            xmlfn = getgladefunc(GLADE_FILE)
        else:
            xmlfn = GLADE_FILE

        self.xml = gtk.glade.XML(xmlfn, "groupSelectionBox",
                                 domain=I18N_DOMAIN)
        self.vbox = self.xml.get_widget("groupSelectionBox")
        self._connectSignals()
        self._createStores()
        self.vbox.show()
        
    def _connectSignals(self):
        sigs = { "on_detailsButton_clicked": self._optionalPackagesDialog, }
        self.xml.signal_autoconnect(sigs)

    def _createStores(self):
        self._createCategoryStore()
        self._createGroupStore()

        b = gtk.TextBuffer()
        self.xml.get_widget("groupDescriptionTextView").set_buffer(b)
        tag = b.create_tag('right-just')
        tag.set_property('justification', gtk.JUSTIFY_RIGHT)

    def _createCategoryStore(self):        
        # display string, category object
        self.catstore = gtk.TreeStore(gobject.TYPE_STRING,
                                      gobject.TYPE_PYOBJECT)
        tree = self.xml.get_widget("categoryList")
        tree.set_model(self.catstore)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Text', renderer, markup=0)
        column.set_clickable(False)
        tree.append_column(column)
        tree.columns_autosize()

        selection = tree.get_selection()
        selection.connect("changed", self._categorySelected)

    def _createGroupStore(self):
        # checkbox, display string, object
        self.groupstore = gtk.TreeStore(gobject.TYPE_BOOLEAN,
                                        gobject.TYPE_STRING,
                                        gobject.TYPE_PYOBJECT,
                                        gobject.TYPE_OBJECT)
        tree = self.xml.get_widget("groupList")
        tree.set_model(self.groupstore)

        column = gtk.TreeViewColumn(None, None)
        column.set_clickable(True)
        pixr = gtk.CellRendererPixbuf()
        pixr.set_property('stock-size', 1)
        column.pack_start(pixr, False)
        column.add_attribute(pixr, 'pixbuf', 3)
        cbr = gtk.CellRendererToggle()
        column.pack_start(cbr, False)
        column.add_attribute(cbr, 'active', 0)
        cbr.connect ("toggled", self._groupToggled)
        tree.append_column(column)
        
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Text', renderer, markup=1)
        column.set_clickable(False)
        tree.append_column(column)
        tree.columns_autosize()

        self.groupstore.set_sort_column_id(1, gtk.SORT_ASCENDING)
        selection = tree.get_selection()
        selection.connect("changed", self._groupSelected)

    def _categorySelected(self, selection):
        self.groupstore.clear()
        (model, i) = selection.get_selected()
        if not i:
            return
        cat = model.get_value(i, 1)
        for g in cat.groups:
            grp = self.ayum.comps.groups[g]
            s = "<span size=\"large\" weight=\"bold\">%s</span>" % _xmltrans(grp.name, grp.translated_name)

            fn = "/usr/share/pixmaps/comps/%s.png" % grp.groupid
            if os.access(fn, os.R_OK):
                imgsize = 24
                pix = gtk.gdk.pixbuf_new_from_file(fn)
                if pix.get_height() != imgsize or pix.get_width() != imgsize:
                    pix = pix.scale_simple(imgsize, imgsize,
                                           gtk.gdk.INTERP_BILINEAR)
            else:
                pix = None
            # FIXME: this needs to handle selected vs installed..
            self.groupstore.append(None, [grp.selected, s, grp, pix])

    def _groupSelected(self, selection):
        (model, i) = selection.get_selected()
        grp = None
        if i:
            grp = model.get_value(i, 2)
        self.__setGroupDescription(grp)

    def __setGroupDescription(self, grp):
        b = self.xml.get_widget("groupDescriptionTextView").get_buffer()
        b.set_text("")
        if grp is None:
            return
        
        if grp.description:
            txt = "%s\n\n" % _xmltrans(grp.description,
                                       grp.translated_description)
        else:
            txt = _("No description available for %s.\n\n") % _xmltrans(grp.name,
                                                                        grp.translated_name)
        b.set_text(txt)

        i = b.get_end_iter()
        inst = 0
        cnt = 0
        pkgs = grp.default_packages.keys() + grp.optional_packages.keys()
        for p in pkgs:
            if self.ayum.isPackageInstalled(p):
                cnt += 1
                inst += 1
            elif self.ayum.pkgSack.searchNevra(name=p):
                cnt += 1
            else:
                self.ayum.log(2, "no such package %s for %s" %(p, grp.groupid))

        if cnt == 0 or grp.selected == False:
            self.xml.get_widget("detailsButton").set_sensitive(False)
        else:
            self.xml.get_widget("detailsButton").set_sensitive(True)
            b.insert_with_tags_by_name(i,
                              _("[%d of %d optional packages installed]")
                                       %(inst, cnt), "right-just")

    def _groupToggled(self, widget, path):
        i = self.groupstore.get_iter_from_string(path)
        cb = self.groupstore.get_value(i, 0)
        self.groupstore.set_value(i, 0, not cb)
        grp = self.groupstore.get_value(i, 2)
        if not cb:
            self.ayum.selectGroup(grp.groupid)
        else:
            self.ayum.deselectGroup(grp.groupid)
            # FIXME: this doesn't mark installed packages for removal.
            # we probably want that behavior with s-c-p, but not anaconda
        self.__setGroupDescription(grp)

    def populateCategories(self):
        self.catstore.clear()
        for cat in self.ayum.comps.categories.values():
            s = "<span size=\"large\" weight=\"bold\">%s</span>" % _xmltrans(cat.name, cat.translated_name)
            self.catstore.append(None, [s, cat])

    def doRefresh(self):
        self.populateCategories()

    def _optionalPackagesDialog(self, *args):
        selection = self.xml.get_widget("groupList").get_selection()        
        (model, i) = selection.get_selected()
        if not i:
            return
        group = model.get_value(i, 2)

        pwin = self.vbox.get_parent() # hack to find the parent window...
        while not isinstance(pwin, gtk.Window):
            pwin = pwin.get_parent()
        d = OptionalPackageSelector(self.ayum, group, pwin, self.getgladefunc)
        if self.framefunc:
            self.framefunc(d.window)
        rc = d.run()
        d.destroy()
        self.__setGroupDescription(group)
