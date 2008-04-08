#!/usr/bin/env python
#
# splittree.py
#
# Copyright (C) 2003, 2004, 2005  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import os.path
import string
import getopt
import time
import types
import rpm

global _ts
_ts = None

# returns n-v-r.a from file filename
def nvra(pkgfile):
    global _ts
    if _ts is None:
        _ts = rpm.TransactionSet()
        _ts.setVSFlags(-1)
    fd = os.open(pkgfile, os.O_RDONLY)
    h = _ts.hdrFromFdno(fd)
    os.close(fd)
    return "%s-%s-%s.%s.rpm" %(h['name'], h['version'], h['release'],
                               h['arch'])
    

class Timber:
    """Split trees like no other"""
    def __init__(self):
        
        """self.release_str : the name and version of the product"
     
self.package_order_file : the location of the file which has
the package ordering
        
self.arch : the arch the tree is intended for
        
self.real_arch : the arch found in the unified tree's
.discinfo file
        
self.dist_dir : the loaction of the unified tree

self.src_dir : the location of the unified SRPM dir
        
self.start_time : the timestamp that's in .discinfo files
        
self.dir_info : The info other than start_time that goes
into the .discinfo files. The info should already exist
after running buildinstall in the unified tree
        
self.total_discs : total number of discs
        
self.total_bin_discs : total number of discs with RPMs
        
self.total_srpm_discs : total number of discs with SRPMs
        
self.reverse_sort_srpms : sort the srpms in reverse order to
fit. Usually only needed if we share a disc between SRPMs
and RPMs. Set to 1 to turn on.

self.reserve_size : Additional size needed to be reserved on the first disc.
"""
        
        self.reserve_size = 0
        self.disc_size = 640.0
        self.target_size = self.disc_size * 1024.0 * 1024
        self.fudge_factor = 1.2 * 1024.0 * 1024
        self.comps_size = 10.0 * 1024 * 1024
        self.release_str = None
        self.package_order_file = None
        self.arch = None
        self.real_arch = None
        self.dist_dir = None
        self.src_dir = None
        self.start_time = None
        self.dir_info = None
        self.total_discs = None
        self.bin_discs = None
        self.src_discs = None
        self.product_path = "anaconda"
        self.bin_list = []
        self.src_list = []
        self.shared_list = []
        self.reverse_sort_srpms=None
        self.common_files = ['beta_eula.txt', 'EULA', 'README', 'GPL', 'RPM-GPG-KEY', 'RPM-GPG-KEY-beta', 'RPM-GPG-KEY-fedora']
        self.logfile = []


    def getSize(self, path, blocksize=None):
        """Gets the size as reported by du -sL"""

        if blocksize:
            p = os.popen("du -sL --block-size=1 %s" % path, 'r')
            thesize = p.read()
            p.close()
            thesize = long(string.split(thesize)[0])
            return thesize
        else:
            p = os.popen("du -sLh %s" % path, 'r')
            thesize = p.read()
            p.close()
            thesize = string.split(thesize)[0]
            return thesize



    def reportSizes(self, disc, firstpkg=None, lastpkg=None):
        """appends to self.logfile"""
        
        if firstpkg:
            self.logfile.append("First package on disc%d: %s" % (disc, firstpkg))
        if lastpkg:
            self.logfile.append("Last package on disc%d : %s" % (disc, lastpkg))

        discsize = self.getSize("%s-disc%d" % (self.dist_dir, disc))
        self.logfile.append("%s-disc%d size: %s" % (self.arch, disc, discsize))


        
    def createDiscInfo(self, discnumber):
        """creates the .discinfo files in the split trees"""

        if not os.path.exists("%s/.discinfo" % self.dist_dir):
            raise RuntimeError, "CRITICAL ERROR : .discinfo doesn't exist in the unified tree, not splitting"

        # if start_time isn't set then we haven't got this info yet
        if not self.start_time:
            file = open("%s/.discinfo" % (self.dist_dir), 'r')
            self.start_time = file.readline()[:-1]
            self.release_str = file.readline()[:-1]
            self.real_arch = file.readline()[:-1]

            if self.real_arch != self.arch:
                raise RuntimeError, "CRITICAL ERROR : self.real_arch is not the same as self.arch"

            # skip the disc number line from the unified tree
            file.readline()
            
            # basedir, packagedir, and pixmapdir
            self.dir_info = [file.readline()[:-1], file.readline()[:-1], file.readline()[:-1]]

            file.close()

        discinfo_file = open("%s-disc%d/.discinfo" % (self.dist_dir, discnumber), 'w')
        discinfo_file.write("%s\n" % self.start_time)
        discinfo_file.write(self.release_str + '\n')
        discinfo_file.write(self.real_arch + '\n')
        discinfo_file.write("%s\n" % discnumber)
        for i in range(0, len(self.dir_info)):
            discinfo_file.write(self.dir_info[i] + '\n')
        discinfo_file.close()

        
            
    def linkFiles(self, src_dir, dest_dir, filelist):
        """Creates hardlinks from files in the unified dir to files in the split dirs. This is not for RPMs or SRPMs"""

        for file in filelist:
            src = "%s/%s" % (src_dir, file)
            dest = "%s/%s" % (dest_dir, file)
            try:
                os.link(src, dest)
            except OSError, (errno, msg):
                pass
            


    def createSplitDirs(self):
        """Figures out which discs are for RPMs, which are for SRPMs,
        and which are shared. Also creates links for files on disc1
        and files which are common across all discs"""

        if self.bin_discs > self.total_discs or self.src_discs > self.total_discs:
            raise RuntimeError, "CRITICAL ERROR : Number of discs specified exceeds the total number of discs"

        # get a list of discs for each type of disc. shared_list will
        # be returned for sorting out which discs SRPMS can land on
        self.bin_list = range(1, self.bin_discs + 1)
        self.src_list = range(self.total_discs - self.src_discs + 1, self.total_discs + 1)
        self.shared_list = range(self.total_discs - self.src_discs + 1, self.bin_discs + 1)


        for i in range(self.bin_list[0], self.bin_list[-1] + 1):
            if i == 1:
                p = os.popen('find %s/ -type f -not -name .discinfo -not -name "*\.rpm"' % self.dist_dir, 'r')
                filelist = p.read()
                p.close()
                filelist = string.split(filelist)
                
                p = os.popen('find %s/ -type d -not -name SRPMS' % self.dist_dir, 'r')
                dirlist = p.read()
                p.close()
                dirlist = string.split(dirlist)
                
                dont_create = []
                # we need to clean up the dirlist first. We don't want everything yet
                for j in range(0, len(dirlist)):
                    dirlist[j] = string.replace(dirlist[j], self.dist_dir, '')


                # now create the dirs for disc1
                for j in range(0, len(dirlist)):
                    os.makedirs("%s-disc%d/%s" % (self.dist_dir, i, dirlist[j]))
                                
                for j in range(0, len(filelist)):
                    filelist[j] = string.replace(filelist[j], self.dist_dir, '')
                    try:
                        os.link(os.path.normpath("%s/%s" % (self.dist_dir, filelist[j])),
                                os.path.normpath("%s-disc%d/%s" % (self.dist_dir, i, filelist[j])))
                    except OSError, (errno, msg):
                        pass

            else:
                os.makedirs("%s-disc%d/%s" % (self.dist_dir, i, self.product_path))
                self.linkFiles(self.dist_dir, "%s-disc%d" %(self.dist_dir, i), self.common_files)
            self.createDiscInfo(i)
            
        if (self.src_discs != 0):
            for i in range(self.src_list[0], self.src_list[-1] + 1):
                os.makedirs("%s-disc%d/SRPMS" % (self.dist_dir, i))
                self.linkFiles(self.dist_dir,
                               "%s-disc%d" %(self.dist_dir, i),
                               self.common_files)
                self.createDiscInfo(i)

                
        
    def splitRPMS(self, reportSize = 1):
        """Creates links in the split dirs for the RPMs"""
        
        packages = {}

        pkgdir = "%s" %(self.product_path,)
            
        rpmlist = os.listdir("%s/%s" %(self.dist_dir, pkgdir))
        rpmlist.sort()

        # create the packages dictionary in this format: n-v-r.a:['n-v-r.arch.rpm']
        for filename in rpmlist:
            filesize = os.path.getsize("%s/%s/%s" % (self.dist_dir, pkgdir, filename))
            try:
                pkg_nvr = nvra("%s/%s/%s" %(self.dist_dir, pkgdir, filename))
            except rpm.error, e:
                continue
            
            if packages.has_key(pkg_nvr):
                # append in case we have multiple packages with the
                # same n-v-r. Ex: the kernel has multiple n-v-r's for
                # different arches
                packages[pkg_nvr].append(filename)
            else:
                packages[pkg_nvr] = [filename]
                
        orderedlist = []
        
        # read the ordered pacakge list into orderedlist
        file = open(self.package_order_file, 'r')
        for pkg_nvr in file.readlines():
            pkg_nvr = string.rstrip(pkg_nvr)
            if pkg_nvr[0:8] != "warning:":
                orderedlist.append(pkg_nvr)
        file.close()

        # last package is the last package placed on the disc
        firstpackage = ''
        lastpackage = ''
        
        # packagenum resets when we change discs. It's used to
        # determine the first package in the split tree and that's
        # about it
        packagenum = 0

        disc = self.bin_list[0]

        for rpm_nvr in orderedlist:
            if not packages.has_key(rpm_nvr):
                continue
            for file_name in packages[rpm_nvr]:
                curused = self.getSize("%s-disc%s" % (self.dist_dir, disc), blocksize=1)
                filesize = self.getSize("%s/%s/%s" % (self.dist_dir, pkgdir, file_name), blocksize=1)
                newsize = filesize + curused

                # compensate for the size of the comps package which has yet to be created
                if disc == 1:
                    maxsize = self.target_size - self.comps_size - self.reserve_size
                else:
                    maxsize = self.target_size
                    
                packagenum = packagenum + 1

                if packagenum == 1:
                    firstpackage = file_name

                # move to the next disc if true
                if newsize > maxsize:
                    self.reportSizes(disc, firstpkg=firstpackage, lastpkg=lastpackage)
                    # try it, if we are already on the last disc then complain loudly
                    try:
                        nextdisc=self.bin_list.index(disc+1)
                        disc = self.bin_list[nextdisc]
                        os.link("%s/%s/%s" % (self.dist_dir, pkgdir, file_name),
                                "%s-disc%d/%s/%s" % (self.dist_dir, disc, pkgdir, file_name))
                        packagenum = 1
                        firstpackage = file_name
                        
                    except:
                        # back down to the last RPM disc and complain about the overflow
                        disc = disc - 1
                        self.logfile.append("No more discs to put packages, overflowing on disc%d" % disc)
                        continue
                    
                else:
                    os.link("%s/%s/%s" % (self.dist_dir, pkgdir, file_name),
                            "%s-disc%d/%s/%s" % (self.dist_dir, disc, pkgdir, file_name))
                    lastpackage = file_name

        if reportSize == 1:
            if firstpackage == '':
                raise RuntimeError, "CRITICAL ERROR : Packages do not fit in given CD size"

            self.reportSizes(disc, firstpkg=firstpackage, lastpkg=lastpackage)

        

    def getLeastUsedTree(self):
        """Returns the least full tree to use for SRPMS"""

        sizes = []
        for i in range(0, len(self.src_list)):
            sizes.append([self.getSize("%s-disc%d" % (self.dist_dir, self.src_list[i]), blocksize=1), self.src_list[i]])
        sizes.sort()
        return sizes[0]



    def splitSRPMS(self):
        """Puts the srpms onto the SRPM split discs. The packages are
        ordered by size, and placed one by one on the disc with the
        most space available"""

        srpm_list = []

        srpm_disc_list = self.src_list
        # create a list of [[size, srpm]]
        for srpm in os.listdir("%s" % self.src_dir):
            if not srpm.endswith('.rpm'):
                continue
            srpm_size = self.getSize("%s/%s" % (self.src_dir, srpm), blocksize=1)
            srpm_list.append([srpm_size, srpm])

        srpm_list.sort()
        srpm_list.reverse()

        for i in range(0, len(srpm_list)):
            # make sure that the src disc is within the size limits,
            # if it isn't, pull it out of the list. If there's only
            # one disk make loud noises over the overflow
            for disc in self.src_list:
                if self.getSize("%s-disc%s" % (self.dist_dir, disc), blocksize=1) > self.target_size:
                    if len(self.src_list) < 2:
                        self.logfile.append("Overflowing %s on disc%d" % (srpm_list[i][1], disc))
                        break
                    else:
                        discsize = self.getSize("%s-disc%d" % (self.dist_dir, disc))
                        self.logfile.append("%s-disc%d size: %s" % (self.arch, disc, discsize))
                        self.src_list.pop(self.src_list.index(disc))
            os.link("%s/%s" % (self.src_dir, srpm_list[i][1]),
                    "%s-disc%d/SRPMS/%s" % (self.dist_dir, self.getLeastUsedTree()[1], srpm_list[i][1]))
        
        for i in range(0, len(srpm_disc_list)):
            self.reportSizes(srpm_disc_list[i])


    def main(self):
        """Just runs everything"""

        # Recalculate this here in case the disc_size changed.
        self.target_size = self.disc_size * 1024.0 * 1024

        self.createSplitDirs()
        self.splitRPMS()
        if (self.src_discs != 0):
            self.splitSRPMS()
        return self.logfile



def usage(theerror):
    print theerror
    print """Usage: %s --arch=i386 --total-discs=8 --bin-discs=4 --src-discs=4 --release-string="distro name" --pkgorderfile=/tmp/pkgorder.12345 --distdir=/usr/src/someunifiedtree --srcdir=/usr/src/someunifiedtree/SRPMS --productpath=product""" % sys.argv[0]
    sys.exit(1)

        
if "__main__" == __name__:
    import getopt
    
    timber = Timber()

    theargs = ["arch=", "total-discs=", "bin-discs=", 'disc-size=',
               "src-discs=", "release-string=", "pkgorderfile=",
               "distdir=", "srcdir=", "productpath=", "reserve-size="]

    try:
        options, args = getopt.getopt(sys.argv[1:], '', theargs)
    except getopt.error, error:
        usage(error)

    myopts = {}
    for i in options:
        myopts[i[0]] = i[1]

    options = myopts

    if options.has_key("--arch"):
        timber.arch = options['--arch']
    else:
        usage("You forgot to specify --arch")

    if options.has_key("--total-discs"):
        timber.total_discs = int(options['--total-discs'])
    else:
        usage("You forgot to specify --total-discs")

    if options.has_key("--bin-discs"):
        timber.bin_discs = int(options['--bin-discs'])
    else:
        usage("You forgot to specify --bin-discs")

    if options.has_key("--src-discs"):
        timber.src_discs = int(options['--src-discs'])
    else:
        usage("You forgot to specify --src-discs")

    if options.has_key("--release-string"):
        timber.release_str = options["--release-string"]
    else:
        usage("You forgot to specify --release-string")

    if options.has_key("--pkgorderfile"):
        timber.package_order_file = options["--pkgorderfile"]
    else:
        usage("You forgot to specify --pkgorderfile")

    if options.has_key("--distdir"):
        timber.dist_dir = options["--distdir"]
    else:
        usage("You forgot to specify --distdir")

    if options.has_key("--srcdir"):
        timber.src_dir = options["--srcdir"]
    else:
        usage("You forgot to specify --srcdir")
    
    if options.has_key("--productpath"):
        timber.product_path = options["--productpath"]

    if options.has_key("--reserve-size"):
        timber.reserve_size = float(options["--reserve-size"])

    if options.has_key("--disc-size"):
        timber.disc_size = float(options["--disc-size"])

    logfile = timber.main()
    
    for logentry in range(0, len(logfile)):
        print logfile[logentry]

    sys.exit(0)
