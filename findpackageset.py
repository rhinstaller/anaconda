import rpm
import rhpl.arch
import string
import types
from constants import *

# set DB_PRIVATE to make rpm happy
rpm.addMacro("__dbi_cdb", "create private mpool mp_mmapsize=16Mb mp_size=1Mb")


def dEBUG(str):
    print str

def addNewPackageToUpgSet(pkgDict, pkg):
    """Check to see if there's already a pkg by the name of pkg already
       in our dictionary.  If not, add this one.  If there is, see if
       this one is 'newer' or has a 'better' arch."""
    name = pkg[rpm.RPMTAG_NAME]
    arch = pkg[rpm.RPMTAG_ARCH]
    if not pkgDict.has_key((name, arch)):
        # nope
        pkgDict[(name,arch)] = pkg
    else:
        # first check version
        val = rpm.versionCompare(pkgDict[(name,arch)], pkg)
        if val < 0:
            # we're newer, add this one
            pkgDict[(name,arch)] = pkg

def comparePackageForUpgrade(updDict, h, pkg):
    val = rpm.versionCompare(h, pkg)
    if (val > 0):
#        dEBUG("found older version of %(name)s %(arch)s" % h)
        pass
    elif (val < 0):
#        dEBUG("found newer version of %(name)s %(arch)s" % h)
        # check if we already have this package in our dictionary
        addNewPackageToUpgSet(updDict, pkg)
    else:
#        dEBUG("found same verison of %(name)s %(arch)s" % h)
        pass

def findBestArch(archlist):
    bestarch = None
    for availarch in archlist:
        newscore = rhpl.arch.score(availarch)
        # unsupported
        if newscore <= 0:
            continue
        # If old arch is better or same
        if bestarch and rhpl.arch.score(bestarch) <= newscore:
            continue
                
        # If we get here we're better
        bestarch = availarch
    return bestarch
        
def getAvailPackages(hdrlist):     
    # go through and figure out which packages in the header list are
    # actually applicable for our architecture
    pkgDict = {}
    nameDict = {}
    for h in hdrlist:
        score1 = rhpl.arch.score(h[rpm.RPMTAG_ARCH])
        if (score1):
            name = h[rpm.RPMTAG_NAME]
            arch = h[rpm.RPMTAG_ARCH]
            pkgDict[(name,arch)] = h
            if nameDict.has_key(name):
                nameDict[name].append(arch)
            else:
                nameDict[name] = [ arch ]
    return (pkgDict, nameDict)

def getInstalledPackages(dbPath='/'):
    pkgDict = {}
    nameDict = {}
    ts = rpm.TransactionSet(dbPath)
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA|rpm.RPMVSF_NOMD5))
    mi = ts.dbMatch()
    for h in mi:
        name = h[rpm.RPMTAG_NAME]
        arch = h[rpm.RPMTAG_ARCH]
        pkgDict[(name,arch)] = h
        if nameDict.has_key(name):
            nameDict[name].append(arch)
        else:
            nameDict[name] = [ arch ]
    return (pkgDict, nameDict)

def findpackageset(hdrlist, dbPath='/'):
    instDict = {}
    availDict = {}
    updDict = {}

    # dicts for name : [archlist]
    availNames = {}
    instNames = {}

    ts = rpm.TransactionSet(dbPath)
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA|rpm.RPMVSF_NOMD5))

    (availDict, availNames)  = getAvailPackages(hdrlist)
    (instDict, instNames) =  getInstalledPackages(dbPath=dbPath)

    hdlist = availDict.values()
    
    # loop through packages and find ones which are a newer
    # version than what we have
    for ( name, arch ) in instDict.keys():
        if ( name, arch ) in availDict.keys():
            # Exact arch upgrade
            h = instDict[(name, arch)]
            pkg = availDict[(name,arch)] 
            comparePackageForUpgrade(updDict, h, pkg)
        else:
            # See if we have a better arch than that installed
            if name in availNames.keys():
                bestarch = findBestArch(availNames[name])
                if not bestarch:
                    continue
                if availDict.has_key((name,bestarch)):
                    h = instDict[(name,arch)]
                    pkg = availDict[(name,bestarch)]
                    comparePackageForUpgrade(updDict, h, pkg)
                    
    # handle obsoletes
    for pkg in hdlist:
        if (pkg[rpm.RPMTAG_NAME],pkg[rpm.RPMTAG_ARCH]) in updDict.keys():
#            dEBUG("%(name)s %(arch)s is already selected" % pkg)
            continue

        if pkg[rpm.RPMTAG_OBSOLETENAME] is not None:
            name = pkg[rpm.RPMTAG_NAME]
            arch = pkg[rpm.RPMTAG_ARCH]
            for obs,obsver in zip(pkg[rpm.RPMTAG_OBSOLETENAME],pkg[rpm.RPMTAG_OBSOLETEVERSION]):
                mi = ts.dbMatch('name', obs)
                oevr = strToVersion(obsver)
                for h in mi:
                    if not obsver:
#                    unversioned obsoletes win
                        addNewPackageToUpgSet(updDict, pkg)
#                    dEBUG("adding %(name)s to the upgrade set for obsoletes" % pkg)
                        break
                    else:
                        if h[rpm.RPMTAG_EPOCH] is None:
                            epoch = '0'
                        else:
                            epoch = str(h[rpm.RPMTAG_EPOCH])
                        val = compareEVR(oevr,(epoch,h[rpm.RPMTAG_VERSION],h[rpm.RPMTAG_RELEASE]))
                        if val > 0:
#                    dEBUG("adding %(name)s %(version)s to the upgrade set for obsoletes" % pkg)
                            updDict[(name,arch)] = pkg 
                            break

    return updDict.values()

def rpmOutToStr(arg):
    if type(arg) != types.StringType:
    # and arg is not None:
        arg = str(arg)

    return arg

def compareEVR((e1, v1, r1), (e2, v2, r2)):
    # return 1: a is newer than b
    # 0: a and b are the same version
    # -1: b is newer than a
    e1 = rpmOutToStr(e1)
    v1 = rpmOutToStr(v1)
    r1 = rpmOutToStr(r1)
    e2 = rpmOutToStr(e2)
    v2 = rpmOutToStr(v2)
    r2 = rpmOutToStr(r2)
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    return rc

def strToVersion(str):
    """Parse a string such as in obsoleteversion into evr.
       Gratuitously borrowed from yum str_to_version
       FIXME: should be implemented in and use rpmUtils"""
    i = string.find(str, ':')
    if i != -1:
        epoch = string.atol(str[:i])
    else:
        epoch = '0'
    j = string.find(str, '-')
    if j != -1:
        if str[i + 1:j] == '':
            version = None
        else:             version = str[i + 1:j]
        release = str[j + 1:]     
    else:
        if str[i + 1:] == '':
            version = None
        else:
            version = str[i + 1:]
        release = None
    return (epoch, version, release)


if __name__ == "__main__":
    import sys, os

    if len(sys.argv) < 2:
        print "Usage: %s /path/to/tree [rootpath]" %(sys.argv[0],)
        sys.exit(0)
        
    tree = sys.argv[1]
    if len(sys.argv) >= 3:
        instPath = sys.argv[2]
    else:
        instPath = "/"
    
    fd = os.open("%s/%s/base/hdlist" %(tree, productPath), os.O_RDONLY)
    hdlist = rpm.readHeaderListFromFD(fd)
    os.close(fd)

    
    packages = findpackageset(hdlist, instPath)
    for pkg in packages:
        print pkg[rpm.RPMTAG_NAME]
                   
