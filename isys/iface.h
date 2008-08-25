/*
 * iface.h - Network interface configuration API
 *
 * Copyright (C) 2006, 2007, 2008  Red Hat, Inc.
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
 *
 * Author(s): David Cantrell <dcantrell@redhat.com>
 */

#ifndef ISYSIFACE_H
#define ISYSIFACE_H

#include <resolv.h>
#include <net/if.h>
#include <netlink/cache.h>
#include <netlink/socket.h>

/* Enumerated types used in iface.c as well as loader's network code */
enum { IPUNUSED, IPV4, IPV6 };

enum { IPV4_UNUSED_METHOD, IPV4_DHCP_METHOD, IPV4_MANUAL_METHOD };
enum { IPV6_UNUSED_METHOD, IPV6_AUTO_METHOD, IPV6_DHCP_METHOD,
       IPV6_MANUAL_METHOD };

#define IPV4_FIRST_METHOD IPV4_DHCP_METHOD
#define IPV4_LAST_METHOD  IPV4_MANUAL_METHOD

#define IPV6_FIRST_METHOD IPV6_AUTO_METHOD
#define IPV6_LAST_METHOD  IPV6_MANUAL_METHOD

/* Flags for the iface_t */
#define IFACE_FLAGS_NO_WRITE_RESOLV_CONF (((uint64_t) 1) << 0)
/* FIXME: do we need these? */
#define IFACE_FLAGS_IS_PRESET            (((uint64_t) 1) << 1)
#define IFACE_FLAGS_IS_DYNAMIC           (((uint64_t) 1) << 2)

#define IFACE_NO_WRITE_RESOLV_CONF(a)    ((a) & IFACE_FLAGS_NO_WRITE_RESOLV_CONF)
#define IFACE_IS_PRESET(a)               ((a) & IFACE_FLAGS_IS_PRESET)
#define IFACE_IS_DYNAMIC(a)              ((a) & IFACE_FLAGS_IS_DYNAMIC)

/* Macros for starting NetworkManager */
#define NETWORKMANAGER  "/usr/sbin/NetworkManager"
#define OUTPUT_TERMINAL "/dev/tty5"

/* Per-interface configuration information */
typedef struct _iface_t {
    /* device name (e.g., eth0) */
    char device[IF_NAMESIZE];

    /* MAC address as xx:xx:xx:xx:xx:xx */
    char *macaddr;

    /* IPv4 (store addresses in in_addr format, use inet_pton() to display) */
    struct in_addr ipaddr;
    struct in_addr netmask;
    struct in_addr broadcast;

    /* IPv6 (store addresses in in6_addr format, prefix is just an int) */
    struct in6_addr ip6addr;
    int ip6prefix;

    /* Gateway settings */
    struct in_addr gateway;
    struct in6_addr gateway6;

    /* BOOTP (these can be IPv4 or IPv6, store human-readable version as str) */
    char *nextserver;
    char *bootfile;

    /* DNS (these can be IPv4 or IPv6, store human-readable version as str) */
    char *dns[MAXNS];
    int numdns;
    char *hostname;
    char *domain;
    char *search;

    /* Misc DHCP settings */
    int dhcptimeout;
    char *vendorclass;

    /* Wireless settings */
    char *ssid;
    char *wepkey;

    /* s390 specifics */
    int mtu;
    char *subchannels;
    char *portname;
    char *peerid;
    char *nettype;
    char *ctcprot;

    /* flags */
    uint64_t flags;
    int ipv4method;
    int ipv6method;
} iface_t;

/* Function prototypes */

/*
 * Given an interface name (e.g., eth0), return the IP address in human
 * readable format (i.e., the output from inet_ntop()).  Return NULL for
 * no match.  NOTE:  This function will check for IPv6 and IPv4
 * addresses.  In the case where the interface has both, the IPv4 address
 * is returned.  The only way you will get an IPv6 address from this function
 * is if that's the only address configured for the interface.
 */
char *iface_ip2str(char *);

/*
 * Given an interface name (e.g., eth0), return the MAC address in human
 * readable format (e.g., 00:11:52:12:D9:A0).  Return NULL for no match.
 */
char *iface_mac2str(char *);

/*
 * Convert an IPv4 CIDR prefix to a dotted-quad netmask.  Return NULL on
 * failure.
 */
struct in_addr *iface_prefix2netmask(int);

/*
 * Convert an IPv4 netmask to an IPv4 CIDR prefix.  Return -1 on failure.
 */
int iface_netmask2prefix(struct in_addr *);

/*
 * Look up the hostname and domain for our assigned IP address.  Tries IPv4
 * first, then IPv6.  Returns 0 on success, non-negative on failure.
 */
int iface_dns_lookup(iface_t *);

/*
 * Initialize a new iface_t structure to default values.
 */
void iface_init_iface_t(iface_t *);

/*
 * Given a pointer to a struct in_addr, return 1 if it contains a valid
 * address, 0 otherwise.
 */
int iface_have_in_addr(struct in_addr *addr);

/*
 * Given a pointer to a struct in6_addr, return 1 if it contains a valid
 * address, 0 otherwise.
 */
int iface_have_in6_addr(struct in6_addr *addr6);

/*
 * Start NetworkManager
 */
int iface_start_NetworkManager(iface_t *iface);

/*
 * Set Maximum Transfer Unit (MTU) on specified interface
 */
int iface_set_interface_mtu(char *ifname, int mtu);

#endif /* ISYSIFACE_H */
