/*
 * loader.c
 * 
 * This is the installer loader.  Its job is to somehow load the rest
 * of the installer into memory and run it.  This may require setting
 * up some devices and networking, etc. The main point of this code is
 * to stay SMALL! Remember that, live by that, and learn to like it.
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 1999 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <arpa/inet.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#include "isys/imount.h"
#include "isys/inet.h"
#include "isys/isys.h"
#include "isys/pci/pciprobe.h"

#include "windows.h"
#include "log.h"
#include "lang.h"

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1

struct device {
    char * name;		/* malloced */
    char * model;
    enum deviceClass { DEVICE_UNKNOWN, DEVICE_DISK, DEVICE_CDROM, DEVICE_NET,
    		       DEVICE_TAPE }
    	class;
};

int testing = 0;
struct device knownDevices[100];		/* arbitrary limit <shrug> */
int numKnownDevices = 0;

int deviceKnown(char * dev) {
    int i;

    for (i = 0; i < numKnownDevices; i++)
    	if (!strcmp(knownDevices[i].name, dev)) return 1;

    return 0;
}

static int findNetList(void) {
    struct ifconf ifc;
    struct ifreq intfs[50];		/* should be enough <shrug> */
    int s;

    ifc.ifc_req = intfs;
    ifc.ifc_len = sizeof(intfs);
    s = socket(AF_INET, SOCK_DGRAM, 0);

    if (ioctl(s, SIOCGIFCONF, &ifc)) {
        logMessage("failed to get list of networking interfaces");
	close(s);
	return 1;
    }

    close(s);

    for (s = 0; s < ifc.ifc_len / sizeof(struct ifreq); s++) {
    	if (!strcmp(intfs[s].ifr_name, "lo")) continue;
	if (deviceKnown(intfs[s].ifr_name)) continue;

	knownDevices[numKnownDevices].name = strdup(intfs[s].ifr_name);
	knownDevices[numKnownDevices].model = NULL;
	knownDevices[numKnownDevices++].class = DEVICE_NET;
    }

    return 0;
}

static int findIdeList(void) {
    DIR * dir;
    char path[80];
    int fd, i;
    struct dirent * ent;
    struct device device;

    if (access("/proc/ide", R_OK)) return 0;

    if (!(dir = opendir("/proc/ide"))) {
        logMessage("failed to open /proc/ide for reading");
	return 1;
    }

    /* set errno to 0, so we can tell when readdir() fails */
    errno = 0;
    while ((ent = readdir(dir))) {
    	if (!deviceKnown(ent->d_name)) {
	    sprintf(path, "/proc/ide/%s/media", ent->d_name);
	    if ((fd = open(path, O_RDONLY)) >= 0) {
		i = read(fd, path, 50);
		close(fd);
		path[i - 1] = '\0';		/* chop off trailing \n */

		device.class = DEVICE_UNKNOWN;
		if (!strcmp(path, "cdrom")) 
		    device.class = DEVICE_CDROM;
		else if (!strcmp(path, "disk"))
		    device.class = DEVICE_DISK;

		if (device.class != DEVICE_UNKNOWN) {
		    device.name = strdup(ent->d_name);

		    sprintf(path, "/proc/ide/%s/model", ent->d_name);
		    if ((fd = open(path, O_RDONLY)) >= 0) {
			i = read(fd, path, 50);
			close(fd);
			path[i - 1] = '\0';	/* chop off trailing \n */
			device.model = strdup(path);
		    }

		    knownDevices[numKnownDevices++] = device;
		}
	    }
	}

        errno = 0;          
    }

    closedir(dir);

    return 0;
}

#define SCSISCSI_TOP	0
#define SCSISCSI_HOST 	1
#define SCSISCSI_VENDOR 2
#define SCSISCSI_TYPE 	3

int findScsiList(void) {
    int fd;
    char buf[16384];
    char linebuf[80];
    char typebuf[10];
    int i, state = SCSISCSI_TOP;
    char * start, * chptr, * next, *end;
    char driveName = 'a';
    char cdromNum = '0';
    char tapeNum = '0';

    if (access("/proc/scsi/scsi", R_OK)) return 0;

    fd = open("/proc/scsi/scsi", O_RDONLY);
    if (fd < 0) return 1;
    
    i = read(fd, buf, sizeof(buf) - 1);
    if (i < 1) {
        close(fd);
	return 1;
    }
    close(fd);
    buf[i] = '\0';

    start = buf;
    while (*start) {
	chptr = start;
 	while (*chptr != '\n') chptr++;
	*chptr = '\0';
	next = chptr + 1;

	switch (state) {
	  case SCSISCSI_TOP:
	    if (strcmp("Attached devices: ", start)) {
		logMessage("unexpected line in /proc/scsi/scsi: %s", start);
		return LOADER_ERROR;
	    }
	    state = SCSISCSI_HOST;
	    break;

	  case SCSISCSI_HOST:
	    if (strncmp("Host: ", start, 6)) {
		logMessage("unexpected line in /proc/scsi/scsi: %s", start);
		return LOADER_ERROR;
	    }

	    start = strstr(start, "Id: ");
	    if (!start) {
		logMessage("Id: missing in /proc/scsi/scsi");
		return LOADER_ERROR;
	    }
	    start += 4;

	    /*id = strtol(start, NULL, 10);*/

	    state = SCSISCSI_VENDOR;
	    break;

	  case SCSISCSI_VENDOR:
	    if (strncmp("  Vendor: ", start, 10)) {
		logMessage("unexpected line in /proc/scsi/scsi: %s", start);
		return LOADER_ERROR;
	    }

	    start += 10;
	    end = chptr = strstr(start, "Model:");
	    if (!chptr) {
		logMessage("Model missing in /proc/scsi/scsi");
		return LOADER_ERROR;
	    }

	    chptr--;
	    while (*chptr == ' ') chptr--;
	    *(chptr + 1) = '\0';

	    strcpy(linebuf, start);
	    *linebuf = toupper(*linebuf);
	    chptr = linebuf + 1;
	    while (*chptr) {
		*chptr = tolower(*chptr);
		chptr++;
	    }

	    start = end;  /* beginning of "Model:" */
	    start += 7;
		
	    chptr = strstr(start, "Rev:");
	    if (!chptr) {
		logMessage("Rev missing in /proc/scsi/scsi");
		return LOADER_ERROR;
	    }
	   
	    chptr--;
	    while (*chptr == ' ') chptr--;
	    *(chptr + 1) = '\0';

	    strcat(linebuf, " ");
	    strcat(linebuf, start);

	    state = SCSISCSI_TYPE;

	    break;

	  case SCSISCSI_TYPE:
	    if (strncmp("  Type:", start, 7)) {
		logMessage("unexpected line in /proc/scsi/scsi: %s", start);
		return LOADER_ERROR;
	    }
	    *typebuf = '\0';
	    if (strstr(start, "Direct-Access")) {
		sprintf(typebuf, "sd%c", driveName++);
		knownDevices[numKnownDevices].class = DEVICE_DISK;
	    } else if (strstr(start, "Sequential-Access")) {
		sprintf(typebuf, "st%c", tapeNum++);
		knownDevices[numKnownDevices].class = DEVICE_DISK;
	    } else if (strstr(start, "CD-ROM")) {
		sprintf(typebuf, "scd%c", cdromNum++);
		knownDevices[numKnownDevices].class = DEVICE_CDROM;
	    }

	    if (*typebuf && !deviceKnown(typebuf)) {
		knownDevices[numKnownDevices].name = strdup(typebuf);
		knownDevices[numKnownDevices].model = strdup(linebuf);

		/* Do we need this for anything?
		sdi[numMatches].bus = 0;
		sdi[numMatches].id = id;
		*/

		numKnownDevices++;
	    }

	    state = SCSISCSI_HOST;
	}

	start = next;
    }

    return 0;
}

static int detectHardware(struct moduleInfo *** modules) {
    struct pciDevice **devices, **device;
    struct moduleInfo * mod, ** modList;
    int numMods, i;

    if (probePciReadDrivers(testing ? "../isys/pci/pcitable" :
			              "/etc/pcitable")) {
        logMessage("An error occured while reading the PCI ID table");
	return LOADER_ERROR;
    }
    
    devices = probePci(0, 0);
    if (devices == NULL) {
        *modules = NULL;
	return LOADER_OK;
    }

    modList = malloc(sizeof(*modList) * 50);	/* should be enough */
    numMods = 0;

    for (device = devices; *device; device++) {
	if ((mod = isysFindModuleInfo((*device)->driver))) {
	    for (i = 0; i < numMods; i++) 
	        if (modList[i] == mod) break;
	    if (i == numMods) 
		modList[numMods++] = mod;
	}
    }

    if (numMods) {
        *modules = modList;
	modList[numMods] = NULL;
    } else {
        free(modList);
	*modules = NULL;
    }

    free(devices);

    return LOADER_OK;
}

int main(int argc, char ** argv) {
    char ** argptr;
    char * anacondaArgs[30];
    char * arg;
    poptContext optCon;
    int network = 0;
    int local = 0;
    int i, rc;
    struct moduleInfo ** modList;
    struct poptOption optionTable[] = {
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
	    { "network", '\0', POPT_ARG_NONE, &network, 0 },
	    { "local", '\0', POPT_ARG_NONE, &local, 0 },
	    { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext(NULL, argc, argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    if ((arg = poptGetArg(optCon))) {
	fprintf(stderr, "unexpected argument: %s\n", arg);
	exit(1);
    }

    if (isysReadModuleInfo("/boot/module-info")) {
        fprintf(stderr, "failed to read /boot/module-info");
	sleep(5);
	exit(1);
    }

    openLog(testing);

    logMessage("looking around for statically compiled devices");

    findIdeList();
    findScsiList();
    findNetList();

    if (!access("/proc/bus/pci/devices", R_OK)) {
        /* autodetect whatever we can */
        if (detectHardware(&modList)) {
	    fprintf(stderr, "failed to scan for pci devices\n");
	    sleep(5);
	    exit(1);
	} else if (modList) {
	    for (i = 0; modList[i]; i++)
	        printf("should try %s\n", modList[i]->moduleName);
	}
    }

    for (i = 0; i < numKnownDevices; i++) {
    	printf("%-5s ", knownDevices[i].name);
	if (knownDevices[i].class == DEVICE_CDROM)
	    printf("cdrom");
	else if (knownDevices[i].class == DEVICE_DISK)
	    printf("disk ");
	else if (knownDevices[i].class == DEVICE_NET)
	    printf("net  ");
    	if (knownDevices[i].model)
	    printf(" %s\n", knownDevices[i].model);
	else
	    printf("\n");
    }

    closeLog();
}

