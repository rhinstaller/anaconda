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

#include "lang.h"
#include "log.h"
#include "modules.h"
#include "windows.h"

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1

typedef int int32;

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

struct intfconfig_s {
    newtComponent ipEntry, nmEntry, gwEntry, nsEntry;
    char * ip, * nm, * gw, * ns;
};

static void spawnShell(void) {
    pid_t pid;
    int fd;

    if (!testing) {
	fd = open("/dev/tty2", O_RDWR);
	if (fd < 0) {
	    logMessage("cannot open /dev/tty2 -- no shell will be provided");
	    return;
	} else if (access("/bin/sh",  X_OK))  {
	    logMessage("cannot open shell - /bin/sh doesn't exist");
	    return;
	}

	if (!(pid = fork())) {
	    dup2(fd, 0);
	    dup2(fd, 1);
	    dup2(fd, 2);

	    close(fd);
	    setsid();
	    if (ioctl(0, TIOCSCTTY, NULL)) {
		perror("could not set new controlling tty");
	    }

	    execl("/bin/sh", "-/bin/sh", NULL);
	    logMessage("exec of /bin/sh failed: %s", strerror(errno));
	}

	close(fd);

	return pid;
    }

    return -1;
}


static void ipCallback(newtComponent co, void * dptr) {
    struct intfconfig_s * data = dptr;
    struct in_addr ipaddr, nmaddr, addr;
    char * ascii;
    int broadcast, network;

    if (co == data->ipEntry) {
	if (strlen(data->ip) && !strlen(data->nm)) {
	    if (inet_aton(data->ip, &ipaddr)) {
		ipaddr.s_addr = ntohl(ipaddr.s_addr);
		if (((ipaddr.s_addr & 0xFF000000) >> 24) <= 127)
		    ascii = "255.0.0.0";
		else if (((ipaddr.s_addr & 0xFF000000) >> 24) <= 191)
		    ascii = "255.255.0.0";
		else 
		    ascii = "255.255.255.0";
		newtEntrySet(data->nmEntry, ascii, 1);
	    }
	}
    } else if (co == data->nmEntry) {
	if (!strlen(data->ip) || !strlen(data->nm)) return;
	if (!inet_aton(data->ip, &ipaddr)) return;
	if (!inet_aton(data->nm, &nmaddr)) return;

        network = ipaddr.s_addr & nmaddr.s_addr;
	broadcast = (ipaddr.s_addr & nmaddr.s_addr) | (~nmaddr.s_addr);

	if (!strlen(data->gw)) {
	    addr.s_addr = htonl(ntohl(broadcast) - 1);
	    newtEntrySet(data->gwEntry, inet_ntoa(addr), 1);
	}

	if (!strlen(data->ns)) {
	    addr.s_addr = htonl(ntohl(network) + 1);
	    newtEntrySet(data->nsEntry, inet_ntoa(addr), 1);
	}
    }
}

int readNetConfig(char * device, struct intfInfo * dev) {
    newtComponent text, f, okay, back, answer;
    newtGrid grid, subgrid, buttons;
    struct intfconfig_s c;
    int i;
    struct in_addr addr;

    text = newtTextboxReflowed(-1, -1, 
		_("Please enter the IP configuration for this machine. Each "
		  "item should be entered as an IP address in dotted-decimal "
		  "notation (for example, 1.2.3.4)."), 50, 5, 10, 0);

    subgrid = newtCreateGrid(2, 4);
    newtGridSetField(subgrid, 0, 0, NEWT_GRID_COMPONENT,
		     newtLabel(-1, -1, _("IP address:")),
		     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 1, NEWT_GRID_COMPONENT,
    		     newtLabel(-1, -1, _("Netmask:")),
		     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 2, NEWT_GRID_COMPONENT,
    		     newtLabel(-1, -1, _("Default gateway (IP):")),
		     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 3, NEWT_GRID_COMPONENT,
    		     newtLabel(-1, -1, _("Primary nameserver:")),
		     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    c.ipEntry = newtEntry(-1, -1, NULL, 16, &c.ip, 0);
    c.nmEntry = newtEntry(-1, -1, NULL, 16, &c.nm, 0);
    c.gwEntry = newtEntry(-1, -1, NULL, 16, &c.gw, 0);
    c.nsEntry = newtEntry(-1, -1, NULL, 16, &c.ns, 0);

    newtGridSetField(subgrid, 1, 0, NEWT_GRID_COMPONENT, c.ipEntry,
		     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 1, NEWT_GRID_COMPONENT, c.nmEntry,
		     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 2, NEWT_GRID_COMPONENT, c.gwEntry,
		     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 3, NEWT_GRID_COMPONENT, c.nsEntry,
		     1, 0, 0, 0, 0, 0);

    buttons = newtButtonBar(_("Ok"), &okay, _("Back"), &back, NULL);

    grid = newtCreateGrid(1, 3);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
		     0, 0, 0, 0, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, subgrid,
		     0, 1, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
		     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Configure TCP/IP"));
    newtGridFree(grid, 1);
   
    newtComponentAddCallback(c.ipEntry, ipCallback, &c);
    newtComponentAddCallback(c.nmEntry, ipCallback, &c);
    
    do {
	answer = newtRunForm(f);

	if (answer == back) {
	    newtFormDestroy(f);
	    newtPopWindow();

	    return LOADER_BACK;
	} 

	i = 0;
	if (*c.ip && inet_aton(c.ip, &addr)) {
	    i++;
	    dev->ip = addr;
	}

	if (*c.nm && inet_aton(c.nm, &addr)) {
	    i++;
	    dev->netmask = addr;
	}

	if (i != 2) {
	    newtWinMessage(_("Missing Information"), _("Retry"),
			    _("You must enter both a valid IP address and a "
			      "netmask."));
	}
    } while (i != 2);

    *((int32 *) &dev->broadcast) = (*((int32 *) &dev->ip) & 
		       *((int32 *) &dev->netmask)) | 
		       ~(*((int32 *) &dev->netmask));

    *((int32 *) &dev->network) = 
	    *((int32 *) &dev->ip) &
	    *((int32 *) &dev->netmask);

    strcpy(dev->device, device);

    return 0;
}

int deviceKnown(char * dev) {
    int i;

    for (i = 0; i < numKnownDevices; i++)
    	if (!strcmp(knownDevices[i].name, dev)) return 1;

    return 0;
}

static int findNetList(void) {
    int fd;
    char buf[1024];
    char * start, * end;

    if ((fd = open("/proc/net/dev", O_RDONLY)) < 0) {
	fprintf(stderr, "failed to open /proc/net/dev!\n");
	return 1;
    }

    read(fd, buf, sizeof(buf));
    close(fd);

    /* skip the first two lines */
    start = strchr(buf, '\n');
    if (!start) return 0;
    start = strchr(start + 1, '\n');
    if (!start) return 0;

    start++;
    while (start && *start) {
	while (isspace(*start)) start++;
	end = strchr(start, ':');
	if (!end) return 0;
	*end = '\0';
	
    	if (strcmp(start, "lo")) {
	    if (deviceKnown(start)) continue;

	    knownDevices[numKnownDevices].name = strdup(start);
	    knownDevices[numKnownDevices].model = NULL;
	    knownDevices[numKnownDevices++].class = DEVICE_NET;
	}

	start = strchr(end + 1, '\n');
	if (start) start++;
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

static int detectHardware(moduleInfoSet modInfo, 
			  struct moduleInfo *** modules) {
    struct pciDevice **devices, **device;
    struct moduleInfo * mod, ** modList;
    int numMods, i;

    if (probePciReadDrivers(testing ? "../isys/pci/pcitable" :
			              "/modules/pcitable")) {
        logMessage("An error occured while reading the PCI ID table");
	return LOADER_ERROR;
    }

    logMessage("looking for devices on pci bus\n");
    
    devices = probePci(0, 0);
    if (devices == NULL) {
        *modules = NULL;
	return LOADER_OK;
    }

    modList = malloc(sizeof(*modList) * 50);	/* should be enough */
    numMods = 0;

    for (device = devices; *device; device++) {
	if ((mod = isysFindModuleInfo(modInfo, (*device)->driver))) {
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
    moduleList modLoaded;
    moduleDeps modDeps;
    int local = 0;
    int i, rc;
    moduleInfoSet modInfo;
    int newtRunning = 0;
    struct intfInfo netDev;
    struct moduleInfo ** modList;
    struct poptOption optionTable[] = {
	    { "network", '\0', POPT_ARG_NONE, &network, 0 },
	    { "local", '\0', POPT_ARG_NONE, &local, 0 },
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
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

    arg = testing ? "/boot/module-info" : "/modules/module-info";
    modInfo = isysNewModuleInfoSet();
    if (isysReadModuleInfo(arg, modInfo)) {
        fprintf(stderr, "failed to read %s\n", arg);
	sleep(5);
	exit(1);
    }

    openLog(testing);

    logMessage("looking around for statically compiled devices");

    findIdeList();
    findScsiList();
    findNetList();
    mlReadLoadedList(&modLoaded);
    modDeps = mlNewDeps();
    mlLoadDeps(modDeps, "/modules/modules.dep");

    if (!access("/proc/bus/pci/devices", R_OK)) {
        /* autodetect whatever we can */
        if (detectHardware(modInfo, &modList)) {
	    fprintf(stderr, "failed to scan for pci devices\n");
	    sleep(5);
	    exit(1);
	} else if (modList) {
	    for (i = 0; modList[i]; i++) {
	    	if (modList[i]->major == DRIVER_NET) {
		    mlLoadModule(modList[i]->moduleName, modLoaded, modDeps, 
				 testing);
		}
	    }

	    for (i = 0; modList[i]; i++) {
	    	if (modList[i]->major == DRIVER_SCSI) {
		    if (!newtRunning) {
		    	newtInit();
			newtCls();
			newtRunning = 1;
		    }

		    winStatus(40, 3, _("Loading SCSI driver"), 
		    	      "Loading %s driver...", modList[i]->moduleName);
		    mlLoadModule(modList[i]->moduleName, modLoaded, modDeps, 
				 testing);
		    newtPopWindow();
		}
	    }

	    findScsiList();
	    findNetList();
	}
    }

    
    if (!newtRunning) {
	newtInit();
	newtCls();
	newtRunning = 1;
    }

    readNetConfig("eth0", &netDev);
    netDev.isPtp = netDev.isUp = 0;

    configureNetDevice(&netDev);

    mlLoadModule("nfs", modLoaded, modDeps, 
		 testing);

    doPwMount("207.175.42.68:/mnt/test/msw/i386",
    	      "/mnt/source", "nfs", 1, 0, NULL, NULL);
 
    symlink("mnt/source/RedHat/instimage/usr", "/usr");
    symlink("mnt/source/RedHat/instimage/lib", "/lib");

    unlink("/modules/modules.dep");
    unlink("/modules/module-info");
    unlink("/modules/modules.cgz");
    unlink("/modules/pcitable");

    symlink("../mnt/source/RedHat/instimage/modules/modules.dep",
	    "/modules/modules.dep");
    symlink("../mnt/source/RedHat/instimage/modules/module-info",
	    "/modules/module-info");
    symlink("../mnt/source/RedHat/instimage/modules/modules.cgz",
	    "/modules/modules.cgz");
    symlink("../mnt/source/RedHat/instimage/modules/pcitable",
	    "/modules/pcitable");

    if (newtRunning) newtFinished();
    closeLog();

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

    configureNetDevice(&netDev);

    spawnShell();

    argptr = anacondaArgs;
    *argptr++ = "/usr/bin/anaconda";
    *argptr++ = "-p";
    *argptr++ = "/mnt/source";

    if (!testing) {
    	execv(anacondaArgs[0], anacondaArgs);
        perror("exec");
    }

    return 1;
}

