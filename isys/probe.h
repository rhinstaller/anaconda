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

/* 0 if the device should be filtered from the list, 1 if it should be 
   included */
typedef int (*kdFilterType)(const struct kddevice * dev);

struct knownDevices kdInit(void);
int kdFindNetList(struct knownDevices * devices, int code);
int kdFindIdeList(struct knownDevices * devices, int code);
int kdFindFilteredIdeList(struct knownDevices * devices, int code, 
			  kdFilterType filter);
int kdFindScsiList(struct knownDevices * devices, int code);
void kdFree(struct knownDevices * devices);
void kdAddDevice(struct knownDevices * devices, enum deviceClass devClass, 
		 char * devName, char * devModel);

#endif
