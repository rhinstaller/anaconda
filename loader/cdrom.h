#ifndef H_LOADER_CDROM
#define H_LOADER_CDROM

#include "isys/isys.h"
#include "isys/probe.h"

#include "modules.h"

int setupCDdevice(struct knownDevices * kd, moduleInfoSet modInfo, 
		  moduleList modLoaded, moduleDeps * modDepsPtr, 
		  char * floppyDevice, int flags);

#endif
