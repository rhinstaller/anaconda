# Substitute something in for REPO or this will all come crashing down.
ostreesetup --nogpg --osname=fedora-atomic --remote=fedora-atomic --url=REPO --ref=fedora-atomic/rawhide/x86_64/base/core
install
network --bootproto=dhcp

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

%post
cat <<EOF > /lib/systemd/system/default.target.wants/run-test.service
[Unit]
Description=Run a test to see if anaconda+ostree worked
After=basic.target

[Service]
Type=oneshot
ExecStart=/usr/bin/run-test.sh
EOF

cat <<EOF > /usr/bin/run-test.sh
#!/bin/bash

# For now, just the fact that we rebooted is good enough.
echo SUCCESS > /root/RESULT
shutdown -h now
EOF

chmod +x /usr/bin/run-test.sh
%end
