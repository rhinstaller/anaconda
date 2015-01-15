%include /usr/share/spin-kickstarts/fedora-live-workstation.ks

url --mirrorlist=https://mirrors.fedoraproject.org/metalink?repo=rawhide&arch=x86_64

shutdown
network --bootproto=dhcp --activate --device=link
rootpw qweqwe

# Override dumb values from the spin-kickstarts.
bootloader --location=mbr
zerombr
clearpart --all
part / --fstype="ext4" --size=6000

%post
cat >> /etc/rc.d/init.d/livesys << EOF
# Mount the attached disk containing test suite information, if it exists.
blkid -l -t LABEL=ANACTEST
if [ \$? = 0 ]; then
    mkdir /mnt/anactest
    mount -L ANACTEST /mnt/anactest
    chown -R liveuser.liveuser /mnt/anactest

    if [ -f /usr/share/applications/anaconda.desktop ]; then
        # Make anaconda start automatically.
        if [ -f ~liveuser/.config/autostart/fedora-welcome.desktop ]; then
            rm ~liveuser/.config/autostart/fedora-welcome.desktop
        fi

        cp /usr/share/applications/anaconda.desktop ~liveuser/.config/autostart/
        sed -i -e '/Exec=/ s|/usr/bin/liveinst|python /mnt/anactest/suite.py|' ~liveuser/.config/autostart/anaconda.desktop

        # Enable accessibility needed for testing.
        cat >> /usr/share/glib-2.0/schemas/org.gnome.desktop.interface.gschema.override << FOE
[org.gnome.desktop.interface]
toolkit-accessibility=true
FOE
    fi
fi

EOF
%end

%packages
@^workstation-product-environment
-@fedora-release-nonproduct
dogtail
syslinux
-@libreoffice
-java*
%end
