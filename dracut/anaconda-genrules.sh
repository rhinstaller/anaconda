#!/bin/sh

rulesfile=/etc/udev/rules.d/99-anaconda.rules

when_diskdev_appears() {
    local dev="${1#/dev/}" cmd=""; shift
    cmd="/sbin/initqueue --settled --onetime --unique $*"
    {
        printf 'SUBSYSTEM=="block", KERNEL=="%s", RUN+="%s"\n' "$dev" "$cmd"
        printf 'SUBSYSTEM=="block", SYMLINK=="%s", RUN+="%s"\n' "$dev" "$cmd"
    } >> $rulesfile
}

# non-network root/repo stuff (network is handled by netroot)
splitsep ":" "$root" repotype repodev repopath
case "$repotype" in
    anaconda-disk)
        repodev=$(disk_to_dev_path $repodev)
        when_diskdev_appears "$repodev" "/sbin/anaconda-diskroot $repodev $repopath"
    ;;
    anaconda-auto-cd)
        # special catch-all rule for CDROMs
        echo 'ENV{ID_CDROM}=="1",' \
               'RUN+="/sbin/initqueue --settled --onetime --unique' \
                 '/sbin/anaconda-diskroot $env{DEVNAME}"\n' >> $rulesfile
    ;;
esac
if str_starts "$root" "anaconda-"; then
    wait_for_dev /dev/root
    # TODO: add useful message to be displayed on emergency
fi

# Kickstart: see https://fedoraproject.org/wiki/Anaconda/Options#ks
# Network rules for handling kickstarts
rule_for_netdev() {
    case $1 in
      any)
        printf 'SUBSYSTEM=="net"' ;;
      link)
        printf 'SUBSYSTEM=="net", ATTR{carrier}=="1"' ;;
      ??:??:??:??:??:??)
        printf 'SUBSYSTEM=="net", ATTR{address}=="%s"' "$1" ;;
      *)
        printf 'SUBSYSTEM=="net", ENV{INTERFACE}=="%s"' "$1" ;;
    esac
}

when_netdev_online() {
    local dev="$1" cmd="" rule="" opts='OPTIONS+="event_timeout=360"'; shift
    {
        rule=$(rule_for_netdev $dev)
        cmd='RUN+="/sbin/ifup $env{INTERFACE}"'
        printf "$rule, $opts, $cmd\n" "$dev"
        rule="${rule%, ACTION==*}, ACTION==\"online\""
        cmd="RUN+=\"/sbin/initqueue --settled --onetime --unique $*\""
        printf "$rule, $opts, $cmd\n" "$dev"
    } >> $rulesfile
}

case "${kickstart%%:*}" in
    file|path) # file:<path> (we accept path: but that's deprecated)
        splitsep ":" "$kickstart" kstype kspath
        if [ -f "$kspath" ]; then
            cp $kspath /tmp/ks.cfg
            /sbin/parse-kickstart $kspath >> /etc/cmdline.d/80kickstart.conf
            unset CMDLINE
        else
            warn "inst.ks='$kickstart'"
            warn "can't find $kspath!"
        fi
    ;;
    cdrom|hd|bd) # cdrom:<dev>, hd:<dev>:<path>, bd:<dev>:<path>
        splitsep ":" "$kickstart" kstype ksdev kspath
        if [ "$kstype" = "bd" ]; then
            # TODO FIXME
            warn "inst.ks='$kickstart'"
            warn "can't get kickstart: biospart isn't supported yet"
            ksdev=""
        else
            ksdev=$(disk_to_dev_path $ksdev)
        fi
        [ -n "$ksdev" ] && \
        when_diskdev_appears "$ksdev" "/sbin/fetch-kickstart-disk $ksdev $kspath"
    ;;
    http|https|ftp|nfs|nfs4)
        [ "$ksiface" = "ibft" ] && warn "inst.ks.device=$ksiface isn't supported yet!" ;;
        when_netdev_online "${ksiface:-any}" "/sbin/fetch-kickstart-net $ksiface $kickstart"
    ;;
esac

if [ -n "$kickstart" ]; then
    echo "[ -e /tmp/ks.cfg.done ]" > $hookdir/initqueue/finished/kickstart.sh
