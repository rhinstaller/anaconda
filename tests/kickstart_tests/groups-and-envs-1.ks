url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install

bootloader --timeout=1
zerombr
clearpart --all
part --fstype=ext4 --size=4400 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
@core
@c-development
@^web-server-environment
%end

%post
cat <<EOF > /lib/systemd/system/default.target.wants/run-test.service
[Unit]
Description=Run a test to see if anaconda worked
After=basic.target

[Service]
Type=oneshot
ExecStart=/usr/bin/run-test.sh
EOF

cat <<EOF > /usr/bin/run-test.sh
#!/bin/bash

# We don't have a way of determining if a group/env is installed or not.
# These sentinel packages will have to do.
if [[ \$(rpm -q httpd) != 0 ]]; then
    echo FAILURE > /root/RESULT
elif [[ \$(rpm -q gcc) != 0 ]]; then
    echo FAILURE > /root/RESULT
else
    echo SUCCESS > /root/RESULT
fi

shutdown -h now
EOF

chmod +x /usr/bin/run-test.sh
%end
