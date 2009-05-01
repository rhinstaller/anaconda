/*
 * nl.c - Netlink helper functions
 *
 * Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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

#include <stdio.h>
#include <stdlib.h>
#include <netinet/in.h>
#include <netlink/netlink.h>
#include <netlink/route/addr.h>
#include <netlink/route/link.h>

#include "nl.h"
#include "str.h"

/*
 * Return an NETLINK_ROUTE cache.
 */
struct nl_cache *nl_get_link_cache(struct nl_handle **handle) {
    struct nl_cache *cache = NULL;

    if ((*handle = nl_handle_alloc()) == NULL) {
        return NULL;
    }

    if (nl_connect(*handle, NETLINK_ROUTE)) {
        nl_handle_destroy(*handle);
        return NULL;
    }

    if ((cache = rtnl_link_alloc_cache(*handle)) == NULL) {
        nl_close(*handle);
        nl_handle_destroy(*handle);
        return NULL;
    }

    return cache;
}

/*
 * Given an interface name (e.g., eth0), return the IP address in human
 * readable format (i.e., the output from inet_ntop()).  Return NULL for
 * no match.  NOTE:  This function will check for IPv6 and IPv4
 * addresses.  In the case where the interface has both, the IPv4 address
 * is returned.  The only way you will get an IPv6 address from this function
 * is if that's the only address configured for the interface.
 */
char *nl_ip2str(char *ifname) {
    int ifindex = -1, buflen = 0, family = 0;
    char *buf = NULL, *bufv4 = NULL, *bufv6 = NULL, *pos = NULL;
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct nl_object *obj = NULL;
    struct rtnl_addr *raddr = NULL;
    struct nl_addr *addr = NULL;

    if (ifname == NULL) {
        return NULL;
    }

    if ((cache = nl_get_link_cache(&handle)) == NULL) {
        return NULL;
    }

    ifindex = rtnl_link_name2i(cache, ifname);

    if ((cache = rtnl_addr_alloc_cache(handle)) == NULL) {
        goto ip2str_error;
    }

    /* find the IPv4 and IPv6 addresses for this interface */
    if ((obj = nl_cache_get_first(cache)) == NULL) {
        goto ip2str_error;
    }

    do {
        raddr = (struct rtnl_addr *) obj;

        if (rtnl_addr_get_ifindex(raddr) == ifindex) {
            family = rtnl_addr_get_family(raddr);

            if (family == AF_INET || family == AF_INET6) {
                /* skip if we have already saved an address */
                /* FIXME: we should handle multiple addresses for the same
                 * family per interface
                 */
                if (family == AF_INET && bufv4 != NULL) {
                    continue;
                }

                if (family == AF_INET6 && bufv6 != NULL) {
                    continue;
                }

                /* get the address */
                addr = rtnl_addr_get_local(raddr);

                /* convert to human readable format */
                if (family == AF_INET) {
                    buflen = INET_ADDRSTRLEN;
                } else if (family == AF_INET6) {
                    buflen = INET6_ADDRSTRLEN;
                }

                buflen += 1;

                if ((buf = malloc(buflen)) == NULL) {
                    nl_addr_destroy(addr);
                    goto ip2str_error;
                }

                buf = nl_addr2str(addr, buf, buflen);
                nl_addr_destroy(addr);

                /* trim the prefix notation */
                if ((pos = index(buf, '/')) != NULL) {
                    *pos = '\0';
                    if ((buf = realloc(buf, strlen(buf) + 1)) == NULL) {
                        nl_addr_destroy(addr);
                        goto ip2str_error;
                    }
                }

                /* save the IP address in the right buffer */
                if (family == AF_INET) {
                    bufv4 = strdup(buf);
                } else if (family == AF_INET6) {
                    bufv6 = strdup(buf);
                }

                /* empty the main conversion buffer */
                if (buf) {
                    free(buf);
                    buf = NULL;
                }
            }
        }
    } while ((obj = nl_cache_get_next(obj)) != NULL);

ip2str_error:
    nl_close(handle);
    nl_handle_destroy(handle);

    /* return IPv4 address if we have both families
     * return IPv6 address if we only have IPv6 family
     * return NULL otherwise
     */
    if ((bufv4 && bufv6) || (bufv4 && !bufv6)) {
        return bufv4;
    } else if (!bufv4 && bufv6) {
        return bufv6;
    } else {
        return NULL;
    }
}

/**
 * Given an interface name (e.g., eth0), return the MAC address in human
 * readable format (e.g., 00:11:52:12:D9:A0).  Return NULL for no match.
 */
char *nl_mac2str(char *ifname) {
    int buflen = 20;
    char *buf = NULL;
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct rtnl_link *link = NULL;
    struct nl_addr *addr = NULL;

    if (ifname == NULL) {
        return NULL;
    }

    if ((cache = nl_get_link_cache(&handle)) == NULL) {
        return NULL;
    }

    if ((link = rtnl_link_get_by_name(cache, ifname)) == NULL) {
        goto mac2str_error2;
    }

    if ((addr = rtnl_link_get_addr(link)) == NULL) {
        goto mac2str_error3;
    }

    if ((buf = malloc(buflen)) == NULL) {
        goto mac2str_error4;
    }

    if ((buf = nl_addr2str(addr, buf, buflen)) != NULL) {
        buf = str2upper(buf);
    }

mac2str_error4:
    nl_addr_destroy(addr);
mac2str_error3:
    rtnl_link_put(link);
mac2str_error2:
    nl_close(handle);
    nl_handle_destroy(handle);

    return buf;
}

/*
 * Set the MTU on the specified device
 */
int nl_set_device_mtu(char *ifname, int mtu) {
    int ret = 0;
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct rtnl_link *link = NULL;
    struct rtnl_link *request = NULL;

    if (ifname == NULL) {
        return -1;
    }

    if (mtu <= 0) {
        return -2;
    }

    if ((cache = nl_get_link_cache(&handle)) == NULL) {
        return -3;
    }

    if ((link = rtnl_link_get_by_name(cache, ifname)) == NULL) {
        ret = -4;
        goto devmtu_error1;
    }

    request = rtnl_link_alloc();
    rtnl_link_set_mtu(request, mtu);

    if (rtnl_link_change(handle, link, request, 0)) {
        ret = -5;
        goto devmtu_error2;
    }

devmtu_error2:
    rtnl_link_put(link);
devmtu_error1:
    nl_close(handle);
    nl_handle_destroy(handle);

    return ret;
}
