#ifndef LOADERHW_H
#define LOADERHW_H

#include "modules.h"
#include "../isys/probe.h"

int agpgartInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags);
void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
                            moduleInfoSet modInfo, int flags);

void updateKnownDevices(struct knownDevices * kd);
int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, struct knownDevices * kd, int flags);

void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags,
               struct knownDevices * kd);
void ideSetup(moduleList modLoaded, moduleDeps modDeps,
              moduleInfoSet modInfo, int flags,
              struct knownDevices * kd);

#endif
