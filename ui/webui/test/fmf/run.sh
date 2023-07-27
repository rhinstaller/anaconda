#!/bin/sh
set -eux

TESTS="$(realpath $(dirname "$0"))"
SOURCE="$(realpath $TESTS/../../../..)"
LOGS="$(pwd)/logs"
mkdir -p "$LOGS"

cd $SOURCE/ui/webui
make -f Makefile.am prepare-test-deps

# support running from clean git tree
if [ ! -d node_modules/chrome-remote-interface ]; then
    # copy package.json temporarily otherwise npm might try to install the dependencies from it
    rm -f package-lock.json  # otherwise the command below installs *everything*, argh
    mv package.json .package.json
    # only install a subset to save time/space
    npm install chrome-remote-interface sizzle
    mv .package.json package.json
fi

# allow test to do Machine.execute(), to ourselves
install -D -m 600 bots/machine/identity.pub ~/.ssh/authorized_keys

export TEST_AUDIT_NO_SELINUX=1

# HACK: apply cockpit.service from pyanaconda/ui/webui/__init__.py; this should go away, and the test talk to the
# webui-desktop's cockpit-ws
printf '[Service]\nExecStart=/usr/libexec/cockpit-ws --no-tls --port 9090 --local-session=cockpit-bridge\n' > /etc/systemd/system/cockpit.service
systemctl daemon-reload

# reproduce enough of the boot.iso environment
setenforce 0
# FIXME: How does this really look like?
printf '[Default]\nIsFinal=false\n' > /.buildstamp
systemctl start anaconda.service

# give tests a (mock) big hard drive; this won't survive an actual install, of course
modprobe scsi_debug virtual_gb=10

# only a subset of tests work in this environment
TESTS="
TestBasic
TestLanguage
"

# FIXME: adjust tests or setup to make these work
EXCLUDES="
--exclude TestBasic.testAboutModal
--exclude TestBasic.testLanguageScreenHiddenLive
--exclude TestBasic.testNavigation
--exclude TestLanguage.testLanguageSwitching
"

RC=0
test/common/run-tests --nondestructive --trace --machine 127.0.0.1:22 --browser 127.0.0.1:9090 $EXCLUDES $TESTS || RC=$?

cp --verbose Test* "$LOGS" || true
exit $RC
