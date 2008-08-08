/*
 * net.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef H_LOADER_NET
#define H_LOADER_NET

#include "loader.h"
#include <ip_addr.h>
#include <libdhcp.h>
#include <newt.h>
#include <pump.h>

#define DHCP_METHOD_STR   _("Dynamic IP configuration (DHCP)")
#define DHCPV6_METHOD_STR _("Dynamic IP configuration (DHCPv6)")
#define MANUAL_METHOD_STR _("Manual configuration")
#define AUTO_METHOD_STR   _("Automatic neighbor discovery")

/* generic names for array index positions in net.c */
enum { IPV4, IPV6 };

/* these match up to the radio button array index order in configureTCPIP() */
enum { IPV4_DHCP_METHOD, IPV4_MANUAL_METHOD };
enum { IPV6_AUTO_METHOD, IPV6_DHCP_METHOD, IPV6_MANUAL_METHOD };

struct networkDeviceConfig {
    struct pumpNetIntf dev;

    /* wireless settings */
    /* side effect: if this is non-NULL, then assume wireless */
    char * essid;
    char * wepkey;

    /* misc settings */
    int isDynamic;
    int noDns;
    int dhcpTimeout;
    int preset;
    int ipv4method, ipv6method;
    char * vendor_class;

    /* s390 settings */
    int mtu;
    char *subchannels, *portname, *peerid, *nettype, *ctcprot;
};

struct intfconfig_s {
    newtComponent ipv4Entry, cidr4Entry;
    newtComponent ipv6Entry, cidr6Entry;
    newtComponent gwEntry, nsEntry;
    const char *ipv4, *cidr4;
    const char *ipv6, *cidr6;
    const char *gw, *ns;
};

struct netconfopts {
    char ipv4Choice;
    char ipv6Choice;
};

typedef int int32;

int readNetConfig(char * device, struct networkDeviceConfig * dev,
                  char * dhcpclass, int methodNum);
int configureTCPIP(char * device, struct networkDeviceConfig * cfg,
                   struct networkDeviceConfig * newCfg,
                   struct netconfopts * opts, int methodNum);
int manualNetConfig(char * device, struct networkDeviceConfig * cfg,
                    struct networkDeviceConfig * newCfg,
                    struct intfconfig_s * ipcomps, struct netconfopts * opts);
void debugNetworkInfo(struct networkDeviceConfig *cfg);
int configureNetwork(struct networkDeviceConfig * dev);
int writeNetInfo(const char * fn, struct networkDeviceConfig * dev);
int findHostAndDomain(struct networkDeviceConfig * dev);
int writeResolvConf(struct networkDeviceConfig * net);
void initLoopback(void);
int chooseNetworkInterface(struct loaderData_s * loaderData);
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData);
int setupWireless(struct networkDeviceConfig *dev);

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv);

int kickstartNetworkUp(struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr);

char *doDhcp(struct networkDeviceConfig *dev);
void netlogger(void *arg, int priority, char *fmt, va_list va);
void splitHostname (char *str, char **host, char **port);

#endif
