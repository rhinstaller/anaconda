#ifndef DRIVERDISK_H
#define DRIVERDISK_H

#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"
#include "../isys/probe.h"

int loadDriverFromMedia(int class, moduleList modLoaded, moduleDeps * modDeps,
                        moduleInfoSet modInfo, struct knownDevices * kd, 
                        int flags);

int getRemovableDevices(char *** devNames);

#endif
