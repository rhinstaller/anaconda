/*
 * hardware.c - various hardware probing functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#include "loader.h"
#include "hardware.h"
#include "pcmcia.h"
#include "log.h"

/* JKFIXME: this is the same hack as in loader.c for second stage modules */
extern struct moduleBallLocation * secondStageModuleLocation;

static int detectHardware(moduleInfoSet modInfo, 
                          char *** modules, int flags) {
    struct device ** devices, ** device;
    char ** modList;
    int numMods;
    char *driver;
    
    logMessage("probing buses");
    
    devices = probeDevices(CLASS_UNSPEC,
                           BUS_PCI | BUS_SBUS | 
                           (has_pcmcia() ? BUS_PCMCIA : 0),
                           PROBE_ALL);
    
    logMessage("finished bus probing");
    
    if (devices == NULL) {
        *modules = NULL;
        return LOADER_OK;
    }
    
    numMods = 0;
    for (device = devices; *device; device++) numMods++;
    
    if (!numMods) {
        *modules = NULL;
        return LOADER_OK;
    }
    
    modList = malloc(sizeof(*modList) * (numMods + 1));
    numMods = 0;
    
    for (device = devices; *device; device++) {
        driver = (*device)->driver;
        if (strcmp (driver, "ignore") && strcmp (driver, "unknown")
            && strcmp (driver, "disabled")) {
            modList[numMods++] = strdup(driver);
        }
        
        freeDevice (*device);
    }
    
    modList[numMods] = NULL;
    *modules = modList;
    
    free(devices);
    
    return LOADER_OK;
}

int agpgartInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags) {
    struct device ** devices, *p;
    int i;

    if (FL_TESTING(flags)) return 0;

    logMessage("looking for video cards requiring agpgart module");
    
    devices = probeDevices(CLASS_VIDEO, BUS_UNSPEC, PROBE_ALL);
    
    if (!devices) {
        logMessage("no video cards found");
        return 0;
    }

    /* loop thru cards, see if we need agpgart */
    for (i=0; devices[i]; i++) {
        p = devices[i];
        logMessage("found video card controller %s", p->driver);
        
        /* HACK - need to have list of cards which match!! */
        /* JKFIXME: verify this is really still needed */
        if (!strcmp(p->driver, "Card:Intel 810") ||
            !strcmp(p->driver, "Card:Intel 815")) {
            logMessage("found %s card requiring agpgart, loading module",
                       p->driver+5);
            
            if (mlLoadModuleSetLocation("agpgart", modLoaded, modDeps, 
					modInfo, flags, 
					secondStageModuleLocation)) {
                logMessage("failed to insert agpgart module");
                return 1;
            } else {
                /* only load it once! */
                return 0;
            }
        }
    }
    
    return 0;
}

/* This loads the necessary parallel port drivers for printers so that
   kudzu can autodetect and setup printers in post install*/
void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
                            moduleInfoSet modInfo, int flags) {
    /* JKFIXME: this can be used on other arches too... */
#if !defined (__i386__)
    return;
#endif
    if (FL_NOPARPORT(flags)) return;
    
    logMessage("loading parallel port drivers...");
    if (mlLoadModuleSetLocation("parport_pc", modLoaded, modDeps, 
				modInfo, flags,
				secondStageModuleLocation)) {
        logMessage("failed to load parport_pc module");
        return;
    }
}

void updateKnownDevices(struct knownDevices * kd) {
    kdFindScsiList(kd, 0);
    kdFindNetList(kd, 0);
}

int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, struct knownDevices * kd, int flags) {
    int i;
    char ** modList;
    char modules[1024];
    
    /* we always want to try to find out about pcmcia controllers even
     * if using noprobe */
    cardbusControllerInitialize(modLoaded, modDeps, modInfo, flags);

    if (FL_NOPROBE(flags)) return 0;
    
    if (!access("/proc/bus/pci/devices", R_OK) ||
        !access("/proc/openprom", R_OK)) {
        /* autodetect whatever we can */
        if (detectHardware(modInfo, &modList, flags)) {
            logMessage("failed to scan pci bus!");
            return 0;
        } else if (modList && justProbe) {
            for (i = 0; modList[i]; i++)
                printf("%s\n", modList[i]);
        } else if (modList) {
            *modules = '\0';
            
            for (i = 0; modList[i]; i++) {
                if (i) strcat(modules, ":");
                strcat(modules, modList[i]);
            }
            
            mlLoadModuleSet(modules, modLoaded, modDeps, modInfo, flags);

            startPcmciaDevices(modLoaded, flags);

            updateKnownDevices(kd);
        } else 
            logMessage("found nothing");
    }
    
    return 0;
}


void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags,
               struct knownDevices * kd) {
    mlLoadModuleSet("sd_mod:sr_mod", modLoaded, modDeps, modInfo, flags);
}

void ideSetup(moduleList modLoaded, moduleDeps modDeps,
              moduleInfoSet modInfo, int flags,
              struct knownDevices * kd) {
    mlLoadModuleSet("ide-cd", modLoaded, modDeps, modInfo, flags);
}
