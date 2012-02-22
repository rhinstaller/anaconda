%post --nochroot

if [ ! -d /tmp/anaconda-screenshots ]; then
    exit 0
fi

mkdir -m 0750 -p /mnt/sysimage/root/anaconda-screenshots
cp -a /tmp/anaconda-screenshots/*.png /mnt/sysimage/root/anaconda-screenshots/

%end
