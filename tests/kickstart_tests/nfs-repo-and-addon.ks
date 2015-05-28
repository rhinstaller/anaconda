nfs --server=NFS-SERVER --dir=NFS-PATH

# The addon repos are setup with the following packages:
# NFS:
#   - testpkg-nfs-core, to be installed with @core
#   - testpkg-nfs-addon, to be installed because we ask for it
#   - testpkg-share1, contains a file /usr/share/testpkg-2/nfs. To be installed by excluding
#                     the HTTP version.
#   - testpkg-share2, contains a file /usr/share/testpkg-3/nfs. To be excluded via cost
# HTTP:
#   - testpkg-http-core, to be installed with @core
#   - testpkg-http-addon, to be installed because we ask for it
#   - testpkg-share1, contains a file /usr/share/testpkg-2/http. To be excluded via excludepkgs.
#   - testpkg-share2, contains a file /usr/share/testpkg-3/http. To be included via cost.
repo --name=kstest-nfs --baseurl=NFS-ADDON-REPO --cost=50 --install
repo --name=kstest-http --baseurl=HTTP-ADDON-REPO --cost=25 --excludepkgs=testpkg-share2 --install

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
    if [[ -e /usr/share/testpkg-1/nfs ]]; then
        echo "*** unable to find marker for testpkg-share1" >> /root/RESULT
        status=1
    fi

    if [[ -e /usr/share/testpkg-2/http ]]; then
        echo "*** unable to find marker for testpkg-share2" >> /root/RESULT
        status=1
    fi
fi

if [[ "${status}" -eq 0 ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
