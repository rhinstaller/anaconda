#ifndef LOADERHW_H
#define LOADERHW_H

#include "modules.h"

int canProbeDevices(void);

int agpgartInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags);
int scsiTapeInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags);
void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
                            moduleInfoSet modInfo, int flags);

int earlyModuleLoad(moduleInfoSet modInfo, moduleList modLoaded, 
                    moduleDeps modDeps, int justProbe, int flags);
int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, int flags);

void lapicSetup(moduleList modLoaded, moduleDeps modDeps,
                moduleInfoSet modInfo, int flags);
void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags);
void ideSetup(moduleList modLoaded, moduleDeps modDeps,
              moduleInfoSet modInfo, int flags);
void dasdSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo, int flags);

#endif
