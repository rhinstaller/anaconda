/*
 * iface.c - Network interface configuration API
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

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/utsname.h>
#include <arpa/inet.h>
#include <dirent.h>
#include <fcntl.h>
#include <netdb.h>
#include <signal.h>
#include <netinet/in.h>
#include <netlink/netlink.h>
#include <netlink/socket.h>
#include <netlink/route/rtnl.h>
#include <netlink/route/route.h>
#include <netlink/route/addr.h>
#include <netlink/route/link.h>

#include "iface.h"
#include "str.h"

/* Internal-only function prototypes. */
static struct nl_handle *_iface_get_handle(void);
static struct nl_cache *_iface_get_link_cache(struct nl_handle **);
static int _iface_name_to_index(char *);
static int _iface_have_valid_addr(void *addr, int family, int length);
static int _iface_redirect_io(char *device, int fd, int mode);

/*
 * Return a libnl handle for NETLINK_ROUTE.
 */
static struct nl_handle *_iface_get_handle(void) {
    struct nl_handle *handle = NULL;

    if ((handle = nl_handle_alloc()) == NULL) {
        return NULL;
    }

    if (nl_connect(handle, NETLINK_ROUTE)) {
        nl_handle_destroy(handle);
        return NULL;
    }

    return handle;
}

/*
 * Return an NETLINK_ROUTE cache.
 */
static struct nl_cache *_iface_get_link_cache(struct nl_handle **handle) {
    struct nl_cache *cache = NULL;

    if ((*handle = _iface_get_handle()) == NULL) {
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
 * Convert an interface name to index number.
 */
static int _iface_name_to_index(char *ifname) {
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;

    if (ifname == NULL) {
        return -1;
    }

    if ((cache = _iface_get_link_cache(&handle)) == NULL) {
        return -1;
    }

    return rtnl_link_name2i(cache, ifname);
}

/*
 * Determine if a struct in_addr or struct in6_addr contains a valid address.
 */
static int _iface_have_valid_addr(void *addr, int family, int length) {
    char buf[length+1];

    if ((addr == NULL) || (family != AF_INET && family != AF_INET6)) {
        return 0;
    }

    memset(buf, '\0', sizeof(buf));

    if (inet_ntop(family, addr, buf, length) == NULL) {
        return 0;
    } else {
        /* check for unknown addresses */
        if (family == AF_INET) {
            if (!strncmp(buf, "0.0.0.0", 7)) {
                return 0;
            }
        } else if (family == AF_INET6) {
            if (!strncmp(buf, "::", 2)) {
                return 0;
            }
        }
    }

    return 1;
}

/*
 * Redirect I/O to another device (e.g., stdout to /dev/tty5)
 */
int _iface_redirect_io(char *device, int fd, int mode) {
    int io = -1;

    if ((io = open(device, mode)) == -1) {
        return 1;
    }

    if (close(fd) == -1) {
        return 2;
    }

    if (dup2(io, fd) == -1) {
        return 3;
    }

    if (close(io) == -1) {
        return 4;
    }

    return 0;
}

/*
 * Given an interface name (e.g., eth0), return the IP address in human
 * readable format (i.e., the output from inet_ntop()).  Return NULL for
 * no match.  NOTE:  This function will check for IPv6 and IPv4
 * addresses.  In the case where the interface has both, the IPv4 address
 * is returned.  The only way you will get an IPv6 address from this function
 * is if that's the only address configured for the interface.
 */
char *iface_ip2str(char *ifname) {
    int ifindex = -1, buflen = 0, family = 0;
    char *buf = NULL, *bufv4 = NULL, *bufv6 = NULL, *pos = NULL;
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct nl_object *obj = NULL;
    struct rtnl_addr *raddr = NULL;
    struct nl_addr *addr = NULL;

    if ((ifindex = _iface_name_to_index(ifname)) == -1) {
        goto ip2str_error;
    }

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

                if ((buf = calloc(sizeof(char *), buflen)) == NULL) {
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

/*
 * Given an interface name (e.g., eth0), return the MAC address in human
 * readable format (e.g., 00:11:52:12:D9:A0).  Return NULL for no match.
 */
char *iface_mac2str(char *ifname) {
    int buflen = 20;
    char *buf = NULL;
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct rtnl_link *link = NULL;
    struct nl_addr *addr = NULL;

    if (ifname == NULL) {
        return NULL;
    }

    if ((cache = _iface_get_link_cache(&handle)) == NULL) {
        return NULL;
    }

    if ((link = rtnl_link_get_by_name(cache, ifname)) == NULL) {
        goto mac2str_error2;
    }

    if ((addr = rtnl_link_get_addr(link)) == NULL) {
        goto mac2str_error3;
    }

    if ((buf = calloc(sizeof(char *), buflen)) == NULL) {
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
 * Convert an IPv4 CIDR prefix to a dotted-quad netmask.  Return NULL on
 * failure.
 */
struct in_addr *iface_prefix2netmask(int prefix) {
    int mask = 0;
    char *buf = NULL;
    struct in_addr *ret;

    if ((buf = calloc(sizeof(char *), INET_ADDRSTRLEN + 1)) == NULL) {
        return NULL;
    }

    mask = htonl(~((1 << (32 - prefix)) - 1));

    if (inet_ntop(AF_INET, (struct in_addr *) &mask, buf,
                  INET_ADDRSTRLEN) == NULL) {
        return NULL;
    }

    if ((ret = calloc(sizeof(struct in_addr), 1)) == NULL) {
        return NULL;
    }

    memcpy(ret, (struct in_addr *) &mask, sizeof(struct in_addr));
    return ret;
}

/*
 * Convert an IPv4 netmask to an IPv4 CIDR prefix.  Return -1 on failure.
 */
int iface_netmask2prefix(struct in_addr *netmask) {
    int ret = -1;
    struct in_addr mask;

    if (netmask == NULL) {
        return -1;
    }

    memcpy(&mask, netmask, sizeof(struct in_addr));

    while (mask.s_addr != 0) {
        mask.s_addr = mask.s_addr >> 1;
        ret++;
    }

    return ret;
}

/*
 * Look up the hostname and domain for our assigned IP address.  Tries IPv4
 * first, then IPv6.  Returns 0 on success, non-negative on failure.
 */
int iface_dns_lookup(iface_t *iface) {
    char *ch = NULL;
    struct sockaddr_in sa;
    struct sockaddr_in6 sa6;

    if ((iface->hostname != NULL) && (iface->domain != NULL)) {
        return 0;
    }

    /* make sure our hostname buffer is large enough */
    if ((iface->hostname = calloc('\0', NI_MAXHOST+1)) == NULL) {
        return 1;
    }

    /* try an IPv4 lookup first */
    if (iface_have_in_addr(&iface->ipaddr)) {
        memset(&sa, 0, sizeof(sa));
        sa.sin_family = AF_INET;
        sa.sin_addr.s_addr = iface->ipaddr.s_addr;

        if (getnameinfo((struct sockaddr *) &sa, sizeof(sa), iface->hostname,
                        NI_MAXHOST, NULL, 0, NI_NAMEREQD)) {
            free(iface->hostname);
            iface->hostname = NULL;
        }
    }

    /* try IPv6 lookup if IPv4 failed */
    if ((iface->hostname == NULL) && iface_have_in6_addr(&iface->ip6addr)) {
        memset(&sa6, 0, sizeof(sa6));
        sa6.sin6_family = AF_INET6;
        memcpy(&sa6.sin6_addr, &iface->ip6addr, sizeof(iface->ip6addr));

        if (getnameinfo((struct sockaddr *) &sa6, sizeof(sa6), iface->hostname,
                        NI_MAXHOST, NULL, 0, NI_NAMEREQD)) {
            free(iface->hostname);
            iface->hostname = NULL;
        }
    }

    /* fill in the domain */
    if ((iface->domain == NULL) && (iface->hostname != NULL)) {
        for (ch = iface->hostname; *ch && (*ch != '.'); ch++);

        if (*ch == '.') {
            iface->domain = strdup(ch + 1);
        }
    }

    return 0;
}

/*
 * Initialize a new iface_t structure to default values.
 */
void iface_init_iface_t(iface_t *iface) {
    int i;

    memset(&iface->device, '\0', sizeof(iface->device));
    memset(&iface->ipaddr, 0, sizeof(iface->ipaddr));
    memset(&iface->netmask, 0, sizeof(iface->netmask));
    memset(&iface->broadcast, 0, sizeof(iface->broadcast));
    memset(&iface->ip6addr, 0, sizeof(iface->ip6addr));
    memset(&iface->gateway, 0, sizeof(iface->gateway));
    memset(&iface->gateway6, 0, sizeof(iface->gateway6));

    for (i = 0; i < MAXNS; i++) {
        iface->dns[i] = NULL;
    }

    iface->macaddr = NULL;
    iface->ip6prefix = 0;
    iface->nextserver = NULL;
    iface->bootfile = NULL;
    iface->numdns = 0;
    iface->hostname = NULL;
    iface->domain = NULL;
    iface->search = NULL;
    iface->dhcptimeout = 0;
    iface->vendorclass = NULL;
    iface->ssid = NULL;
    iface->wepkey = NULL;
    iface->mtu = 0;
    iface->subchannels = NULL;
    iface->portname = NULL;
    iface->peerid = NULL;
    iface->nettype = NULL;
    iface->ctcprot = NULL;
    iface->flags = 0;
    iface->ipv4method = IPV4_UNUSED_METHOD;
    iface->ipv6method = IPV6_UNUSED_METHOD;

    return;
}

/*
 * Given a pointer to a struct in_addr, return 1 if it contains a valid
 * address, 0 otherwise.
 */
int iface_have_in_addr(struct in_addr *addr) {
    return _iface_have_valid_addr(addr, AF_INET, INET_ADDRSTRLEN);
}

/*
 * Given a pointer to a struct in6_addr, return 1 if it contains a valid
 * address, 0 otherwise.
 */
int iface_have_in6_addr(struct in6_addr *addr6) {
    return _iface_have_valid_addr(addr6, AF_INET6, INET6_ADDRSTRLEN);
}

/*
 * Start NetworkManager -- requires that you have already written out the
 * control files in /etc/sysconfig for the interface.
 */
int iface_start_NetworkManager(iface_t *iface) {
    int status;
    pid_t pid;

    /* Start NetworkManager */
    pid = fork();
    if (pid == 0) {
        if (setpgrp() == -1) {
            exit(1);
        }

        if (_iface_redirect_io("/dev/null", STDIN_FILENO, O_RDONLY) ||
            _iface_redirect_io(OUTPUT_TERMINAL, STDOUT_FILENO, O_WRONLY) ||
            _iface_redirect_io(OUTPUT_TERMINAL, STDERR_FILENO, O_WRONLY)) {
            exit(2);
        }

        if (execl(NETWORKMANAGER, NETWORKMANAGER,
                  "--pid-file=/var/run/NetworkManager/NetworkManager.pid",
                  NULL) == -1) {
            exit(3);
        } else {
            exit(0);
        }
    } else if (pid == -1) {
        return 1;
    } else {
        if (waitpid(pid, &status, 0) == -1) {
            return 2;
        }
    }

    return 0;
}

/*
 * Set the MTU on the specified device.
 */
int iface_set_interface_mtu(char *ifname, int mtu) {
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

    if ((cache = _iface_get_link_cache(&handle)) == NULL) {
        return -3;
    }

    if ((link = rtnl_link_get_by_name(cache, ifname)) == NULL) {
        ret = -4;
        goto ifacemtu_error1;
    }

    request = rtnl_link_alloc();
    rtnl_link_set_mtu(request, mtu);

    if (rtnl_link_change(handle, link, request, 0)) {
        ret = -5;
        goto ifacemtu_error2;
    }

ifacemtu_error2:
    rtnl_link_put(link);
ifacemtu_error1:
    nl_close(handle);
    nl_handle_destroy(handle);

    return ret;
}
