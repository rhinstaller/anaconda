#ifndef H_METHOD
#define H_METHOD

#include "../isys/probe.h"
#include "modules.h"
#include "moduledeps.h"
#include "loader.h"

struct installMethod {
    char * name;
    char * shortname;
    int network;
    enum deviceClass deviceType;			/* for pcmcia */
    char * (*mountImage)(struct installMethod * method,
                         char * location, struct knownDevices * kd,
                         struct loaderData_s * loaderData,
                         moduleInfoSet modInfo, moduleList modLoaded,
                         moduleDeps * modDepsPtr, int flags);
};


int umountLoopback(char * mntpoint, char * device);
int mountLoopback(char * fsystem, char * mntpoint, char * device);

char * validIsoImages(char * dirName);
int readStampFileFromIso(char *file, char **descr, char **timestamp);
void queryIsoMediaCheck(char * isoDir, int flags);

int verifyStamp(char * path);

void umountStage2(void);
int mountStage2(char * path);
int copyFileAndLoopbackMount(int fd, char * dest, int flags,
                             char * device, char * mntpoint);

void copyUpdatesImg(char * path);
int copyDirectory(char * from, char * to);


/* JKFIXME: move these to specific include files*/
struct nfsInstallData {
    char * host;
    char * directory;
};
void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv, int * flagsPtr);
int kickstartFromNfs(char * url, struct knownDevices * kd,
                     struct loaderData_s * loaderData, int flags);

struct hdInstallData {
    char * partition;
    char * directory;
};
void setKickstartHD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr);

/* no install data for CD, we just use the first one */
void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr);

/* JKFIXME: url stuff */
struct urlInstallData {
    char * url;
};
void setKickstartUrl(struct loaderData_s * loaderData, int argc,
		     char ** argv, int * flagsPtr);
int kickstartFromUrl(char * url, struct knownDevices * kd,
                     struct loaderData_s * loaderData, int flags);

#endif
