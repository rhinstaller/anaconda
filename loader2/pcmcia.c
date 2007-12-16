/*
 * pcmcia.c - pcmcia functionality
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005  Red Hat, Inc.
 * All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Red Hat Author(s): Erik Troan <ewt@redhat.com>
 *                    Matt Wilson <msw@redhat.com>
 *                    Michael Fulbright <msf@redhat.com>
 *                    Jeremy Katz <katzj@redhat.com>
 *                    Bill Nottingham <notting@redhat.com>
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
                            int i;
			    
			    logMessage(DEBUGLVL, "found pcmcia adapter %s", devices[x]->driver);
			    if (!pcic)
				    tmp = strdup(devices[x]->driver);
			    else {
                                    i = asprintf(&tmp, "%s:%s", pcic,
                                            devices[x]->driver);
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

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
                               moduleInfoSet modInfo) {
    char * pcic = NULL;
    char * mods;
    int i;

    if (FL_NOPCMCIA(flags) || FL_TESTING(flags))
	return 0;

    pcic = getPcicController();
    if (!pcic)
        return 0;

    i = asprintf(&mods, "pcmcia_core:%s:pcmcia", pcic);
    free(pcic);
    mlLoadModuleSet(mods, modLoaded, modDeps, modInfo);
    free(mods);

    startupPcmciaControllers();
    return 0;
}
