#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "loader.h"
#include "pump.h"


struct networkDeviceConfig {
    struct pumpNetIntf dev;

    /* wireless settings */
    char * essid; /* side effect: if this is non-NULL, then assume wireless */
    char * wepkey;

    /* misc settings */
    int isDynamic;
    int noDns;
    int preset;
    int dhcpTimeout;

    /* s390 settings */
    char *subchannels, *portname, *peerid, *nettype, *ctcprot, *layer2, *macaddr;
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

char * setupInterface(struct networkDeviceConfig *dev);
char * doDhcp(char * ifname, 
              struct networkDeviceConfig *dev, char * dhcpclass);

#endif
