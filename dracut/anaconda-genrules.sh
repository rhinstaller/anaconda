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

rule_for_netdev() {
    case $1 in
      any)
        printf 'SUBSYSTEM=="net"' ;;
      ??:??:??:??:??:??)
        printf 'SUBSYSTEM=="net", ATTR{address}=="%s", ACTION=="add"' "$1" ;;
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

# non-network root/repo stuff (network is handled by netroot)
splitsep ":" "$root" repotype dev path
case "$repotype" in
  anaconda-hd) when_diskdev_appears "$dev" "/sbin/anaconda-hdroot $dev $path" ;;
  anaconda-cd) when_diskdev_appears "$dev" "/sbin/anaconda-cdroot $dev" ;;
  anaconda-auto-cd)
    # TODO: special catch-all rule to check every CD that appears
  ;;
esac
str_starts "$root" "anaconda-" && wait_for_dev /dev/root

# Kickstart: see https://fedoraproject.org/wiki/Anaconda/Options#ks
case "$kickstart" in
    file:*|path:*) # file:<path>
        splitsep ":" "$kickstart" kstype kspath
        # It's already here! Parse away!
        if [ "$kstype" = "path" ]; then
            warn "inst.ks='$kickstart'"
            warn "'path:...' is deprecated; please use 'file:...' instead"
        fi
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
            warn "inst.ks='$kickstart'"
            warn "can't get kickstart: biospart isn't supported yet"
            ksdev=""
        else
            ksdev=$(disk_to_dev_path $ksdev)
        fi

        [ -n "$ksdev" ] && \
        when_diskdev_appears "$ksdev" "/sbin/fetch-kickstart $ksdev $kspath"
    ;;
    http|https|ftp|nfs|nfs4)
        # ksiface is set in parse-anaconda-kickstart.sh
        case $ksiface in
            link|ibft) warn "inst.ks.device=$ksiface isn't supported yet!" ;;
            "") ksiface="any" ;;
        esac
        when_netdev_online $ksiface "/sbin/fetch-kickstart $ksiface $kickstart"
    ;;
esac

if [ -n "$kickstart" ]; then
    echo "[ -e /tmp/ks.cfg.done ]" > $hookdir/initqueue/finished/kickstart.sh
