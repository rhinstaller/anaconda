#include <sys/socket.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <net/route.h>
#include <sys/ioctl.h>

#include "inet.h"

int configureNetDevice(struct intfInfo * intf) {
    struct ifreq req;
    int s;
    struct sockaddr_in addr;
    struct in_addr ia;
    char ip[20], nm[20], nw[20], bc[20];
#if 0 /* 2.0 kernels only */
    struct rtentry route;
#endif
	
    addr.sin_family = AF_INET;
    addr.sin_port = 0;

    memcpy(&ia, &intf->ip, sizeof(intf->ip));
    strcpy(ip, inet_ntoa(ia));

    memcpy(&ia, &intf->netmask, sizeof(intf->netmask));
    strcpy(nm, inet_ntoa(ia));

    memcpy(&ia, &intf->broadcast, sizeof(intf->broadcast));
    strcpy(bc, inet_ntoa(ia));

    memcpy(&ia, &intf->network, sizeof(intf->network));
    strcpy(nw, inet_ntoa(ia));

    s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) {
	perror("socket");
        return 1;
    }
    
    strcpy(req.ifr_name, intf->device);
    req.ifr_flags &= ~(IFF_UP | IFF_RUNNING); /* Take down iface */
    if (ioctl(s, SIOCSIFFLAGS, &req)) {
        perror("SIOCSIFFLAGS");
        close(s);
        return 1;
    }

    addr.sin_port = 0;
    memcpy(&addr.sin_addr, &intf->ip, sizeof(intf->ip));
    memcpy(&req.ifr_addr, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFADDR, &req)) {
        perror("SIOCSIFADDR");
        close(s);
        return 1;
    }

    memcpy(&addr.sin_addr, &intf->broadcast, sizeof(intf->broadcast));
    memcpy(&req.ifr_broadaddr, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFBRDADDR, &req)) {
        perror("SIOCSIFNETMASK");
        close(s);
        return 1;
    }

    memcpy(&addr.sin_addr, &intf->netmask, sizeof(intf->netmask));
    memcpy(&req.ifr_netmask, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFNETMASK, &req)) {
        perror("SIOCSIFNETMASK\n");
        close(s);
        return 1;
    }

    if (intf->isPtp)
        req.ifr_flags = IFF_UP | IFF_RUNNING | IFF_POINTOPOINT | IFF_NOARP;
    else
        req.ifr_flags = IFF_UP | IFF_RUNNING | IFF_BROADCAST;

    if (ioctl(s, SIOCSIFFLAGS, &req)) {
        perror("SIOCSIFFLAGS");
        close(s);
        return 1;
    }

#if 0 /* kernel 2.0 only */
    memset(&route, 0, sizeof(route));
    route.rt_dev = intf->device;
    route.rt_flags = RTF_UP;

    memcpy(&addr.sin_addr, &intf->network, sizeof(intf->netmask));
    memcpy(&route.rt_dst, &addr, sizeof(addr));

    memcpy(&addr.sin_addr, &intf->netmask, sizeof(intf->netmask));
    memcpy(&route.rt_genmask, &addr, sizeof(addr));

    if (ioctl(s, SIOCADDRT, &route)) {
        perror("SIOCADDRT");
        close(s);
        return 1;

    }
#endif
    
    intf->isUp = 1;

    return 0;
}

int addDefaultRoute(struct intfInfo * net) {
    int s;
    struct rtentry route;
    struct sockaddr_in addr;

    /* It should be okay to try and setup a machine w/o a default gateway */
    /* XXX 
    if (!(net->set & NETINFO_HAS_GATEWAY)) return 0;
    */

    s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) {
	close(s);
	perror("socket:");
	return 1;
    }

    memset(&route, 0, sizeof(route));

    addr.sin_family = AF_INET;
    addr.sin_port = 0;
    addr.sin_addr = net->gateway;
    memcpy(&route.rt_gateway, &addr, sizeof(addr));

    addr.sin_addr.s_addr = INADDR_ANY;
    memcpy(&route.rt_dst, &addr, sizeof(addr));
    memcpy(&route.rt_genmask, &addr, sizeof(addr));

    route.rt_flags = RTF_UP | RTF_GATEWAY;
    route.rt_metric = 0;

    if (ioctl(s, SIOCADDRT, &route)) {
	close(s);
	perror("SIOCADDRT");
	return 1;
    }

    return 0;
}
