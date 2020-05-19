#!/bin/python3
#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
#
# Resolve dependencies from spec file.
#
# Return a list of packages required for build, runtime, tests or combination of those.
#
# For detailed help call ./dependency_resolver.py -h
#

import os
import re
from argparse import ArgumentParser

ANACONDA_SPEC_NAME = "anaconda.spec.in"

TEST_DEPENDENCIES = [
    "e2fsprogs",
    "git",
    "bzip2",
    "cppcheck",
    "rpm-ostree",
    "pykickstart",
    "python3-pip",
    "python3-lxml",
    "policycoreutils",  # contains restorecon which was removed in Fedora 28 mock
]

# This is useful to remove dependencies from spec file.
EXCLUDE_SPEC_DEPENDENCIES = [
    "blivet-gui-runtime",
    "hfsplus-tools",
]

PIP_DEPENDENCIES = [
    "rpmfluff",
    "dogtail",
    "pocketlint",
    "nose-testconfig",
    "coverage",
    "pycodestyle",  # pep8 check
]

RELEASE_DEPENDENCIES = []


def _resolve_top_dir():
    top_dir = os.path.dirname(os.path.realpath(__file__))
    # go up two dirs to get top path
    top_dir = os.path.split(top_dir)[0]
    return os.path.split(top_dir)[0]


def _read_spec_file():
    top_dir = _resolve_top_dir()

    spec_path = os.path.join(top_dir, ANACONDA_SPEC_NAME)
    with open(spec_path, 'r') as f:
        spec_content = f.read()

    return spec_content


def _filter_out_excludes(pkgs):
    return list(filter(lambda x: x not in EXCLUDE_SPEC_DEPENDENCIES, pkgs))


def parse_args():
    parser = ArgumentParser(description="Resolve Anaconda all dependencies.",
                            epilog="Without any options the '-b -r -t' options will be used.")
    parser.add_argument('-b', '--build', action='store_true', dest='build',
                        help="resolve build dependencies")
    parser.add_argument('-r', '--runtime', action='store_true', dest='runtime',
                        help="resolve runtime dependencies")
    parser.add_argument('-t', '--test', action='store_true', dest='test',
                        help="resolve test dependencies")
    parser.add_argument('-p', '--pip', action='store_true', dest='pip',
                        help="resolve pip dependencies")
    parser.add_argument('--release', action='store_true', dest='release',
                        help="packages required to make a new release")
    parser.add_argument('--s390', action='store_true', dest='s390',
                        help="this is s390 mock environment")

    return parser.parse_args()


def runtime_dependencies(spec_content):
    """Find all Requires from spec file."""
    packages = re.findall(r"\n *Requires: *([^ \n]*)", spec_content)
    result = set()

    for pkg in packages:
        # remove anaconda packages and packages with special autoconf variables
        if "anaconda" not in pkg and "%{" not in pkg:
            result.add(pkg.strip())

    result = _filter_out_excludes(result)

    return result


def build_dependencies(spec_content, is_s390):
    """Find all BuildRequires from spec file."""
    packages = re.findall(r"\n *BuildRequires: *([^ \n]*)", spec_content)
    result = set()

    for pkg in packages:
        if not is_s390 and "s390utils" in pkg:
            continue
        result.add(pkg.strip())

    result = _filter_out_excludes(result)

    return result


def test_dependencies():
    """Install all packages required for running the tests"""
    result = set()
    result.update(TEST_DEPENDENCIES)
    return result


def pip_dependencies():
    """Install these test dependencies via pip"""
    result = set()
    result.update(PIP_DEPENDENCIES)
    return result


def release_dependencies():
    """Dependencies required to make a new release"""
    result = set()
    result.update(RELEASE_DEPENDENCIES)
    return result


if __name__ == "__main__":
    args = parse_args()
    spec = ""
    res_packages = set()

    nothing_specified = not any([args.runtime, args.build, args.release, args.test])

    if args.build or args.runtime or nothing_specified:
        spec = _read_spec_file()

    if args.runtime or nothing_specified:
        res_packages.update(runtime_dependencies(spec))
    if args.build or nothing_specified:
        res_packages.update(build_dependencies(spec, args.s390))
    if args.test or nothing_specified:
        res_packages.update(test_dependencies())
    if args.release:
        res_packages.update(release_dependencies())
    if args.pip:
        res_packages = pip_dependencies()

    print(" ".join(res_packages))
