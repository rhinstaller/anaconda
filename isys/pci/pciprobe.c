#include <alloca.h>
#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

struct pciDrivers {
    unsigned int manufacturer, device;
    char * driver;
};

struct pciDrivers * pciDriverList = NULL;
static int numPciDrivers = 0;

static int driverCmp(const void * a, const void * b);

int probePciReadDrivers(const char * fn) {
    int fd;
    struct stat sb;
    char * buf;
    int numDrivers;
    char * start;
    struct pciDrivers * nextDriver;
    char module[5000];

    fd = open(fn, O_RDONLY);
    if (fd < 0) return -1;

    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    read(fd, buf, sb.st_size);
    buf[sb.st_size] = '\0';
    close(fd);

    /* upper bound */
    numDrivers = 1;
    start = buf;
    while ((start = strchr(start, '\n'))) {
	numDrivers++;
	start++;
    }

    pciDriverList = realloc(pciDriverList, sizeof(*pciDriverList) *
				(numPciDrivers + numDrivers));
    nextDriver = pciDriverList + numPciDrivers;

    start = buf;
    while (start && *start) {
	while (isspace(*start)) start++;
	if (*start != '#' && *start != '\n') {
	    if (sscanf(start, "%x %x %s\n", &nextDriver->manufacturer,
		       &nextDriver->device, module) == 3) {
		numPciDrivers++;
		nextDriver++;
		nextDriver->driver = strdup(module);
	    }
	}

	start = strchr(start, '\n');
	if (start) start++;
    }

    /*qsort(pciDriverList, numPciDrivers, sizeof(*pciDriverList), driverCmp);*/

    return 0;
}

static int driverCmp(const void * a, const void * b) {
    const struct pciDrivers * one = a;
    const struct pciDrivers * two = b;

    if (one->manufacturer < two->manufacturer) return -1;
    if (one->manufacturer > two->manufacturer) return 1;

    if (one->device < two->device) return -1;
    if (one->device > two->device) return 1;

    return 0;
}

char ** probePciDriverList(void) {
    char ** drivers;
    int driverCount = 0;
    int fd;
    char * buf, * chptr;
    int bufSize;
    int bytes;
    unsigned int tmp, i;
    struct pciDrivers needle, * item;

    fd = open("/proc/bus/pci/devices", O_RDONLY);
    if (fd < 0) return NULL;

    bufSize = 1024;
    buf = malloc(bufSize);
    while ((bytes = read(fd, buf, bufSize)) == bufSize) {
	bufSize += 1024;
	buf = realloc(buf, bufSize);
	lseek(fd, SEEK_SET, 0);
    }
    close(fd);

    buf[bytes] = '\0';

    drivers = malloc(sizeof(*drivers) * 500);
    chptr = buf;
    while (*chptr) {
	strtoul(chptr, &chptr, 16);
	tmp = strtoul(chptr, &chptr, 16);

	chptr = strchr(chptr, '\n') + 1;

	needle.manufacturer = tmp >> 16;
	needle.device = tmp & 0xFFFF;

	item = bsearch(&needle, pciDriverList, numPciDrivers,
		       sizeof(*pciDriverList), driverCmp);

	if (item) {
	    for (i = 0; i < driverCount; i++)
		if (!strcmp(drivers[i], item->driver)) break;
	    if (i == driverCount) {
		drivers[driverCount++] = item->driver;
	    }
	}
    }

    free(buf);
    if (!driverCount) {
	free(drivers);
	drivers = NULL;
    } else {
	drivers[driverCount++] = NULL;
    }

    return drivers;
}
