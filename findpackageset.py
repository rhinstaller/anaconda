import rpm

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

    

def findpackageset(hdlist, dbPath='/'):
    db = rpm.opendb(0, dbPath)

    pkgDict = {}
    
    # first loop through packages and find ones which are a newer
    # version than what we have
    for pkg in hdlist:
        mi = db.match('name', pkg[rpm.RPMTAG_NAME])
        h = mi.next()
        while h:
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
            h = mi.next()
            
    # handle obsoletes
    for pkg in hdlist:
        if pkg[rpm.RPMTAG_NAME] in pkgDict.keys():
#            dEBUG("%(name)s is already selected" % pkg)
            continue

        if pkg[rpm.RPMTAG_OBSOLETENAME] is not None:
            for obs in pkg[rpm.RPMTAG_OBSOLETENAME]:
                mi = db.match('name', obs)
                h = mi.next()
                # FIXME: I should really iterate over all matches and verify
                # versioned obsoletes, but nothing in Red Hat Linux uses
                # them, so I'll optimize
                if h:
#                    dEBUG("adding %(name)s to the upgrade set for obsoletes" % pkg)
                    addNewPackageToUpgSet(pkgDict, pkg)                    
                    h = mi.next()

    return pkgDict.values()

