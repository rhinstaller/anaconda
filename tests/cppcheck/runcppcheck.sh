#!/bin/sh

# Print a list of files to test on stdout
# Takes filter arguments identical to the find utility, for example
# findtestfiles -name '*.py'. Note that pruning directories will not
# work since find is passed a list of filenames as the path arguments.
findtestfiles()
{
    # If the test is being run from a git work tree, use a list of all files
    # known to git
    # shellcheck disable=SC2154
    if [ -d "${top_srcdir}/.git" ]; then
        findpath=$(git ls-files -c "${top_srcdir}")
    # Otherwise list everything under $top_srcdir
    else
        findpath="${top_srcdir} -type f"
    fi

    # shellcheck disable=SC2086
    find $findpath "$@"
}

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
    . "${top_srcdir}/tests/testenv.sh"
fi

if ! type cppcheck > /dev/null 2>&1 ; then
    echo "SKIP - cppcheck must be installed to run it."
    exit 77
fi

# If files were specified on the command line, use those. Otherwise, look
# for all .c files
filelist=
if [ "$#" -gt 0 ]; then
    filelist="$*"
else
    filelist=$(findtestfiles -name '*.c')
fi

# Disable unusedFunction in widgets since everything will show up as unused
# Specify the path twice so the path works relative to both the top of the
# tree and from the tests/ directory.
#
# -D will define macros from libraries for the cppcheck and with --force it
# will tell cppcheck to look even on code which won't be compiled if a macro
# is defined
cppcheck_output="$(echo "$filelist" |
    xargs cppcheck -q -v --error-exitcode=1 \
        --check-level=exhaustive \
        --template='{id}:{file}:{line}: {message}' \
        --inline-suppr \
        --enable=warning,unusedFunction \
        --suppressions-list=cppcheck/suppression-list.txt \
        -DG_DEFINE_TYPE \
        -DG_DEFINE_ABSTRACT_TYPE \
        -DG_DEFINE_TYPE_WITH_CODE \
        -DHAVE_WORKING_FORK \
        -DG_GNUC_END_IGNORE_DEPRECATIONS \
        --force \
        2>&1 )"

if [ -n "$cppcheck_output" ]; then
    echo "$cppcheck_output"
    exit 1
fi
