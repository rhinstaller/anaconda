#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "loader.h"
#include "pump.h"

struct networkDeviceConfig {
    struct pumpNetIntf dev;
    int isDynamic;
    int noDns;
    int preset;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev, 
		  char * dhcpclass, int flags);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev);
int findHostAndDomain(struct networkDeviceConfig * dev, int flags);
int writeResolvConf(struct networkDeviceConfig * net);
extern char *netServerPrompt;
int nfsGetSetup(char ** hostptr, char ** dirptr);
void initLoopback(void);
int chooseNetworkInterface(struct loaderData_s * loaderData,
                           int flags);
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData, 
                              int flags);

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv, int * flagsPtr);

int kickstartNetworkUp(struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr,
                       int flags);

#endif
