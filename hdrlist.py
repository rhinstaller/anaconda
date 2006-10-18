#
# hdrlist.py: header list and group set management.
# Parts from old anaconda/comps.py
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import rpm
import os,sys,time

from rhpl.log import log
from rhpl.translate import _, N_
import rhpl.comps
import rhpl.arch

from constants import *

import language

ON = 1
MANUAL_ON = 2
DEP_ON = 3
OFF = -1
MANUAL_OFF = -2
MANUAL_NONE = 0
ON_STATES = (ON, MANUAL_ON, DEP_ON)
OFF_STATES = (OFF, MANUAL_OFF)

PKGTYPE_MANDATORY = 0
PKGTYPE_DEFAULT = 1
PKGTYPE_OPTIONAL = 2

EVERYTHING_DESCRIPTION = _("This group includes all the packages available.  "
                           "Note that there are substantially more packages "
                           "than just the ones in all the other package "
                           "groups on this page.")

EverythingExclude = {'kernel' : None,		'kernel-BOOT' : None,
                     'kernel-smp' : None,	'kernel-bigmem' : None,
                     'kernel-summit' : None,    'kernel-enterprise' : None,
                     'kernel-tape' : None,      'kernel-BOOTtape' : None,
                     'kernel-pseries': None,    'kernel-iseries': None,
                     'kernel-unsupported': None,'kernel-smp-unsupported': None,
                     'kernel-bigmem-unsupported': None,
                     'kernel-hugemem': None,
                     'kernel-hugemem-unsupported': None,
                     'kernel-largesmp': None,
                     'kernel-xenU': None, }

def showMem():
    f = open("/proc/self/status", "r")
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.startswith("VmSize:"):
            vmsize = line.split(":")[1].strip()
        if line.startswith("VmRSS:"):
            vmrss = line.split(":")[1].strip()
    print vmsize, vmrss


def nevra(hdr):
    "Convenience function to return the NEVRA in canonical form for a header."
    if hdr[rpm.RPMTAG_EPOCH]:
        epoch = hdr[rpm.RPMTAG_EPOCH]
    else:
        epoch = "0"

    return "%s-%s:%s-%s.%s" %(hdr[rpm.RPMTAG_NAME],
                              epoch,
                              hdr[rpm.RPMTAG_VERSION],
                              hdr[rpm.RPMTAG_RELEASE],
                              hdr[rpm.RPMTAG_ARCH])

def getLangs():
    if os.environ.has_key("LANG"):
        langs = language.expandLangs(os.environ["LANG"])
    else:
        langs = []
    return langs

# poor heuristic for figuring out the best of two packages with the same
# name.  it sucks, but it's the best we've got right now.
# basically, we generally prefer the shorter name with some special-case
# caveats.
def betterPackageForProvides(h1, h2):
    # make sure we don't try to return a bogus arch
    if h1 is not None and rhpl.arch.score(h1['arch']) == 0:
        h1 = None
    if h2 is not None and rhpl.arch.score(h2['arch']) == 0:
        h2 = None
        
    # if one is none, return the other
    if h2 is None:
        return h1
    if h1 is None:
        return h2

    # if we're already being installed, then we're clearly the superior
    # answer
    if h1.isSelected():
        return h1
    if h2.isSelected():
        return h2
    
    # sendmail is preferred over postfix
    if h1['name'] == "sendmail" and h2['name'] == "postfix":
        return h1
    if h2['name'] == "sendmail" and h1['name'] == "postfix":
        return h2

    # we generally prefer non-devel over devel
    if h1['name'].endswith("-devel") and not h2["name"].endswith("-devel"):
        return h2
    if h2['name'].endswith("-devel") and not h1["name"].endswith("-devel"):
        return h1

    # else, shorter name wins
    # this handles glibc-debug, kernel-*, kde2-compat, etc
    if len(h1['name']) < len(h2['name']):
        return h1
    if len(h2['name']) < len(h1['name']):
        return h2

    # compare versions, newer version is better
    cmp = rpm.versionCompare(h1.hdr, h2.hdr)
    if cmp < 0:
        return h2
    elif cmp > 0:
        return h1

    # same package names, which is a better arch?
    score1 = rhpl.arch.score(h1['arch'])
    score2 = rhpl.arch.score(h2['arch'])
    if (score1 < score2):
        return h1
    elif (score2 < score1):
        return h2

    # okay, there's no convincing difference.  just go with the first
    return h1

cached = {}
# returns the best nevra in hdrlist to match dep
# FIXME: doesn't care about EVR right now -- the tree is assumed to be
# sane and dep is just the name
def depMatch(dep, hdrlist):
    # ignore rpmlib
    if dep.startswith("rpmlib("):
        return None
    # try to see if it just exists first
    elif hdrlist.has_key(dep):
        return nevra(hdrlist[dep])
    elif cached.has_key(dep):
        return cached[dep]
    # next, see if its a file dep
    elif dep[0] == "/":
        hdr = None
        for h in hdrlist.pkgs.values():
            l = []
            for f in h.hdr.fiFromHeader():
                l.append(f[0])
            if (dep in l):
                hdr = betterPackageForProvides(h, hdr)
        if hdr is not None:
            # cache all binaries from this package.  helps with, eg, coreutils
            for f in hdr.hdr.fiFromHeader():
                if f[0].find("bin") != -1: cached[f[0]] = nevra(hdr)
            cached[dep] = nevra(hdr)
            return nevra(hdr)

    # else:
    # need to do this even on file deps too because they could be virtual
    # provides such as /usr/sbin/sendmail or /usr/bin/lpr.  
    if 1:
        hdr = None
        for h in hdrlist.pkgs.values():
            if (dep in h[rpm.RPMTAG_PROVIDENAME]):
                hdr = betterPackageForProvides(h, hdr)
        if hdr is not None:
            cached[dep] = nevra(hdr)
            return nevra(hdr)
    return None
    

class DependencyChecker:
    def __init__(self, grpset, how = "i"):
        self.grpset = grpset
        self.added = []
        self.unknown = []
        self.how = how

    # FIXME: this is the simple stupid version.  it doesn't actually handle
    # paying attention to EVR.  
    def callback(self, ts, tag, name, evr, flags):
        if tag == rpm.RPMTAG_REQUIRENAME:
            pkgnevra = depMatch(name, self.grpset.hdrlist)
            if pkgnevra and self.grpset.hdrlist.has_key(pkgnevra):
                hdr = self.grpset.hdrlist[pkgnevra]
            else:
                hdr = None
                
            if hdr is not None and not hdr.isSelected():
                if evr:
                    nevr = "%s-%s" %(name, evr)
                else:
                    nevr = name
                log("using %s to satisfy %s" %(nevra(hdr), nevr))
                ts.addInstall(hdr.hdr, hdr.hdr, self.how)
                hdr.select(isDep = 1)
                self.added.append(nevra(hdr.hdr))

                return -1

        return 1
            

class Package:
    def __init__(self, hdr):
        self.hdr = hdr
        self.usecount = 0
        self.manual_state = MANUAL_NONE
        self.dependencies = []
        self.depsFound = 0

        self.name = self.hdr[rpm.RPMTAG_NAME]

    def getState(self):
        return (self.usecount, self.manual_state)

    def setState(self, state):
        (self.usecount, self.manual_state) = state

    def addDeps(self, deps, main = 1):
        self.dependencies.extend(deps)
        # FIXME: this is a hack so that adding deps for lang support stuff
        # doesn't set depsFound
        if main:
            self.depsFound = 1

    def select(self, isManual = 0, isDep = 0):
        self.usecount = self.usecount + 1
        if isManual:
            if self.manual_state == MANUAL_NONE:
                self.manual_state = MANUAL_ON
            elif self.manual_state == MANUAL_OFF:
                self.manual_state = MANUAL_NONE
        if isDep:
            self.manual_state = DEP_ON

    def unselect(self, isManual = 0):
        self.usecount = self.usecount - 1
        if isManual:
            if self.manual_state == MANUAL_NONE:
                self.manual_state = MANUAL_OFF
            elif self.manual_state == MANUAL_ON:
                self.manual_state = MANUAL_NONE

        # DEBUG
        if self.usecount < 0:
            log("WARNING: usecount for %s dropped below 0 (%d)" %(nevra(self.hdr),self.usecount))

    # if we've been manually turned on or off, follow that
    # otherwise, if the usecount is > 0, then we're selected
    def isSelected(self):
        if self.manual_state == MANUAL_ON or self.manual_state == DEP_ON:
            return 1
        elif self.manual_state == MANUAL_OFF:
            return 0
        elif self.usecount > 0:
            return 1
        else:
            return 0

    def __getitem__(self, item):
        return self.hdr[item]

    def keys(self):
        return self.hdr.keys()

    def __repr__(self):
        return "%s" %(self.nevra(),)

    def getDescription(self):
        return self.hdr[rpm.RPMTAG_SUMMARY]

    def nevra(self):
        return nevra(self.hdr)

class HeaderList:
    def __init__(self, hdlist):
        self.hdlist = hdlist
        self.pkgs = {}
        self.pkgnames = {}

        for h in hdlist:
            nevrastr = nevra(h)
            name = h['name']

            if self.pkgs.has_key(nevra):
                log("Have more than one copy of %s, skipping" %(nevrastr,))
                continue

            self.pkgs[nevrastr] = Package(h)
            if self.pkgnames.has_key(name):
                self.pkgnames[name].append( (nevrastr, h['arch']) )
            else:
                self.pkgnames[name] = [ (nevrastr, h['arch']) ]

        self.hasFullHeaders = None

    def has_key(self, item):
        if self.pkgs.has_key(item):
            return 1
        elif self.getBestNevra(item):
            return 1
        return 0

    def keys(self):
        return self.pkgnames.keys()

    def values(self):
        return self.pkgs.values()

    # this is definite crack rock, but it allows us to avoid tripling
    # our memory usage :(
    # reads an hdlist2 file and merges the header information we split out
    # (things like file lists)
    def mergeFullHeaders(self, file):
        if self.hasFullHeaders is not None:
            return
        fd = os.open(file, os.O_RDONLY)
        rpm.mergeHeaderListFromFD(self.hdlist, fd, 1000004)
        os.close(fd)
        self.hasFullHeaders = 1
 
    def preordered(self):
        preordered = 1
        for h in self.pkgs.values():
            if h.isSelected() and h[1000003] == None:
                preordered = 0
            if h.isSelected() and not 1000003 in h.hdr.keys():
                preordered = 0
        return preordered

    # get the best nevra for the package name.
    # FIXME: surely this can be made faster/less complicated
    # doing scoring everytime seems like it might be overkill
    # then again, it shouldn't be called *that* often so it might not matter
    def getBestNevra(self, item, prefArch = None):
        bestscore = 0
        bestpkg = None

        if not self.pkgnames.has_key(item):
            return None

        # the best nevra is going to be defined by being 1) the best match
        # for the primary arch (eg, x86_64 on AMD64, ppc on pSeries) and
        # if that fails, fall back to the canonical (which could be the same)
        # This will allow us to get the best package by name for both
        # system packages and kernel while not getting the secondary arch
        # glibc.
        if prefArch is not None:
            arches = (prefArch, )
        elif rhpl.arch.getBaseArch() != rhpl.arch.canonArch:
            arches = (rhpl.arch.getBaseArch(), rhpl.arch.canonArch)
        else:
            arches = (rhpl.arch.canonArch, )

        # FIXME: this is a bad bad bad hack.  we should probably tag
        # the kernel in the comps file somehow instead.  basearchonly
        # was sort of intended for this, but ppc is kind of backwards on
        # what basearch means :/
        if item == "kernel":
            arches = (rhpl.arch.canonArch,)
            
        for basearch in arches:
            for (nevra, arch) in self.pkgnames[item]:
                score = rhpl.arch.archDifference(basearch, arch)
                if not score:
                    continue
                
                # get the "best" version
                if bestpkg is not None:
                    cmp = rpm.versionCompare(self.pkgs[nevra].hdr,
                                             self.pkgs[bestpkg].hdr)
                    if cmp < 0:
                        continue
                    elif cmp > 0:
                        bestscore = score
                        bestpkg = nevra
                        continue
                
                if (bestscore == 0) or (score < bestscore):
                    bestpkg = nevra
                    bestscore = score
            if bestpkg is not None:
                return bestpkg
        return bestpkg

    # FIXME: surely this can be made faster/less complicated
    # doing scoring everytime seems like it might be overkill
    # then again, it shouldn't be called *that* often so it might not matter
    def __getitem__(self, item):
        if self.pkgs.has_key(item):
            return self.pkgs[item]

        # explict nevra not specified -- see what we can do
        pkg = self.getBestNevra(item)

        if pkg is None:
            raise KeyError, "No such package %s" %(item,)

        return self.pkgs[pkg]


class HeaderListFromFile (HeaderList):
    def __init__(self, path):
	hdlist = rpm.readHeaderListFromFile(path)
	HeaderList.__init__(self, hdlist)

class Group:
    def __init__(self, grpset, xmlgrp):
        
        self.id = xmlgrp.id
        self.basename = xmlgrp.name

        # We want to have translated name/descriptions
        self.name = None
        self.description = None
        for lang in getLangs():
            if (self.name is None and
                xmlgrp.translated_name.has_key(lang)):
                self.name = xmlgrp.translated_name[lang]
            if (self.description is None and
                xmlgrp.translated_description.has_key(lang)):
                self.description = xmlgrp.translated_description[lang]
        # fall back to english if they're not set and try to see if the
        # translation is in the anaconda.po (eg, Everything)
        if self.name is None:
            self.name = _(xmlgrp.name)
        if self.description is None:
            self.description = xmlgrp.description

        # obviously enough, hidden components aren't shown
        self.hidden = not xmlgrp.user_visible

        # whether or not a group should be enabled by default.  only
        # really matters for custom installs
        self.default = xmlgrp.default

        # if it's a biarch group and we're not a biarch-arch, be hidden and off
        if xmlgrp.biarchonly and rhpl.arch.getMultiArchInfo() is None:
            self.hidden = 1
            self.default = 0

        # figure out the preferred arch.  if this isn't a biarch group,
        # fall back to the normal picking.  if its a biarch group and we
        # are a biarch arch, use the information we've got
        if xmlgrp.biarchonly and rhpl.arch.getMultiArchInfo() is not None:
            (comp, best, biarch) = rhpl.arch.getMultiArchInfo()
            pref = biarch
        else:
            pref = None

        # FIXME: this is a hack to handle language support groups
        self.langonly = xmlgrp.langonly

        # FIXME: do we really want to keep this?  needed to select packages
        self.grpset = grpset
        hdrlist = grpset.hdrlist

        # refcount/manual state just like with packages
        self.usecount = 0
        self.manual_state = MANUAL_NONE

        # included groups (ie groups that are required if we're selected)
        self.groupreqs = []

        self.packages = {}
        for (pkg, (type, name)) in xmlgrp.packages.items():
            if hdrlist.pkgs.has_key(pkg):
                pkgnevra = pkg
            else:
                pkgnevra = hdrlist.getBestNevra(pkg, prefArch = pref)
                
            if pkgnevra is None:
                log("%s references package %s which doesn't exist"
                    %(self.id, pkg))
                continue

            self.packages[pkgnevra] = self.makePackageDict(pkgnevra, type)

        # if we don't have any packages, make it hidden to avoid confusion
        if len(self.packages.keys()) == 0:
            self.hidden = 1

    def getState(self):
        return (self.usecount, self.manual_state)

    def setState(self, state):
        (self.usecount, self.manual_state) = state

    def addGroupRequires(self, grpid):
        if grpid not in self.groupreqs:
            self.groupreqs.append(grpid)

    def addMetaPkg(self, metapkginfo):
        (type, id) = metapkginfo
        if id in self.packages.keys():
            log("already have %s in %s" %(id, self.id))
            return
        self.packages[id] = self.makePackageDict(id, type, isMeta = 1)

    # dict of package info.  nevra and type are obvious
    # state is one of the ON/OFF states
    def makePackageDict(self, pkgnevra, type, installed = 0, isMeta = 0):
        if type == u'mandatory':
            pkgtype = PKGTYPE_MANDATORY
        elif type == u'default':
            pkgtype = PKGTYPE_DEFAULT
        elif type == u'optional':
            pkgtype = PKGTYPE_OPTIONAL
        else:
            log("Invalid package type of %s for %s in %s; defaulting to "
                "optional" % (type, pkgnevra, self.id))
            pkgtype = PKGTYPE_OPTIONAL
        
        return { "nevra": pkgnevra, "type": pkgtype, "state": installed,
                 "meta": isMeta }

    # FIXME: this doesn't seem like the right place for it, but ... :/
    def selectDeps(self, pkgs, uses = 1):
        checked = []
        while len(pkgs) > 0:
            tocheck = pkgs
            pkgs = []
            for pkgnevra in tocheck:
              if pkgnevra in checked:
                  continue
              pkg = self.grpset.hdrlist[pkgnevra]

              # this is a little bit complicated.  we don't want to keep
              # the deps in the comps file (because that gets ugly with biarch)
              # but we also don't want to have to resolve every time
              # (it's slow!).  so, we cache the first time through 
              if pkg.depsFound == 0:
                  deps = pkg[rpm.RPMTAG_REQUIRENAME]
                  thisone = []
                  for dep in deps:
                      # hey wait, this is me!
                      if ((pkg[rpm.RPMTAG_PROVIDENAME] is not None) and
                          (dep in pkg[rpm.RPMTAG_PROVIDENAME])):
                          continue
                      for f in pkg.hdr.fiFromHeader():
                          if f[0] == dep:
                              continue
                      # ignore rpmlib stuff
                      if dep.startswith("rpmlib("):
                          continue
                      p = depMatch(dep, self.grpset.hdrlist)
                      # don't care about self referential deps
                      if p == pkg.nevra():
                          continue
                      if p in checked or p in tocheck or p in pkgs:
                          continue
                      if p is None:
#                          log("ERROR: unable to resolve dep %s" %(dep,))
                          continue

                      self.grpset.hdrlist[p].select()
                      # FIXME: this is a hack so we can make sure the
                      # usecount is bumped high enough for
                      # langsupport packages
                      self.grpset.hdrlist[p].usecount += uses - 1

                      pkgs.append(p)
                      thisone.append(p)
                  pkg.addDeps(thisone)
              else:
                  deps = pkg.dependencies
                  for dep in deps:
                      # if we've already checked for this package, don't worry
                      if dep in checked or dep in tocheck or dep in pkgs:
                          continue
                      # hmm, not in the header list.  we can't do much but
                      # hope for the best
                      if not self.grpset.hdrlist.has_key(dep):
                          log("Package %s requires %s which we don't have"
                              %(tocheck, dep))
                          continue
                      self.grpset.hdrlist[dep].select()
                      # FIXME: this is a hack so we can make sure the usecount
                      # is bumped high enough for langsupport packages
                      self.grpset.hdrlist[dep].usecount += uses - 1
                      pkgs.append(dep)
              checked.append(pkgnevra)


    # FIXME: this doesn't seem like the right place for it, but ... :/
    def unselectDeps(self, pkgs):
        checked = []
        while len(pkgs) > 0:
            tocheck = pkgs
            pkgs = []
            for pkgnevra in tocheck:
                pkg = self.grpset.hdrlist[pkgnevra]

                deps = pkg.dependencies
                for dep in deps:
                    # if we've already checked for this package, don't worry
                    if dep in checked or dep in tocheck or dep in pkgs:
                        continue
                    # hmm, not in the header list.  we can't do much but
                    # hope for the best
                    if not self.grpset.hdrlist.has_key(dep):
                        log("Package %s requires %s which we don't have"
                            %(tocheck, dep))
                        continue
                    self.grpset.hdrlist[dep].unselect()
                    pkgs.append(dep)
                checked.append(pkgnevra)
        

    # forInclude is whether this group is an include from a previous
    # asMeta means that we should include the members of the group,
    # but not this one (useful for Workstation Common, etc)
    def select(self, forInclude = 0, asMeta = 0, selectOptional = 0):
        hdrlist = self.grpset.hdrlist

        # if we're being selected as a meta group, then just select
        # the members.  otherwise, we end up in weirdo states
        if asMeta:
            for grpid in self.groupreqs:
                self.grpset.groups[grpid].select(forInclude = 0)
            return
                
        # update the usecount.  if this is manual, change the state if needed
        # if we were already previously selected, we don't need to bump up
        # refcounts (which makes things faster)
        self.usecount = self.usecount + 1
        if not forInclude:
            self.manual_state = MANUAL_ON

        for grpid in self.groupreqs:
            self.grpset.groups[grpid].select(forInclude = 1)

        if self.usecount > 1:
            return

        selected = []
        for (pkgnevra, pkg) in self.packages.items():
            # if it's not optional, we should turn it on
            if pkg["type"] == PKGTYPE_OPTIONAL and not selectOptional:
                continue
            pkg["state"] = ON
            if pkg["meta"] == 0:
                hdrlist[pkgnevra].select()
                selected.append(pkgnevra)
                self.selectDeps([pkgnevra])                
            else:
                self.grpset.groups[pkgnevra].select(forInclude = 1)

    # manual package selection
    def selectPackage(self, pkgnevra):
        pkg = self.packages[pkgnevra]
        if pkg["state"] in ON_STATES:
            return
        pkg["state"] = ON
        if pkg["meta"] == 0:
            self.grpset.hdrlist[pkgnevra].select()
            self.selectDeps([pkgnevra])
        else:
            self.grpset.groups[pkgnevra].select(forInclude = 1)
            
    def unselect(self, forInclude = 0):
        hdrlist = self.grpset.hdrlist

        # update the usecount.  if this is manual, change the state if needed
        # if we were already previously selected, we don't need to bump up
        # refcounts (which makes things faster)
        self.usecount = self.usecount - 1
        if not forInclude:
            self.manual_state = MANUAL_OFF
        if self.usecount < 0: log("WARNING: usecount for %s < 0 (%d)" %(self.id, self.usecount))

        for grpid in self.groupreqs:
            self.grpset.groups[grpid].unselect(forInclude = 1)

        if self.usecount > 0:
            return

        selected = []
        for pkg in self.packages.values():
            pkgnevra = pkg["nevra"]
            if pkg["state"] not in ON_STATES:
                continue
            pkg["state"] = OFF
            if pkg["meta"] == 0:
                hdrlist[pkgnevra].unselect()
                selected.append(pkgnevra)
                self.unselectDeps([pkgnevra])
            else:
                self.grpset.groups[pkgnevra].unselect(forInclude = 1)

    def unselectPackage(self, pkgnevra):
        pkg = self.packages[pkgnevra]
        if pkg["state"] not in ON_STATES:
            return
        pkg["state"] = OFF
        if pkg["meta"] == 0:
            self.grpset.hdrlist[pkgnevra].unselect()
            self.unselectDeps([pkgnevra])
        else:
            self.grpset.groups[pkgnevra].unselect(forInclude = 1)

    def isSelected(self, justManual = 0):
        if justManual:
            if self.manual_state == MANUAL_ON:
                return 1
            else:
                return 0
        return (self.usecount > 0)

    def packageInfo(self):
        ret = {}
        for pkg in self.packages.values():
            ret[pkg["nevra"]] = (pkg["type"], pkg["state"])

        return ret

    # FIXME: remove this
    def includesPackage(self, pkg):
        pkgnevra = nevra(pkg)
        if self.packages.has_key(pkgnevra):
            return 1

        # make sure it's not in this group for deps
        tocheck = self.packages.keys()
        checked = []
        while len(tocheck) > 0:
            pkgs = tocheck
            tocheck = []
            for p in pkgs:
                if pkgnevra in self.grpset.hdrlist[p].dependencies:
                    return 1
                checked.append(p)
                for m in self.grpset.hdrlist[p].dependencies:
                    if m not in checked and m not in tocheck:
                        tocheck.append(m)
        return 0
            
    def getDescription(self):
        return self.description
        

class GroupSet:
    def __init__(self, compsxml, hdrlist):
        self.hdrlist = hdrlist
        self.compsxml = compsxml
        self.groups = {}

        for xmlgrp in compsxml.groups.values():
            group = Group(self, xmlgrp)
            self.groups[xmlgrp.id] = group

        # build up an Everything group 
        everything = rhpl.comps.Group(self.compsxml)
        everything.name = N_("Everything")
        everything.id = "everything"
        everything.description = EVERYTHING_DESCRIPTION

        multiarch = rhpl.arch.getMultiArchInfo()
        if multiarch is not None:
            (comp, best, biarch) = multiarch
        for pkgname in hdrlist.pkgnames.keys():
            if EverythingExclude.has_key(pkgname):
                continue
            
            mainnevra = hdrlist.getBestNevra(pkgname, prefArch = None)
            if mainnevra is None:
                continue
            
            everything.packages[mainnevra] = (u"mandatory", mainnevra)
            if multiarch is not None:
                # get the main and the biarch version of this package
                # for everything group
                secnevra = hdrlist.getBestNevra(pkgname, prefArch = biarch)
                if mainnevra != secnevra and secnevra is not None:
                    everything.packages[secnevra] = (u"mandatory", secnevra)

        self.compsxml.groups["Everything"] = everything
        self.groups["everything"] = Group(self, everything)

        # have to do includes and metagroups in a second pass so that
        # we can make sure the group is defined.  
        for xmlgrp in compsxml.groups.values():
            group = self.groups[xmlgrp.id]
            for id in xmlgrp.groups.keys():
                if not self.groups.has_key(id):
                    log("%s references component %s which doesn't exist"
                        %(xmlgrp.id, id))
                    continue
                group.addGroupRequires(id)

            for id in xmlgrp.metapkgs.keys():
                if not self.groups.has_key(id):
                    log("%s references component %s which doesn't exist"
                        %(xmlgrp.id, id))
                    continue
                group.addMetaPkg(xmlgrp.metapkgs[id])
        

    def selectGroup(self, group, asMeta = 0, missingOk = 0):
        if self.groups.has_key(group):
            self.groups[group].select(asMeta = asMeta)
            return
        for grp in self.compsxml.groups.values():
            if (grp.name == group) and self.groups.has_key(grp.id):
                self.groups[grp.id].select(asMeta = asMeta)
                return
        if missingOk:
            return
        raise KeyError, "No such group %s" %(group,)

    def unselectAll(self):
        # force everything to be in an off state
        for group in self.groups.values():
            group.usecount = 0
            group.manual_state = MANUAL_NONE
        for pkg in self.hdrlist.pkgs.values():
            pkg.usecount = 0
            pkg.manual_state = MANUAL_NONE

    def getSelectionState(self):
        grpst = []
        for group in self.groups.values():
            grpst.append((group, group.getState()))

        pkgst = []
        for pkg in self.hdrlist.values():
            pkgst.append((pkg, pkg.getState()))
            
        return (grpst, pkgst)

    def setSelectionState(self, state):
        (grpst, pkgst) = state

        for (grp, state) in grpst:
            grp.setState(state)

        for (pkg,state) in pkgst:
            pkg.setState(state)

    def size(self):
	size = 0
	for pkg in self.hdrlist.values():
	    if pkg.isSelected(): size = size + (pkg[rpm.RPMTAG_SIZE] / 1024)

	return size / 1024

    def sizeStr(self):
	megs = self.size()
	if (megs >= 1000):
	    big = megs / 1000
	    little = megs % 1000
	    return "%d,%03dM" % (big, little)

	return "%dM" % (megs)

    def kernelVersionList(self):
	kernelVersions = []

	# nick is used to generate the lilo name
	for (ktag, nick) in [ ('kernel-summit', 'summit'),
                              ('kernel-bigmem', 'bigmem'),
                              ('kernel-hugemem', 'hugemem'),
			      ('kernel-smp', 'smp'),
			      ('kernel-largesmp', 'largesmp'),
                              ('kernel-xenU', 'xenU'),
			      ('kernel-tape', 'tape'),
                              ('kernel-pseries', ''),
                              ('kernel-iseries', '') ]:
	    tag = ktag.split('-')[1]
	    if (self.hdrlist.has_key(ktag) and 
		self.hdrlist[ktag].isSelected()):
		version = (self.hdrlist[ktag][rpm.RPMTAG_VERSION] + "-" +
			   self.hdrlist[ktag][rpm.RPMTAG_RELEASE] + tag)
		kernelVersions.append((version, nick))

        if (self.hdrlist.has_key('kernel') and
            self.hdrlist['kernel'].isSelected()):
            version = (self.hdrlist['kernel'][rpm.RPMTAG_VERSION] + "-" +
                       self.hdrlist['kernel'][rpm.RPMTAG_RELEASE])
            kernelVersions.append((version, 'up'))
 
	return kernelVersions


def groupSetFromCompsFile(filename, hdrlist, doSelect = 1):
    import urllib2

    file = None
    tries = 0
    while tries < 5:
        try:
            file = urllib2.urlopen(filename)
        except urllib2.HTTPError, e:
            log("HTTPError: %s occurred getting %s", filename, e)
        except urllib2.URLError, e:
            log("URLError: %s occurred getting %s", filename, e)
        except IOError, (errnum, msg):
            log("IOError %s occurred getting %s: %s", filename,
                errnum, str(msg))
        except IOError, (errnum, msg):
            log("OSError %s occurred getting %s: %s", filename,
                errnum, str(msg))
        else:
            break

        time.sleep(5)
        tries = tries + 1

    if file is None:
        raise FileCopyException
        
    compsxml = rhpl.comps.Comps(file)
    file.close()
    grpset = GroupSet(compsxml, hdrlist)

    # precache provides of base and core.  saves us about 10% time-wise
    for groupname in [ "base", "core" ]:
        if not grpset.groups.has_key(groupname):
            continue
        for pnevra in grpset.groups[groupname].packages.keys():
            for prov in grpset.hdrlist[pnevra][rpm.RPMTAG_PROVIDENAME]:
                cached[prov] = pnevra

    if doSelect:
        for group in grpset.groups.values():
            if group.default:
                group.select()
    return grpset

def getGroupDescription(group):
    if group.id == "everything":
	return _("This group includes all the packages available.  Note that "
		 "there are substantially more packages than just the ones "
		 "in all the other package groups on this page.")
    elif group.id == "base":
	return _("Choose this group to get the minimal possible set of "
		 "packages.  Useful for creating small router/firewall "
		 "boxes, for example.")
    
    return group.description

# this is a temporary way to set order of packages
def orderPackageGroups(grpset):
    compsParents = grpset.compsxml.hierarchy.order
    compsHierarchy = grpset.compsxml.hierarchy

    grpids = []
    for grp in grpset.groups.values():
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
                thecomp = grpset.groups[grp]
		ignorelst.append(grp)
                retdict[myname].append(thecomp)

    miscgrp = _("Miscellaneous")
    for grp in grpids:
	if grp in ignorelst:
	    continue

        thecomp = grpset.groups[grp]
	if miscgrp not in retlist:
	    retlist.append(miscgrp)
	    retdict[miscgrp] = [thecomp]
	else:
	    retdict[miscgrp].append(thecomp)
		    
    return (retlist, retdict)

if __name__ == "__main__":
    tree = "/mnt/redhat/test/rawhide-20040109/i386/"
    
    def simpleInstallCallback(what, amount, total, h, (param)):
        global rpmfd
	if (what == rpm.RPMCALLBACK_TRANS_START):
	    # step 6 is the bulk of the transaction set
	    # processing time
	    if amount == 6:
                print "Preparing to install..."
	if (what == rpm.RPMCALLBACK_TRANS_PROGRESS):
            pass
		
        if (what == rpm.RPMCALLBACK_TRANS_STOP):
            pass

	if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
            print "Installing %s" %(nevra(h),)
            rpmfd = os.open("%s/%s/RPMS/%s-%s-%s.%s.rpm"
                            %(tree, productPath, h['name'], h['version'], h['release'],
                              h['arch']), os.O_RDONLY)
	    return rpmfd
	elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
            pass
	elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
	    os.close (rpmfd)
        elif ((what == rpm.RPMCALLBACK_UNPACK_ERROR) or
              (what == rpm.RPMCALLBACK_CPIO_ERROR)):
            print "ERROR!"
            sys.exit(0)
	else:
	    pass

    def packageSort(first, second):
        one = first[1000002]
        two = second[1000002]

        if one < two:
            return -1
        elif one > two:
            return 1
        return 0
        
    
    fd = os.open("%s/%s/base/hdlist" % (tree, productPath), os.O_RDONLY)
    hdrs = rpm.readHeaderListFromFD(fd)
    os.close(fd)
    showMem()
#     fd = os.open(tree + "/RedHat/base/hdlist2", os.O_RDONLY)
#     rpm.mergeHeaderListFromFD(hdrs, fd, 1000004)
#     os.close(fd)
    showMem()
    f = open("%s/%s/base/comps.xml" % (tree, productPath), "r")
    comps = rhpl.comps.Comps(f)
    f.close()
    showMem()
    hdrlist = HeaderList(hdrs)
    hdrlist.mergeFullHeaders("%s/%s/base/hdlist2" % (tree, productPath))
    showMem()
    groups = GroupSet(comps, hdrlist)
    showMem()

    for h in hdrlist.hdlist:
        print h[rpm.RPMTAG_NAME], h[rpm.RPMTAG_FILENAMES]
    sys.exit(0)

    ts = rpm.TransactionSet("/tmp/testinstall")
    ts.setVSFlags(-1)
    ts.setFlags(rpm.RPMTRANS_FLAG_ANACONDA)
    showMem()

    l = []
    groups.groups["base"].select()
    groups.hdrlist["evolution"].select()

    for hdr in groups.hdrlist.pkgs.values():
        if hdr.isSelected():
            l.append(hdr)
            print "going to install %s" %(nevra(hdr),)

    depcheck = DependencyChecker(groups)

    l.sort(packageSort)
    for h in l:
        ts.addInstall(h.hdr, h.hdr, "i")
    foo = ts.check(depcheck.callback)

    print depcheck.added
    sys.exit(0)
    ts.run(simpleInstallCallback, 0)


