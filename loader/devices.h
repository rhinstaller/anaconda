#ifndef H_DEVICES
#define H_DEVICES

#include "../isys/isys.h"
#include "modules.h"

int devDeviceMenu(enum driverMajor type, moduleInfoSet modInfo, 
		  moduleList modLoaded, moduleDeps * modDepsPtr, int flags,
		  char ** moduleName);
int devLoadDriverDisk(moduleInfoSet modInfo, moduleList modLoaded,
		     moduleDeps *modDepsPtr, int flags, int cancelNotBack);
int devInitDriverDisk(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps *modDepsPtr, int flags, char * mntPoint);

#endif
