#ifndef H_LOADER_NET
#define H_LOADER_NET

#ifdef __STANDALONE__
#include "pump.h"
#else
#include "pump/pump.h"
#endif

struct networkDeviceConfig {
    struct pumpNetIntf dev;
    int isDynamic;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev, 
		  int flags);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev);
int findHostAndDomain(struct networkDeviceConfig * dev, int flags);
int writeResolvConf(struct networkDeviceConfig * net);
#ifndef __STANDALONE__
int nfsGetSetup(char ** hostptr, char ** dirptr);
int kickstartNetwork(char * device, struct networkDeviceConfig * netDev, 
		     char * bootProto, int flags);
void initLoopback(void);
#endif

#endif
