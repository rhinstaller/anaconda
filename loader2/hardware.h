#ifndef LOADERHW_H
#define LOADERHW_H

#include "modules.h"

int canProbeDevices(void);

int scsiTapeInitialize(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo);

int earlyModuleLoad(moduleInfoSet modInfo, moduleList modLoaded, 
                    moduleDeps modDeps, int justProbe);
int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe);

void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo);
void ideSetup(moduleList modLoaded, moduleDeps modDeps,
              moduleInfoSet modInfo);
void dasdSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo);

void ipv6Setup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo);

void spufsSetup(moduleList modLoaded, moduleDeps modDeps,
               moduleInfoSet modInfo);
#endif
