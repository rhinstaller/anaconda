#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "../isys/probe.h"
#include "pump.h"

struct networkDeviceConfig {
    struct pumpNetIntf dev;
    int isDynamic;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev, 
		  int flags);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev,
		 struct knownDevices * kd);
int findHostAndDomain(struct networkDeviceConfig * dev, int flags);
int writeResolvConf(struct networkDeviceConfig * net);
#ifndef __STANDALONE__
int nfsGetSetup(char ** hostptr, char ** dirptr);
int kickstartNetwork(char ** devicePtr, struct networkDeviceConfig * netDev, 
		     char * bootProto, int flags);
void initLoopback(void);
#endif

#endif
