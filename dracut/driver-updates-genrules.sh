#!/bin/bash

command -v wait_for_dd >/dev/null || . /lib/anaconda-lib.sh

# Don't leave initqueue until we've finished with the requested dd stuff
[ -f /tmp/dd_todo ] && wait_for_dd

if [ -f /tmp/dd_interactive ]; then
    initqueue --onetime --settled --name zz_dd_interactive \
        systemctl start driver-updates@$(find_tty).service
fi

# Run driver-updates for LABEL=OEMDRV and any other requested disk
for dd in LABEL=OEMDRV $(cat /tmp/dd_disk); do
    when_diskdev_appears "$(disk_to_dev_path $dd)" \
        driver-updates --disk $dd \$devnode
done

# force us to wait at least until we've settled at least once
echo '> /tmp/settle.done' > $hookdir/initqueue/settled/settle_done.sh
echo '[ -f /tmp/settle.done ]' > $hookdir/initqueue/finished/wait_for_settle.sh

# NOTE: dd_net is handled by fetch-driver-net.sh
