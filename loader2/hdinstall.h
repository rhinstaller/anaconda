#ifndef H_HDINSTALL
#define H_HDINSTALL

#include "method.h"

struct hdInstallData {
    char * partition;
    char * directory;
};


void setKickstartHD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr);
char * mountHardDrive(struct installMethod * method,
                      char * location, struct loaderData_s * loaderData,
                      moduleInfoSet modInfo, moduleList modLoaded,
                      moduleDeps * modDepsPtr, int flags);
int kickstartFromHD(char *kssrc, int flags);

#endif
