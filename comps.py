#
# comps.py: header list and component set (package groups) management
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
# Jeremy Katzj <katzj@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import rpm
import os
from string import *
import types
import urllib2
import time
import language

from rhpl.log import log
from rhpl.translate import _, N_
import rhpl.comps

ExcludePackages = { 'XFree86-3DLabs' : None, 	'XFree86-8514' : None,
                    'XFree86-AGX' : None, 	'XFree86-I128' : None,
                    'XFree86-Mach32' : None, 	'XFree86-Mach64' : None,
                    'XFree86-Mach8' : None, 	'XFree86-Mono' : None,
                    'XFree86-P9000' : None, 	'XFree86-S3' : None,
                    'XFree86-S3V' : None, 	'XFree86-SVGA' : None,
                    'XFree86-VGA16' : None,	'XFree86-W32' : None,

                    'kernel' : None,		'kernel-BOOT' : None,
                    'kernel-smp' : None,	'kernel-bigmem' : None,
                    'kernel-vrdr' : None,	'kernel-tape' : None,
                    'kernel-BOOTtape' : None,	'kernel-BOOTvrdr' : None,
                    'kernel-summit' : None,

                    'kinput2-canna' : None,	'kinput-canna-wnn4' : None,
                    'kinput2-wnn4' : None,	'kinput2-wnn6' : None }

# Package selection is complicated. Here are the rules:
#
# Calling package.select() forces the package on. No other rules apply.
# Calling package.unselect() forces the package off. No other rules apply.
#
# Else:
#
# Each package contains a list of components that include it.  Each
# registered component is checked to see if it and all its parent
# components are on (this is done by recursive checking of 
# parent.isSelected()).  Some subcomps are keyed on the state of
# another toplevel component.  If a component, all of its ancestors,
# and conditional components are selected, the package is selected.
# Otherwise it is not.
#

CHECK_COMPS	= 0
FORCE_SELECT	= 1
FORCE_UNSELECT	= 2


PKGTYPE_MANDATORY = 0
PKGTYPE_DEFAULT = 1
PKGTYPE_OPTIONAL = 2

class Package:
    def __getitem__(self, item):
	return self.h[item]

    def __repr__(self):
	return "%s" % self.name

    def select(self):
	self.state = FORCE_SELECT
	self.selected = 1

    def unselect(self):
	self.state = FORCE_UNSELECT
	self.selected = 0

    def isSelected(self):
	return self.selected

    def wasForcedOff(self):
        if self.state == FORCE_UNSELECT and not self.selected:
            return 1
        else:
            return 0

    def updateSelectionCache(self):
	if self.state == FORCE_SELECT or self.state == FORCE_UNSELECT:
	    return

	self.selected = 0
	for comp in self.comps:
	    on = 1
            # if this component is selected for any reason at all,
            # the package is not selected.
            if not comp.isSelected(justManual = 0):
                on = 0
            else:
                # if the component is on, check to see if this package
                # was listed with an expression conditional in the comps
                # file.  If it did, we'll find a list of expressions
                # in the component's package dictionary.  If any of them
                # evaluates to be true, the package is selected.
                if comp.pkgDict[self] != None:
                    on = 0
                    for expr in comp.pkgDict[self]:
                        if comp.set.exprMatch (expr):
                                on = 1
                                # one is sufficient
                                break
            if on:
                self.selected = 1
                # one component is sufficient in the "package is selected"
                # case, stop looking to save time.
                break

    def getState(self):
	return (self.state, self.selected)

    def setState(self, state):
	(self.state, self.selected) = state

    def registerComponent(self, comp):
        if comp not in self.comps:
            self.comps.append(comp)

    def unregisterComponent(self, comp):
        try:
            self.comps.remove(comp)
        except:
            log("WARNING: Unable to unregister %s for pkg %s" % (comp, self.name))
            pass

    def __init__(self, header):
	self.h = header
	self.comps = []
	self.selected = 0
	self.state = CHECK_COMPS
	self.name = header[rpm.RPMTAG_NAME]
	self.size = header[rpm.RPMTAG_SIZE]

class HeaderList:
    def selected(self):
	l = []
 	keys = self.packages.keys()
	keys.sort()
	for name in keys:
	    if self.packages[name].selected: l.append(self.packages[name])
	return l

    def has_key(self, item):
	return self.packages.has_key(item)

    def keys(self):
        return self.packages.keys()

    def values(self):
        return self.packages.values()

    def __getitem__(self, item):
	return self.packages[item]

    def list(self):
	return self.packages.values()

    def mergeFullHeaders(self, file):
        if self.hasFullHeaders:
            return
        fd = os.open(file, os.O_RDONLY)
        rpm.mergeHeaderListFromFD(self.hdlist, fd, 1000004)
        os.close(fd)
        self.hasFullHeaders = 1

    def preordered(self):
        preordered = 1
	for h in self.selected():
            if h[1000003] == None:
                preordered = 0
        return preordered

    def __init__(self, hdlist, compatPackages = None, noscore = 0):
        self.hdlist = hdlist
	self.packages = {}
	newCompat = []
        self.hasFullHeaders = 0
	for h in hdlist:
	    name = h[rpm.RPMTAG_NAME]
            if noscore:
                self.packages[name] = Package(h)
                continue
	    score1 = rpm.archscore(h['arch'])
	    if (score1):
		if self.packages.has_key(name):
		    score2 = rpm.archscore(self.packages[name].h['arch'])
		    if (score1 < score2):
			newCompat.append(self.packages[name])
			self.packages[name] = Package(h)
		    else:
			newCompat.append(Package(h))
		else:
		    self.packages[name] = Package(h)
        if hdlist and not self.packages:
            raise RuntimeError, ("the header list was read, but no packages "
                                 "matching architecture '%s' were found."
                                 % os.uname()[4])

	if compatPackages != None:
            compatPackages.extend(newCompat)

class HeaderListFromFile (HeaderList):

    def __init__(self, path, compatPackages = None, noscore = 0):
	hdlist = rpm.readHeaderListFromFile(path)
	HeaderList.__init__(self, hdlist, compatPackages = compatPackages,
			    noscore = noscore)

class HeaderListFD (HeaderList):
    def __init__(self, fd):
	hdlist = rpm.readHeaderListFromFD (fd)
	HeaderList.__init__(self, hdlist)

# A component has a name, a selection state, a list of included components,
# and a list of packages whose selection depends in some way on this component 
# being selected. Selection and deselection recurses through included 
# components.
#
# When the component file is parsed, the comp lists that include each
# package are built up. Component selection is used by the packages to
# determine whether or not they are selected.
#
# The selection state consists of a manually selected flag and an included
# selection count. They are separate to make UI coding easier.

class Component:
    def __len__(self):
	return len(self.pkgDict.keys())

    def __repr__(self):
	return "comp %s" % (self.name)

    def packages(self):
	return self.pkgDict.keys()

    # return dictionary of packages in component with full info from xml comps
    def packagesFullInfo(self):
	return self.newpkgDict
    
    def metapackagesFullInfo(self):
	return self.metapkgs
    
    def includesPackage(self, pkg, includeDeps = 0):
        if not self.pkgDict.has_key(pkg):
            return 0
        if self.pkgDict[pkg] == None:
            return 1
        # if this package is the component with a condition,
        # check to see if the condition is met before saying that
        # the package is included in this component
        for expr in self.pkgDict[pkg]:
            if self.set.exprMatch (expr):
                return 1
        return 0

    def select(self, forInclude = 0, toplevel = 1):
	if forInclude:
            self.selectionCount = self.selectionCount + 1
	else:
	    self.manuallySelected = 1

	for name in self.includes:
            if not self.set.has_key(name):
                log ("warning, unknown toplevel component %s "
                     "included by component %s", name, self.name)
            self.set[name].select(forInclude = 1, toplevel = 0)

        for comp in self.metapkgs.keys():
            if self.metapkgs[comp][1] == 1:
                comp.select(forInclude = 1, toplevel = 0)

        if toplevel:
            self.set.updateSelections()

    def includeMembers(self):
        for name in self.includes:
            if not self.set.has_key(name):
                log ("warning, unknown toplevel component %s "
                     "included by component %s", name, self.name)
            self.set[name].select(forInclude = 0, toplevel = 0)

        self.set.updateSelections()

    def isSelected(self, justManual = 0):
        if self.conditionalKey:
            if not self.set.has_key(self.conditionalKey):
                log ("warning, unknown conditional trigger %s wanted by %s",
                     self.conditionalKey, self.name)
                return 0
            else:
                if (self.set[self.conditionalKey].isSelected()
                    and self.parent.isSelected()):
                    return 1
                return 0

	# don't admit to selection-by-inclusion
	if justManual:
	    return self.manuallySelected

	return self.manuallySelected or (self.selectionCount > 0)

    def unselect(self, forInclude = 0, toplevel = 1):
	if forInclude:
	    self.selectionCount = self.selectionCount - 1
	    if self.selectionCount < 0:
		self.selectionCount = 0
	else:
	    self.manuallySelected = 0

	for name in self.includes:
            if not self.set.has_key(name):
                log ("warning, unknown toplevel component %s "
                     "included by component %s", name, self.name)
            self.set[name].unselect(forInclude = 1, toplevel = 0)

        for comp in self.metapkgs.keys():
            if self.metapkgs[comp][1] == 1:
                comp.unselect(forInclude = 1, toplevel = 0)

        if toplevel:
            self.set.updateSelections()

    def addInclude(self, comp):
	self.includes.append(comp)

    def addMetaPkg(self, comp, isDefault = 0):
        self.metapkgs[comp] = (PKGTYPE_OPTIONAL, isDefault)

    def addPackage(self, p, pkgtype, handleDeps = 1):
        if pkgtype == PKGTYPE_MANDATORY:
            p.registerComponent(self)
            self.newpkgDict[p] = (pkgtype, 1)
            self.pkgDict[p] = None
            if handleDeps == 1:
                self.updateDependencyCountForAddition(p)            
        elif pkgtype == PKGTYPE_DEFAULT:
            p.registerComponent(self)
            self.newpkgDict[p] = (PKGTYPE_OPTIONAL, 1)
            self.pkgDict[p] = None
            if handleDeps == 1:            
                self.updateDependencyCountForAddition(p)            
        elif pkgtype == PKGTYPE_OPTIONAL:
            self.newpkgDict[p] = (PKGTYPE_OPTIONAL, 0)
        else:
            log("Unable to add package %s to component %s because it has an unknown pkgtype of %d" %(p.name, self.name, pkgtype))

    def addDependencyPackage(self, p):
        if not self.depsDict.has_key(p):
            self.depsDict[p.name] = 1
            # make sure it's registered in this component
            p.registerComponent(self)
            # and it also has to be in the pkgDict
            self.pkgDict[p] = None
        else:
            self.depsDict[p.name] = self.depsDict[p.name] + 1

    def selectOptionalPackage(self, p):
        if isinstance(p, Package):
            if p not in self.newpkgDict.keys():
                log("%s not in pkgDict for component %s" % (p.name, self.name))
            else:
                # dont ref count more than once
                if p in self.pkgDict.keys():
                    log("%s already enabled in pkgDict for component %s" % (p.name, self.name))
                    return

                self.newpkgDict[p] = (PKGTYPE_OPTIONAL, 1)
                p.registerComponent(self)
                self.pkgDict[p] = None
                # up the refcount since, otherwise, when you have things
                # which are deps as optional also, Bad Things Happen (tm)
                if p.name in self.depsDict.keys():
                    self.depsDict[p.name] = self.depsDict[p.name] + 1
                else:
                    self.depsDict[p.name] = 1
                
                self.updateDependencyCountForAddition(p)
        elif isinstance(p, Component):
            p.select(forInclude = 1, toplevel = 0)
            self.metapkgs[p] = (PKGTYPE_OPTIONAL, 1)
        else:
            log("don't know how to select %s" %(p,))
        self.set.updateSelections()

    def unselectOptionalPackage(self, p):
        if isinstance(p, Package):        
            if p not in self.pkgDict.keys():
                log("%s not in pkgDict for component %s" % (p.name, self.name))
            else:
                self.newpkgDict[p] = (PKGTYPE_OPTIONAL, 0)
                p.unregisterComponent(self)
                if self.pkgDict.has_key(p):
                    del self.pkgDict[p]
                # dec the refcount since, otherwise, when you have things
                # which are deps as optional also, Bad Things Happen (tm)
                if p.name in self.depsDict.keys():
                    self.depsDict[p.name] = self.depsDict[p.name] - 1
                    if self.depsDict[p.name] == 0:
                        del self.depsDict[p.name]
                self.updateDependencyCountForRemoval(p)
        elif isinstance(p, Component):
            p.unselect(forInclude = 1, toplevel = 0)
            self.metapkgs[p] = (PKGTYPE_OPTIONAL, 0)
        else:
            log("don't know how to unselect %s" %(p,))
        self.set.updateSelections()
        
    def updateDependencyCountForAddition(self, p):
        pkgs = [ p ]
        checked = []
        while len(pkgs) > 0:
            tocheck = pkgs
            pkgs = []
            for pkg in tocheck:
                pkg = pkg.name
                # make sure the package is in the package list
                if not self.set.compsxml.packages.has_key(pkg):
                    log("Component %s needs package %s which doesn't exist"
                        %(self.name, pkg))
                    continue
                deps = self.set.compsxml.packages[pkg].dependencies
                for dep in deps:
                    # really needs to be in the hdlist
                    if not self.set.packages.has_key(dep):
                        log("Package %s requires %s which we don't have"
                            %(tocheck, dep))
                        continue
                    # if we've already checked for this package, don't worry
                    if dep in checked:
                        continue
                    # up the refcount on the dependency
                    if dep in self.depsDict.keys():
                        self.depsDict[dep] = self.depsDict[dep] + 1
                    else:
                        self.depsDict[dep] = 1
                        # make sure it's registered in this component
                        self.set.packages[dep].registerComponent(self)
                        # and it also has to be in the pkgDict
                        self.pkgDict[self.set.packages[dep]] = None
                    pkgs.append(self.set.packages[dep])
                    checked.append(dep)

    def updateDependencyCountForRemoval(self, p):
        pkgs = [ p ]
        checked = []
        while len(pkgs) > 0:
            tocheck = pkgs
            pkgs = []
            for pkg in tocheck:
                pkg = pkg.name
                # make sure the package is in the package list
                if not self.set.compsxml.packages.has_key(pkg):
                    log("Component %s needs package %s which doesn't exist"
                        %(self.name, pkg))
                    continue
                deps = self.set.compsxml.packages[pkg].dependencies
                for dep in deps:
                    # really needs to be in the hdlist
                    if not self.set.packages.has_key(dep):
                        log("Package %s requires %s which we don't have"
                            %(tocheck, dep))
                        continue
                    # if we've already checked for this package, don't worry
                    if dep in checked:
                        continue
                    # up the refcount on the dependency
                    if dep in self.depsDict.keys():
                        self.depsDict[dep] = self.depsDict[dep] - 1
                        if self.depsDict[dep] == 0:
                            self.set.packages[dep].unregisterComponent(self)
                            # remove it from the pkgDict
                            if self.pkgDict.has_key(self.set.packages[dep]):
                                del self.pkgDict[self.set.packages[dep]]
                            else:
                                log("tried to remove %s and failed" %(self.set.packages[dep],))
                            del self.depsDict[dep]
                    else:
                        log("WARNING: trying to reduce refcount on dep %s in group %s without being in deps dict" % (dep, self.name))
                    pkgs.append(self.set.packages[dep])
                    checked.append(dep)

    def setDefault(self, default):
        self.default = default

    def setDefaultSelection(self):
	if self.default:
	    self.select()

    def getState(self):
	return (self.manuallySelected, self.selectionCount)

    def setState(self, state):
	(self.manuallySelected, self.selectionCount) = state

    def __init__(self, set, compgroup, packages,
                 conditionalKey = "", parent=None,
                 langs = [], doDeps = 1):

        self.set = set

        # set the name and description based on the language
        # we have to keep self.name as english, though, to avoid
        # confusion with kickstart and a lot of our referencing that
        # should be by groupid :/
        self.name = compgroup.name
        self.displayName = None
	self.description = None
        for lang in langs:
            if self.displayName is None and compgroup.translated_name.has_key(lang):
                self.displayName = compgroup.translated_name[lang]
            if (self.description is None and
                compgroup.translated_description.has_key(lang)):
                self.description = compgroup.translated_description[lang]
        # if we didn't find a translation, fall back to english
        if self.displayName is None:
            self.displayName = compgroup.name
        if self.description is None:
            self.description = compgroup.description

        self.hidden = not compgroup.user_visible
        self.default = compgroup.default
        self.comp = compgroup
        self.id = compgroup.id
	
        # do we use these anymore?
        self.conditionalKey = conditionalKey
        self.parent = parent

        self.pkgDict = {}
        self.newpkgDict = {}
        self.includes = []
        self.metapkgs = {}
        self.manuallySelected = 0
        self.selectionCount = 0
        self.depsDict = {}

        for pkg in compgroup.packages.keys():
            if not packages.has_key(pkg):
                log("%s references package %s which doesn't exist"
                    %(self.name, pkg))
                continue
            (type, name) = compgroup.packages[pkg]
            if type == u'mandatory':
                pkgtype = PKGTYPE_MANDATORY
            elif type == u'default':
                pkgtype = PKGTYPE_DEFAULT
            elif type == u'optional':
                pkgtype = PKGTYPE_OPTIONAL
            else:
                log("Invalid package type of %s for %s in %s; defaulting to optional" % (type, pkg, self.name))
                pkgtype = PKGTYPE_OPTIONAL
            self.addPackage(packages[pkg], pkgtype, doDeps)
                

class ComponentSet:
    def __len__(self):
	return len(self.comps)

    def __getitem__(self, key):
	if (type(key) == types.IntType):
	    return self.comps[key]
	return self.compsDict[key]

    def has_key(self, key):
        return self.compsDict.has_key(key)

    def getSelectionState(self):
	compsState = []
	for comp in self.comps:
	    compsState.append((comp, comp.getState()))

	pkgsState = []
	for pkg in self.packages.list():
	    pkgsState.append((pkg, pkg.getState()))

	return (compsState, pkgsState)

    def setSelectionState(self, pickle):
	(compsState, pkgsState) = pickle

        for (comp, state) in compsState:
	    comp.setState(state)

	for (pkg, state) in pkgsState:
	    pkg.setState(state)
	    
    def sizeStr(self):
	megs = self.size()
	if (megs >= 1000):
	    big = megs / 1000
	    little = megs % 1000
	    return "%d,%03dM" % (big, little)

	return "%dM" % (megs)

    def totalSize(self):
	total = 0
	for pkg in self.packages.list():
	    total = total + (pkg[rpm.RPMTAG_SIZE] / 1024)
	return total

    def size(self):
	size = 0
	for pkg in self.packages.list():
	    if pkg.isSelected(): size = size + (pkg[rpm.RPMTAG_SIZE] / 1024)

	return size / 1024

    def keys(self):
	return self.compsDict.keys()

    def exprMatch(self, expr, tags = [ "lang", "arch" ]):
        # FIXME: okay, we don't have this nonsense right now at least...
        # always assume true
        return 1
        
        theTags = []
        for tag in tags:
            theTags.append(tag)

        # no expression == true
        if not expr:
            return 1

        # XXX preserve backwards compatible behavior
        if self.allLangs and "lang" in theTags:
            theTags.remove ("lang")

        if "lang" in theTags:
            if os.environ.has_key('LINGUAS'):
                langs = split (os.environ['LINGUAS'], ':')
                if len (langs) == 1 and not langs[0]:
                    langs = None
            else:
                if os.environ.has_key('LANG'):
                    langs = [ os.environ['LANG'] ]
                else:
                    langs = None

            if langs == None:
                # no languages specified, install them all
                theTags.remove ("lang")

	if expr[0] != '(':
	    raise ValueError, "leading ( expected"
	expr = expr[1:]
	if expr[len(expr) - 1] != ')':
	    raise ValueError, "bad comps file [missing )]"
	expr = expr[:len(expr) - 1]

	exprList = split(expr, 'and')
	truth = 1
	for expr in exprList:
	    l = split(expr)

            if l[0] == "lang":
                if theTags and "lang" not in theTags:
                    newTruth = 1
                else:
                    if len(l) != 2:
                        raise ValueError, "too many arguments for lang"
                    if l[1] and l[1][0] == "!":
                        newTruth = l[1][1:] not in langs
                    else:
                        newTruth = l[1] in langs
	    elif l[0] == "arch":
                if theTags and "arch" not in theTags:
                    newTruth = 1
                if len(l) != 2:
                    raise ValueError, "too many arguments for arch"
                if l[1] and l[1][0] == "!":
                    newTruth = l[1][1:] not in self.archList
                else:
                    newTruth = l[1] in self.archList
	    else:
		s = "unknown condition type %s" % (l[0],)
		raise ValueError, s

	    truth = truth and newTruth
	return truth

    def readCompsFile(self, filename, packages):
        connected = 0
        while not connected:
            try:
		file = urllib2.urlopen(filename)
            except IOError, (errnum, msg):
		log("IOError %s occurred getting %s: %s", filename,
			errnum, str(msg))
                time.sleep(5)
            else:
                connected = 1

        self.compsxml = rhpl.comps.Comps(file)
        file.close()

        self.comps = []
        self.compsDict = {}
        self.compsById = {}

        groups = self.compsxml.groups.keys()
        groups.sort()

        # be leet and construct an everything group
        everything = rhpl.comps.Group(self.compsxml)
        everything.name = N_("Everything")
        everything.id = "everything"
        for pkg in packages.keys():
            if ExcludePackages.has_key(packages[pkg]['name']):
                continue
            everything.packages[pkg] = (u'mandatory', pkg)
        self.compsxml.groups['Everything'] = everything
        groups.append('Everything')

        if os.environ.has_key("LANG"):
            langs = language.expandLangs(os.environ["LANG"])
        else:
            langs = []

        # we have to go through first and make Comp objects for all
        # of the groups.  then we can go through and set up the includes
        for group in groups[:-1]:
            group = self.compsxml.groups[group]
            comp = Component(self, group, packages, langs = langs)
            self.comps.append(comp)
            self.compsDict[comp.name] = comp
            self.compsById[comp.id] = comp

        # special case everything to make it faster...
        for group in [ groups[-1] ]:
            group = self.compsxml.groups[group]
            comp = Component(self, group, packages, doDeps = 0, langs = langs)
            # everything really is a hack
            comp.displayName = _("Everything")
            self.comps.append(comp)
            self.compsDict[comp.name] = comp
            self.compsById[comp.id] = comp

        for group in groups:
            # everything is special and this speeds things up a bit
            if group == "everything":
                continue
            group = self.compsxml.groups[group]            
            comp = self.compsDict[group.name]
            for id in group.groups.keys():
                if not self.compsById.has_key(id):
                    log("%s references component %s which doesn't exist"
                        %(group.name, id))
                    continue
                comp.addInclude(self.compsById[id].name)
            for id in group.metapkgs.keys():
                if not self.compsById.has_key(id):
                    log("%s references component %s which doesn't exist"
                        %(group.name, id))
                    continue
                if group.metapkgs[id][0] == u'default':
                    comp.addMetaPkg(self.compsById[id], isDefault = 1)
                else:
                    comp.addMetaPkg(self.compsById[id], isDefault = 0)

##         everything = Component(self, N_("Everything"), 0, 0)
##         for package in packages.keys ():
## 	    if ExcludePackages.has_key(packages[package][rpm.RPMTAG_NAME]):
##                 continue
##             if self.expressions.has_key (packages[package]): 
##                 expressions = self.expressions[packages[package]]
##                 if expressions == None:
##                     everything.addPackageWithExpression (None,
##                                                          packages[package])
##                 else:
##                     for expression in expressions:
##                         everything.addPackageWithExpression (expression,
##                                                              packages[package])
##             else:
##                 everything.addPackage (packages[package])
##         self.comps.append (everything)
##         self.compsDict["Everything"] = everything

	for comp in self.comps:
	    comp.setDefaultSelection()

    def updateSelections(self):
        if not self.frozen:
            for pkg in self.packages.values():
                pkg.updateSelectionCache()

    def freeze(self):
        self.frozen = self.frozen + 1

    def thaw(self):
        self.frozen = self.frozen - 1
        if not self.frozen:
            self.updateSelections()
        
    def __repr__(self):
	s = ""
	for n in self.comps:
	    s = s + "{ " + n.name + " [";
	    for include in n.includes:
		s = s + " @" + include.name

	    for package in n:
		s = s + " " + str(package)
	    s = s + " ] } "

	return s

    def verifyDeps (self, instPath, upgrade):
        def formatRequire (name, version, flags):
            string = name
            
            if flags:
                if flags & (rpm.RPMSENSE_LESS | rpm.RPMSENSE_GREATER | 
                            rpm.RPMSENSE_EQUAL):
                    string = string + " "
                    if flags & rpm.RPMSENSE_LESS:
                        string = string + "<"
                    if flags & rpm.RPMSENSE_GREATER:
                        string = string + ">"
                    if flags & rpm.RPMSENSE_EQUAL:
                        string = string + "="
                    string = string + " %s" % version
            return string

        # if we still have the same packages selected, bail - we don't need to
        # do this again.
        if self.verifiedState == self.getSelectionState()[1]:
            return []

        self.verifiedState = None

	checkDeps = 1
	rc = []
        extras = {}
	while checkDeps:
            if upgrade:
                ts = rpm.TransactionSet(instPath, rpm.RPMVSF_NOHDRCHK)
                how = 'u'
            else:
                ts = rpm.TransactionSet()
                how = 'i'

            ts.setVSFlags(~(rpm.RPMVSF_NODSA|rpm.RPMVSF_NORSA))

            for p in self.packages.values():
                if p.selected:
                    ts.addInstall(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), how)
                else:
                    if extras.has_key(p.h):
                        ts.addInstall(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), how)
                    else:
                        ts.addInstall(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), "a")

	    deps = ts.check()
	    checkDeps = 0

	    if not deps:
		break

            for ((name, version, release),
                 (reqname, reqversion),
                 flags, suggest, sense) in deps:
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if suggest:
                        (header, sugname) = suggest
                        log ("depcheck: package %s needs %s (provided by %s)",
                             name, formatRequire(reqname, reqversion, flags),
                             sugname)
                        extras[header] = None
			checkDeps = 1
                    else:
                        log ("depcheck: package %s needs %s (not provided)",
                             name, formatRequire(reqname, reqversion, flags))
                        sugname = _("no suggestion")
                    if not (name, sugname) in rc:
                        rc.append ((name, sugname))
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
		    # We need to check if the one we are going to
		    # install is ok.
		    conflicts = 1
		    if reqversion:
			fields = split(reqversion, '-')
			if (len (fields) == 2):
			    needed = ("", fields [0], fields [1])
			else:
			    needed = ("", fields [0], "")
                        try:
                            h = self.packages[reqname].h
                        except KeyError:
                            # we don't actually have the conflicting package
                            # in our available packages, the conflict is
                            # on the system.  Continue on.
                            continue
			installed = ("", h[rpm.RPMTAG_VERSION],
				     h [rpm.RPMTAG_RELEASE])
			if rpm.labelCompare (installed, needed) >= 0:
			    conflicts = 0

		    if conflicts:
			log ("%s-%s-%s conflicts with older "
                             "package %s-%s, removing %s from set",
                             name, version, release, reqname, reqversion, reqname)
			if self.packages.packages.has_key (reqname):
			    self.packages.packages[reqname].selected = 0
			    log ("... removed")

        ts.closeDB()
        del ts

        if not rc: 
            self.verifiedState = self.getSelectionState()[1]

        return rc

    def selectDepCause (self, deps):
	for (who, dep) in deps:
	    if self.packages.has_key(who):
                self.packages[who].select ()

    def unselectDepCause (self, deps):
	for (who, dep) in deps:
	    if self.packages.has_key(who):            
                self.packages[who].unselect ()

    def selectDeps (self, deps):
	for (who, dep) in deps:
	    if self.packages.has_key(dep):
		self.packages[dep].select ()

    def unselectDeps (self, deps):
	for (who, dep) in deps:
	    if self.packages.has_key(dep):
		self.packages[dep].unselect ()

    def canResolveDeps (self, deps):
        canresolve = 0
        if deps:
            for (who, dep) in deps:
                if dep != _("no suggestion"):
                    canresolve = 1
        return canresolve

    def kernelVersionList(self):
	kernelVersions = []

	# nick is used to generate the lilo name
	for (ktag, nick) in [ ('kernel-summit', 'summit'),
                              ('kernel-bigmem', 'bigmem'),
			      ('kernel-smp', 'smp'),
			      ('kernel-tape', 'tape') ]:
	    tag = split(ktag, '-')[1]
	    if (self.packages.has_key(ktag) and 
		self.packages[ktag].selected):
		version = (self.packages[ktag][rpm.RPMTAG_VERSION] + "-" +
			   self.packages[ktag][rpm.RPMTAG_RELEASE] + tag)
		kernelVersions.append((version, nick))

        if (self.packages.has_key('kernel') and
            self.packages['kernel'].selected):
            version = (self.packages['kernel'][rpm.RPMTAG_VERSION] + "-" +
                       self.packages['kernel'][rpm.RPMTAG_RELEASE])
            kernelVersions.append((version, 'up'))
 
	return kernelVersions

    def __init__(self, file, hdlist, arch = None, matchAllLang = 0):
        self.frozen = 0
        self.allLangs = matchAllLang
        self.archList = []
	self.verifiedState = None
	if not arch:
	    import iutil
	    arch = iutil.getArch()
            self.archList.append(arch)
            # always set since with can have i386 arch with i686 arch2,
            # for example:
            #   arch2 = None
            #   if arch == "sparc" and os.uname ()[4] == "sparc64":
            #	    arch2 = "sparc64"
            #
            arch2 = os.uname ()[4]
            if not arch2 in self.archList:
                self.archList.append (arch2)
        else:
            self.archList.append(arch)
        
	self.packages = hdlist
	self.readCompsFile(file, self.packages)


# this is a temporary way to set order of packages
def orderPackageGroups(curgroups):
    compsParents = curgroups.compsxml.hierarchy.order
    compsHierarchy = curgroups.compsxml.hierarchy

    grpids = []
    for grp in curgroups:
	grpids.append(grp.id)

    ignorelst = []
    retlist = []
    retdict = {}
 
    if os.environ.has_key("LANG"):
        langs = language.expandLangs(os.environ["LANG"])
    else:
        langs = []
   
    for key in compsParents:

        # get the translated name
        myname = None
        if not compsHierarchy.translations.has_key(key):
            myname = key
        else:
            for lang in langs:
                if compsHierarchy.translations[key].has_key(lang):
                    myname = compsHierarchy.translations[key][lang]
                    break
            if myname is None:
                myname = key
        
        retlist.append(myname)
        retdict[myname] = []
        
	compslist = compsHierarchy[key]
	for grp in compslist:

	    if grp in grpids:
                thecomp = curgroups.compsById[grp]
		ignorelst.append(grp)
                retdict[myname].append(thecomp)

    miscgrp = _("Miscellaneous")
    for grp in grpids:
	if grp in ignorelst:
	    continue

        thecomp = curgroups.compsById[grp]
	if miscgrp not in retlist:
	    retlist.append(miscgrp)
	    retdict[miscgrp] = [thecomp]
	else:
	    retdict[miscgrp].append(thecomp)
		    
    return (retlist, retdict)

def getCompGroupDescription(comp):
    if comp.name == u"Everything":
	return _("This group includes all the packages available.  Note that "
		 "this is substantially more packages than just the ones "
		 "in all the other package groups on this page.")
    elif comp.name == u"Base":
	return _("Choose this group to get the minimal possible set of "
		 "packages.  Useful for creating small router/firewall "
		 "boxes, for example.")
    
    descr = comp.description
    if descr:
	return _(descr)
    else:
	return None
