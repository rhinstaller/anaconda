/*
 * hardware.c - various hardware probing functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2003 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <popt.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>

#include "loader.h"
#include "hardware.h"
#include "pcmcia.h"
#include "log.h"

/* JKFIXME: this is the same hack as in loader.c for second stage modules */
extern struct moduleBallLocation * secondStageModuleLocation;

/* returns whether or not we can probe devices automatically or have to 
 * ask for them manually. */
int canProbeDevices(void) {
#if defined(__s390__) || defined(__s390x__)
    return 1;
#endif

    if ((access("/proc/bus/pci/devices", R_OK) &&
         access("/proc/openprom", R_OK) &&
         access("/proc/iSeries", R_OK)))
        return 0;

    return 1;    
}

static int detectHardware(moduleInfoSet modInfo, 
                          char *** modules, int flags) {
    struct device ** devices, ** device;
    char ** modList;
    int numMods;
    char *driver;
    
    logMessage("probing buses");
    
    devices = probeDevices(CLASS_UNSPEC,
                           BUS_PCI | BUS_SBUS | 
                           ((has_pcmcia() >= 0) ? BUS_PCMCIA : 0),
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
        /* this is kind of icky and verbose.  there are better and more 
         * general ways to do it but this is simple and obvious */
        if (FL_NOPCMCIA(flags) && ((*device)->type == CLASS_SOCKET)) {
            logMessage("ignoring pcmcia device %s (%s)", (*device)->desc,
                       (*device)->driver);
        } else if (FL_NOIEEE1394(flags) && ((*device)->type == CLASS_FIREWIRE)) {
            logMessage("ignoring firewire device %s (%s)", (*device)->desc,
                       (*device)->driver);
        } else if (FL_NOUSB(flags) && ((*device)->type == CLASS_USB)) {
            logMessage("ignoring usb device %s (%s)", (*device)->desc,
                       (*device)->driver);
        } else if (strcmp (driver, "ignore") && strcmp (driver, "unknown")
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

int scsiTapeInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags) {
    struct device ** devices;

    if (FL_TESTING(flags)) return 0;

    logMessage("looking for scsi tape devices");
    
    devices = probeDevices(CLASS_TAPE, BUS_SCSI, PROBE_ALL);
    
    if (!devices) {
        logMessage("no scsi tape devices found");
        return 0;
    }

    logMessage("scsi tape device(s) found, loading st.o");

    if (mlLoadModuleSetLocation("st", modLoaded, modDeps, 
				modInfo, flags, 
				secondStageModuleLocation)) {
	logMessage("failed to insert st module");
	return 1;
    }
    
    return 0;
}


/* This loads the necessary parallel port drivers for printers so that
   kudzu can autodetect and setup printers in post install*/
void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
                            moduleInfoSet modInfo, int flags) {
    /* JKFIXME: this could be useful on other arches too... */
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
    kdFindIdeList(kd, 0);
    kdFindScsiList(kd, 0);
    kdFindDasdList(kd, 0);
    kdFindNetList(kd, 0);
}

static int probeVirtualPPCDevs(moduleInfoSet modInfo, moduleList modLoaded, 
                               moduleDeps modDeps, struct knownDevices * kd, 
                               int flags) {
#ifdef __powerpc__
    int loadveth = 0, loadvscsi = 0;
    char * buf = NULL;

    if (!access("/proc/device-tree/vdevice/l-lan", F_OK))
        loadveth = 1;
    if (!access("/proc/device-tree/vdevice/v-scsi", F_OK))
        loadvscsi = 1;

    if (loadveth && loadvscsi)
        buf = strdup("ibmveth:ibmvscsic");
    else if (loadveth)
        buf = strdup("ibmveth");
    else if (loadvscsi)
        buf = strdup("ibmvscsic");

    if (buf != NULL) {
	mlLoadModuleSet(buf, modLoaded, modDeps, modInfo, flags);
	updateKnownDevices(kd);
        free(buf);
    }

#endif
    return 0;
}

int probeiSeries(moduleInfoSet modInfo, moduleList modLoaded, 
		 moduleDeps modDeps, struct knownDevices * kd, int flags) {
    /* this is a hack since we can't really probe on iSeries */
#ifdef __powerpc__
    if (!access("/proc/iSeries", X_OK)) {
	mlLoadModuleSet("veth:viodasd:viocd", modLoaded, modDeps, modInfo, flags);
	updateKnownDevices(kd);
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
int earlyModuleLoad(moduleInfoSet modInfo, moduleList modLoaded, 
                    moduleDeps modDeps, int justProbe, 
                    struct knownDevices * kd, int flags) {
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
            logMessage("loading %s early", argv[i] + 11);
            mlLoadModuleSet(argv[i] + 11, modLoaded, modDeps, modInfo, flags);
        }
    }
    updateKnownDevices(kd);
    return 0;
}

int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, struct knownDevices * kd, int flags) {
    int i;
    char ** modList;
    char modules[1024];
    
    /* we always want to try to find out about pcmcia controllers even
     * if using noprobe */
    initializePcmciaController(modLoaded, modDeps, modInfo, flags);

    if (FL_NOPROBE(flags)) return 0;

    /* we can't really *probe* on iSeries, but we can pretend */
    probeiSeries(modInfo, modLoaded, modDeps, kd, flags);

    /* probe power5 virtual devices also (#127705) */
    probeVirtualPPCDevs(modInfo, modLoaded, modDeps, kd, flags);
    
    if (canProbeDevices()) {
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


/* check if the system has been booted with dasd parameters */
/* These parameters define the order in which the DASDs */
/* are visible to Linux. Otherwise load dasd modules probeonly, */
/* then parse proc to find active DASDs */
/* Reload dasd_mod with correct range of DASD ports */
void dasdSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags,
               struct knownDevices * kd) {
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
        free(line);
    }
    if(!parms || (strlen(parms) == 5)) {
        parms = NULL;
    } else {
        dasd_parms[0] = strdup(parms);
        mlLoadModule("dasd_mod", modLoaded, modDeps, modInfo,
                     dasd_parms, flags);

        mlLoadModuleSet("dasd_diag_mod:dasd_fba_mod:dasd_eckd_mod", 
                        modLoaded, modDeps, modInfo, flags);
        return;
    }
    if(!parms) {
        dasd_parms[0] = "dasd=autodetect";
        mlLoadModule("dasd_mod", modLoaded, modDeps, modInfo, dasd_parms, flags);
        mlLoadModuleSet("dasd_diag_mod:dasd_fba_mod:dasd_eckd_mod",
                        modLoaded, modDeps, modInfo, flags);
        free(dasd_parms);
    }
#endif
}

