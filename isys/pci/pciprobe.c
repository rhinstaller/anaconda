#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sys/stat.h>

#include <pci/pci.h>

#include "pciprobe.h"

struct pciDevice * pciDeviceList = NULL;
static int numPciDevices = 0;
static struct pci_access *pacc=NULL;

static int devCmp(const void * a, const void * b) {
    const struct pciDevice * one = a;
    const struct pciDevice * two = b;
    int x=0,y=0;
    
    x = (one->vendor - two->vendor);
    y = (one->device - two->device);
    if (x)
      return x;
    else
      return y;
}

static int vendCmp(const void * a, const void * b) {
    const struct pciDevice * one = a;
    const struct pciDevice * two = b;
    
    return (one->vendor - two->vendor);
}


char *getVendor(unsigned int vendor) {
    struct pciDevice *searchDev, key;
    char *tmpstr;
    
    key.vendor = vendor;
    
    searchDev = bsearch(&key,pciDeviceList,numPciDevices,
			sizeof(struct pciDevice), vendCmp);
    if (searchDev) {
	int x;
	
	x=strchr(searchDev->desc,'|')-searchDev->desc-1;
	tmpstr=calloc(x,sizeof(char));
	tmpstr=strncpy(tmpstr,searchDev->desc,x);
	return tmpstr;
    } else {
	return NULL;
    }
}

int probePciReadDrivers(const char * fn) {
    int fd;
    struct stat sb;
    char * buf;
    int numDrivers;
    char * start;
    struct pciDevice * nextDevice;
    char module[5000];
    char descrip[5000];

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

    pciDeviceList = realloc(pciDeviceList, sizeof(*pciDeviceList) *
				(numPciDevices + numDrivers));
    nextDevice = pciDeviceList + numPciDevices;

    start = buf;
    while (start && *start) {
	while (isspace(*start)) start++;
	if (*start != '#' && *start != '\n') {
	    if (sscanf(start, "%x %x %s \"%[^\"]", &nextDevice->vendor,
		       &nextDevice->device, module, descrip ) == 4) {
		numPciDevices++;
		nextDevice->driver = strdup(module);
		nextDevice->desc = strdup(descrip);
		nextDevice++;
	    }
	}

	start = strchr(start, '\n');
	if (start) start++;
    }

    qsort(pciDeviceList, numPciDevices, sizeof(*pciDeviceList), devCmp);

    return 0;
}

struct pciDevice * pciGetDeviceInfo(unsigned int vend, unsigned int dev) {
    struct pciDevice *searchDev, key;
    
    key.vendor = vend;
    key.device = dev;
    
    searchDev = bsearch(&key,pciDeviceList,numPciDevices,
			sizeof(struct pciDevice), devCmp);
    if (!searchDev) {
	char *namebuf;

	searchDev = malloc(sizeof(struct pciDevice));
	searchDev->vendor = vend;
	searchDev->device = dev;
	searchDev->driver = strdup("unknown");
	searchDev->desc = calloc(128, sizeof(char));
	namebuf = getVendor(vend);
	if (!namebuf) {
	    snprintf(searchDev->desc,128,
		     "Unknown vendor unknown device %04x:%04x",
		     searchDev->vendor, searchDev->device);
	} else {
	    snprintf(searchDev->desc,128,
		     "%s unknown device %04x:%04x",
		     namebuf, searchDev->vendor, searchDev->device);
	}
    }
    return searchDev;
}

struct pciDevice ** probePci(unsigned int type, int all) {
    struct pciDevice **devices=NULL;
    struct pci_dev *p;
    int numDevices=0;
    
    pacc = pci_alloc();
    if (!pacc) return NULL;
    pci_init(pacc);
    pci_scan_bus(pacc);
    for (p = pacc->devices; p; p=p->next) {
	byte config[256];
	int x=64;
	struct pciDevice *dev;
	
	memset(config,256,0);
	pci_read_block(p, 0, config, x);
	if (x<128 &&  (config[PCI_HEADER_TYPE] & 0x7f) == PCI_HEADER_TYPE_CARDBUS) {
	    pci_read_block(p, 0, config+64, 64);
	    x=128;
	}
        dev = pciGetDeviceInfo(p->vendor_id,p->device_id);
	dev->type = config[PCI_CLASS_DEVICE+1] << 8 | config[PCI_CLASS_DEVICE];
	if (all || (strcmp(dev->driver,"unknown") && strcmp(dev->driver,"ignore"))) {
	    if (!type || (type<0xff && (type==dev->type>>8))
		|| (type==dev->type)) {
		if (!numDevices) {
		    devices = malloc(sizeof(struct pciDevice *));
		} else {
		    devices = realloc(devices,(numDevices+1)*sizeof(struct pciDevice *));
		}
		devices[numDevices] = dev;
		numDevices++;
	    } 
	}
    }
    pci_cleanup(pacc);
    if (devices) {
	devices = realloc(devices,(numDevices+1)*sizeof(struct pciDevice *));
	devices[numDevices] = NULL;
    }
    return devices;
}

#ifdef TESTING
int main(int argc, char **argv) {
    struct pciDevice **list,*dev;
    int x=0;
    
    if (probePciReadDrivers("pcitable")) {
	perror("error reading pci table");
	exit(0);
    }
    list = probePci(0,1);
    if (list)
      while ((dev=list[x])) {
	  printf("%04x %04x %s (%s)\n",dev->vendor,dev->device,
		 dev->desc, dev->driver);
	  x++;
      }
    exit(0);
}
#endif
