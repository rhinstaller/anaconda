#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "method.h"

char * mountCdromImage(struct installMethod * method,
                       char * location, struct loaderData_s * loaderData,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags);

char * findAnacondaCD(char * location, 
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags,
		    int requirepkgs);


void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr);

int kickstartFromCD(char *kssrc, int flags);
#endif
