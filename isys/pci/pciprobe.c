#include <alloca.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct pciDrivers {
    unsigned short manufacturer, device;
    char * driver;
};

#include "driverlist.h"

static int numPciDrivers = sizeof(pciDriverList) / sizeof(*pciDriverList);

static int driverCmp(const void * a, const void * b) {
    const struct pciDrivers * one = a;
    const struct pciDrivers * two = b;

    if (one->manufacturer < two->manufacturer) return -1;
    if (one->manufacturer > two->manufacturer) return -1;

    if (one->device < two->device) return 1;
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
    int tmp, i;
    struct pciDrivers needle, * item;

    fd = open("/proc/bus/pci/devices", O_RDONLY);
    if (fd < 0) return NULL;

    bufSize = 1024;
    buf = malloc(bufSize);
    while ((bytes = read(fd, buf, bufSize)) == bufSize) {
	bufSize += 1024;
	buf = realloc(buf, bufSize);
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
	needle.device = tmp &0xFFFF;

	item = NULL;
	for (i = 0; i < numPciDrivers; i++) {
	    if (!driverCmp(pciDriverList + i, &needle)) {
		item = pciDriverList + i;
		break;
	    }
	}

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

void main() {
    char ** d, ** p;

    d = probePciDriverList();
    p = d;
    while (p && *p)
	printf("%s\n", *p), p++;
}
