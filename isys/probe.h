#ifndef H_PROBE
#define H_PROBE

#include "kudzu/kudzu.h"

struct kddevice {
    char * name;		/* malloced */
    char * model;
    enum deviceClass class;
};

struct knownDevices {
    struct kddevice * known;
    int numKnown;
    int numKnownAlloced;
};

struct knownDevices kdInit(void);
int kdFindNetList(struct knownDevices * devices);
int kdFindIdeList(struct knownDevices * devices);
int kdFindScsiList(struct knownDevices * devices);
void kdFree(struct knownDevices * devices);
void kdAddDevice(struct knownDevices * devices, enum deviceClass devClass, 
		 char * devName, char * devModel);

#endif
