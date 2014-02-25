%include /usr/share/spin-kickstarts/fedora-livecd-desktop.ks

url --mirrorlist=https://mirrors.fedoraproject.org/metalink?repo=rawhide&arch=x86_64

shutdown
network --bootproto=dhcp --activate
rootpw qweqwe

# Override dumb values from the spin-kickstarts.
bootloader --location=mbr
zerombr
clearpart --all
part / --fstype="ext4" --size=4400
part swap --fstype="swap" --size=512

%post
cat >> /etc/rc.d/init.d/livesys << EOF

if [ -f /usr/share/applications/anaconda.desktop ]; then
    # Make anaconda start automatically, not the welcome thing.
    if [ -f ~liveuser/.config/autostart/fedora-welcome.desktop ]; then
        rm ~liveuser/.config/autostart/fedora-welcome.desktop
    fi

    cp /usr/share/applications/anaconda.desktop ~liveuser/.config/autostart/

    # Enable accessibility needed for testing.
    cat >> /usr/share/glib-2.0/schemas/org.gnome.desktop.interface.gschema.override << FOE
[org.gnome.desktop.interface]
toolkit-accessibility=true
FOE
fi

EOF
%end

%packages
dogtail
-@libreoffice
-java*
%end
