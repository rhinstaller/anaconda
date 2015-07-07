#!/usr/bin/python
# mkdud.py - test helper that makes driverdisk images
#
# Copyright (c) 2015 Red Hat, Inc.
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
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Will Woods <wwoods@redhat.com>

import os
import rpmfluff
import subprocess
import argparse
import tempfile
import shutil

from contextlib import contextmanager

@contextmanager
def in_tempdir(prefix='tmp'):
    oldcwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    os.chdir(tmpdir)
    yield
    os.chdir(oldcwd)
    shutil.rmtree(tmpdir)

def parse_args():
    p = argparse.ArgumentParser(
        description="make fake driver disk images for testing",
        epilog="ex: %(prog)s dd.iso",
    )
    p.add_argument("filename",
        help="image filename to write")
    p.add_argument("--label", "-L", default="OEMDRV",
        help="disk image label (default: %(default)s)")
    p.add_argument("--description", "-d", default="fake driverdisk",
        help="driverdisk description (default: %(default)r)")
    p.add_argument("--arch", "-a", default=rpmfluff.expectedArch,
        help="arch to create RPMs for (default: host arch [%(default)s])")
    p.add_argument("--kmod", "-k", action="store_true", default=False,
        help="add a fake kmod to the driverdisk")
    p.add_argument("--binary", "-b", action="store_true", default=False,
        help="add a fake binary to the driverdisk")
    p.add_argument("--createrepo", "-c", action="store_true", default=False,
        help="run createrepo to add repodata to the driverdisk")

    return p.parse_args()

def write_description(desc):
    with open("rhdd3",'w') as rhdd3:
        rhdd3.write(desc+'\n')

def make_rpm(pkg, outdir=".", arch=None):
    outdir = os.path.abspath(outdir)
    with in_tempdir(prefix='mkdud.rpmfluff.'):
        pkg.make()
        rpmfile = pkg.get_built_rpm(arch or rpmfluff.expectedArch)
        outfile = os.path.join(outdir, os.path.basename(rpmfile))
        shutil.move(rpmfile, outfile)
    return outfile

def write_kmod_rpm(outdir, for_kernel_ver=None, arch=None):
    pkg = rpmfluff.SimpleRpmBuild('fake_kmod', '1.0', '1')
    pkg.add_provides('kernel-modules >= %s' % for_kernel_ver)
    pkg.add_installed_file("/lib/modules/%s/extra/fake-dd.ko" % for_kernel_ver,
        rpmfluff.SourceFile("fake-dd.ko", "this is a fake kernel module"),
    )
    pkg.add_installed_file("/root/fake-dd-2.ko",
        rpmfluff.SourceFile("fake-dd-2.ko", "another fake kernel module"),
    )
    return make_rpm(pkg, outdir, arch)

def write_installer_enhancement_rpm(outdir, for_anaconda_ver=None, arch=None):
    pkg = rpmfluff.SimpleRpmBuild('fake_bin', '1.0', '1')
    pkg.add_provides('installer-enhancement = %s' % for_anaconda_ver)
    pkg.add_installed_file("/usr/bin/fake-dd-bin",
        rpmfluff.SourceFile("fake-dd-bin", "#!/bin/sh\necho FAKE BINARY OK"),
        mode='755',
    )
    return make_rpm(pkg, outdir, arch)

def createrepo(repodir):
    return subprocess.check_call(["createrepo", repodir])

def mkisofs(outfile, cd_dir, label=None):
    cmd = ["mkisofs", "-o", outfile, "-r", "-input-charset", "utf-8"]
    if label:
        cmd += ["-V", label]
    cmd.append(cd_dir)
    subprocess.check_call(cmd)

def main():
    opts = parse_args()
    outfile = os.path.abspath(opts.filename)
    with in_tempdir(prefix='mkdud.'):
        write_description(opts.description)
        rpmdir = os.path.join("rpms", opts.arch)
        os.makedirs(rpmdir)
        if opts.kmod:
            write_kmod_rpm(rpmdir, "3.0.0")
        if opts.binary:
            write_installer_enhancement_rpm(rpmdir, "19.0")
        if opts.createrepo:
            createrepo(rpmdir)
        mkisofs(outfile, cd_dir=".", label=opts.label)

if __name__ == '__main__':
    main()
