#
# comps.py: header list and component set (package groups) management
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
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
import urllib
import time

from rhpl.log import log
from rhpl.translate import _, N_

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


                    # XXX this is a hack.  remove me.
                    "rpm404-python",

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
	self.comps.append(comp)

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
	return len(self.pkgs)

    def __repr__(self):
	return "comp %s" % (self.name)

    def packages(self):
	return self.pkgs

    def includesPackage(self, pkg):
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

        if toplevel:
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

        if toplevel:
            self.set.updateSelections()

    def addInclude(self, comp):
	self.includes.append(comp)

    def addPackage(self, p):
	self.pkgs.append(p)
	p.registerComponent(self)
	self.pkgDict[p] = None

    def addPackageWithExpression(self, expr, p):
        if not self.pkgDict.has_key (p):
            self.pkgDict[p] = [ expr ]
            self.pkgs.append(p)
            p.registerComponent(self)
        else:
            if type (self.pkgDict[p]) == type ([]):
                self.pkgDict[p].append (expr)
            else:
                self.pkgDict[p] = [ expr ]

    def setDefault(self, default):
        self.default = default

    def setDefaultSelection(self):
	if self.default:
	    self.select()

    def getState(self):
	return (self.manuallySelected, self.selectionCount)

    def setState(self, state):
	(self.manuallySelected, self.selectionCount) = state

    def __init__(self, set, name, selected, hidden = 0, conditionalKey = "",
                 parent=None):
        self.set = set
	self.name = name
	self.hidden = hidden
	self.default = selected
        self.conditionalKey = conditionalKey
        self.parent = parent
	self.pkgs = []
	self.pkgDict = {}
	self.includes = []
	self.manuallySelected = 0
	self.selectionCount = 0

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
		file = urllib.urlopen(filename)
            except IOError, (errnum, msg):
		log("IOError %s occured getting %s: %s", filename,
			errnum, str(msg))
                time.sleep(5)
            else:
                connected = 1

	lines = file.readlines()

	file.close()
	top = lines[0]
	lines = lines[1:]
	if (top != "3\n" and top != "4\n"):
	    raise TypeError, "comp file version 3 or 4 expected"
	
	comp = None
	self.comps = []
	self.compsDict = {}
        self.expressions = {}
        state = [ None ]
	for l in lines:
	    l = strip (l)
	    if (not l): continue
            expression = None

	    if (find(l, ":") > -1):
		(expression, l) = split(l, ":", 1)
                expression = strip (expression)
                l = strip(l)
                if expression and not expression[0] == '(':
                    # normalize expressions to all be of () type
                    expression = "(arch %s)" % (expression,)
                if not self.exprMatch (expression, tags = [ "arch" ]):
                    continue

	    if (find(l, "?") > -1):
                (trash, cond) = split (l, '?', 1)
                (cond, trash) = split (cond, '{', 1)
                cond = strip(cond)
                conditional = "%s/%s" % (comp.name, cond)
                # push our parent onto the stack, we'll need to restore
                # it when this subcomp comes to a close.
                parent = comp
                state.append(parent)
                comp = Component(self, conditional, 0, 1, cond, parent)
                continue

	    if (comp == None):
		(default, l) = split(l, None, 1)
		hidden = 0
                if (l.startswith('--hide')):
		    hidden = 1
		    (foo, l) = split(l, None, 1)
                (l, trash) = split(l, '{', 1)
                l = strip (l)
                if l == "Base" and expression == None:
                    hidden = 1
		comp = Component(self, l, default == '1', hidden)
	    elif (l == "}"):
                parent = state.pop()
                if parent == None:
                    # toplevel, add it to the set
                    self.comps.append(comp)
                    self.compsDict[comp.name] = comp
                    comp = None
                    state.append(None)
                else:
                    # end of a subcomp group, restore state
                    comp = parent
	    else:
		if (l[0] == "@"):
		    (at, l) = split(l, None, 1)
		    comp.addInclude(l)
		else:
                    if expression:
                        # this is a package with some qualifier prefixing it

                        list = self.expressions.get(packages[l])
                        if type(list) == type([]):
                            list.append(expression)
                        else:
                            self.expressions[packages[l]] = [ expression ]
                        comp.addPackageWithExpression (expression, packages[l])
                    else:
                        # if this package is listed anywhere without an
                        # expression, it can go in Everything.
                        self.expressions[packages[l]] = None
                        # this is a package.
                        comp.addPackage(packages[l])

        everything = Component(self, N_("Everything"), 0, 0)
        for package in packages.keys ():
	    if ExcludePackages.has_key(packages[package][rpm.RPMTAG_NAME]):
                continue
            if self.expressions.has_key (packages[package]): 
                expressions = self.expressions[packages[package]]
                if expressions == None:
                    everything.addPackageWithExpression (None,
                                                         packages[package])
                else:
                    for expression in expressions:
                        everything.addPackageWithExpression (expression,
                                                             packages[package])
            else:
                everything.addPackage (packages[package])
        self.comps.append (everything)
        self.compsDict["Everything"] = everything

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

        if upgrade:
            db = rpm.opendb (0, instPath)
            how = 'u'
        else:
            db = None
            ts = rpm.TransactionSet()
            how = 'i'

	checkDeps = 1
	rc = []
        extras = {}
	while checkDeps:
            if upgrade:
                ts = rpm.TransactionSet(instPath, db)
                how = 'u'
            else:
                ts = rpm.TransactionSet()
                how = 'i'

            for p in self.packages.values():
                if p.selected:
                    ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), how)
                else:
                    if extras.has_key(p.h):
                        ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), how)
                    else:
                        ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), "a")

	    deps = ts.depcheck()
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
			log ("%s-%s-%s conflicts with to-be-installed "
                             "package %s-%s, removing %s from set",
                             name, version, release, reqname, reqversion, reqname)
			if self.packages.packages.has_key (reqname):
			    self.packages.packages[reqname].selected = 0
			    log ("... removed")
            
        del ts
        if db:
            del db

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
	for (ktag, nick) in [ ('kernel-bigmem', 'bigmem'),
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
