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

#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

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
        } else {
            devices = probeDevices(CLASS_SOCKET, BUS_MISC, PROBE_ALL);
            if (devices && strcmp (devices[0]->driver, "ignore") &&
                strcmp(devices[0]->driver, "unknown") && 
                strcmp(devices[0]->driver, "disabled")) {
                logMessage("found pcmcia adapter");
                pcic = strdup(devices[0]->driver);
            }
        }

        if (!pcic) {
            logMessage("no pcic controller found");
        }
        return pcic;
    } else {
        return pcic;
    }
}

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
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



/* code from notting to activate pcmcia devices.  all kinds of wackiness */
static int pcmcia_major = 0;

static int lookup_dev(char *name) {
    FILE *f;
    int n;
    char s[32], t[32];
             
    f = fopen("/proc/devices", "r");
    if (f == NULL)
        return -errno;
    while (fgets(s, 32, f) != NULL) {
        if (sscanf(s, "%d %s", &n, t) == 2)
            if (strcmp(name, t) == 0)
                break;
    }
    fclose(f);
    if (strcmp(name, t) == 0)
        return n;
    else
        return -ENODEV;
}

static int open_sock(int sock) {
    int fd;
    char fn[64];
    dev_t dev = (pcmcia_major<<8) + sock;
        
    snprintf(fn, 64, "/tmp/pcmciadev-%d", getpid());
    if (mknod(fn, (S_IFCHR|0600), dev) == 0) {
        fd = open(fn, O_RDONLY);
        unlink(fn);
        if (fd >= 0)
            return fd;
    }
    return -1;
}

/* return whether or not we have pcmcia loaded */
int has_pcmcia(void) {
    if (pcmcia_major > 0)
        return pcmcia_major;
    pcmcia_major = lookup_dev("pcmcia");
    return pcmcia_major;
}

struct bind_info_t {
    char dev_info[32];
    unsigned char function;
    /* Not really a void *. Some convuluted structure that appears
     * to be NULL in cardmgr. */
    void *instance;
    char name[32];
    unsigned short major;
    unsigned short minor;
    void *next;
};


#define DS_BIND_REQUEST _IOWR('d', 60, struct bind_info_t)
int activate_pcmcia_device(struct pcmciaDevice *pdev) {
    int fd;
    struct bind_info_t * bind;

    if (has_pcmcia() <= 0) {
        logMessage("pcmcia not loaded, can't activate module");  
        return -1;
    }

    fd = open_sock(pdev->slot);
    if (fd < 0) {
        logMessage("unable to open slot");
        return -1;
    }

    bind = calloc(1, sizeof(struct bind_info_t *));
    strcpy(bind->dev_info,pdev->driver);
    bind->function = pdev->function;
    if (ioctl(fd, DS_BIND_REQUEST, bind) == -1) {
        logMessage("failed to activate pcmcia device");
        return LOADER_ERROR;
    }
    return LOADER_OK;
}

void startPcmciaDevices(moduleList modLoaded, int flags) {
    struct device ** devices;
    int i;

    /* no pcmcia, don't try to start the devices */
    if (has_pcmcia() <= 0)
        return;

    devices = probeDevices(CLASS_UNSPEC, BUS_PCMCIA, PROBE_ALL);
    if (!devices) {
        logMessage("no devices to activate\n");
        return;
    }

    for (i = 0; devices[i]; i++) {
        if (devices[i]->bus != BUS_PCMCIA)
            continue;
        if (!(strcmp (devices[i]->driver, "ignore") && 
              strcmp (devices[i]->driver, "unknown") &&
              strcmp (devices[i]->driver, "disabled"))) 
            continue;
        if (!mlModuleInList(devices[i]->driver, modLoaded))
            continue;
        
        logMessage("going to activate device using %s", devices[i]->driver);
        activate_pcmcia_device((struct pcmciaDevice *)devices[i]);
    }
}
