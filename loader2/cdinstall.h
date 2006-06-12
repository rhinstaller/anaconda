#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "method.h"

char * mountCdromImage(struct installMethod * method,
                       char * location, struct loaderData_s * loaderData,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr);

char * findAnacondaCD(char * location, moduleInfoSet modInfo, 
                      moduleList modLoaded, moduleDeps modDeps, 
                      int requirepkgs);


void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv);

int kickstartFromCD(char *kssrc);
#endif
