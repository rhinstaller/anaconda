#!/bin/sh

when_dev_appears() {
    local dev="${1#/dev/}"; shift
    {
        printf 'KERNEL=="%s", ' "$dev"
        printf 'RUN="/sbin/initqueue --settled --onetime --unique %s"\n' "$*"
        printf 'SYMLINK=="%s", ' "$dev"
        printf 'RUN="/sbin/initqueue --settled --onetime --unique %s"\n' "$*"
    } >> /etc/udev/rules.d/99-anaconda.rules
    wait_for_dev "$dev"
}

splitsep ":" "$root" repotype dev path

if [ "$repotype" = "anaconda.hdiso" ]; then
    when_dev_appears "$dev" "/sbin/anaconda-hdroot $dev $path"
    wait_for_mount $repodir
fi
