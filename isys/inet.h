#ifndef _INET_H_
#define _INET_H_

#include <netinet/in.h>

#define INET_ERR_ERRNO 1
#define INET_ERR_OTHER 2

struct intfInfo {
    char device[10];
    int isPtp, isUp;
    int set, manuallySet;
    struct in_addr ip, netmask, broadcast, network;
    struct in_addr bootServer, gateway;
    char * bootFile;
    int bootProto;
};

int configureNetDevice(struct intfInfo * intf);
int addDefaultRoute(struct intfInfo * net);

#endif /* _INET_H_ */
