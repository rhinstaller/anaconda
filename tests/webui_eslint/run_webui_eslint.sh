#!/bin/bash

# If $top_srcdir has not been set by automake, detect it
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
fi

# Check if this test can be run
if ! type npm > /dev/null 2>&1 ; then
    echo "SKIP - npm must be installed to run eslint."
    exit 77
fi
if ! type npx > /dev/null 2>&1 ; then
    echo "SKIP - npx must be installed to run eslint."
    exit 77
fi

# identify what is running to help debugging
echo "npm $(npm --version)"
echo "eslint $(npx eslint --version)"
echo

pushd "${top_srcdir}/ui/webui" > /dev/null || return 1

echo "Installing npm packages:"
npm install
echo

echo "Linting:"
npx eslint --format stylish --no-color src/
exit $?
