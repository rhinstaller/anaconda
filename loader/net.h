#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "pump/pump.h"

struct networkDeviceConfig {
    struct pumpNetIntf dev;
    int isDynamic;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev, 
		  int flags);
int configureNetwork(struct networkDeviceConfig * dev);
int nfsGetSetup(char ** hostptr, char ** dirptr);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev);
int findHostAndDomain(struct networkDeviceConfig * dev, int flags);
int writeResolvConf(struct networkDeviceConfig * net);

#endif
