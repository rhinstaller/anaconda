#!/bin/bash
# parse-anaconda-dd.sh: handle driver update disk settings

# Creates the following files:
#  /tmp/dd_net: list of URLs to fetch
#  /tmp/dd_disk: list of disk devices to load from
#  /tmp/dd_interactive: "menu" if interactive mode requested
#  /tmp/dd_todo: concatenation of the above files

# clear everything to ensure idempotency
rm -f /tmp/dd_interactive /tmp/dd_net /tmp/dd_disk /tmp/dd_todo

# parse any dd/inst.dd args found
for dd in $(getargs dd= inst.dd=); do
    case "$dd" in
        # plain 'dd'/'inst.dd': Engage interactive mode!
        dd|inst.dd) echo menu > /tmp/dd_interactive ;;
        # network URLs: add to dd_net
        http:*|https:*|ftp:*|nfs:*|nfs4:*) echo $dd >> /tmp/dd_net ;;
        # disks: strip "cdrom:" or "hd:" and add to dd_disk
        cdrom:*|hd:*) echo ${dd#*:} >> /tmp/dd_disk ;;
        # anything else is assumed to be a disk
        *) echo $dd >> /tmp/dd_disk
    esac
done

# for convenience's sake, mash 'em all into one list
cat /tmp/dd_net /tmp/dd_disk /tmp/dd_interactive > /tmp/dd_todo
