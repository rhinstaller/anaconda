#ifndef H_METHOD
#define H_METHOD

#include "../isys/probe.h"
#include "modules.h"
#include "moduledeps.h"

struct installMethod {
    char * name;
    int network;
    enum deviceClass deviceType;			/* for pcmcia */
    char * (*mountImage)(struct installMethod * method,
                         char * location, struct knownDevices * kd,
                         moduleInfoSet modInfo, moduleList modLoaded,
                         moduleDeps * modDepsPtr, int flags);
};


int umountLoopback(char * mntpoint, char * device);
int mountLoopback(char * fsystem, char * mntpoint, char * device);

char * validIsoImages(char * dirName);
void queryIsoMediaCheck(char * isoDir, int flags);

int mountStage2(char * path);
int copyFileAndLoopbackMount(int fd, char * dest, int flags,
                             char * device, char * mntpoint);

void copyUpdatesImg(char * path);
int copyDirectory(char * from, char * to);

#endif
