url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/ --proxy=127.0.0.1:8080
repo --name=kstest-http --baseurl=HTTP-ADDON-REPO --proxy=127.0.0.1:8080
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
# primary.xml from the repodata
# the kernel package from the Fedora repo
# testpkg-http-core from the addon repo

if ! grep -q '\.treeinfo$' /tmp/proxy.log; then
    result='.treeinfo request was not proxied'
elif ! grep -q 'repodata/.*primary.xml' /tmp/proxy.log; then
    result='repodata requests were not proxied'
elif ! grep -q 'kernel-.*\.rpm' /tmp/proxy.log; then
    result='base repo package requests were not proxied'
elif ! grep -q 'testpkg-http-core.*\.rpm' /tmp/proxy.log; then
    result='addon repo package requests were not proxied'
else
    result='SUCCESS'
fi

# Write the result to the installed /root
echo "$result" > $ANA_INSTALL_PATH/root/RESULT
%end
