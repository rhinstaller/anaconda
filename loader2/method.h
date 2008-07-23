#ifndef H_METHOD
#define H_METHOD

#include "modules.h"
#include "moduledeps.h"
#include "loader.h"
#include <kudzu/kudzu.h>

/* method identifiers, needs to match struct installMethod order in loader.c */
enum {
    METHOD_CDROM,
    METHOD_HD,
    METHOD_NFS,
    METHOD_FTP,
    METHOD_HTTP
};

struct installMethod {
    char * name;
    char * shortname;
    int network;
    enum deviceClass deviceType;			/* for pcmcia */
    char * (*mountImage)(struct installMethod * method,
                         char * location, struct loaderData_s * loaderData,
                         moduleInfoSet modInfo, moduleList modLoaded,
                         moduleDeps * modDepsPtr);
};

int umountLoopback(char * mntpoint, char * device);
int mountLoopback(char * fsystem, char * mntpoint, char * device);

char * validIsoImages(char * dirName, int *foundinvalid);
int readStampFileFromIso(char *file, char **descr, char **timestamp);
void queryIsoMediaCheck(char * isoDir);

int verifyStamp(char * path);

void umountStage2(void);
int mountStage2(char * path);
int copyFileAndLoopbackMount(int fd, char *dest, char *device, char *mntpoint);
int getFileFromBlockDevice(char *device, char *path, char * dest);

void copyUpdatesImg(char * path);
void copyProductImg(char * path);
int copyDirectory(char * from, char * to);

void setMethodFromCmdline(char * arg, struct loaderData_s * ld);

#endif
