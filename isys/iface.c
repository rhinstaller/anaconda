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

#include <dbus/dbus.h>
#include <NetworkManager.h>

#include "iface.h"
#include "str.h"

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
    char *ipaddr = NULL;
    char *nm_iface = NM_DBUS_INTERFACE;
    char *property = NULL;
    char *device_path = NULL;
    char *interface = NULL;
    struct in_addr addr;
    DBusConnection *connection = NULL;
    DBusError error;
    DBusMessage *message = NULL, *reply = NULL, *devreply = NULL;
    DBusMessageIter iter, a_iter, d_iter, v_iter;

    if (ifname == NULL) {
        return NULL;
    }

    /* DCFIXME: add IPv6 once NM gains support */
    if (family != AF_INET) {
        return NULL;
    }

    dbus_error_init(&error);
    connection = dbus_bus_get(DBUS_BUS_SYSTEM, &error);
    if (connection == NULL) {
        dbus_error_free(&error);
        return NULL;
    }

    message = dbus_message_new_method_call(NM_DBUS_SERVICE,
                                           NM_DBUS_PATH,
                                           NM_DBUS_SERVICE,
                                           "GetDevices");
    if (!message) {
        return NULL;
    }

    reply = dbus_connection_send_with_reply_and_block(connection,
                                                      message,
                                                      -1, &error);
    dbus_message_unref(message);
    if (!reply) {
        return NULL;
    }

    dbus_message_iter_init(reply, &iter);
    dbus_message_iter_recurse(&iter, &a_iter);

    while (dbus_message_iter_get_arg_type(&a_iter) != DBUS_TYPE_INVALID) {
        dbus_message_iter_get_basic(&a_iter, &device_path);

        message = dbus_message_new_method_call(NM_DBUS_SERVICE,
                                               device_path,
                                               DBUS_INTERFACE_PROPERTIES,
                                               "Get");
        if (!message) {
            return NULL;
        }

        property = "Interface";
        if (!dbus_message_append_args(message,
                                      DBUS_TYPE_STRING, &nm_iface,
                                      DBUS_TYPE_STRING, &property,
                                      DBUS_TYPE_INVALID)) {
            dbus_message_unref(message);
            return NULL;
        }

        devreply = dbus_connection_send_with_reply_and_block(connection,
                                                             message,
                                                             -1, &error);
        dbus_message_unref(message);
        if (!devreply) {
            dbus_message_iter_next(&a_iter);
            continue;
        }

        dbus_message_iter_init(devreply, &d_iter);
        while (dbus_message_iter_get_arg_type(&d_iter) != DBUS_TYPE_INVALID) {
            dbus_message_iter_recurse(&d_iter, &v_iter);
            dbus_message_iter_get_basic(&v_iter, &interface);

            if (!strcmp(ifname, interface)) {
                message = dbus_message_new_method_call(NM_DBUS_SERVICE,
                              device_path, DBUS_INTERFACE_PROPERTIES, "Get");
                if (!message) {
                    return NULL;
                }

                if (family == AF_INET) {
                    property = "Ip4Address";
                }

                if (!dbus_message_append_args(message,
                                              DBUS_TYPE_STRING, &nm_iface,
                                              DBUS_TYPE_STRING, &property,
                                              DBUS_TYPE_INVALID)) {
                    dbus_message_unref(message);
                    return NULL;
                }

                devreply = dbus_connection_send_with_reply_and_block(connection,
                               message, -1, &error);
                dbus_message_unref(message);
                if (!devreply) {
                    return NULL;
                }

                dbus_message_iter_init(devreply, &d_iter);
                dbus_message_iter_recurse(&d_iter, &v_iter);
                if (dbus_message_iter_get_arg_type(&v_iter)==DBUS_TYPE_UINT32) {
                    memset(&addr, 0, sizeof(addr));
                    dbus_message_iter_get_basic(&v_iter, &addr.s_addr);

                    if ((ipaddr = malloc(INET_ADDRSTRLEN+1)) == NULL) {
                        abort();
                    }

                    if (inet_ntop(family, &addr, ipaddr,
                                  INET_ADDRSTRLEN) == NULL) {
                        abort();
                    }

                    dbus_connection_unref(connection);
                    return ipaddr;
                }
            }


            dbus_message_iter_next(&d_iter);
        }

        dbus_message_iter_next(&a_iter);
    }

    dbus_connection_unref(connection);
    return NULL;
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

/* Check if NM is already running */
int is_nm_running(DBusConnection *connection, int *running, char **error_str)
{
    DBusError error;
    DBusMessage *message, *reply;
    const char *nm_service = NM_DBUS_SERVICE;
    dbus_bool_t alive = FALSE;

    message = dbus_message_new_method_call("org.freedesktop.DBus",
                                           "/org/freedesktop/DBus",
                                           "org.freedesktop.DBus",
                                           "NameHasOwner");
    if (!message)
        return 33;

    if (!dbus_message_append_args(message,
                                  DBUS_TYPE_STRING, &nm_service,
                                  DBUS_TYPE_INVALID)) {
        dbus_message_unref(message);
        return 34;
    }

    dbus_error_init(&error);
    reply = dbus_connection_send_with_reply_and_block(connection,
                                                        message, 2000,
                                                        &error);
    if (!reply) {
        if (dbus_error_is_set(&error)) {
            *error_str = strdup(error.message);
            dbus_error_free(&error);
        }

        dbus_message_unref(message);
        return 35;
    }

    dbus_error_init(&error);
    if (!dbus_message_get_args(reply, &error,
                                DBUS_TYPE_BOOLEAN, &alive,
                                DBUS_TYPE_INVALID)) {
        if (dbus_error_is_set(&error)) {
            *error_str = strdup(error.message);
            dbus_error_free(&error);
        }

        dbus_message_unref(message);
        dbus_message_unref(reply);
        return 36;
    }

    *running = alive;

    dbus_message_unref(message);
    dbus_message_unref(reply);
    return 0;
}

/*
 * Wait for NetworkManager to appear on the system bus
 */
int wait_for_nm(DBusConnection *connection, char **error_str) {
    int count = 0;

    /* send message and block until a reply or error comes back */
    while (count < 45) {
        int running = 0, ret;

        ret = is_nm_running(connection, &running, error_str);
        if (ret != 0)
            return ret;  /* error */
        if (running)
            return 0;  /* nm is alive */

        sleep(1);
        count++;
    }

    return 37;
}

/*
 * Start NetworkManager -- requires that you have already written out the
 * control files in /etc/sysconfig for the interface.
 */
int iface_start_NetworkManager(DBusConnection *connection, char **error) {
    pid_t pid;
    int ret, running = 0;
    char *ignore = NULL;

    ret = is_nm_running(connection, &running, &ignore);
    if (ignore)
        free(ignore);

    if (ret == 0 && running)
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
        return wait_for_nm(connection, error);
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
