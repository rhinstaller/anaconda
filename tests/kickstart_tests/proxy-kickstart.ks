url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/ --proxy=127.0.0.1:8080
repo --name=kstest-http --baseurl=HTTP-ADDON-REPO --proxy=127.0.0.1:8080 --install
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all
autopart

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

# Install @core, which will also pull in testpkg-http-core from the addon repo
%packages
%end

# Start the proxy server
%include proxy-common.ks

%post --nochroot
# Look for the following as evidence that a proxy was used:
# a .treeinfo request
grep -q '\.treeinfo$' /tmp/proxy.log
if [[ $? -ne 0 ]]; then
    echo '.treeinfo request was not proxied' >> $ANA_INSTALL_PATH/root/RESULT
fi

# primary.xml from the repodata
grep -q 'repodata/.*primary.xml' /tmp/proxy.log
if [[ $? -ne 0 ]]; then
    echo 'repodata requests were not provxied' >> $ANA_INSTALL_PATH/root/RESULT
fi

# the kernel package from the Fedora repo
grep -q 'kernel-.*\.rpm' /tmp/proxy.log
if [[ $? -ne 0 ]]; then
    echo 'base repo package requests were not proxied' >> $ANA_INSTALL_PATH/root/RESULT
fi

# testpkg-http-core from the addon repo
grep -q 'testpkg-http-core.*\.rpm' /tmp/proxy.log
if [[ $? -ne 0 ]]; then
    echo 'addon repo package requests were not proxied' >> $ANA_INSTALL_PATH/root/RESULT
fi

# Check that the addon repo file was installed
if [[ ! -f $ANA_INSTALL_PATH/etc/yum.repos.d/kstest-http.repo ]]; then
    echo 'kstest-http.repo does not exist' >> $ANA_INSTALL_PATH/root/RESULT
fi

# Check that the proxy configuration was written to the repo file
grep -q 'proxy=http://127.0.0.1:8080' $ANA_INSTALL_PATH/etc/yum.repos.d/kstest-http.repo
if [[ $? -ne 0 ]]; then
    echo 'kstest-http.repo does not contain proxy information' >> $ANA_INSTALL_PATH/root/RESULT
fi

# Check that the installed repo file is usable
# dnf exits with 0 even if something goes wrong, so do a repoquery and look for
# the package in the output
chroot $ANA_INSTALL_PATH \
    dnf --disablerepo=\* --enablerepo=kstest-http --quiet repoquery testpkg-http-core 2>/dev/null | \
    grep -q 'testpkg-http-core'
if [[ $? -ne 0 ]]; then
    echo 'unable to query kstest-http repo' >> $ANA_INSTALL_PATH/root/RESULT
fi

# Finally, check that the repoquery used the proxy
tail -1 /tmp/proxy.log | grep -q repodata
if [[ $? -ne 0 ]]; then
    echo 'repoquery on installed system was not proxied' >> $ANA_INSTALL_PATH/root/RESULT
fi

# If nothing was written to RESULT, it worked
if [[ ! -f $ANA_INSTALL_PATH/root/RESULT ]]; then
    echo 'SUCCESS' > $ANA_INSTALL_PATH/root/RESULT
fi

%end
