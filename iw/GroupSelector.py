# Copyright 2005-2007 Red Hat, Inc.
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

import os, sys
import logging
import gettext

import gtk
import gtk.glade
import gtk.gdk as gdk
import gobject

import yum
import yum.Errors
try:
    import repomd.mdErrors as mdErrors
except ImportError: # yum 2.9.x
    mdErrors = yum.Errors
from yum.constants import *
from compssort import *

I18N_DOMAIN="anaconda"

import rpm

def sanitizeString(s, translate = True):
    if len(s) == 0:
        return s

    if not translate:
        i18ndomains = []
    elif hasattr(rpm, "expandMacro"):
        i18ndomains = rpm.expandMacro("%_i18ndomains").split(":")
    else:
        i18ndomains = ["redhat-dist"]
        
    # iterate over i18ndomains to find the translation
    for d in i18ndomains:
        r = gettext.dgettext(d, s)
        if r != s:
            s = r
            break
        
    s = s.replace("\n\n", "\x00")
    s = s.replace("\n", " ")
    s = s.replace("\x00", "\n\n")
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if type(s) != unicode:
        try:
            s = unicode(s, "utf-8")
        except UnicodeDecodeError, e:
            sys.stderr.write("Unable to convert %s to a unicode object: %s\n" % (s, e))
            return ""
    return s

# given a package object, spit out a string reasonable for the list widgets
def listEntryString(po):
    desc = po.returnSimple('summary') or ''
    pkgStr = "%s-%s-%s.%s" % (po.name, po.version, po.release, po.arch)
    desc = "<b>%s</b> - %s" %(pkgStr, sanitizeString(desc))
    return desc

GLADE_FILE = "GroupSelector.glade"

def _getgladefile(fn):
    if os.path.exists(fn):
        return fn
    elif os.path.exists("data/%s" %(fn,)):
        return "data/%s" %(fn,)
    else:
        return "/usr/share/pirut/ui/%s" %(fn,)

t = gettext.translation(I18N_DOMAIN, "/usr/share/locale", fallback = True)
_ = t.lgettext


def _deselectPackage(ayum, group, pkg):
    grpid = group.groupid
    try:
        pkgs = ayum.pkgSack.returnNewestByName(pkg)
    except mdErrors.PackageSackError:
        log = logging.getLogger("yum.verbose")
        log.debug("no such package %s from group %s" % (pkg, grpid))
    if pkgs:
        pkgs = ayum.bestPackagesFromList(pkgs)
    for po in pkgs:
        txmbrs = ayum.tsInfo.getMembers(pkgtup = po.pkgtup)
        for txmbr in txmbrs:
            try:
                txmbr.groups.remove(grpid)
            except ValueError:
                log = logging.getLogger("yum.verbose")                
                log.debug("package %s was not marked in group %s" %(po, grpid))
            if len(txmbr.groups) == 0:
                ayum.tsInfo.remove(po.pkgtup)

def _selectPackage(ayum, group, pkg):
    grpid = group.groupid
    try:
        txmbrs = ayum.install(name = pkg)
    except yum.Errors.InstallError, e:
        log = logging.getLogger("yum.verbose")
        log.info("No package named %s available to be installed: %s" %(pkg, e))
    else:
        map(lambda x: x.groups.append(grpid), txmbrs)

def _catHasGroupWithPackages(cat, ayum):
    grps = map(lambda x: ayum.comps.return_group(x),
                   filter(lambda x: ayum.comps.has_group(x), cat.groups))
    for g in grps:
        if ayum._groupHasPackages(g):
            return True
    return False

class OptionalPackageSelector:
    def __init__(self, yumobj, group, parent = None, getgladefunc = None):
        self.ayum = yumobj
        self.group = group

        if getgladefunc:
            xmlfn = getgladefunc(GLADE_FILE)
        else:
            xmlfn = _getgladefile(GLADE_FILE)

        self.xml = gtk.glade.XML(xmlfn, "groupDetailsDialog",
                                 domain=I18N_DOMAIN)

        self.window = self.xml.get_widget("groupDetailsDialog")
        if parent:
            self.window.set_transient_for(parent)
        self.window.set_title(_("Packages in %s") %
                               xmltrans(group.name, group.translated_name))
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.set_size_request(600, 400)
        self._createStore()
        self._populate()

    def __search_pkgs(self, model, col, key, i):
        val = model.get_value(i, 2).returnSimple('name')
        if val.lower().startswith(key.lower()):
            return False
        return True

    def _createStore(self):
        self.pkgstore = gtk.ListStore(gobject.TYPE_BOOLEAN,
                                      gobject.TYPE_STRING,
                                      gobject.TYPE_PYOBJECT)
        tree = self.xml.get_widget("packageList")
        tree.set_model(self.pkgstore)

        column = gtk.TreeViewColumn(None, None)
        cbr = gtk.CellRendererToggle()
        cbr.connect ("toggled", self._pkgToggled)
        column.pack_start(cbr, False)
        column.add_attribute(cbr, 'active', 0)
        tree.append_column(column)
        
        column = gtk.TreeViewColumn(None, None)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.add_attribute(renderer, 'markup', 1)
        tree.append_column(column)
        tree.set_search_equal_func(self.__search_pkgs)
        tree.connect("row-activated", self._rowToggle)

        self.pkgstore.set_sort_column_id(1, gtk.SORT_ASCENDING)

    def _rowToggle(self, tree, path, col):
        self._pkgToggled(None, path)

    def _pkgToggled(self, widget, path):
        if type(path) == type(str):
            i = self.pkgstore.get_iter_from_string(path)
        else:
            i = self.pkgstore.get_iter(path)
        sel = self.pkgstore.get_value(i, 0)
        pkg = self.pkgstore.get_value(i, 2).returnSimple('name')
        if sel and not self.ayum.simpleDBInstalled(name = pkg):
            _deselectPackage(self.ayum, self.group, pkg)
        elif sel:
            self.ayum.remove(name = pkg)
        elif self.ayum.simpleDBInstalled(name = pkg):
            txmbrs = self.ayum.tsInfo.matchNaevr(name = pkg)
            for tx in txmbrs:
                if tx.output_state == TS_ERASE:
                    self.ayum.tsInfo.remove(tx.pkgtup)
        else:
            _selectPackage(self.ayum, self.group, pkg)
        self.pkgstore.set_value(i, 0, not sel)
            

    def __getPackageObject(self, pkgname):
        pos = self.ayum.pkgSack.searchNevra(name=pkgname)
        if len(pos) > 0:
            return pos[0]
        return None

    def _populate(self):
        pkgs = self.group.default_packages.keys() + \
               self.group.optional_packages.keys()
        for pkg in pkgs:
            po = self.__getPackageObject(pkg)
            if not po:
                continue

            # Don't display obsolete packages in the UI
            if self.ayum.up.checkForObsolete([po.pkgtup]).has_key(po.pkgtup):
                continue

            self.pkgstore.append([self.ayum.isPackageInstalled(pkg), listEntryString(po), po])

    def run(self):
        self.window.show_all()
        return self.window.run()

    def destroy(self):
        return self.window.destroy()

# the GroupSelector requires a YumBase object which also implements the
# following additional methods:
# * isPackageInstalled(p): is there a package named p installed or selected
# * isGroupInstalled(grp): is there a group grp installed or selected
class GroupSelector:
    def __init__(self, yumobj, getgladefunc = None, framefunc = None):
        self.ayum = yumobj

        self.getgladefunc = getgladefunc
        self.framefunc = framefunc
        if getgladefunc:
            xmlfn = getgladefunc(GLADE_FILE)
        else:
            xmlfn = _getgladefile(GLADE_FILE)

        self.xml = gtk.glade.XML(xmlfn, "groupSelectionBox",
                                 domain=I18N_DOMAIN)
        self.vbox = self.xml.get_widget("groupSelectionBox")
        self.xml.get_widget("detailsButton").set_sensitive(False)

        self.menuxml = gtk.glade.XML(xmlfn, "groupPopupMenu",
                                     domain=I18N_DOMAIN)
        self.groupMenu = self.menuxml.get_widget("groupPopupMenu")

        self._connectSignals()
        self._createStores()
        self.vbox.show()

    def _connectSignals(self):
        sigs = { "on_detailsButton_clicked": self._optionalPackagesDialog,
                 "on_groupList_button_press": self._groupListButtonPress,
                 "on_groupList_popup_menu": self._groupListPopup, }
        self.xml.signal_autoconnect(sigs)

        menusigs = { "on_select_activate": self._selectAllPackages,
                     "on_selectgrp_activate": self._groupSelect,
                     "on_deselectgrp_activate": self._groupDeselect,
                     "on_deselect_activate": self._deselectAllPackages }
        self.menuxml.signal_autoconnect(menusigs)

    def _createStores(self):
        self._createCategoryStore()
        self._createGroupStore()

        b = gtk.TextBuffer()
        self.xml.get_widget("groupDescriptionTextView").set_buffer(b)

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
        tree.set_enable_search(False)

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
        tree.set_enable_search(False)
        tree.grab_focus()

        selection = tree.get_selection()
        selection.connect("changed", self._groupSelected)
        selection.set_mode(gtk.SELECTION_MULTIPLE)

    def _get_pix(self, fn):
        imgsize = 24
        pix = gtk.gdk.pixbuf_new_from_file(fn)
        if pix.get_height() != imgsize or pix.get_width() != imgsize:
            pix = pix.scale_simple(imgsize, imgsize,
                                   gtk.gdk.INTERP_BILINEAR)
        return pix

    def _categorySelected(self, selection):
        self.groupstore.clear()
        (model, i) = selection.get_selected()
        if not i:
            return
        cat = model.get_value(i, 1)

        # fall back to the category pixbuf
        fbpix = None
        fn = "/usr/share/pixmaps/comps/%s.png" %(cat.categoryid,)
        if os.access(fn, os.R_OK):
            fbpix = self._get_pix(fn)
        self._populateGroups(cat.groups, fbpix)

    def _populateGroups(self, groups, defaultpix = None):
        grps = map(lambda x: self.ayum.comps.return_group(x),
                   filter(lambda x: self.ayum.comps.has_group(x), groups))
        grps.sort(ui_comps_sort)
        for grp in grps:
            if not self.ayum._groupHasPackages(grp):
                continue
            s = "<span size=\"large\" weight=\"bold\">%s</span>" % xmltrans(grp.name, grp.translated_name)

            fn = "/usr/share/pixmaps/comps/%s.png" % grp.groupid
            if os.access(fn, os.R_OK):
                pix = self._get_pix(fn)
            elif defaultpix:
                pix = defaultpix
            else:
                pix = None
            self.groupstore.append(None,
                                   [self.ayum.isGroupInstalled(grp),s,grp,pix])

        tree = self.xml.get_widget("groupList")
        gobject.idle_add(lambda x: x.flags() & gtk.REALIZED and x.scroll_to_point(0, 0), tree)
        self.xml.get_widget("optionalLabel").set_text("")
        self.xml.get_widget("detailsButton").set_sensitive(False)

        # select the first group
        i = self.groupstore.get_iter_first()
        if i is not None:
            sel = self.xml.get_widget("groupList").get_selection()
            sel.select_iter(i)

    def _groupSelected(self, selection):
        if selection.count_selected_rows() != 1:
            # if we have more groups (or no group) selected, then
            # we can't show a description or allow selecting optional
            self.__setGroupDescription(None)
            return
        (model, paths) = selection.get_selected_rows()
        grp = model.get_value(model.get_iter(paths[0]), 2)
        self.__setGroupDescription(grp)

    def __setGroupDescription(self, grp):
        b = self.xml.get_widget("groupDescriptionTextView").get_buffer()
        b.set_text("")
        if grp is None:
            return
        
        if grp.description:
            txt = xmltrans(grp.description, grp.translated_description)
        else:
            txt = xmltrans(grp.name, grp.translated_name)

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
                log = logging.getLogger("yum.verbose")
                log.debug("no such package %s for %s" %(p, grp.groupid))

        b.set_text(txt)
        if cnt == 0 or not self.ayum.isGroupInstalled(grp):
            self.xml.get_widget("detailsButton").set_sensitive(False)
            self.xml.get_widget("optionalLabel").set_text("")
        else:
            self.xml.get_widget("detailsButton").set_sensitive(True)
            txt = _("Optional packages selected: %(inst)d of %(cnt)d") \
                    % {'inst': inst, 'cnt': cnt}
            self.xml.get_widget("optionalLabel").set_markup(_("<i>%s</i>") %(txt,))

    def _groupToggled(self, widget, path, sel = None, updateText = True):
        if type(path) == type(str):
            i = self.groupstore.get_iter_from_string(path)
        else:
            i = self.groupstore.get_iter(path)
        if sel is None:
            sel = not self.groupstore.get_value(i, 0)
            
        self.groupstore.set_value(i, 0, sel)
        grp = self.groupstore.get_value(i, 2)

        self.vbox.window.set_cursor(gdk.Cursor(gdk.WATCH))
        
        if sel:
            self.ayum.selectGroup(grp.groupid)
        else:
            self.ayum.deselectGroup(grp.groupid)
            # FIXME: this doesn't mark installed packages for removal.
            # we probably want that behavior with s-c-p, but not anaconda

        if updateText:
            self.__setGroupDescription(grp)

        self.vbox.window.set_cursor(None)

    def populateCategories(self):
        self.catstore.clear()
        cats = self.ayum.comps.categories
        cats.sort(ui_comps_sort)
        for cat in cats:
            if not _catHasGroupWithPackages(cat, self.ayum):
                continue
            s = "<span size=\"large\" weight=\"bold\">%s</span>" % xmltrans(cat.name, cat.translated_name)
            self.catstore.append(None, [s, cat])

        # select the first category
        i = self.catstore.get_iter_first()
        if i is not None:
            sel = self.xml.get_widget("categoryList").get_selection()
            sel.select_iter(i)

    def _setupCatchallCategory(self):
        # FIXME: this is a bad hack, but catch groups which aren't in
        # a category yet are supposed to be user-visible somehow.
        # conceivably should be handled by yum
        grps = {}
        for g in self.ayum.comps.groups:
            if g.user_visible and self.ayum._groupHasPackages(g):
                grps[g.groupid] = g

        for cat in self.ayum.comps.categories:
            for g in cat.groups:
                if grps.has_key(g):
                    del grps[g]

        if len(grps.keys()) == 0:
            return
        c = yum.comps.Category()
        c.name = _("Uncategorized")
        c._groups = grps
        c.categoryid = "uncategorized"

        self.ayum.comps._categories[c.categoryid] = c

    def doRefresh(self):
        if len(self.ayum.comps.categories) == 0:
            self.xml.get_widget("categorySW").hide()
            self._populateGroups(map(lambda x: x.groupid,
                                     self.ayum.comps.groups))
        else:
            self._setupCatchallCategory()
            self.populateCategories()

    def _getSelectedGroup(self):
        """Return the selected group.
        NOTE: this only ever returns one group."""
        selection = self.xml.get_widget("groupList").get_selection()
        (model, paths) = selection.get_selected_rows()
        for p in paths:
            return model.get_value(model.get_iter(p), 2)
        return None
    
    def _optionalPackagesDialog(self, *args):
        group = self._getSelectedGroup()
        if group is None:
            return

        pwin = self.vbox.get_parent() # hack to find the parent window...
        while not isinstance(pwin, gtk.Window):
            pwin = pwin.get_parent()
        d = OptionalPackageSelector(self.ayum, group, pwin, self.getgladefunc)
        if self.framefunc:
            self.framefunc(d.window)
        rc = d.run()
        d.destroy()
        self.__setGroupDescription(group)

    def _groupSelect(self, *args):
        selection = self.xml.get_widget("groupList").get_selection()
        if selection.count_selected_rows() == 0:
            return

        (model, paths) = selection.get_selected_rows()
        for p in paths:
            self._groupToggled(model, p, True, updateText=(len(paths) == 1))

    def _groupDeselect(self, *args):
        selection = self.xml.get_widget("groupList").get_selection()
        if selection.count_selected_rows() == 0:
            return

        (model, paths) = selection.get_selected_rows()
        for p in paths:
            self._groupToggled(model, p, False, updateText=(len(paths) == 1))

    def _selectAllPackages(self, *args):
        selection = self.xml.get_widget("groupList").get_selection()
        if selection.count_selected_rows() == 0:
            return
        (model, paths) = selection.get_selected_rows()

        self.vbox.window.set_cursor(gdk.Cursor(gdk.WATCH))

        for p in paths:
            i = model.get_iter(p)
            grp = model.get_value(i, 2)

            # ensure the group is selected
            self.ayum.selectGroup(grp.groupid)
            model.set_value(i, 0, True)
        
            for pkg in grp.default_packages.keys() + \
                    grp.optional_packages.keys():
                if self.ayum.isPackageInstalled(pkg):
                    continue
                elif self.ayum.simpleDBInstalled(name = pkg):
                    txmbrs = self.ayum.tsInfo.matchNaevr(name = pkg)
                    for tx in txmbrs:
                        if tx.output_state == TS_ERASE:
                            self.ayum.tsInfo.remove(tx.pkgtup)
                else:
                    _selectPackage(self.ayum, grp, pkg)

        if len(paths) == 1:
            self.__setGroupDescription(grp)
        self.vbox.window.set_cursor(None)

    def _deselectAllPackages(self, *args):
        selection = self.xml.get_widget("groupList").get_selection()
        if selection.count_selected_rows() == 0:
            return
        (model, paths) = selection.get_selected_rows()
        
        for p in paths:
            i = model.get_iter(p)
            grp = model.get_value(i, 2)

            for pkg in grp.default_packages.keys() + \
                    grp.optional_packages.keys():
                if not self.ayum.isPackageInstalled(pkg):
                    continue
                elif self.ayum.simpleDBInstalled(name=pkg):
                    self.ayum.remove(name=pkg)
                else:
                    _deselectPackage(self.ayum, grp, pkg)
        if len(paths) == 1:
            self.__setGroupDescription(grp)

    def __doGroupPopup(self, button, time):
        menu = self.groupMenu
        menu.popup(None, None, None, button, time)
        menu.show_all()

    def _groupListButtonPress(self, widget, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            pthinfo = widget.get_path_at_pos(x, y)
            if pthinfo is not None:
                sel = widget.get_selection()
                if sel.count_selected_rows() == 1:
                    path, col, cellx, celly = pthinfo                    
                    widget.grab_focus()
                    widget.set_cursor(path, col, 0)
                self.__doGroupPopup(event.button, event.time)
            return 1

    def _groupListPopup(self, widget):
        sel = widget.get_selection()
        if sel.count_selected_rows() > 0:
            self.__doGroupPopup(0, 0)
        
        
