#ifndef LOADERHW_H
#define LOADERHW_H

#include "modules.h"
#include "../isys/probe.h"

int canProbeDevices(void);

int agpgartInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags);
int scsiTapeInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags);
void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
                            moduleInfoSet modInfo, int flags);

void updateKnownDevices(struct knownDevices * kd);
int earlyModuleLoad(moduleInfoSet modInfo, moduleList modLoaded, 
                    moduleDeps modDeps, int justProbe, 
                    struct knownDevices * kd, int flags);
int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, struct knownDevices * kd, int flags);

void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags,
               struct knownDevices * kd);
void ideSetup(moduleList modLoaded, moduleDeps modDeps,
              moduleInfoSet modInfo, int flags,
              struct knownDevices * kd);
void dasdSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags,
               struct knownDevices * kd);

#endif
