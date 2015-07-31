nfs --server=NFS-SERVER --dir=NFS-PATH

# The addon repos are setup with the following packages:
# NFS:
#   - testpkg-nfs-core, to be installed with @core
#   - testpkg-nfs-addon, to be installed because we ask for it
#   - testpkg-share1, contains a file /usr/share/testpkg-1/nfs. To be installed by excluding
#                     the HTTP version, despite http's lower cost.
#   - testpkg-share2, contains a file /usr/share/testpkg-2/nfs. To be excluded via cost
# HTTP:
#   - testpkg-http-core, to be installed with @core
#   - testpkg-http-addon, to be installed because we ask for it
#   - testpkg-share1, contains a file /usr/share/testpkg-1/http. To be excluded via excludepkgs.
#   - testpkg-share2, contains a file /usr/share/testpkg-2/http. To be included because the cost
#                     is lower.
repo --name=kstest-nfs --baseurl=NFS-ADDON-REPO --cost=50
repo --name=kstest-http --baseurl=HTTP-ADDON-REPO --cost=25 --excludepkgs=testpkg-share1 --install

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

%packages
testpkg-nfs-addon
testpkg-http-addon
testpkg-share1
testpkg-share2
%end

%post
status=0

# Check that all the packages were installed
for pkg in testpkg-nfs-core testpkg-nfs-addon testpkg-http-core testpkg-http-addon \
           testpkg-share1 testpkg-share2 ; do
    if ! rpm -q $pkg ; then
        echo "*** package $pkg was not installed" >> /root/RESULT
        status=1
    fi
done

if [[ "${status}" -eq 0 ]]; then
    # Check that the right packages were installed
    if [[ -e /usr/share/testpkg-1/http ]]; then
        echo "*** wrong version of testpkg-share1 was installed" >> /root/RESULT
        status=1
    fi

    if [[ -e /usr/share/testpkg-2/nfs ]]; then
        echo "*** wrong version of testpkg-share2 was installed" >> /root/RESULT
        status=1
    fi

    # Double check that the correct marker files are in place
    if [[ ! -e /usr/share/testpkg-1/nfs ]]; then
        echo "*** unable to find marker for testpkg-share1" >> /root/RESULT
        status=1
    fi

    if [[ ! -e /usr/share/testpkg-2/http ]]; then
        echo "*** unable to find marker for testpkg-share2" >> /root/RESULT
        status=1
    fi
fi

repofile=/etc/yum.repos.d/kstest-http.repo
if [[ "${status}" -eq 0 ]]; then
    # Check that the repo file got installed
    if [[ ! -e $repofile ]]; then
        echo "*** kstest-http.repo was not installed" >> /root/RESULT
        status=1
    # Check that it has all the options
    elif ! grep -q '^baseurl=HTTP-ADDON-REPO$' $repofile ; then
        echo "*** kstest-http.repo is missing the baseurl" >> /root/RESULT
        status=1
    elif ! grep -q '^cost=25$' $repofile; then
        echo "*** kstest-http.repo is missing the cost" >> /root/RESULT
        status=1
    elif ! grep -q '^exclude=testpkg-share1$' $repofile; then
        echo "*** kstest-http.repo is missing the exclude" >> /root/RESULT
        status=1
    fi
fi

if [[ "${status}" -eq 0 ]]; then
    # Check that the NFS repo file was not installed
    if [[ -e /etc/yum.repos.d/kstest-nfs.repo ]]; then
        echo "*** kstest-nfs.repo was installed with --install" >> /root/RESULT
        status=1
    fi
fi

if [[ "${status}" -eq 0 ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
