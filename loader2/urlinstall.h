#ifndef URLINSTALL_H
#define URLINSTALL_H

#include "method.h"

struct urlInstallData {
    char * url;
};


void setKickstartUrl(struct knownDevices * kd, 
                     struct loaderData_s * loaderData, int argc,
		     char ** argv, int * flagsPtr);
int kickstartFromUrl(char * url, struct knownDevices * kd,
                     struct loaderData_s * loaderData, int flags);
char * mountUrlImage(struct installMethod * method,
                     char * location, struct knownDevices * kd,
                     struct loaderData_s * loaderData,
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDepsPtr, int flags);
int getFileFromUrl(char * url, char * dest, struct knownDevices * kd,
                   struct loaderData_s * loaderData, int flags);


#endif
