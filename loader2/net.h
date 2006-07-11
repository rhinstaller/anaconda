#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "loader.h"
#include <ip_addr.h>
#include <libdhcp.h>
#include <pump.h>

#define IP_STRLEN( ip ) \
    ( ((ip)->sa_family == AF_INET) ? INET_ADDRSTRLEN : \
      ((ip)->sa_family == AF_INET6) ? INET6_ADDRSTRLEN : 0 )

struct networkDeviceConfig {
    struct pumpNetIntf dev;

    /* wireless settings */
    /* side effect: if this is non-NULL, then assume wireless */
    char * essid;
    char * wepkey;

    /* misc settings */
    int isDynamic;
    int noDns;
    int preset;

    /* s390 settings */
    int mtu;
    char *subchannels, *portname, *peerid, *nettype, *ctcprot;
};

int readNetConfig(char * device, struct networkDeviceConfig * dev,
                  char * dhcpclass);
int configureTCPIP(char * device, struct networkDeviceConfig * cfg,
                   struct networkDeviceConfig * newCfg,
                   char * ipv4Choice, char * ipv6Choice);
int manualNetConfig(char * device, struct networkDeviceConfig * cfg,
                    struct networkDeviceConfig * newCfg,
                    char ipv4Choice, char ipv6Choice);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev);
int findHostAndDomain(struct networkDeviceConfig * dev);
int writeResolvConf(struct networkDeviceConfig * net);
extern char *netServerPrompt;
int nfsGetSetup(char ** hostptr, char ** dirptr);
void initLoopback(void);
int chooseNetworkInterface(struct loaderData_s * loaderData);
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData);
int setupWireless(struct networkDeviceConfig *dev);

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv);

int kickstartNetworkUp(struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr);

char *doDhcp(struct networkDeviceConfig *dev, int ipv4Choice, int ipv6Choice);
void netlogger(void *arg, int priority, char *fmt, va_list va);

#endif
