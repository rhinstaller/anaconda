#ifndef DRIVERDISK_H
#define DRIVERDISK_H

#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"
#include "../isys/probe.h"

int loadDriverFromMedia(int class, moduleList modLoaded, 
                        moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                        struct knownDevices * kd, int flags, int usecancel);

int loadDriverDisks(int class, moduleList modLoaded, 
                    moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                    struct knownDevices * kd, int flags);

int getRemovableDevices(char *** devNames);

int chooseManualDriver(int class, moduleList modLoaded, 
                       moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                       struct knownDevices * kd, int flags);
#endif
