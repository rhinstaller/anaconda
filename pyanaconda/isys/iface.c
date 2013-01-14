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

#include <glib.h>
#include <NetworkManager.h>
#include <nm-client.h>
#include <nm-device.h>
#include <nm-ip4-config.h>
#include <nm-setting-ip4-config.h>
#include <nm-device-wifi.h>

#include "isys.h"
#include "iface.h"
#include "log.h"

/* Internal-only function prototypes. */
static struct nl_handle *_iface_get_handle(void);
static struct nl_cache *_iface_get_link_cache(struct nl_handle **);
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
 * Given an interface name (e.g., eth0) and address family (e.g., AF_INET),
 * return the IP address in human readable format (i.e., the output from
 * inet_ntop()).  Return NULL for no match or error.
 */
char *iface_ip2str(char *ifname, int family) {
    int i;
    NMClient *client = NULL;
    NMIP4Config *ip4config = NULL;
    NMIP4Address *ipaddr = NULL;
    NMDevice *candidate = NULL;
    struct in_addr tmp_addr;
    const GPtrArray *devices;
    const char *iface;
    char ipstr[INET_ADDRSTRLEN+1];

    if (ifname == NULL) {
        return NULL;
    }

    /* DCFIXME: add IPv6 once NM gains support */
    if (family != AF_INET) {
        return NULL;
    }

    client = nm_client_new();
    if (!client) {
        return NULL;
    }

    if (! is_connected_state(nm_client_get_state(client))) {
        g_object_unref(client);
        return NULL;
    }

    devices = nm_client_get_devices(client);
    for (i=0; i < devices->len; i++) {
        candidate = g_ptr_array_index(devices, i);
        iface = nm_device_get_iface(candidate);

        if (nm_device_get_state(candidate) != NM_DEVICE_STATE_ACTIVATED)
            continue;

        if (!iface || strcmp(iface, ifname))
            continue;

        if (!(ip4config = nm_device_get_ip4_config(candidate)))
            continue;

        if (!(ipaddr = nm_ip4_config_get_addresses(ip4config)->data))
            continue;

        memset(&ipstr, '\0', sizeof(ipstr));
        tmp_addr.s_addr = nm_ip4_address_get_address(ipaddr);

        if (inet_ntop(AF_INET, &tmp_addr, ipstr, INET_ADDRSTRLEN) == NULL) {
            g_object_unref(client);
            return NULL;
        }

        g_object_unref(client);
        return g_strdup(ipstr);
    }

    g_object_unref(client);
    return NULL;
}

/* Given an interface's MAC address, return the name (e.g., eth0) in human
 * readable format.  Return NULL for no match
 */
char *iface_mac2device(char *mac) {
    struct nl_handle *handle = NULL;
    struct nl_cache *cache = NULL;
    struct rtnl_link *link = NULL;
    struct nl_addr *mac_as_nl_addr = NULL;
    char *retval = NULL;
    int i, n;

    if (mac == NULL) {
        return NULL;
    }

    if ((mac_as_nl_addr = nl_addr_parse(mac, AF_LLC)) == NULL) {
        return NULL;
    }

    if ((cache = _iface_get_link_cache(&handle)) == NULL) {
        return NULL;
    }

    n = nl_cache_nitems(cache);
    for (i = 0; i <= n; i++) {
        struct nl_addr *addr;

        if ((link = rtnl_link_get(cache, i)) == NULL) {
            continue;
        }

        addr = rtnl_link_get_addr(link);

        if (!nl_addr_cmp(mac_as_nl_addr, addr)) {
            retval = strdup(rtnl_link_get_name(link));
            rtnl_link_put(link);
            break;
        }

        rtnl_link_put(link);
    }

    nl_close(handle);
    nl_handle_destroy(handle);

    return retval;
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
        char *oldbuf = buf;
        buf = g_ascii_strup(buf, -1);
        free(oldbuf);
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
    iface->options = NULL;
    iface->flags = 0;
    iface->ipv4method = IPV4_UNUSED_METHOD;
    iface->ipv6method = IPV6_UNUSED_METHOD;
    iface->defroute = 1;

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

int is_connected_state(NMState state) {
    return (state == NM_STATE_CONNECTED_LOCAL ||
            state == NM_STATE_CONNECTED_SITE ||
            state == NM_STATE_CONNECTED_GLOBAL);
}

/* Check if NM has an active connection */
gboolean is_nm_connected(void) {
    NMState state;
    NMClient *client = NULL;

    client = nm_client_new();
    if (!client)
        return FALSE;

    state = nm_client_get_state(client);
    g_object_unref(client);

    if (is_connected_state(state))
        return TRUE;
    else
        return FALSE;
}

/* Check if NM is already running */
gboolean is_nm_running(void) {
    gboolean running;
    NMClient *client = NULL;

    client = nm_client_new();
    if (!client)
        return FALSE;

    running = nm_client_get_manager_running(client);
    g_object_unref(client);
    return running;
}

gboolean is_iface_activated(char * ifname) {
    int i, state;
    NMClient *client = NULL;
    const GPtrArray *devices;

    client = nm_client_new();
    if (!client)
        return FALSE;

    devices = nm_client_get_devices(client);
    for (i = 0; i < devices->len; i++) {
        NMDevice *candidate = g_ptr_array_index(devices, i);
        const char *devname = nm_device_get_iface(candidate);
        if (strcmp(ifname, devname))
            continue;
        state = nm_device_get_state(candidate);
        g_object_unref(client);
        if (state == NM_DEVICE_STATE_ACTIVATED)
            return TRUE;
        else
            return FALSE;
    }

    g_object_unref(client);
    return FALSE;
}

/*
 * Wait for NetworkManager to appear on the system bus
 */
int wait_for_nm(void) {
    int count = 0;

    /* send message and block until a reply or error comes back */
    while (count < 45) {
        if (is_nm_running())
            return 0;

        sleep(1);
        count++;
    }

    return 1;
}

/*
 * Start NetworkManager -- requires that you have already written out the
 * control files in /etc/sysconfig for the interface.
 */
int iface_restart_NetworkManager(void) {
    int child, status;

    if (!(child = fork())) {

        if (_iface_redirect_io("/dev/null", STDIN_FILENO, O_RDONLY) ||
            _iface_redirect_io("/dev/tty3", STDOUT_FILENO, O_WRONLY) ||
            _iface_redirect_io("/dev/tty3", STDERR_FILENO, O_WRONLY)) {
            exit(253);
        }

        execl("/bin/systemctl", "/bin/systemctl", "restart", "NetworkManager.service", NULL);
        exit(254);
    } else if (child < 0) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        return 1;
    }

    if (waitpid(child, &status, 0) == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        return 1;
    }

    if (!WIFEXITED(status)) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        return 1;
    }

    if (WEXITSTATUS(status)) {
        logMessage(ERROR, "failed to restart NetworkManager with status %d", WEXITSTATUS(status));
        return 1;
    } else {
        return wait_for_nm();
    }
}

/*
 * Start NetworkManager -- requires that you have already written out the
 * control files in /etc/sysconfig for the interface.
 * This is needed on s390 until we have systemd init doing it as for other archs.
 */
int iface_start_NetworkManager(void) {
    pid_t pid;

    if (is_nm_running())
        return 0;  /* already running */

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
        }
    } else if (pid == -1) {
        return 1;
    } else {
        return wait_for_nm();
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

