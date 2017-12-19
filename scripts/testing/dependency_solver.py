#!/bin/python3
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

TEST_DEPENDENCIES = ["e2fsprogs", "git", "bzip2", "cppcheck", "rpm-ostree", "pykickstart",
                     "python3-rpmfluff", "python3-mock", "python3-pocketlint",
                     "python3-nose-testconfig", "python3-sphinx_rtd_theme", "python3-lxml",
                     "python3-dogtail", "sudo"]


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


def parse_args():
    parser = ArgumentParser(description="Resolve Anaconda all dependencies.")
    parser.add_argument('-b', '--build', action='store_true',  dest="build",
                        help="resolve build dependencies")
    parser.add_argument('-r', '--runtime', action='store_true', dest='runtime',
                        help="resolve runtime dependencies")
    parser.add_argument('-t', '--test', action='store_true', dest='test',
                        help="resolve test dependencies")
    parser.add_argument('--s390', action='store_true', dest='s390',
                        help="""this is s390 mock environment""")

    return parser.parse_args()


def runtime_dependencies(spec_content):
    """Find all Requires from spec file."""
    packages = re.findall(r"(?<!BuildRequires: )(?<=Requires: ) *[^ \n]*", spec_content)
    result = set()

    for pkg in packages:
        # remove anaconda packages and packages with special autoconf variables
        if "anaconda" not in pkg and "%{" not in pkg:
            result.add(pkg.strip())

    return result


def build_dependencies(spec_content, is_s390):
    """Find all BuildRequires from spec file."""
    packages = re.findall(r"(?<=BuildRequires: ) *[^ \n]*", spec_content)
    result = set()

    for pkg in packages:
        if not is_s390 and "s390utils" in pkg:
            continue
        result.add(pkg.strip())

    return result


def test_dependencies():
    """Install all packages required for running the tests"""
    result = set()
    result.update(TEST_DEPENDENCIES)
    return result


if __name__ == "__main__":
    args = parse_args()
    spec = ""
    res_packages = set()

    nothing_specified = not any([args.runtime, args.build, args.test])

    if args.build or args.runtime or nothing_specified:
        spec = _read_spec_file()

    if args.runtime or nothing_specified:
        res_packages.update(runtime_dependencies(spec))
    if args.build or nothing_specified:
        res_packages.update(build_dependencies(spec, args.s390))
    if args.test or nothing_specified:
        res_packages.update(test_dependencies())

    print(" ".join(res_packages))
