#ifndef NFSINSTALL_H
#define NFSINSTALL_H

#include "method.h"

struct nfsInstallData {
    char * host;
    char * directory;
    char * mountOpts;
};


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv, int * flagsPtr);
int kickstartFromNfs(char * url, struct loaderData_s * loaderData, int flags);
char * mountNfsImage(struct installMethod * method,
                     char * location, struct loaderData_s * loaderData,
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDepsPtr, int flags);
int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData, 
                   int flags);

#endif
