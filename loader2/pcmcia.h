#ifndef H_PCMCIA
#define H_PCMCIA

#include <kudzu/kudzu.h>

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
                                moduleInfoSet modInfo);
void startPcmciaDevices(moduleList modLoaded);

#endif
