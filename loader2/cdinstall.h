#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "../isys/probe.h"
#include "modules.h"

char * mountCdromImage(struct installMethod * method,
                       char * location, struct knownDevices * kd,
                       struct loaderData_s * loaderData,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags);

char * findRedHatCD(char * location, 
                    struct knownDevices * kd, 
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags);

#endif
