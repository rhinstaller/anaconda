#ifndef NFSINSTALL_H
#define NFSINSTALL_H

#include "method.h"

struct nfsInstallData {
    char * host;
    char * directory;
};


void setKickstartNfs(struct knownDevices * kd, 
                     struct loaderData_s * loaderData, int argc,
                     char ** argv, int * flagsPtr);
int kickstartFromNfs(char * url, struct knownDevices * kd,
                     struct loaderData_s * loaderData, int flags);
char * mountNfsImage(struct installMethod * method,
                     char * location, struct knownDevices * kd,
                     struct loaderData_s * loaderData,
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDepsPtr, int flags);
int getFileFromNfs(char * url, char * dest, struct knownDevices * kd,
                   struct loaderData_s * loaderData, int flags);

#endif
