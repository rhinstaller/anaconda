#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "method.h"

char * mountCdromImage(struct installMethod * method,
                       char * location, struct knownDevices * kd,
                       struct loaderData_s * loaderData,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags);

char * findRedHatCD(char * location, 
                    struct knownDevices * kd, 
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags);


void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr);

int kickstartFromCD(char *kssrc, struct knownDevices * kd, int flags);
#endif
