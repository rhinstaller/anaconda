#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "probe.h"

static int sortDevices(const void * a, const void * b) {
    const struct kddevice * one = a;
    const struct kddevice * two = b;

    return strcmp(one->name, two->name);
}

static int deviceKnown(struct knownDevices * devices, char * dev) {
    int i;

    for (i = 0; i < devices->numKnown; i++)
    	if (!strcmp(devices->known[i].name, dev)) return 1;

    return 0;
}

static void addDevice(struct knownDevices * devices, struct kddevice dev) {
    if (devices->numKnown == devices->numKnownAlloced) {
    	devices->numKnownAlloced += 5;
    	devices->known = realloc(devices->known, 
		sizeof(*devices->known) * devices->numKnownAlloced);
    }

    devices->known[devices->numKnown++] = dev;
}

void kdAddDevice(struct knownDevices * devices, enum deviceClass devClass, 
		 char * devName, char * devModel) {
    struct kddevice new;

    new.class = devClass;
    new.name = devName;
    new.model = devModel;

    addDevice(devices, new);
}

void kdFree(struct knownDevices * devices) {
    if (devices->known) free(devices->known);
    devices->known = NULL;
    devices->numKnown = devices->numKnownAlloced = 0;
}

int kdFindNetList(struct knownDevices * devices) {
    int fd;
    char buf[1024];
    char * start, * end;
    struct kddevice newDevice;

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
	    if (deviceKnown(devices, start)) continue;

	    newDevice.name = strdup(start);
	    newDevice.model = NULL;
	    newDevice.class = CLASS_NETWORK;
	    addDevice(devices, newDevice);
	}

	start = strchr(end + 1, '\n');
	if (start) start++;
    }

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

    return 0;
}

int kdFindIdeList(struct knownDevices * devices) {
    DIR * dir;
    char path[80];
    int fd, i;
    struct dirent * ent;
    struct kddevice device;

    if (access("/proc/ide", R_OK)) return 0;

    if (!(dir = opendir("/proc/ide"))) {
	return 1;
    }

    /* set errno to 0, so we can tell when readdir() fails */
    errno = 0;
    while ((ent = readdir(dir))) {
    	if (!deviceKnown(devices, ent->d_name)) {
	    sprintf(path, "/proc/ide/%s/media", ent->d_name);
	    if ((fd = open(path, O_RDONLY)) >= 0) {
		i = read(fd, path, 50);
		close(fd);
		path[i - 1] = '\0';		/* chop off trailing \n */

		device.class = CLASS_UNSPEC;
		if (!strcmp(path, "cdrom")) 
		    device.class = CLASS_CDROM;
		else if (!strcmp(path, "disk"))
		    device.class = CLASS_HD;

		if (device.class != CLASS_UNSPEC) {
		    device.name = strdup(ent->d_name);

		    sprintf(path, "/proc/ide/%s/model", ent->d_name);
		    if ((fd = open(path, O_RDONLY)) >= 0) {
			i = read(fd, path, 50);
			close(fd);
			path[i - 1] = '\0';	/* chop off trailing \n */
			device.model = strdup(path);
		    }

		    addDevice(devices, device);
		}
	    }
	}

        errno = 0;          
    }

    closedir(dir);

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

    return 0;
}

#define SCSISCSI_TOP	0
#define SCSISCSI_HOST 	1
#define SCSISCSI_VENDOR 2
#define SCSISCSI_TYPE 	3

int kdFindScsiList(struct knownDevices * devices) {
    int fd;
    char buf[16384];
    char linebuf[80];
    char typebuf[10];
    int i, state = SCSISCSI_TOP;
    char * start, * chptr, * next, *end;
    char driveName = 'a';
    char cdromNum = '0';
    char tapeNum = '0';
    struct kddevice device;

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
		return -1;
	    }
	    state = SCSISCSI_HOST;
	    break;

	  case SCSISCSI_HOST:
	    if (strncmp("Host: ", start, 6)) {
		return -1;
	    }

	    start = strstr(start, "Id: ");
	    if (!start) {
		return -1;
	    }
	    start += 4;

	    /*id = strtol(start, NULL, 10);*/

	    state = SCSISCSI_VENDOR;
	    break;

	  case SCSISCSI_VENDOR:
	    if (strncmp("  Vendor: ", start, 10)) {
		return -1;
	    }

	    start += 10;
	    end = chptr = strstr(start, "Model:");
	    if (!chptr) {
		return -1;
	    }

	    chptr--;
	    while (*chptr == ' ' && *chptr != ':' ) chptr--;
	    if (*chptr == ':') {
		    chptr++;
		    *(chptr + 1) = '\0';
		    strcpy(linebuf,"Unknown");
	    } else {
		    *(chptr + 1) = '\0';
		    strcpy(linebuf, start);
	    }
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
		return -1;
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
		return -1;
	    }
	    *typebuf = '\0';
	    if (strstr(start, "Direct-Access")) {
		sprintf(typebuf, "sd%c", driveName++);
		device.class = CLASS_HD;
	    } else if (strstr(start, "Sequential-Access")) {
		sprintf(typebuf, "st%c", tapeNum++);
		device.class = CLASS_TAPE;
	    } else if (strstr(start, "CD-ROM")) {
		sprintf(typebuf, "scd%c", cdromNum++);
		device.class = CLASS_CDROM;
	    }

	    if (*typebuf && !deviceKnown(devices, typebuf)) {
		device.name = strdup(typebuf);
		device.model = strdup(linebuf);

		/* Do we need this for anything?
		sdi[numMatches].bus = 0;
		sdi[numMatches].id = id;
		*/

		addDevice(devices, device);
	    }

	    state = SCSISCSI_HOST;
	}

	start = next;
    }

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

    return 0;
}

struct knownDevices kdInit(void) {
    struct knownDevices kd;

    memset(&kd, 0, sizeof(kd));

    return kd;
}
