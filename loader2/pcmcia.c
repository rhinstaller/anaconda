/*
 * pcmcia.c - pcmcia functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 * Bill Nottingham <notting@redhat.com>
 *
 * Copyright 1999 - 2005 Red Hat, Inc.
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

/* boot flags */
extern uint64_t flags;

char * getPcicController() {
    struct device ** devices;
    static int probed = 0;
    static char * pcic = NULL;

    if (!probed) {
        probed = 1;
 
        devices = probeDevices(CLASS_SOCKET, BUS_UNSPEC, 0);
	if (devices) {    
	    int x;
		
	    for (x = 0; devices[x]; x++) {
		    if (devices[x]->driver) {
			    char *tmp;
			    
			    logMessage(DEBUGLVL, "found pcmcia adapter %s", devices[x]->driver);
			    if (!pcic)
				    tmp = strdup(devices[x]->driver);
			    else {
				    tmp = sdupprintf("%s:%s",pcic,devices[x]->driver);
				    free(pcic);
			    }
			    pcic = tmp;
		    }
	    }
        }

        if (!pcic) {
            logMessage(DEBUGLVL, "no pcic controller found");
        }
        return pcic;
    } else {
        return pcic;
    }
}

int startupPcmciaControllers() {
	char *adj_io[] = {
		"0x00000100 - 0x000003af",
		"0x000003bb - 0x000004cf",
		"0x000004d8 - 0x000004ff",
		"0x00000a00 - 0x00000aff",
		"0x00000c00 - 0x00000cff",
		"0x00004000 - 0x00008fff",
		NULL
	};
	char *adj_mem[] = {
		"0x000c0000 - 0x000fffff",
		"0x60000000 - 0x60ffffff",
		"0xa0000000 - 0xa0ffffff",
		"0xc0200000 - 0xcfffffff",
		"0xe8000000 - 0xefffffff",
		NULL
	};
	char path[128];
	int x;
	
	for (x = 0; ; x++) {
		int y;
		FILE *f;
		
		sprintf(path,"/sys/class/pcmcia_socket/pcmcia_socket%d/available_resources_io", x);
		f = fopen(path, "w");
		if (!f)
			break;
		for (y = 0; adj_io[y]; y++) {
			fprintf(f, "%s\n", adj_io[y]);
		}
		fclose(f);
		
		sprintf(path,"/sys/class/pcmcia_socket/pcmcia_socket%d/available_resources_mem", x);
		f = fopen(path, "w");
		if (!f)
			break;
		for (y = 0; adj_mem[y]; y++) {
			fprintf(f, "%s\n", adj_mem[y]);
		}
		fclose(f);
		
		sprintf(path,"/sys/class/pcmcia_socket/pcmcia_socket%d/available_resources_setup_done", x);
		f = fopen(path,"w");
		if (!f)
			break;
		fprintf(f,"1\n");
		fclose(f);
	}
	return 0;
}

int initializePcmciaDevice(struct device *device) {
    char *path;
    int fd, ret;
    struct pcmciaDevice *dev = (struct pcmciaDevice *)device;

    logMessage(DEBUGLVL, "enabling pcmcia allow_func_id_match for device %d.%d", dev->slot, dev->function);
    if (dev->bus != BUS_PCMCIA)
        return 0;
    asprintf(&path,"/sys/bus/pcmcia/devices/%d.%d/allow_func_id_match",dev->slot, dev->function);
    fd = open(path, O_WRONLY);
    if (fd == -1) {
        logMessage(DEBUGLVL, "error opening %s", path);
        return 1;
    }
    ret = write(fd,"1",1);
    close(fd);
    logMessage(DEBUGLVL, "enabled pcmcia allow_func_id_match");
    return 0;
}

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
                               moduleInfoSet modInfo) {
    char * pcic = NULL;
    char * mods;

    if (FL_NOPCMCIA(flags) || FL_TESTING(flags))
	return 0;

    pcic = getPcicController();
    if (!pcic)
        return 0;

    mods = sdupprintf("pcmcia_core:%s:pcmcia", pcic);
    mlLoadModuleSet(mods, modLoaded, modDeps, modInfo);
	
    startupPcmciaControllers();
    return 0;
}
