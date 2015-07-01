#!/bin/bash
#
# Copyright (C) 2014, 2015  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>

# This script runs the entire kickstart_tests suite.  It is an interface
# between "make check" (which is why it takes environment variables instead
# of arguments) and livemedia-creator.  Each test consists of a kickstart
# file that specifies most everything about the installation, and a shell
# script that does validation and specifies kernel boot parameters.  lmc
# then fires up a VM and watches for tracebacks or stuck installs.
#
# A boot ISO is required, which should be specified with TEST_BOOT_ISO=.
#
# The number of jobs corresponds to the number of VMs that will be started
# simultaneously.  Each one wants about 2 GB of memory.  The default is
# two simultaneous jobs, but you can control this with TEST_JOBS=.  It is
# suggested you not run out of memory.
#
# You can control what logs are held onto after the test is complete via the
# KEEPIT= variable, explained below.  By default, nothing is kept.
#
# Finally, you can run tests across multiple computers at the same time by
# putting all the hostnames into TEST_REMOTES= as a space separated list.
# Do not add localhost manually, as it will always be added for you.  You
# must create a user named kstest on each remote system, allow that user to
# sudo to root for purposes of running livemedia-creator, and have ssh keys
# set up so that the user running this script can login to the remote systems
# as kstest without a password.  TEST_JOBS= applies on a per-system basis.
# KEEPIT= controls how much will be kept on the master system (where "make
# check" is run).  All results will be removed from the slave systems.

# The boot.iso location can come from one of two different places:
# (1) $TEST_BOOT_ISO, if this script is being called from "make check"
# (2) The command line, if this script is being called directly.  That will
#     be checked below.
IMAGE="${TEST_BOOT_ISO}"

# Possible values for this parameter:
# 0 - Keep nothing (the default)
# 1 - Keep log files
# 2 - Keep log files and disk images (will take up a lot of space)
KEEPIT=${KEEPIT:-0}

while getopts ":i:k:" opt; do
    case $opt in
       i)
           # If this wasn't set from the environment, set it from the command line
           # here.  If it never gets set, we'll catch that later and error out.
           IMAGE=$OPTARG
           ;;

       k)
           # This overrides either the $KEEPIT environment variable, or the default
           # setting from above.
           KEEPIT=$OPTARG
           ;;

       *)
           echo "Usage: run_kickstart_tests.sh [-i boot.iso] [-k 0|1|2] [tests]"
           exit 1
           ;;
    esac
done

if [[ ! -e "${IMAGE}" ]]; then
    echo "Required boot.iso does not exist; skipping."
    exit 77
fi

shift $((OPTIND - 1))

# This is for environment variables that parallel needs to pass to
# remote systems.
#
# NOTE:  You will also need to add these to the list in /etc/sudoers
# if you are using env_reset there, or they will not get passed from
# this script to parallel.
env_args=$(printenv | while read line; do
    v="$(echo $line | cut -d'=' -f1)"
    [[ "${v}" =~ ^KSTEST_ ]] && echo "--env ${v}"
 done)

# We get the list of tests from one of two places:
# (1) From the command line, all the other arguments.
# (2) From finding all scripts in kickstart_tests/ that are executable and are
#     not support files.
if [[ $# != 0 ]]; then
    tests="$*"
else
    tests=$(find kickstart_tests -name '*sh' -a -perm -o+x -a \! -wholename 'kickstart_tests/run_*.sh')
fi

if [[ "$TEST_REMOTES" != "" ]]; then
    _IMAGE=kickstart_tests/$(basename ${IMAGE})

    # (1) Copy everything to the remote systems.  We do this ourselves because
    # parallel doesn't like globs, and we need to put the boot image somewhere
    # that qemu on the remote systems can read.
    for remote in ${TEST_REMOTES}; do
        scp -r kickstart_tests kstest@${remote}:
        scp ${IMAGE} kstest@${remote}:kickstart_tests/
    done

    # (1a) We also need to copy the provided image to under kickstart_tests/ on
    # the local system too.  This is because parallel will attempt to run the
    # same command line on every system and that requires the image to also be
    # in the same location.
    cp ${IMAGE} ${_IMAGE}

    # (2) Run parallel.  We always add the local system to the list of machines
    # being passed to parallel.  Don't add it yourself.
    remote_args="--sshlogin :"
    for remote in ${TEST_REMOTES}; do
        remote_args="${remote_args} --sshlogin kstest@${remote}"
    done

    parallel --no-notice ${remote_args} \
             ${env_args} --jobs ${TEST_JOBS:-2} \
             sudo PYTHONPATH=$PYTHONPATH kickstart_tests/run_one_ks.sh -i ${_IMAGE} -k ${KEEPIT} {} ::: ${tests}
    rc=$?

    # (3) Get all the results back from the remote systems, which will have already
    # applied the KEEPIT setting.  However if KEEPIT is 0 (meaning, don't save
    # anything) there's no point in trying.  We do this ourselves because, again,
    # parallel doesn't like globs.
    #
    # We also need to clean up the stuff we copied over in step 1, and then clean up
    # the results from the remotes too.  We don't want to keep things scattered all
    # over the place.
    for remote in ${TEST_REMOTES}; do
        if [[ ${KEEPIT} > 0 ]]; then
            scp -r kstest@${remote}:/var/tmp/kstest-\* /var/tmp/
        fi

        ssh kstest@${remote} sudo rm -rf kickstart_tests /var/tmp/kstest-\*
    done

    # (3a) And then also remove the copy of the image we made earlier.
    rm ${_IMAGE}

    # (4) Exit the subshell defined by "find ... | " way up at the top.  The exit
    # code will be caught outside and converted into the overall exit code.
    exit ${rc}
else
    parallel --no-notice ${env_args} --jobs ${TEST_JOBS:-2} \
        sudo PYTHONPATH=$PYTHONPATH kickstart_tests/run_one_ks.sh -i ${IMAGE} -k ${KEEPIT} {} ::: ${tests}

    # For future expansion - any cleanup code can go in between the variable
    # setting and the exit, like in the other branch of the if-else above.
    rc=$?
    exit ${rc}
fi

# Catch the exit code of the subshell and return it.  This is structured for
# future expansion, too.  Any extra global cleanup code can go in between the
# variable setting and the exit.
rc=$?
exit ${rc}
