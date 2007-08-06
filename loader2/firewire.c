/*
 * firewire.c - firewire probing/module loading functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <kudzu/kudzu.h>
#include <newt.h>
#include <unistd.h>

#include "loader.h"
#include "log.h"
#include "modules.h"
#include "windows.h"

/* boot flags */
extern uint64_t flags;

int firewireInitialize(moduleList modLoaded, moduleDeps modDeps,
			      moduleInfoSet modInfo) {
    struct device ** devices;
    int i = 0;
    int found = 0;

    if (FL_NOIEEE1394(flags)) return 0;

    devices = probeDevices(CLASS_FIREWIRE, BUS_PCI, 0);

    if (!devices) {
	logMessage(INFO, "no firewire controller found");
	return 0;
    }

    startNewt();

    /* JKFIXME: if we looked for all of them, we could batch this up and it
     * would be faster */
    for (i=0; devices[i]; i++) {
	if (!devices[i]->driver)
	    continue;
	logMessage(INFO, "found firewire controller %s", devices[i]->driver);

        winStatus(40, 3, _("Loading"), _("Loading %s driver..."), 
                  devices[0]->driver);

        if (mlLoadModuleSet(devices[i]->driver, modLoaded, modDeps, modInfo)) {
            logMessage(ERROR, "failed to insert firewire module");
        } else {
           found++;
        }
    }

    if (found == 0) {
        newtPopWindow();
        return 1;
    }

    sleep(3);

    logMessage(INFO, "probing for firewire scsi devices");
    devices = probeDevices(CLASS_SCSI, BUS_FIREWIRE, 0);

    if (!devices) {
	logMessage(DEBUGLVL, "no firewire scsi devices found");
        newtPopWindow();
	return 0;
    }

    for (i=0;devices[i];i++) {
	if ((devices[i]->detached == 0) && (devices[i]->driver != NULL)) {
 	    logMessage(INFO, "found firewire device using %s",
		       devices[i]->driver);
	    mlLoadModuleSet(devices[i]->driver, modLoaded, modDeps, modInfo);
	}
    }

    newtPopWindow();

    return 0;
}

