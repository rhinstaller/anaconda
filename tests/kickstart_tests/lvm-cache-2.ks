#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part /boot --fstype=ext4 --size=300
part pv.1 --fstype=lvmpv --size=6600
part pv.2 --fstype=lvmpv --size=3100

volgroup fedora pv.1 pv.2
logvol swap --name=swap --vgname=fedora --size=500 --fstype=swap
logvol / --name=root --vgname=fedora --size=4000 --grow --fstype=ext4 --cachepvs=pv.2 --cachesize=1000 --cachemode=writethrough
logvol /home --name=home --vgname=fedora --size=1000 --grow --fstype=ext4 --cachepvs=pv.2 --cachesize=1000 --cachemode=writeback

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
%end

%post
root_lv="/dev/mapper/fedora-root"
root_uuid="UUID=$(blkid -o value -s UUID "$root_lv")"
home_lv="/dev/mapper/fedora-home"
home_uuid="UUID=$(blkid -o value -s UUID "$home_lv")"

# verify root LV is mounted at /mnt/sysimage
root_mount=$(grep ^$root_lv\\s/\\s /proc/mounts)
if [ -z  "$root_mount" ]; then
    echo "*** lvm lv 'fedora-root' is not mounted at /" >> /root/RESULT
fi

root_fstype=$(echo "$root_mount" | cut -d' ' -f3)
if [ "$root_fstype" != "ext4" ]; then
    echo "*** lvm lv 'fedora-root' does not contain an ext4 fs" >> /root/RESULT
fi

# verify root entry in /etc/fstab is correct
root_lv_entry=$(grep ^$root_lv\\s/\\s /etc/fstab)
root_uuid_entry=$(grep ^$root_uuid\\s/\\s /etc/fstab)
if [ -z "$root_lv_entry" -a -z "$root_uuid_entry" ] ; then
    echo "*** root LV is not the root entry in /etc/fstab" >> /root/RESULT
fi

# verify swap on lvm is active
swap_lv="/dev/mapper/fedora-swap"
swap_uuid="UUID=$(blkid -o value -s UUID "$swap_lv")"
swap_dm=$(basename $(readlink "$swap_lv"))
if ! grep -q "$swap_dm" /proc/swaps ; then
    echo "*** lvm lv 'fedora-swap' is not active as swap space" >> /root/RESULT
fi

# verify swap entry in /etc/fstab is correct
swap_lv_entry=$(grep ^$swap_lv\\sswap\\s /etc/fstab)
swap_uuid_entry=$(grep ^$swap_uuid\\sswap\\s /etc/fstab)
if [ -z "$swap_lv_entry" -a -z "$swap_uuid_entry" ] ; then
    echo "*** swap lv is not in /etc/fstab" >> /root/RESULT
fi

# verify size of swap lv
# FIXME: this is not true now!
# swap_lv_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/swap)
# if [ "$swap_lv_size" != "500.00" ]; then
#     echo "*** swap lv has incorrect size" >> /root/RESULT
# fi

# we don't need to check sizes of grown LVs, the fact that the installation
# reached this point means everything fit into the VG somehow

## cache-specific checks
# verify that root and home LVs are cached
lvs -o lv_attr --noheadings fedora/root|grep -q '^\s\+C'
if [ $? != 0 ]; then
    echo "*** root LV is not cached" >> /root/RESULT
fi
lvs -o lv_attr --noheadings fedora/home|grep -q '^\s\+C'
if [ $? != 0 ]; then
    echo "*** home LV is not cached" >> /root/RESULT
fi

# verify size of root LV's cache
root_cache_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/root_cache | sed -r 's/\s*([0-9]+)\..*/\1/')
root_cache_md_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/root_cache_cmeta | sed -r 's/\s*([0-9]+)\..*/\1/')
root_cache_all=$(($root_cache_size + $root_cache_md_size))
if [ "$root_cache_all" != "1000" ]; then
    echo "*** root LV's cache has incorrect size" >> /root/RESULT
fi

# verify size of home LV's cache
home_cache_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/home_cache | sed -r 's/\s*([0-9]+)\..*/\1/')
home_cache_md_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/home_cache_cmeta | sed -r 's/\s*([0-9]+)\..*/\1/')
home_cache_all=$(($home_cache_size + $home_cache_md_size))
if [ "$home_cache_all" != "1000" ]; then
    echo "*** home LV's cache has incorrect size" >> /root/RESULT
fi

# verify mode of root LV's cache
root_cache_mode=$(lvs --noheadings -o cachemode fedora/root|sed -r 's/\s*//')
if [ "$root_cache_mode" != "writethrough" ]; then
    echo "*** root LV's cache has wrong mode" >> /root/RESULT
fi

# verify mode of home LV's cache
home_cache_mode=$(lvs --noheadings -o cachemode fedora/home|sed -r 's/\s*//')
if [ "$home_cache_mode" != "writeback" ]; then
    echo "*** home LV's cache has wrong mode" >> /root/RESULT
fi

# verify caches are using (only) the right (aka "faster") PV for both data and metadata
fast_pv=$(pvs --noheadings -o name,size --unit m --nosuffix|egrep '3[0-9]{3}'|sed -r 's/\s+(\S+)\s+.*/\1/')

root_cache_num_pvs=$(lvs -a --noheadings -o devices fedora/root_cache_cdata|wc -l)
if [ "$root_cache_num_pvs" != "1" ]; then
    echo "*** root LV's cache is using multiple PVs" >> /root/RESULT
fi
home_cache_num_pvs=$(lvs -a --noheadings -o devices fedora/home_cache_cdata|wc -l)
if [ "$home_cache_num_pvs" != "1" ]; then
    echo "*** home LV's cache is using multiple PVs" >> /root/RESULT
fi

root_cache_num_pvs=$(lvs -a --noheadings -o devices fedora/root_cache_cmeta|wc -l)
if [ "$root_cache_num_pvs" != "1" ]; then
    echo "*** root LV's cache (meta) is using multiple PVs" >> /root/RESULT
fi
home_cache_num_pvs=$(lvs -a --noheadings -o devices fedora/home_cache_cmeta|wc -l)
if [ "$home_cache_num_pvs" != "1" ]; then
    echo "*** home LV's cache (meta) is using multiple PVs" >> /root/RESULT
fi

root_cache_pv=$(lvs -a --noheadings -o devices fedora/root_cache_cdata|sed -r 's/\s*([^(]+)\(.*/\1/')
if [ "$root_cache_pv" != "$fast_pv" ]; then
    echo "*** root LV's cache is using wrong PV" >> /root/RESULT
fi
home_cache_pv=$(lvs -a --noheadings -o devices fedora/home_cache_cdata|sed -r 's/\s*([^(]+)\(.*/\1/')
if [ "$home_cache_pv" != "$fast_pv" ]; then
    echo "*** home LV's cache is using wrong PV" >> /root/RESULT
fi

root_cache_pv=$(lvs -a --noheadings -o devices fedora/root_cache_cmeta|sed -r 's/\s*([^(]+)\(.*/\1/')
if [ "$root_cache_pv" != "$fast_pv" ]; then
    echo "*** root LV's cache (meta) is using wrong PV" >> /root/RESULT
fi
home_cache_pv=$(lvs -a --noheadings -o devices fedora/home_cache_cmeta|sed -r 's/\s*([^(]+)\(.*/\1/')
if [ "$home_cache_pv" != "$fast_pv" ]; then
    echo "*** home LV's cache (meta) is using wrong PV" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi

%end
