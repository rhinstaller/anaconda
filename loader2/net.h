#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "loader.h"
#include "pump.h"
#include "../isys/probe.h"

struct networkDeviceConfig {
    struct pumpNetIntf dev;
    int isDynamic;
    int noDns;
    int preset;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev, 
		  int flags);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev,
		 struct knownDevices * kd);
int findHostAndDomain(struct networkDeviceConfig * dev, int flags);
int writeResolvConf(struct networkDeviceConfig * net);
extern char *netServerPrompt;
int nfsGetSetup(char ** hostptr, char ** dirptr);
void initLoopback(void);
int chooseNetworkInterface(struct knownDevices * kd, 
                           struct loaderData_s * loaderData,
                           int flags);
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData, 
                              int flags);

void setKickstartNetwork(struct knownDevices * kd, 
                         struct loaderData_s * loaderData, int argc, 
                         char ** argv, int * flagsPtr);

int kickstartNetworkUp(struct knownDevices * kd, 
                       struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr,
                       int flags);

#endif
