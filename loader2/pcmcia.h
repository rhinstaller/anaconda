#ifndef H_PCMCIA
#define H_PCMCIA

#include <kudzu/kudzu.h>

int initializePcmciaController(moduleList modLoaded, moduleDeps modDeps,
                                moduleInfoSet modInfo, int flags);
int has_pcmcia(void);
int activate_pcmcia_device(struct pcmciaDevice *pdev);
void startPcmciaDevices(moduleList modLoaded, int flags);

#endif
