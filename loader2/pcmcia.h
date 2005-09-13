#ifndef H_PCMCIA
#define H_PCMCIA

#include <kudzu/kudzu.h>

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
                                moduleInfoSet modInfo, int flags);
void startPcmciaDevices(moduleList modLoaded, int flags);

#endif
