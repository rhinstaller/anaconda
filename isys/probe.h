#ifndef H_PROBE
#define H_PROBE

#include "kudzu/kudzu.h"

struct kddevice {
    char * name;		/* malloced */
    char * model;
    enum deviceClass class;
    int code;
};

struct knownDevices {
    struct kddevice * known;
    int numKnown;
    int numKnownAlloced;
};

struct knownDevices kdInit(void);
int kdFindNetList(struct knownDevices * devices, int code);
int kdFindIdeList(struct knownDevices * devices, int code);
int kdFindScsiList(struct knownDevices * devices, int code);
void kdFree(struct knownDevices * devices);
void kdAddDevice(struct knownDevices * devices, enum deviceClass devClass, 
		 char * devName, char * devModel);

#endif
