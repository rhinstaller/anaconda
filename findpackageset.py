import rpm
import string
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
    if not pkgDict.has_key(name):
        # nope
        pkgDict[name] = pkg
    else:
        # first check version
        val = rpm.versionCompare(pkgDict[name], pkg)
        if val < 0:
            # we're newer, add this one
            pkgDict[name] = pkg
        elif val == 0:
            # same version, so check the architecture
            newscore = rpm.archscore(pkg[rpm.RPMTAG_ARCH])
            oldscore = pkgDict[name][rpm.RPMTAG_ARCH]
            if newscore and newscore < oldscore:
                # if the score is less, we're "better"
                pkgDict[name] = pkg

    

def findpackageset(hdrlist, dbPath='/'):
    ts = rpm.TransactionSet(dbPath)
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA|rpm.RPMVSF_NOMD5))

    pkgDict = {}

    # go through and figure out which packages in the header list are
    # actually applicable for our architecture
    pkgDict = {}
    for h in hdrlist:
        score1 = rpm.archscore(h[rpm.RPMTAG_ARCH])
        if (score1):
            name = h[rpm.RPMTAG_NAME]
            if pkgDict.has_key(name):
                score2 = rpm.archscore(pkgDict[name][rpm.RPMTAG_ARCH])
                if (score1 < score2):
                    pkgDict[name] = h
            else:
                pkgDict[name] = h
    hdlist = pkgDict.values()
    
    pkgDict = {}
    # loop through packages and find ones which are a newer
    # version than what we have
    for pkg in hdlist:
        mi = ts.dbMatch('name', pkg[rpm.RPMTAG_NAME])
        for h in mi:
            val = rpm.versionCompare(h, pkg)
            if (val > 0):
#                dEBUG("found older version of %(name)s" % h)
                pass
            elif (val < 0):
#                dEBUG("found newer version of %(name)s" % h)
                # check if we already have this package in our dictionary
                addNewPackageToUpgSet(pkgDict, pkg)
            else:
#                dEBUG("found same verison of %(name)s" % h)
                pass
            
    # handle obsoletes
    for pkg in hdlist:
        if pkg[rpm.RPMTAG_NAME] in pkgDict.keys():
#            dEBUG("%(name)s is already selected" % pkg)
            continue

        if pkg[rpm.RPMTAG_OBSOLETENAME] is not None:
            for obs,obsver in zip(pkg[rpm.RPMTAG_OBSOLETENAME],pkg[rpm.RPMTAG_OBSOLETEVERSION]):
                mi = ts.dbMatch('name', obs)
                oevr = strToVersion(obsver)
                for h in mi:
                    if not obsver:
#                    unversioned obsoletes win
                        addNewPackageToUpgSet(pkgDict, pkg)
                        break
                    else:
#                    dEBUG("adding %(name)s to the upgrade set for obsoletes" % pkg)
                        if h[rpm.RPMTAG_EPOCH] is None:
                            epoch = '0'
                        else:
                            epoch = str(h[rpm.RPMTAG_EPOCH])
                        val = rpm.labelCompare(oevr,(epoch,h[rpm.RPMTAG_VERSION],h[rpm.RPMTAG_RELEASE]))
                        if val > 0:
                            addNewPackageToUpgSet(pkgDict, pkg)
                            break

    return pkgDict.values()

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
                   
