#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/cdrom.h>
#include <linux/hdreg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "isys.h"
#include "probe.h"

static int dac960GetDevices(struct knownDevices * devices);
static int CompaqSmartArrayGetDevices(struct knownDevices * devices);
static int CompaqSmartArray5300GetDevices(struct knownDevices * devices);
static int I2OGetDevices(struct knownDevices * devices, int code);

static int readFD (int fd, char **buf)
{
    char *p;
    size_t size = 4096;
    int s, filesize;

    *buf = malloc (size);
    if (*buf == 0)
      return -1;

    filesize = 0;
    do {
	p = &(*buf) [filesize];
	s = read (fd, p, 4096);
	if (s < 0)
	    break;
	filesize += s;
	if (s != 4096)
	    break;
	size += 4096;
	*buf = realloc (*buf, size);
    } while (1);

    if (filesize == 0 && s < 0) {
	free (*buf);     
	*buf = NULL;
	return -1;
    }

    return filesize;
}

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

int kdFindNetList(struct knownDevices * devices, int code) {
    int fd;
    char *buf;
    char * start, * end;
    struct kddevice newDevice;
    int s;

    if ((fd = open("/proc/net/dev", O_RDONLY)) < 0) {
	fprintf(stderr, "failed to open /proc/net/dev!\n");
	return 1;
    }

    s = readFD(fd, &buf);
    close(fd);
    if (s < 0) {
	fprintf(stderr, "error reading /proc/net/dev!\n");
	return 1;
    }

    buf[s] = '\0';

    /* skip the first two lines */
    start = strchr(buf, '\n');
    if (!start) goto bye;
    start = strchr(start + 1, '\n');
    if (!start) goto bye;

    start++;
    while (start && *start) {
	while (isspace(*start)) start++;
	end = strchr(start, ':');
	if (!end) goto bye;
	*end = '\0';
	
    	if (strcmp(start, "lo")) {
	    if (deviceKnown(devices, start)) continue;

	    newDevice.name = strdup(start);
	    newDevice.model = NULL;
	    newDevice.class = CLASS_NETWORK;
	    newDevice.code = code;
	    addDevice(devices, newDevice);
	}

	start = strchr(end + 1, '\n');
	if (start) start++;
    }

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

bye:
    free (buf);
    return 0;
}

int kdFindIdeList(struct knownDevices * devices, int code) {
    DIR * dir;
    char path[80];
    int fd, i;
    struct dirent * ent;
    struct kddevice device;
    struct hd_driveid hdId;
    char devChar;
    char name[10];
    struct cdrom_volctrl vol;

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

		device.code = code;

		device.class = CLASS_UNSPEC;
		if (!strcmp(path, "cdrom")) 
		    device.class = CLASS_CDROM;
		else if (!strcmp(path, "disk"))
		    device.class = CLASS_HD;
		else if (!strcmp(path, "floppy"))
		    device.class = CLASS_FLOPPY;

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

    for (devChar = 'a'; devChar <= 'h'; devChar++) {
	sprintf(name, "hd%c", devChar);
	if (deviceKnown(devices, name)) continue;
	
	devMakeInode(name, "/tmp/ideprobe");
	fd = open("/tmp/ideprobe", O_RDONLY | O_NONBLOCK);
	unlink("/tmp/ideprobe");

	if (fd < 0) continue;

	device.name = strdup(name);

	ioctl(fd, HDIO_GET_IDENTITY, &hdId);
	close(fd);

	if (!ioctl(fd, CDROMVOLCTRL, &vol))
		device.class = CLASS_CDROM;
	else if (hdId.command_set_1 & 4)
		device.class = CLASS_FLOPPY;
	else
		device.class = CLASS_HD;

	if (*hdId.model)
		device.model = strdup(hdId.model);

	addDevice(devices, device);
    }

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

    return 0;
}

#define SCSISCSI_TOP	0
#define SCSISCSI_HOST 	1
#define SCSISCSI_VENDOR 2
#define SCSISCSI_TYPE 	3

int kdFindScsiList(struct knownDevices * devices, int code) {
    int fd;
    char *buf;
    char linebuf[80];
    char typebuf[10];
    int i, state = SCSISCSI_TOP;
    char * start, * chptr, * next, *end;
    char driveName = 'a';
    char cdromNum = '0';
    char tapeNum = '0';
    struct kddevice device;
    int val = 0;

    if (access("/proc/scsi/scsi", R_OK)) {
	dac960GetDevices(devices);
	CompaqSmartArrayGetDevices(devices);
	CompaqSmartArray5300GetDevices(devices);
	I2OGetDevices(devices, code);
	return 0;
    }

    fd = open("/proc/scsi/scsi", O_RDONLY);
    if (fd < 0) return 1;
    
    i = readFD(fd, &buf);
    if (i < 1) {
        close(fd);
	return 1;
    }
    close(fd);
    buf[i] = '\0';

    if (!strncmp(buf, "Attached devices: none", 22)) {
	dac960GetDevices(devices);
	CompaqSmartArrayGetDevices(devices);
	CompaqSmartArray5300GetDevices(devices);
	I2OGetDevices(devices, code);
	goto bye;
    }

    start = buf;
    while (*start) {
	chptr = start;
 	while (*chptr != '\n') chptr++;
	*chptr = '\0';
	next = chptr + 1;

	switch (state) {
	  case SCSISCSI_TOP:
	    if (strcmp("Attached devices: ", start)) {
		val = -1;
		goto bye;
	    }
	    state = SCSISCSI_HOST;
	    break;

	  case SCSISCSI_HOST:
	    if (strncmp("Host: ", start, 6)) {
		val = -1;
		goto bye;
	    }

	    start = strstr(start, "Id: ");
	    if (!start) {
		val = -1;
		goto bye;
	    }
	    start += 4;

	    /*id = strtol(start, NULL, 10);*/

	    state = SCSISCSI_VENDOR;
	    break;

	  case SCSISCSI_VENDOR:
	    if (strncmp("  Vendor: ", start, 10)) {
		val = -1;
		goto bye;
	    }

	    start += 10;
	    end = chptr = strstr(start, "Model:");
	    if (!chptr) {
		val = -1;
		goto bye;
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
		val = -1;
		goto bye;
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
		val = -1;
		goto bye;
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
		device.code = code;

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

    dac960GetDevices(devices);
    CompaqSmartArrayGetDevices(devices);
    CompaqSmartArray5300GetDevices(devices);
    I2OGetDevices(devices, code);

    qsort(devices->known, devices->numKnown, sizeof(*devices->known),
	  sortDevices);

bye:
    free (buf);
    return val;
}

struct knownDevices kdInit(void) {
    struct knownDevices kd;

    memset(&kd, 0, sizeof(kd));

    return kd;
}

static int dac960GetDevices(struct knownDevices * devices) {
    struct kddevice newDevice;
    char ctl[50];
    int ctlNum = 0;
    char *buf = NULL;
    int fd;
    int i;
    char * start, * chptr;

    sprintf(ctl, "/proc/rd/c%d/current_status", ctlNum++);

    while ((fd = open(ctl, O_RDONLY)) >= 0) {
    	free (buf);
	i = readFD(fd, &buf);
	buf[i] = '\0';
	start = buf;
	while (start && (start = strstr(start, "/dev/rd/"))) {
	    start += 5;
	    chptr = strchr(start, ':');

	    *chptr = '\0';
	    if (!deviceKnown(devices, start)) {
		newDevice.name = strdup(start);

		start = chptr + 2;
		chptr = strchr(start, '\n');
		*chptr = '\0';

		newDevice.model = strdup(start);
		newDevice.class = CLASS_HD;
		addDevice(devices, newDevice);

		*chptr = '\n';
	    } else {
		*chptr = '\0';
	    }

	    start = strchr(chptr, '\n');
	    if (start) start++;
	}

	sprintf(ctl, "/proc/rd/c%d/current_status", ctlNum++);
    }

    free (buf);
    return 0;
}

static int CompaqSmartArrayGetDevices(struct knownDevices * devices) {
    struct kddevice newDevice;
    FILE *f;
    char buf[256];
    char *ptr;
    int numMatches = 0, ctlNum = 0;
    char ctl[64];
    char *path;
	
    path = "/proc/driver/array";

    sprintf(ctl, "%s/ida%d", path, ctlNum++);
		
    f = fopen(ctl, "r");
    if (!f) {
	    path = "/proc/ida";
	    sprintf(ctl, "%s/ida%d", path, ctlNum++);
	    f = fopen(ctl, "r");
    }

    if (f) {
	while (fgets(buf, sizeof(buf) - 1, f)) {
	    if (!strncmp(buf, "ida/", 4)) {
		ptr = strchr(buf, ':');
		*ptr = '\0';

		if (!deviceKnown(devices, buf)) {
		    newDevice.name = strdup(buf);
		    newDevice.model = strdup("Compaq RAID logical disk");
		    newDevice.class = CLASS_HD;
		    addDevice(devices, newDevice);
		}
	    }
	}
	sprintf(ctl, "%s/ida%d", path, ctlNum++);
        fclose(f);
    }

    
    return 0;
}


static int I2OGetDevices(struct knownDevices * devices, int code) {
    struct kddevice newDevice;
    FILE *f;
    char buf[256];
    char *ptr;
    int numMatches = 0, ctlNum = 0;
    char ctl[40];
/*
TODO:
 Currently just allowing user to install on the
 first I2O volume created. Look at I2O code,
 it will guarantee that a bootable volume
 always shows up as /dev/i2o/hda. The other
 volumes may change device names if there is 
 TID reuse.
 Other reason is that currently in 2.2 kernels
 we cannot determine how many I2O volumes were 
 created via the /proc file system. Too cumbersome
 to wade thru the syslog !
*/
    sprintf(ctl, "i2o/hda");

/*
TODO:
 There is currently no checking to see if
 the I2O Block device /dev/i2o/hda ACTUALLY
 exists. Consequently this hack should be used
 only when installing on I2O devices. Otherwise
 it will complain !
*/
                if (!deviceKnown(devices, ctl)) {
                    newDevice.name = strdup(ctl);
                    newDevice.model = strdup("I2O Block Device");
                    newDevice.class = CLASS_HD;
                    addDevice(devices, newDevice);
                }
    return 0;
}



static int CompaqSmartArray5300GetDevices(struct knownDevices * devices) {
    struct kddevice newDevice;
    FILE *f;
    char buf[256];
    char *ptr;
    int numMatches = 0, ctlNum = 0;
    char ctl[64];
    char *path;
	
    path = "/proc/driver/cciss";

    sprintf(ctl, "%s/cciss%d", path, ctlNum++);
		
    f = fopen(ctl, "r");
    if (!f) {
	    path = "/proc/cciss";
	    sprintf(ctl, "%s/cciss%d", path, ctlNum++);
	    f = fopen(ctl, "r");
    }

    if (f) {
	while (fgets(buf, sizeof(buf) - 1, f)) {
	    if (!strncmp(buf, "cciss/", 6)) {
		ptr = strchr(buf, ':');
		*ptr = '\0';

		if (!deviceKnown(devices, buf)) {
		    newDevice.name = strdup(buf);
		    newDevice.model = strdup("Compaq RAID logical disk");
		    newDevice.class = CLASS_HD;
		    addDevice(devices, newDevice);
		}
	    }
	}
	sprintf(ctl, "%s/cciss%d", path, ctlNum++);
	fclose(f);
    }

    
    return 0;
}
