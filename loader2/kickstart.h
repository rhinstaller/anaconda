#ifndef H_KICKSTART

#include "../isys/probe.h"
#include "loader.h"

#define KS_CMD_NONE	    0
#define KS_CMD_NFS	    1
#define KS_CMD_CDROM	    2
#define KS_CMD_HD	    3
#define KS_CMD_URL	    4
#define KS_CMD_NETWORK	    5
#define KS_CMD_TEXT	    6
#define KS_CMD_KEYBOARD     7
#define KS_CMD_LANG 8

int ksReadCommands(char * cmdFile);
int ksGetCommand(int cmd, char ** last, int * argc, char *** argv);
int ksHasCommand(int cmd);

void getKickstartFile(struct knownDevices * kd,
                      struct loaderData_s * loaderData, int * flagsPtr);
void setupKickstart(struct loaderData_s * loaderData, int * flagsPtr);
int getKickstartFromBlockDevice(char *device, char *path);
#endif
