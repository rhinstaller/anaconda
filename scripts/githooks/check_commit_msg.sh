#!/bin/bash
#
# Check whether the given commit has a valid BZ ID reference for the given
# release.
#
# $1 -- release number
# $2 -- commit hash
#

exec 1>&2

bzcmd="bugzilla"
release=${1}
commit=${2}
msg="$(git show -s --pretty='%s%n%b' ${commit})"
summary="$(git show -s --pretty='%s%n%b' ${commit}|head -n 1)"

## helper functions ##
# Check the bz to see if it has an ack for this release. If the branch is
# a local branch, just warn. If it is the primary branch, block the commit.
bz_has_ack() {
    bug=$1
    flags=$(${bzcmd} query --bug_id=${bug} --outputformat="%{flags}")

    ack_pattern="rhel-${release}\.[[:digit:]]+\.[[:digit:]]+\+"
    if [[ ! "$flags" =~ $ack_pattern ]]; then
        echo "*** BZ ${bug} is missing acks: ${flags}"

        return 1
    fi
    return 0
}

echo "${summary}" | grep -i '^new version' > /dev/null
if [ $? -eq 0 ]; then
    # "New version" commit doesn't need a BZ ID
    exit 0
fi

for word in ${summary} ; do
    echo "${word}" | grep -q -E "^.*(#[0-9]+).*"
    if [ $? -eq 0 ]; then
        bug="$(echo "${word}" | sed -e 's/^(#//g' -e 's/).*$//g')"
        ${bzcmd} query --bug_id=${bug} --outputformat="%{product}" | grep -q "^Red Hat Enterprise Linux.*"
        if [ $? -ne 0 ]; then
            echo "*** BZ ${bug} is not a RHEL bug."
            exit 1
        fi
        bz_has_ack ${bug}
        exit $?
    fi
done

last=$(($(echo "${msg}" |wc -l) - 2))
if [ ${last} -gt 0 ]; then
    echo "${msg}" | tail -n ${last} | grep -v "^#" |
    grep -E "^(Resolves|Related|Conflicts): rhbz#[0-9]+$" |
    while read line ; do
        bug="$(echo ${line} | cut -d '#' -f 2)"
        ${bzcmd} query --bug_id=${bug} --outputformat="%{product}" | grep -q "^Red Hat Enterprise Linux.*"
        if [ $? -ne 0 ]; then
            echo "*** BZ ${bug} is not a RHEL bug."
            exit 1
        fi
        bz_has_ack ${bug}
        # exit from the loop (piping to while creates a subprocess???)
        exit $?
    done

    # exit from the script with the code from the loop
    exit $?
else
    # nothing found
    echo "*** Commit ${commit} doesn't have bugzilla ID specified ***" >&2
    exit 1
fi
