url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part pv.68 --asprimary --fstype="lvmpv" --ondisk=sda --size=7691
part /boot --asprimary --fstype="ext4" --ondisk=sda --size=500
volgroup vg01 --pesize=4096 pv.68
logvol /  --fstype="ext4" --size=5000 --encrypted --name=root_lv --vgname=vg01 --passphrase=OntarioIsAProvince --label=root
logvol /var  --fstype="ext4" --size=1000 --name=var_lv --vgname=vg01
logvol swap  --fstype="swap" --size=1024 --name=swap_lv --vgname=vg01
logvol /home  --fstype="ext4" --grow --size=1 --name=home_lv --vgname=vg01

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages --default
%end

%post
root_lv_type=$(blkid -ovalue -sTYPE /dev/mapper/vg01-root_lv)
if [ "$root_lv_type" != "crypto_LUKS" ]; then
    echo "root LV is not encrypted" > /home/RESULT
else
    echo SUCCESS > /home/RESULT
fi
%end
