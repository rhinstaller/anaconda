/*
 * pcmcia.c - pcmcia functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1999 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <kudzu/kudzu.h>
#include <stdlib.h>
#include <string.h>

#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "modules.h"

char * getPcicController() {
    struct device ** devices;
    static int probed = 0;
    static char * pcic = NULL;

    if (!probed) {
        probed = 1;

        devices = probeDevices(CLASS_SOCKET, BUS_PCI, PROBE_ALL);
        if (devices) {
            logMessage("found cardbus pci adapter");
            pcic = "yenta_socket";
        }

        /* JKFIXME: need to probe for non-cardbus adapters */

        if (!pcic) {
            logMessage("no pcic controller found");
        }
        return pcic;
    } else {
        return pcic;
    }
}

int cardbusControllerInitialize(moduleList modLoaded, moduleDeps modDeps,
                                moduleInfoSet modInfo, int flags) {
    char * pcic = NULL;
    char * mods;
    int i;

    if (FL_NOPCMCIA(flags))
	return 0;
    
    pcic = getPcicController();
    if (!pcic)
        return 0;

    for (i = 0; i < modInfo->numModules ; i++) {
        if (strcmp(pcic, modInfo->moduleList[i].moduleName)) {
            mods = sdupprintf("pcmcia_core:%s:ds", pcic);
            logMessage("going to insert %s", mods);
            /* JKFIXME: this depends on a hack until pcmcia has module-info */
            mlLoadModuleSetLocation(mods, modLoaded, modDeps, modInfo, 
                                    flags, modInfo->moduleList[i].locationID);
            free(mods);
            break;
        }
    }

    return 0;
}
