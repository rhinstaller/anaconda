#ifndef H_DEVICES
#define H_DEVICES

#include "../isys/isys.h"
#include "modules.h"

struct driverDiskInfo {
    char * device;	/* may be null */
    char * mntDevice;
    char * fs;
    char * title;
};

int devDeviceMenu(enum driverMajor type, moduleInfoSet modInfo, 
		  moduleList modLoaded, moduleDeps * modDepsPtr, 
		  char * ddDevice, int flags, char ** moduleName);
int devLoadDriverDisk(moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps *modDepsPtr, int flags, int cancelNotBack,
		      int askForExistence, char * device);
int devInitDriverDisk(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps *modDepsPtr, int flags, char * mntPoint,
		      struct driverDiskInfo * ddi);

void ejectFloppy(void);
char * extractModule(struct driverDiskInfo * location, char * modName);

#endif
