#ifndef DRIVERDISK_H
#define DRIVERDISK_H

#include "loader.h"
#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"
#include "../isys/probe.h"

int loadDriverFromMedia(int class, moduleList modLoaded, 
                        moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                        struct knownDevices * kd, int flags, 
                        int usecancel, int noprobe);

int loadDriverDisks(int class, moduleList modLoaded, 
                    moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                    struct knownDevices * kd, int flags);

int getRemovableDevices(char *** devNames);

int chooseManualDriver(int class, moduleList modLoaded, 
                       moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                       struct knownDevices * kd, int flags);
void useKickstartDD(struct knownDevices * kd, 
                    struct loaderData_s * loaderData, int argc, 
                    char ** argv, int * flagsPtr);

#endif
