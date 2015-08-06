url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all
part --fstype=ext4 --size=4400 --label=rootfs /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

# Create a partition that's easy to umount and poke at in %post
# The escrow certificate is created in %pre, below
part --fstype=ext4 --size=500 --encrypted --passphrase='passphrase' --escrowcert=file:///tmp/escrow_test/escrow.crt --backuppassphrase /home

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%pre
# Create an nss database for the escrow certificate
mkdir -p /tmp/escrow_test/nss
certutil -d /tmp/escrow_test/nss --empty-password -N

# Create a self-signed certificate
# certutil waits for input if not provided with entropy data (-z). Use some
# crappy data from urandom in the hope of leaving some entropy for the LUKS
# operations to use later.
dd if=/dev/urandom of=/tmp/escrow_test/entropy bs=20 count=1
certutil -d /tmp/escrow_test/nss -S -x -n escrow_cert \
    -s 'CN=Escrow Test' -t ',,TC' -z /tmp/escrow_test/entropy

# Export the certificate
certutil -d /tmp/escrow_test/nss -L -n escrow_cert -a -o /tmp/escrow_test/escrow.crt
%end

%pre-install
# Copy the escrow database to the install path so we can use it during %post
mkdir $ANA_INSTALL_PATH/root
cp -a /tmp/escrow_test $ANA_INSTALL_PATH/root/
%end

%packages
volume_key
%end

%post
# First, check that the escrow stuff is there
ls /root/*-escrow >/dev/null 2>&1
if [[ $? != 0 ]]; then
    echo '*** escrow packet was not created' > /root/RESULT
    exit 1
fi

ls /root/*-escrow-backup-passphrase >/dev/null 2>&1
if [[ $? != 0 ]]; then
    echo '*** backup passphrase was not created' > /root/RESULT
    exit 1
fi

# Get the LUKS device UUID from the escrow packet filename
uuid="$(basename /root/*-escrow | sed 's|-escrow$||')"

# umount and close the LUKS device
umount /home
cryptsetup close /dev/mapper/luks-$uuid

# Try out the backup passphrase
backup_passphrase="$(volume_key --secrets -d /root/escrow_test/nss /root/$uuid-escrow-backup-passphrase | sed -n '/^Passphrase:/s|^Passphrase:[[:space:]]*||p')"

if [[ $? != 0 ]] || [[ -z "$backup_passphrase" ]]; then
    echo '*** unable to parse backup passphrase' > /root/RESULT
    exit 1
fi

echo -n $backup_passphrase | cryptsetup open -q --key-file - --type luks --test-passphrase /dev/disk/by-uuid/$uuid
if [[ $? != 0 ]]; then
    echo '*** unable to decrypt volume with backup passphrase' > /root/RESULT
    exit 1
fi

# Restore access to the volume with the escrow packet
# First, re-encrypt the packet with a passphrase
echo -n -e 'packet passphrase\0packet passphrase\0' | volume_key --reencrypt -b -d /root/escrow_test/nss /root/$uuid-escrow -o /root/escrow-out
if [[ $? != 0 ]] || [[ ! -f /root/escrow-out ]]; then
    echo '*** unable to reencrypt escrow packet' > /root/RESULT
    exit 1
fi

# Use the escrow packet to set a new passphrase on the LUKS volume
echo -n -e 'packet passphrase\0volume passphrase\0volume passphrase\0' | volume_key --restore -b /dev/disk/by-uuid/$uuid /root/escrow-out
if [[ $? != 0 ]]; then
    echo '*** unable to restore volume access with escrow packet' > /root/RESULT
    exit 1
fi

# Make sure the new passphrase actually works
echo -n 'volume passphrase' | cryptsetup open -q --key-file - --type luks --test-passphrase /dev/disk/by-uuid/$uuid
if [[ $? != 0 ]]; then
    echo '*** unable to open volume with restored passphrase' > /root/RESULT
    exit 1
fi

echo 'SUCCESS' > /root/RESULT

%end
