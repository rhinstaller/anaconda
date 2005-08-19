import sys
sys.path.append("..")
from hdrlist import *

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print "Usage: %s /path/to/tree [rootpath]" %(sys.argv[0],)
        sys.exit(0)
    tree = sys.argv[1] 
    
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

