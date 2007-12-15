/*
 * hardware.c - various hardware probing functionality
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
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
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <popt.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>

#include "loader.h"
#include "hardware.h"
#include "pcmcia.h"
#include "log.h"

/* FIXME: for turning off dma */
#include <sys/ioctl.h>
#include <linux/hdreg.h>
#include "../isys/isys.h"

/* boot flags */
extern uint64_t flags;

static int detectHardware(moduleInfoSet modInfo, char *** modules) {
    struct device ** devices, ** device;
    char ** modList;
    int numMods;
    char *driver;

    logMessage(DEBUGLVL, "probing buses");

    devices = probeDevices(CLASS_UNSPEC,
                           BUS_PCI | BUS_SBUS | BUS_VIO | BUS_MACIO |
                           /* Waiting on a kudzu that supports BUS_EBUS... */
                           /* BUS_PCMCIA | BUS_XEN | BUS_EBUS | BUS_PS3, */
                           BUS_PCMCIA | BUS_XEN | BUS_PS3 | BUS_USB,
                           PROBE_ALL);

    logMessage(DEBUGLVL, "finished bus probing");

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
        /* this is kind of icky and verbose.  there are better and more 
         * general ways to do it but this is simple and obvious */
	if (!driver) {
	    logMessage(DEBUGLVL, "ignoring driverless device %s", (*device)->desc);
        } else if (FL_NOPCMCIA(flags) && ((*device)->type == CLASS_SOCKET)) {
            logMessage(DEBUGLVL, "ignoring pcmcia device %s (%s)",
                       (*device)->desc, driver);
        } else if (FL_NOIEEE1394(flags) && ((*device)->type == CLASS_FIREWIRE)) {
            logMessage(DEBUGLVL, "ignoring firewire device %s (%s)",
                       (*device)->desc, driver);
        } else if (FL_NOUSB(flags) && ((*device)->type == CLASS_USB)) {
            logMessage(DEBUGLVL, "ignoring usb device %s (%s)", (*device)->desc,
                       driver);
        } else if (FL_NOSTORAGE(flags) && 
                   (((*device)->type == CLASS_SCSI) || 
                    ((*device)->type == CLASS_IDE) ||
                    ((*device)->type == CLASS_RAID) ||
                    ((*device)->type == CLASS_ATA) ||
                    ((*device)->type == CLASS_SATA))) {
            logMessage(DEBUGLVL, "ignoring storage device %s (%s)",
                       (*device)->desc, driver);
        } else if (FL_NONET(flags) && ((*device)->type == CLASS_NETWORK)) {
            logMessage(DEBUGLVL, "ignoring network device %s (%s)",
                       (*device)->desc, driver);
        } else {
            modList[numMods++] = strdup(driver);
        }
        
        freeDevice (*device);
    }
    
    modList[numMods] = NULL;
    *modules = modList;
    
    free(devices);
    
    return LOADER_OK;
}

int scsiTapeInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo) {
    struct device ** devices;

    if (FL_TESTING(flags)) return 0;

    logMessage(INFO, "looking for scsi tape devices");
    
    devices = probeDevices(CLASS_TAPE, BUS_SCSI, 0);
    
    if (!devices) {
        logMessage(INFO, "no scsi tape devices found");
        return 0;
    }

    logMessage(INFO, "scsi tape device(s) found, loading st.ko");

    if (mlLoadModuleSet("st", modLoaded, modDeps, modInfo)) {
	logMessage(ERROR, "failed to insert st module");
	return 1;
    }
    
    return 0;
}


int probeiSeries(moduleInfoSet modInfo, moduleList modLoaded, 
		 moduleDeps modDeps) {
    /* this is a hack since we can't really probe on iSeries */
#ifdef __powerpc__
    if (!access("/proc/iSeries", X_OK)) {
	mlLoadModuleSet("iseries_veth:veth:viodasd:viocd", modLoaded, modDeps, modInfo);
    }
#endif
    return 0;
}

/* this allows us to do an early load of modules specified on the
 * command line to allow automating the load order of modules so that
 * eg, certain scsi controllers are definitely first.
 * FIXME: this syntax is likely to change in a future release
 *        but is done as a quick hack for the present.
 */
int earlyModuleLoad(int justProbe) {
    int fd, len, i;
    char buf[1024], *cmdLine;
    int argc;
    char ** argv;

    /* FIXME: reparsing /proc/cmdline to avoid major loader changes.  
     * should probably be done in loader.c:parseCmdline() like everything 
     * else
     */
    if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return 1;
    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (len <= 0) return 1;
        
    buf[len] = '\0';
    cmdLine = buf;
    
    if (poptParseArgvString(cmdLine, &argc, (const char ***) &argv))
        return 1;
    
    for (i=0; i < argc; i++) {
        if (!strncasecmp(argv[i], "driverload=", 11)) {
            logMessage(INFO, "loading %s early", argv[i] + 11);
            mlLoadModuleSet(argv[i] + 11);
        }
    }
    return 0;
}

int busProbe(int justProbe) {
    /* autodetect whatever we can */
    if (justProbe)
        return 0;
    return detectHardware(NULL);
}


void ipv6Setup() {
    if (!FL_NOIPV6(flags))
        mlLoadModule("ipv6", NULL);
}

/* check if the system has been booted with dasd parameters */
/* These parameters define the order in which the DASDs */
/* are visible to Linux. Otherwise load dasd modules probeonly, */
/* then parse proc to find active DASDs */
/* Reload dasd_mod with correct range of DASD ports */
void dasdSetup() {
#if !defined(__s390__) && !defined(__s390x__)
    return;
#else
    char **dasd_parms;
    char *line;
    char *parms = NULL, *parms_end;
    FILE *fd;

    dasd_parms = malloc(sizeof(*dasd_parms) * 2);
    dasd_parms[0] = NULL;
    dasd_parms[1] = NULL;

    fd = fopen ("/tmp/dasd_ports", "r");
    if(fd) {
        line = (char *)malloc(sizeof(char) * 200);
        while (fgets (line, 199, fd) != NULL) {
            if((parms = strstr(line, "dasd=")) ||
               (parms = strstr(line, "DASD="))) {
                strncpy(parms, "dasd", 4);
                parms_end = parms;
                while(*parms_end && !(isspace(*parms_end))) parms_end++;
                *parms_end = '\0';
                break;
            }
        }
        fclose(fd);
        if (strlen(parms) > 5)
		dasd_parms[0] = strdup(parms);
        free(line);
    }
    if(dasd_parms[0]) {
        mlLoadModule("dasd_mod", dasd_parms);

        mlLoadModuleSet("dasd_diag_mod:dasd_fba_mod:dasd_eckd_mod");
        free(dasd_parms);
        return;
    } else {
        dasd_parms[0] = "dasd=autodetect";
        mlLoadModule("dasd_mod", dasd_parms);
        mlLoadModuleSet("dasd_diag_mod:dasd_fba_mod:dasd_eckd_mod");
        free(dasd_parms);
    }
#endif
}

void spufsSetup() {
#if !defined(__powerpc__)
    return;
#else
    FILE *fd;
    fd = fopen("/proc/cpuinfo", "r");
    if(fd) {
        char buf[1024];
        while (fgets(buf, 1024, fd) != NULL) {
            if(!strncmp(buf, "cpu\t\t:", 5)) {
                if(strstr(buf, "Cell")) {
                    mlLoadModule("spufs", NULL);
                    break;
                }
            }
        }
        fclose(fd);
        return;
    } else {
        return;
    }
#endif
}
