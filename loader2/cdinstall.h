#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "../isys/probe.h"
#include "modules.h"

char * findRedHatCD(char * location, 
		    struct knownDevices * kd, 
		    moduleInfoSet modInfo, 
		    moduleList modLoaded, 
		    moduleDeps modDeps, 
		    int flags);

#endif
