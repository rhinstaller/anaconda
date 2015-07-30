url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
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

# Just install @core
%packages
%end

# Run the proxy
%include proxy-common.ks

%post --nochroot
# Look for the following as evidence that a proxy was used:
# a .treeinfo request
# primary.xml from the repodata
# a package. Let's say kernel, there should definitely have been a kernel

if ! grep -q '\.treeinfo$' /tmp/proxy.log; then
    result='.treeinfo request was not proxied'
elif ! grep -q 'repodata/.*primary.xml' /tmp/proxy.log; then
    result='repodata requests were not proxied'
elif ! grep -q 'kernel-.*\.rpm' /tmp/proxy.log; then
    result='package requests were not proxied'
else
    result='SUCCESS'
fi

# Write the result to the installed /root
echo "$result" > $ANA_INSTALL_PATH/root/RESULT
%end
