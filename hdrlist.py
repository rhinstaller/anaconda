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

import language

ON = 1
MANUAL_ON = 2
OFF = -1
MANUAL_OFF = -2
MANUAL_NONE = 0
ON_STATES = (ON, MANUAL_ON)
OFF_STATES = (OFF, MANUAL_OFF)

PKGTYPE_MANDATORY = 0
PKGTYPE_DEFAULT = 1
PKGTYPE_OPTIONAL = 2

EVERYTHING_DESCRIPTION = N_("This group includes all the packages available.  "
                            "Note that there are substantially more packages "
                            "than just the ones in all the other package "
                            "groups on this page.")

EverythingExclude = {'kernel' : None,		'kernel-BOOT' : None,
                     'kernel-smp' : None,	'kernel-bigmem' : None,
                     'kernel-summit' : None,    'kernel-enterprise' : None,
                     'kernel-tape' : None,      'kernel-BOOTtape' : None,
                     'kernel-pseries': None,    'kernel-iseries': None}

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


class DependencyChecker:
    def __init__(self, grpset, how = "i"):
        self.grpset = grpset
        self.added = []
        self.unknown = []
        self.how = how

    # FIXME: this is the simple stupid version.  it doesn't actually handle
    # paying attention to EVR
    def callback(self, ts, tag, name, evr, flags):
        if tag == rpm.RPMTAG_REQUIRENAME:
            hdr = None
            if name[0] == "/":
                for h in self.grpset.hdrlist.pkgs.values():
                    l = []
                    for f in h.hdr.fiFromHeader(): l.append(f[0])
                    
                    if ((name in l) and
                        ((hdr is None) or (len(h[rpm.RPMTAG_NAME]) <
                                           len(hdr[rpm.RPMTAG_NAME])))):
                        hdr = h
            else:
                # do we have a package named this?
                if self.grpset.hdrlist.has_key(name):
                    hdr = self.grpset.hdrlist[name]
                # otherwise, go through provides and find the shortest name
                else:
                    for h in self.grpset.hdrlist.pkgs.values():
                        if ((name in h[rpm.RPMTAG_PROVIDENAME]) and
                            ((hdr is None) or (len(h[rpm.RPMTAG_NAME]) <
                                               len(hdr[rpm.RPMTAG_NAME])))):
                            hdr = h
                            
            if hdr is not None:
                if evr:
                    nevr = "%s-%s" %(name, evr)
                else:
                    nevr = name
                log("using %s to satisfy %s" %(nevra(hdr), nevr))
                ts.addInstall(hdr.hdr, hdr.hdr, self.how)
                self.added.append(nevra(hdr.hdr))
                return -1

        return 1
            

class Package:
    def __init__(self, hdr):
        self.hdr = hdr
        self.usecount = 0
        self.manual_state = MANUAL_NONE
        self.dependencies = []

        self.name = self.hdr[rpm.RPMTAG_NAME]

    def getState(self):
        return (self.usecount, self.manual_state)

    def setState(self, state):
        (self.usecount, self.manual_state) = state

    def addDeps(self, deps):
        self.dependencies.extend(deps)

    def select(self, isManual = 0):
        self.usecount = self.usecount + 1
        if isManual:
            if self.manual_state == MANUAL_NONE:
                self.manual_state = MANUAL_ON
            elif self.manual_state == MANUAL_OFF:
                self.manual_state = MANUAL_NONE

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
        if self.manual_state == MANUAL_ON:
            return 1
        elif self.manual_state == MANUAL_OFF:
            return 0
        elif self.usecount > 0:
            return 1
        else:
            return 0

    def __getitem__(self, item):
        return self.hdr[item]

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
        elif self.pkgnames.has_key(item):
            return 1
        return 0

    def keys(self):
        return self.pkgnames.keys()

    def values(self):
        return self.pkgs.values()

    # FIXME: the package deps stuff needs to be nevra instead of name based
    def mergePackageDeps(self, pkgsxml):
        for pkg in pkgsxml.values():
            for (p, a) in self.pkgnames[pkg.name]:
                self.pkgs[p].addDeps(pkg.dependencies)

    # this is definite crack rock, but it allows us to avoid tripling
    # our memory usage :(
    # reads an hdlist2 file and merges the header information we split out
    # (things like file lists)
    # FIXME: BUSTED!
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
        return preordered

    # get the best nevra for the package name.
    # FIXME: surely this can be made faster/less complicated
    # doing scoring everytime seems like it might be overkill
    # then again, it shouldn't be called *that* often so it might not matter
    def getBestNevra(self, item):
        bestscore = 0
        bestpkg = None

        if not self.pkgnames.has_key(item):
            return None
        
        for (nevra, arch) in self.pkgnames[item]:
            # FIXME: need to use our replacement for arch scoring
            # so that we can work with biarch
            score = rpm.archscore(arch)
            if not score:
                continue
            if (bestscore == 0) or (score < bestscore):
                bestpkg = nevra
                bestscore = score
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
            raise KeyError, "No such package"

        return self.pkgs[pkg]


class HeaderListFromFile (HeaderList):
    def __init__(self, path):
	hdlist = rpm.readHeaderListFromFile(path)
	HeaderList.__init__(self, hdlist)

class Group:
    def __init__(self, grpset, xmlgrp):
        # dict of package info.  nevra and type are obvious
        # state is one of the ON/OFF states
        def makePackageDict(pkgnevra, type, installed = 0):
            return { "nevra": pkgnevra, "type": type, "state": installed }
        
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
        # fall back to english if they're not set
        if self.name is None:
            self.name = xmlgrp.name
        if self.description is None:
            self.description = xmlgrp.description

        # obviously enough, hidden components aren't shown
        self.hidden = not xmlgrp.user_visible
        # whether or not a group should be enabled by default.  only
        # really matters for custom installs
        self.default = xmlgrp.default
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
            pkgnevra = hdrlist.getBestNevra(pkg)
            if pkgnevra is None:
                log("%s references package %s which doesn't exist"
                    %(self.id, pkg))
                continue

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

            self.packages[pkgnevra] = makePackageDict(pkgnevra, pkgtype)

    def getState(self):
        return (self.usecount, self.manual_state)

    def setState(self, state):
        (self.usecount, self.manual_state) = state

    def addGroupRequires(self, grpid):
        if grpid not in self.groupreqs:
            self.groupreqs.append(grpid)

    # FIXME: this doesn't seem like the right place for it, but ... :/
    def selectDeps(self, pkgs, uses = 1):
        checked = []
        while len(pkgs) > 0:
            tocheck = pkgs
            pkgs = []
            for pkgnevra in tocheck:
                pkg = self.grpset.hdrlist[pkgnevra]

                deps = pkg.dependencies
                for dep in deps:
                    # hmm, not in the header list.  we can't do much but
                    # hope for the best
                    if not self.grpset.hdrlist.has_key(dep):
                        log("Package %s requires %s which we don't have"
                            %(tocheck, dep))
                        continue
                    # if we've already checked for this package, don't worry
                    if dep in checked:
                        continue
                    self.grpset.hdrlist[dep].select()
                    # FIXME: this is a hack so we can make sure the usecount
                    # is bumped high enough for langsupport packages
                    self.grpset.hdrlist[dep].usecount += uses - 1
                    pkgs.append(nevra(self.grpset.hdrlist[dep]))
                    checked.append(dep)


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
                    # hmm, not in the header list.  we can't do much but
                    # hope for the best
                    if not self.grpset.hdrlist.has_key(dep):
                        log("Package %s requires %s which we don't have"
                            %(tocheck, dep))
                        continue
                    # if we've already checked for this package, don't worry
                    if dep in checked:
                        continue
                    sys.stdout.flush()
                    self.grpset.hdrlist[dep].unselect()
                    pkgs.append(nevra(self.grpset.hdrlist[dep]))
                    checked.append(dep)
        

    # forInclude is whether this group is an include from a previous
    # subAsInclude allows us to say that included groups shouldn't be
    #    forInclude  (useful for Workstation Common, etc)
    def select(self, forInclude = 0, subAsInclude = 0):
        hdrlist = self.grpset.hdrlist

        # update the usecount.  if this is manual, change the state if needed
        # if we were already previously selected, we don't need to bump up
        # refcounts (which makes things faster)
        self.usecount = self.usecount + 1
        if not forInclude:
            self.manual_state = MANUAL_ON
        if self.usecount > 1:
            return

        selected = []
        for (pkgnevra, pkg) in self.packages.items():
            # if it's not optional, we should turn it on
            if pkg["type"] == PKGTYPE_OPTIONAL:
                continue
            pkg["state"] = ON
            hdrlist[pkgnevra].select()
            selected.append(pkgnevra)
        self.selectDeps(selected)

        for grpid in self.groupreqs:
            self.grpset.groups[grpid].select(forInclude = (not subAsInclude))

    # manual package selection
    def selectPackage(self, pkgnevra):
        pkg = self.packages[pkgnevra]
        if pkg["state"] in ON_STATES:
            return
        pkg["state"] = ON
        self.grpset.hdrlist[pkgnevra].select()
        self.selectDeps([pkgnevra])
            
    def unselect(self, forInclude = 0):
        hdrlist = self.grpset.hdrlist

        # update the usecount.  if this is manual, change the state if needed
        # if we were already previously selected, we don't need to bump up
        # refcounts (which makes things faster)
        self.usecount = self.usecount - 1
        if not forInclude:
            self.manual_state = MANUAL_OFF
        if self.usecount < 0: log("WARNING: usecount for %s < 0 (%d)" %(self.id, self.usecount))
        if self.usecount > 0:
            return

        selected = []
        for pkg in self.packages.values():
            pkgnevra = pkg["nevra"]
            if pkg["state"] not in ON_STATES:
                continue
            hdrlist[pkgnevra].unselect()
            pkg["state"] = OFF
            selected.append(pkgnevra)
        self.unselectDeps(selected)
        
        for grpid in self.groupreqs:
            self.grpset.groups[grpid].unselect(forInclude = 1)

    def unselectPackage(self, pkgnevra):
        pkg = self.packages[pkgnevra]
        if pkg["state"] not in ON_STATES:
            return
        self.grpset.hdrlist[pkgnevra].unselect()
        pkg["state"] = OFF
        self.unselectDeps([pkgnevra])        

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
        if self.id == "everything":
            return _("This group includes all the packages available.  "
                     "Note that there are substantially more packages than "
                     "just the ones in all the other package groups on "
                     "this page.")
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
        for pkgname in hdrlist.pkgnames.keys():
            if EverythingExclude.has_key(pkgname):
                continue
            everything.packages[pkgname] = (u'mandatory', pkgname)
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
            # FIXME: need to add back metapkgs
        

    def mergePackageDeps(self):
        self.hdrlist.mergePackageDeps(self.compsxml.packages)

    def selectGroup(self, group, asMeta = 0):
        if self.groups.has_key(group):
            self.groups[group].select(subAsInclude = asMeta)
            return
        for grp in self.compsxml.groups.values():
            if (grp.name == group) and self.groups.has_key(grp.id):
                self.groups[grp.id].select(subAsInclude = asMeta)
                return
        raise KeyError, "No such group %s" %(group,)

    def unselectAll(self):
        for group in self.groups.values():
            if group.isSelected(justManual = 1):
                group.unselect()

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
			      ('kernel-smp', 'smp'),
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


def groupSetFromCompsFile(filename, hdrlist):
    import urllib2
    
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

    compsxml = rhpl.comps.Comps(file)
    file.close()
    grpset = GroupSet(compsxml, hdrlist)

    grpset.mergePackageDeps()

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
    tree = "/mnt/test/latest-taroon-i386/"
    
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
            rpmfd = os.open("%s/RedHat/RPMS/%s-%s-%s.%s.rpm"
                            %(tree, h['name'], h['version'], h['release'],
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
        
    
    fd = os.open(tree + "/RedHat/base/hdlist", os.O_RDONLY)
    hdrs = rpm.readHeaderListFromFD(fd)
    os.close(fd)
    showMem()
#     fd = os.open(tree + "/RedHat/base/hdlist2", os.O_RDONLY)
#     rpm.mergeHeaderListFromFD(hdrs, fd, 1000004)
#     os.close(fd)
    showMem()
    f = open(tree + "/RedHat/base/comps.xml", "r")
    comps = rhpl.comps.Comps(f)
    f.close()
    showMem()
    hdrlist = HeaderList(hdrs)
    hdrlist.mergeFullHeaders(tree + "/RedHat/base/hdlist2")
    showMem()
    hdrlist.mergePackageDeps(comps.packages)
    showMem()    
    groups = GroupSet(comps, hdrlist)
    showMem()

#    sys.exit(0)

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


