#ifndef H_PROBE
#define H_PROBE

struct device {
    char * name;		/* malloced */
    char * model;
    enum deviceClass { DEVICE_UNKNOWN, DEVICE_DISK, DEVICE_CDROM, DEVICE_NET,
    		       DEVICE_TAPE }
    	class;
};

struct knownDevices {
    struct device * known;
    int numKnown;
    int numKnownAlloced;
};

struct knownDevices kdInit(void);
int kdFindNetList(struct knownDevices * devices);
int kdFindIdeList(struct knownDevices * devices);
int kdFindScsiList(struct knownDevices * devices);
void kdFree(struct knownDevices * devices);

#endif
