/*
 * net.c
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005  Red Hat, Inc.
 *               2006, 2007, 2008
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

#include <netdb.h>
#include <sys/types.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/utsname.h>
#include <arpa/inet.h>
#include <errno.h>
#include <popt.h>
#include <resolv.h>
#include <net/if.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <dbus/dbus.h>
#include <NetworkManager.h>

#include "../isys/isys.h"
#include "../isys/ethtool.h"
#include "../isys/iface.h"
#include "../isys/str.h"

#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "windows.h"

/* boot flags */
extern uint64_t flags;

/**
 * Callback function for the CIDR entry boxes on the manual TCP/IP
 * configuration window.
 *
 * @param co The entry field that triggered the callback.
 * @param dptr Pointer to intfconfig_s data structure for this field.
 * @see intfconfig_s
 */
static void cidrCallback(newtComponent co, void * dptr) {
    struct intfconfig_s * data = dptr;
    int cidr, upper = 0;
    struct in_addr addr;

    if (co == data->cidr4Entry) {
        if (data->cidr4 == NULL && data->ipv4 == NULL)
            return;

        if (inet_pton(AF_INET, data->cidr4, &addr) >= 1)
            return;

        errno = 0;
        cidr = strtol(data->cidr4, NULL, 10);
        if ((errno == ERANGE && (cidr == LONG_MIN || cidr == LONG_MAX)) ||
            (errno != 0 && cidr == 0)) {
            logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

        if (strcmp(data->ipv4, ""))
            upper = 32;
    } else if (co == data->cidr6Entry) {
        if (data->cidr6 == NULL && data->ipv6 == NULL)
            return;

        errno = 0;
        cidr = strtol(data->cidr6, NULL, 10);
        if ((errno == ERANGE && (cidr == LONG_MIN || cidr == LONG_MAX)) ||
            (errno != 0 && cidr == 0)) {
            logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

        if (strcmp(data->ipv6, ""))
            upper = 128;
    }

    if (upper != 0) {
        if (cidr < 1 || cidr > upper) {
            newtWinMessage(_("Invalid Prefix"), _("Retry"),
                           _("Prefix must be between 1 and 32 "
                             "for IPv4 networks or between 1 and 128 "
                             "for IPv6 networks"));
        }
    }
}

static void ipCallback(newtComponent co, void * dptr) {
    int i;
    char *buf, *octet;
    struct intfconfig_s * data = dptr;

    if (co == data->ipv4Entry) {
        /* do we need to guess a netmask for the user? */
        if (data->cidr4 == NULL && data->ipv4 != NULL) {
            buf = strdup(data->ipv4);
            octet = strtok(buf, ".");
            errno = 0;
            i = strtol(octet, NULL, 10);

            if ((errno == ERANGE && (i == LONG_MIN || i == LONG_MAX)) ||
                (errno != 0 && i == 0)) {
                logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            free(buf);
            free(octet);

            if (i >= 0 && i <= 127)
                newtEntrySet(data->cidr4Entry, "8", 1);
            else if (i >= 128 && i <= 191)
                newtEntrySet(data->cidr4Entry, "16", 1);
            else if (i >= 192 && i <= 222)
                newtEntrySet(data->cidr4Entry, "24", 1);
        }

        return;
    } else if (co == data->ipv6Entry) {
        /* users must provide a mask, we can't guess for ipv6 */
        return;
    }
}

static void setMethodSensitivity(void *dptr, int radio_button_count) {
    int i = 0;

    for (i = 0; i < radio_button_count; i++) {
        newtCheckboxSetFlags(*((newtComponent *) dptr), NEWT_FLAG_DISABLED,
                             NEWT_FLAGS_TOGGLE);
        dptr += sizeof (newtComponent);
    }

    return;
}

static void v4MethodCallback(newtComponent co, void *dptr) {
    setMethodSensitivity(dptr, 2);
    return;
}

static void v6MethodCallback(newtComponent co, void *dptr) {
    setMethodSensitivity(dptr, 3);
    return;
}

static void parseEthtoolSettings(struct loaderData_s * loaderData) {
    char * option, * buf;
    ethtool_duplex duplex = ETHTOOL_DUPLEX_UNSPEC;
    ethtool_speed speed = ETHTOOL_SPEED_UNSPEC;
    
    buf = strdup(loaderData->ethtool);
    option = strtok(buf, " ");
    while (option) {
        if (option[strlen(option) - 1] == '\"')
            option[strlen(option) - 1] = '\0';
        if (option[0] == '\"')
            option++;
        if (!strncmp(option, "duplex", 6)) {
            if (!strncmp(option + 7, "full", 4)) 
                duplex = ETHTOOL_DUPLEX_FULL;
            else if (!strncmp(option + 7, "half", 4))
                duplex = ETHTOOL_DUPLEX_HALF;
            else
                logMessage(WARNING, "Unknown duplex setting: %s", option + 7);
            option = strtok(NULL, " ");
        } else if (!strncmp("speed", option, 5)) {
            if (!strncmp(option + 6, "1000", 4))
                speed = ETHTOOL_SPEED_1000;
            else if (!strncmp(option + 6, "100", 3))
                speed = ETHTOOL_SPEED_100;
            else if (!strncmp(option + 6, "10", 2))
                speed = ETHTOOL_SPEED_10;
            else
                logMessage(WARNING, "Unknown speed setting: %s", option + 6);
            option = strtok(NULL, " ");
        } else {
            logMessage(WARNING, "Unknown ethtool setting: %s", option);
        }
        option = strtok(NULL, " ");
    }
    setEthtoolSettings(loaderData->netDev, speed, duplex);
    free(buf);
}

/* given loader data from kickstart, populate network configuration struct */
void setupNetworkDeviceConfig(iface_t * iface,
                              struct loaderData_s * loaderData) {
    int err;
    struct in_addr addr;
    struct in6_addr addr6;
    char * c;

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->netCls_set) {
        iface->vendorclass = loaderData->netCls;
    } else {
        iface->vendorclass = NULL;
    }

    if (loaderData->ipinfo_set) {
        /* this is how we specify dhcp */
        if (!strncmp(loaderData->ipv4, "dhcp", 4)) {
            int ret = 0;

            /* JKFIXME: this soooo doesn't belong here.  and it needs to
             * be broken out into a function too */
            logMessage(INFO, "sending dhcp request through device %s",
                       loaderData->netDev);

            if (!FL_TESTING(flags)) {
                if (loaderData->noDns) {
                    iface->flags |= IFACE_FLAGS_NO_WRITE_RESOLV_CONF;
                }

                iface->dhcptimeout = loaderData->dhcpTimeout;

                err = writeEnabledNetInfo(iface);
                if (err) {
                    logMessage(ERROR,
                               "failed to write /etc/sysconfig data for %s (%d)",
                               iface->device, err);
                    return;
                }

                ret = get_connection(iface);
                newtPopWindow();
            }

            if (ret) {
                logMessage(ERROR, "failed to start NetworkManager (%d)", ret);
                return;
            }

            iface->flags |= IFACE_FLAGS_IS_DYNAMIC | IFACE_FLAGS_IS_PRESET;
        } else if (loaderData->ipv4) {
            if (inet_pton(AF_INET, loaderData->ipv4, &addr) >= 1) {
                iface->ipaddr = addr;
                iface->flags &= ~IFACE_FLAGS_IS_DYNAMIC;
                iface->flags |= IFACE_FLAGS_IS_PRESET;
            }
        } else if (loaderData->ipv6) {
            if (inet_pton(AF_INET6, loaderData->ipv6, &addr6) >= 1) {
                memcpy(&iface->ip6addr, &addr6, sizeof(struct in6_addr));
                iface->flags &= ~IFACE_FLAGS_IS_DYNAMIC;
                iface->flags |= IFACE_FLAGS_IS_PRESET;
            }
        } else { /* invalid ip information, disable the setting of ip info */
            loaderData->ipinfo_set = 0;
            iface->flags &= ~IFACE_FLAGS_IS_DYNAMIC;
            loaderData->ipv4 = NULL;
            loaderData->ipv6 = NULL;
        }
    }

    if (loaderData->netmask) {
        if (inet_pton(AF_INET, loaderData->netmask, &iface->netmask) <= 0) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }

    if (loaderData->gateway) {
        if (inet_pton(AF_INET, loaderData->gateway, &iface->gateway) <= 0) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }

    /* FIXME: add support for loaderData->gateway6 */

    if (loaderData->dns) {
        char * buf;
        char ret[INET6_ADDRSTRLEN+1];
        buf = strdup(loaderData->dns);

        /* Scan the dns parameter for multiple comma-separated IP addresses */
        c = strtok(buf, ",");
        while ((iface->numdns < MAXNS) && (c != NULL)) {
            if (inet_pton(AF_INET, c, &addr) >= 1) {
                iface->dns[iface->numdns] = strdup(c);
                iface->numdns++;

                if (inet_ntop(AF_INET, &addr, ret, INET_ADDRSTRLEN) == NULL) {
                    logMessage(ERROR, "%s (%d): %s", __func__, __LINE__, strerror(errno));
                } else {
                    logMessage(DEBUGLVL, "adding dns4 %s", ret);
                    c = strtok(NULL, ",");
                }
            } else if (inet_pton(AF_INET6, c, &addr6) >= 1) {
                iface->dns[iface->numdns] = strdup(c);
                iface->numdns++;

                if (inet_ntop(AF_INET6, &addr6, ret, INET6_ADDRSTRLEN) == NULL) {
                    logMessage(ERROR, "%s (%d): %s", __func__, __LINE__, strerror(errno));
                } else {
                    logMessage(DEBUGLVL, "adding dns6 %s", ret);
                    c = strtok(NULL, ",");
                }
            }
        }

        logMessage(INFO, "dnsservers is %s", loaderData->dns);
    }

    if (loaderData->hostname) {
        logMessage(INFO, "setting specified hostname of %s",
                   loaderData->hostname);
        iface->hostname = strdup(loaderData->hostname);
    }

    if (loaderData->mtu) {
        iface->mtu = loaderData->mtu;
    }

    if (loaderData->peerid) {
        iface->peerid = strdup(loaderData->peerid);
    }

    if (loaderData->subchannels) {
        iface->subchannels = strdup(loaderData->subchannels);
    }

    if (loaderData->ctcprot) {
        iface->ctcprot = strdup(loaderData->ctcprot);
    }

    if (loaderData->portname) {
        iface->portname = strdup(loaderData->portname);
    }

    if (loaderData->nettype) {
        iface->nettype = strdup(loaderData->nettype);
    }

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->noDns) {
        iface->flags |= IFACE_FLAGS_NO_WRITE_RESOLV_CONF;
    }

    iface->dhcptimeout = loaderData->dhcpTimeout;
}

int readNetConfig(char * device, iface_t * iface,
                  char * dhcpclass, int methodNum) {
    int err;
    int ret;
    int i = 0;
    struct netconfopts opts;
    struct in_addr addr;
    struct intfconfig_s ipcomps;

    /* ipcomps contains the user interface components */
    ipcomps.ipv4 = NULL;
    ipcomps.ipv6 = NULL;
    ipcomps.cidr4 = NULL;
    ipcomps.cidr6 = NULL;
    ipcomps.gw = NULL;
    ipcomps.gw6 = NULL;
    ipcomps.ns = NULL;

    /* init opts */
    opts.ipv4Choice = 0;
    opts.ipv6Choice = 0;

    /* JKFIXME: we really need a way to override this and be able to change
     * our network config */
    if (!FL_TESTING(flags) && IFACE_IS_PRESET(iface->flags)) {
        logMessage(INFO, "doing kickstart... setting it up");

        err = writeEnabledNetInfo(iface);
        if (err) {
            logMessage(ERROR, "failed to write /etc/sysconfig data for %s (%d)",
                       iface->device, err);
            return LOADER_BACK;
        }

        i = get_connection(iface);
        newtPopWindow();

        if (i > 0) {
            newtWinMessage(_("Network Error"), _("Retry"),
                           _("There was an error configuring your network "
                             "interface."));
            return LOADER_BACK;
        }

        return LOADER_NOOP;
    }

    /* dhcp/manual network configuration loop */
    i = 1;
    while (i == 1) {
        ret = configureTCPIP(device, iface, &opts, methodNum);

        if (ret == LOADER_NOOP) {
            /* dhcp selected, proceed */
            i = 0;
        } else if (ret == LOADER_OK) {
            /* do manual configuration */
            ret = manualNetConfig(device, iface, &ipcomps, &opts);

            if (ret == LOADER_BACK) {
                continue;
            } else if (ret == LOADER_OK) {
                i = 0;
            }
        } else if (ret == LOADER_BACK) {
            return LOADER_BACK;
        }
    }

    /* calculate any missing IPv4 pieces */
    if (opts.ipv4Choice == '*') {
        memset(&addr, 0, sizeof(addr));
        addr.s_addr = (iface->ipaddr.s_addr) & (iface->netmask.s_addr);

        if (iface->broadcast.s_addr == 0) {
            iface->broadcast.s_addr = addr.s_addr | ~(iface->netmask.s_addr);
        }
    }

    /* bring up the interface */
    if (!FL_TESTING(flags)) {
        err = writeEnabledNetInfo(iface);
        if (err) {
            logMessage(ERROR, "failed to write /etc/sysconfig data for %s (%d)",
                       iface->device, err);
            return LOADER_BACK;
        }

        i = get_connection(iface);
        newtPopWindow();

        if (i > 0) {
            newtWinMessage(_("Network Error"), _("Retry"),
                           _("There was an error configuring your network "
                             "interface."));
            return LOADER_BACK;
        }
    }

    return LOADER_OK;
}

int configureTCPIP(char * device, iface_t * iface,
                   struct netconfopts * opts, int methodNum) {
    int i = 0, z = 0, skipForm = 0, dret = 0, err;
    newtComponent f, okay, back, answer;
    newtComponent ipv4Checkbox, ipv6Checkbox, v4Method[2], v6Method[3];
    newtGrid grid, checkgrid, buttons;

    /* UI WINDOW 1: ask for ipv4 choice, ipv6 choice, and conf methods */

    /* IPv4 checkbox */
    if (!opts->ipv4Choice) {
        if (FL_NOIPV4(flags) && !FL_IP_PARAM(flags))
            opts->ipv4Choice = ' ';
        else
            opts->ipv4Choice = '*';
    }

    ipv4Checkbox = newtCheckbox(-1, -1, _("Enable IPv4 support"),
                                opts->ipv4Choice, NULL, &(opts->ipv4Choice));
    v4Method[0] = newtRadiobutton(-1, -1, DHCP_METHOD_STR, 1, NULL);
    v4Method[1] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, 0, v4Method[0]);

    /* IPv6 checkbox */
    if (!opts->ipv6Choice) {
        if (FL_NOIPV6(flags) && !FL_IPV6_PARAM(flags))
            opts->ipv6Choice = ' ';
        else
            opts->ipv6Choice = '*';
    }

    ipv6Checkbox = newtCheckbox(-1, -1, _("Enable IPv6 support"),
                                opts->ipv6Choice, NULL, &(opts->ipv6Choice));
    v6Method[0] = newtRadiobutton(-1, -1, AUTO_METHOD_STR, 1, NULL);
    v6Method[1] = newtRadiobutton(-1, -1, DHCPV6_METHOD_STR, 0, v6Method[0]);
    v6Method[2] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, 0, v6Method[1]);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

    /* checkgrid contains the toggle options for net configuration */
    checkgrid = newtCreateGrid(1, 8);

    newtGridSetField(checkgrid, 0, 0, NEWT_GRID_COMPONENT, ipv4Checkbox,
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    for (i = 1; i < 3; i++)
        newtGridSetField(checkgrid, 0, i, NEWT_GRID_COMPONENT, v4Method[i-1],
                         7, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    newtGridSetField(checkgrid, 0, 4, NEWT_GRID_COMPONENT, ipv6Checkbox,
                     0, 1, 0, 0, NEWT_ANCHOR_LEFT, 0);
    for (i = 5; i < 8; i++)
        newtGridSetField(checkgrid, 0, i, NEWT_GRID_COMPONENT, v6Method[i-5],
                         7, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    /* main window layout */
    grid = newtCreateGrid(1, 2);
    newtGridSetField(grid, 0, 0, NEWT_GRID_SUBGRID, checkgrid,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Configure TCP/IP"));
    newtGridFree(grid, 1);

    /* callbacks */
    newtComponentAddCallback(ipv4Checkbox, v4MethodCallback, &v4Method);
    newtComponentAddCallback(ipv6Checkbox, v6MethodCallback, &v6Method);

    /* match radio button sensitivity to initial checkbox choices */
    if (opts->ipv4Choice == ' ')
        setMethodSensitivity(&v4Method, 2);

    if (opts->ipv6Choice == ' ')
        setMethodSensitivity(&v6Method, 3);

    /* If the user provided any of the following boot paramters, skip
     * prompting for network configuration information:
     *     ip=<val> ipv6=<val>
     *     noipv4 noipv6
     *     ip=<val> noipv6
     *     ipv6=<val> noipv4
     * we also skip this form for anyone doing a kickstart install
     */
    if ((FL_IP_PARAM(flags) && FL_IPV6_PARAM(flags)) ||
        (FL_IP_PARAM(flags) && FL_NOIPV6(flags)) ||
        (FL_IPV6_PARAM(flags) && FL_NOIPV4(flags)) ||
        (FL_NOIPV4(flags) && FL_NOIPV6(flags)) ||
        (FL_IS_KICKSTART(flags))) {
        skipForm = 1;
        newtPopWindow();
    }

    /* run the form */
    do {
        if (!skipForm) {
            answer = newtRunForm(f);

            if (answer == back) {
                newtFormDestroy(f);
                newtPopWindow();
                return LOADER_BACK;
            }

            /* need at least one stack */
            if (opts->ipv4Choice == ' ' && opts->ipv6Choice == ' ') {
                newtWinMessage(_("Missing Protocol"), _("Retry"),
                               _("You must select at least one protocol (IPv4 "
                                 "or IPv6)."));
                continue;
            }

            /* NFS only works over IPv4 */
            if (opts->ipv4Choice == ' ' && methodNum == METHOD_NFS) {
                newtWinMessage(_("IPv4 Needed for NFS"), _("Retry"),
                           _("NFS installation method requires IPv4 support."));
                continue;
            }
        }

        /* what TCP/IP stacks do we use? what conf methods? */
        if (opts->ipv4Choice == '*') {
            flags &= ~LOADER_FLAGS_NOIPV4;
            for (z = IPV4_FIRST_METHOD; z <= IPV4_LAST_METHOD; z++)
                if (newtRadioGetCurrent(v4Method[0]) == v4Method[z-1])
                    iface->ipv4method = z;
        } else {
            flags |= LOADER_FLAGS_NOIPV4;
        }

        if (opts->ipv6Choice == '*') {
            flags &= ~LOADER_FLAGS_NOIPV6;
            for (z = IPV6_FIRST_METHOD; z <= IPV6_LAST_METHOD; z++)
                if (newtRadioGetCurrent(v6Method[0]) == v6Method[z-1])
                    iface->ipv6method = z;
        } else {
            flags |= LOADER_FLAGS_NOIPV6;
        }

        /* do interface configuration (call DHCP here, or return for manual) */
        if ((!FL_NOIPV4(flags) && iface->ipv4method == IPV4_DHCP_METHOD) ||
            (!FL_NOIPV6(flags) && (iface->ipv6method == IPV6_AUTO_METHOD ||
                                   iface->ipv6method == IPV6_DHCP_METHOD))) {
            /* do DHCP if selected */
            if (!FL_TESTING(flags)) {
                err = writeEnabledNetInfo(iface);
                if (err) {
                    logMessage(ERROR,
                               "failed to write /etc/sysconfig data for %s (%d)",
                               iface->device, err);
                    return LOADER_BACK;
                }

                dret = get_connection(iface);
                newtPopWindow();
            }

            if (!dret) {
                iface->flags |= IFACE_FLAGS_IS_DYNAMIC;
                i = 1;
            } else {
                logMessage(DEBUGLVL, "get_connection() failed, returned %d", dret);
                i = 0;
            }
        } else {
            /* manual IP configuration for IPv4 and IPv6 */
            newtFormDestroy(f);
            newtPopWindow();
            return LOADER_OK;
        }
    } while (i != 1);

    newtFormDestroy(f);
    newtPopWindow();

    if ((!FL_NOIPV4(flags) && iface->ipv4method == IPV4_MANUAL_METHOD) ||
        (!FL_NOIPV6(flags) && iface->ipv6method == IPV6_MANUAL_METHOD))
        return LOADER_OK;
    else
        return LOADER_NOOP;
}

int manualNetConfig(char * device, iface_t * iface,
                    struct intfconfig_s * ipcomps, struct netconfopts * opts) {
    int i, rows, pos, prefix, cidr, have[2], stack[2];
    char *buf = NULL;
    char ret[48];
    struct in_addr addr;
    struct in6_addr addr6;
    struct in_addr *tmpaddr = NULL;
    newtComponent f, okay, back, answer;
    newtGrid egrid = NULL;
    newtGrid qgrid = NULL;
    newtGrid rgrid = NULL;
    newtGrid buttons, grid;
    newtComponent text = NULL;

    memset(ret, '\0', INET6_ADDRSTRLEN+1);

    /* so we don't perform this test over and over */
    stack[IPV4] = opts->ipv4Choice == '*' &&
                  iface->ipv4method == IPV4_MANUAL_METHOD;
    stack[IPV6] = opts->ipv6Choice == '*' &&
                  iface->ipv6method == IPV6_MANUAL_METHOD;

    /* UI WINDOW 2 (optional): manual IP config for non-DHCP installs */
    rows = 2;
    for (i = 0; i < 2; i++) {
        if (stack[i]) {
            rows++;
        }
    }
    egrid = newtCreateGrid(4, rows);

    pos = 0;

    /* IPv4 entry items */
    if (stack[IPV4]) {
        newtGridSetField(egrid, 0, pos, NEWT_GRID_COMPONENT,
                         newtLabel(-1, -1, _("IPv4 address:")),
                         0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        ipcomps->ipv4Entry = newtEntry(-1, -1, NULL, 16, &ipcomps->ipv4, 0);
        ipcomps->cidr4Entry = newtEntry(-1, -1, NULL, 16, &ipcomps->cidr4, 0);

        /* use a nested grid for ipv4 addr & netmask */
        qgrid = newtCreateGrid(3, 1);

        newtGridSetField(qgrid, 0, 0, NEWT_GRID_COMPONENT,
                         ipcomps->ipv4Entry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
        newtGridSetField(qgrid, 1, 0, NEWT_GRID_COMPONENT,
                         newtLabel(-1, -1, _("/")),
                         1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
        newtGridSetField(qgrid, 2, 0, NEWT_GRID_COMPONENT,
                         ipcomps->cidr4Entry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        newtGridSetField(egrid, 1, pos, NEWT_GRID_SUBGRID, qgrid,
                         0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        newtComponentAddCallback(ipcomps->ipv4Entry, ipCallback, ipcomps);
        newtComponentAddCallback(ipcomps->cidr4Entry, cidrCallback, ipcomps);

        /* populate fields if we have data already */
        if (iface_have_in_addr(&iface->ipaddr)) {
            if (inet_ntop(AF_INET, &iface->ipaddr, ret,
                          INET_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        } else if (iface_have_in_addr(&iface->ipaddr)) {
            if (inet_ntop(AF_INET, &iface->ipaddr, ret,
                          INET_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        }

        if (*ret) {
            newtEntrySet(ipcomps->ipv4Entry, ret, 1);
        }

        if (iface_have_in_addr(&iface->netmask)) {
            if (inet_ntop(AF_INET, &iface->netmask, ret,
                          INET_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        } else if (iface_have_in_addr(&iface->netmask)) {
            if (inet_ntop(AF_INET, &iface->netmask, ret,
                          INET_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        }

        if (*ret) {
            newtEntrySet(ipcomps->cidr4Entry, ret, 1);
        }

        pos++;
    }

    /* IPv6 entry items */
    if (stack[IPV6]) {
        newtGridSetField(egrid, 0, pos, NEWT_GRID_COMPONENT,
                         newtLabel(-1, -1, _("IPv6 address:")),
                         0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        ipcomps->ipv6Entry = newtEntry(-1, -1, NULL, 41, &ipcomps->ipv6, 0);
        ipcomps->cidr6Entry = newtEntry(-1, -1, NULL, 4, &ipcomps->cidr6, 0);

        /* use a nested grid for ipv6 addr & netmask */
        rgrid = newtCreateGrid(3, 1);

        newtGridSetField(rgrid, 0, 0, NEWT_GRID_COMPONENT,
                         ipcomps->ipv6Entry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
        newtGridSetField(rgrid, 1, 0, NEWT_GRID_COMPONENT,
                         newtLabel(-1, -1, _("/")),
                         1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
        newtGridSetField(rgrid, 2, 0, NEWT_GRID_COMPONENT,
                         ipcomps->cidr6Entry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        newtGridSetField(egrid, 1, pos, NEWT_GRID_SUBGRID, rgrid,
                         0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

        newtComponentAddCallback(ipcomps->ipv6Entry, ipCallback, ipcomps);
        newtComponentAddCallback(ipcomps->cidr6Entry, cidrCallback, ipcomps);

        /* populate fields if we have data already */
        if (iface_have_in6_addr(&iface->ip6addr)) {
            if (inet_ntop(AF_INET6, &iface->ip6addr, ret,
                          INET6_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        } else if (iface_have_in6_addr(&iface->ip6addr)) {
            if (inet_ntop(AF_INET6, &iface->ip6addr, ret,
                          INET6_ADDRSTRLEN) == NULL) {
                logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                           strerror(errno));
            }
        }

        if (*ret) {
            newtEntrySet(ipcomps->ipv6Entry, ret, 1);
        }

        if (iface->ip6prefix) {
            if (asprintf(&buf, "%d", iface->ip6prefix) == -1) {
                buf = NULL;
            }
        } else if (iface->ip6prefix) {
            if (asprintf(&buf, "%d", iface->ip6prefix) == -1) {
                buf = NULL;
            }
        }

        if (buf != NULL) {
            newtEntrySet(ipcomps->cidr6Entry, buf, 1);
            free(buf);
        }

        pos++;
    }

    /* common entry items */
    ipcomps->gwEntry = newtEntry(-1, -1, NULL, 41, &ipcomps->gw, 0);
    ipcomps->nsEntry = newtEntry(-1, -1, NULL, 41, &ipcomps->ns, 0);

    newtGridSetField(egrid, 0, pos, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Gateway:")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(egrid, 1, pos, NEWT_GRID_COMPONENT,
                     ipcomps->gwEntry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    pos++;

    newtGridSetField(egrid, 0, pos, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Name Server:")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(egrid, 1, pos, NEWT_GRID_COMPONENT,
                     ipcomps->nsEntry, 1, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    if (iface_have_in_addr(&iface->gateway)) {
        if (inet_ntop(AF_INET, &iface->gateway, ret,
                      INET_ADDRSTRLEN) == NULL) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        } else {
            newtEntrySet(ipcomps->gwEntry, ret, 1);
        }
    } else if (iface_have_in6_addr(&iface->gateway6)) {
        if (inet_ntop(AF_INET6, &iface->gateway6, ret,
                      INET6_ADDRSTRLEN) == NULL) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        } else {
            newtEntrySet(ipcomps->gwEntry, ret, 1);
        }
    }

    if (iface->numdns) {
        newtEntrySet(ipcomps->nsEntry, iface->dns[0], 1);
    } else if (iface->numdns) {
        newtEntrySet(ipcomps->nsEntry, iface->dns[0], 1);
    }

    newtComponentAddCallback(ipcomps->gwEntry, ipCallback, ipcomps);
    newtComponentAddCallback(ipcomps->nsEntry, ipCallback, ipcomps);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

    /* main window layout */
    grid = newtCreateGrid(1, 3);

    if (asprintf(&buf,
                 _("Enter the IPv4 and/or the IPv6 address and prefix "
                   "(address / prefix).  For IPv4, the dotted-quad "
                   "netmask or the CIDR-style prefix are acceptable. "
                   "The gateway and name server fields must be valid IPv4 "
                   "or IPv6 addresses.")) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    text = newtTextboxReflowed(-1, -1, buf, 52, 0, 10, 0);

    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
                     0, 0, 0, 1, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, egrid,
                     0, 0, 0, 1, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Manual TCP/IP Configuration"));
    newtGridFree(grid, 1);

    /* run the form */
    while ((have[IPV4] != 2) || (have[IPV6] != 2)) {
        have[IPV4] = 0;
        have[IPV6] = 0;

        for (i = 0; i < 2; i++)
            if (!stack[i]) have[i] = 2;

        answer = newtRunForm(f);

        /* collect IPv4 data */
        if (stack[IPV4]) {
            if (ipcomps->ipv4) {
                if (inet_pton(AF_INET, ipcomps->ipv4, &iface->ipaddr) <= 0) {
                    logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                               strerror(errno));
                } else {
                    have[IPV4]++;
                }
            }

            if (ipcomps->cidr4) {
                if (inet_pton(AF_INET, ipcomps->cidr4, &iface->netmask)>=1) {
                    have[IPV4]++;
                } else {
                    errno = 0;
                    cidr = strtol(ipcomps->cidr4, NULL, 10);

                    if ((errno == ERANGE && (cidr == LONG_MIN ||
                                             cidr == LONG_MAX)) ||
                        (errno != 0 && cidr == 0)) {
                        logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                        abort();
                    }

                    if (cidr >= 1 && cidr <= 32) {
                        tmpaddr = iface_prefix2netmask(cidr);
                        if (tmpaddr != NULL) {
                            memcpy(&iface->netmask, tmpaddr,
                                   sizeof(struct in_addr));
                            have[IPV4]++;
                        } else {
                            iface->netmask.s_addr = 0;
                        }
                    }
                }
            }
        }

        /* collect IPv6 data */
        if (stack[IPV6]) {
            if (ipcomps->ipv6) {
                if (inet_pton(AF_INET6, ipcomps->ipv6, &iface->ip6addr) <= 0) {
                    logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                               strerror(errno));
                } else {
                    have[IPV6]++;
                }
            }

            if (ipcomps->cidr6) {
                errno = 0;
                prefix = strtol(ipcomps->cidr6, NULL, 10);

                if ((errno == ERANGE && (prefix == LONG_MIN ||
                                         prefix == LONG_MAX)) ||
                    (errno != 0 && prefix == 0)) {
                    logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                    abort();
                }

                if (prefix > 0 || prefix <= 128) {
                    iface->ip6prefix = prefix;
                    have[IPV6]++;
                }
            }
        }

        /* collect common network settings */
        if (ipcomps->gw) {
            if (inet_pton(AF_INET, ipcomps->gw, &iface->gateway) <= 0) {
               memset(&iface->gateway, 0, sizeof(iface->gateway));

               if (inet_pton(AF_INET6, ipcomps->gw, &iface->gateway6) <= 0) {
                   logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                              strerror(errno));
                   memset(&iface->gateway6, 0, sizeof(iface->gateway6));
               }
            }
        }

        /* gather nameservers */
        if (ipcomps->ns) {
            if ((inet_pton(AF_INET, ipcomps->ns, &addr) >= 1) ||
                (inet_pton(AF_INET6, ipcomps->ns, &addr6) >= 1)) {
                iface->dns[0] = strdup(ipcomps->ns);
                if (iface->numdns < 1)
                    iface->numdns = 1;
            }
        }

        /* user selected back, but we've saved what they entered already */
        if (answer == back) {
            newtFormDestroy(f);
            newtPopWindow();
            free(buf);
            return LOADER_BACK;
        }

        /* we might be done now */
        if (have[IPV4] != 2) {
            newtWinMessage(_("Missing Information"), _("Retry"),
                           _("You must enter both a valid IPv4 address and a "
                             "network mask or CIDR prefix."));
        }

        if (have[IPV6] != 2) {
            newtWinMessage(_("Missing Information"), _("Retry"),
                           _("You must enter both a valid IPv6 address and a "
                             "CIDR prefix."));
        }

        strcpy(iface->device, device);
        iface->flags &= ~IFACE_FLAGS_IS_DYNAMIC;
    }

    free(buf);
    newtFormDestroy(f);
    newtPopWindow();

    return LOADER_OK;
}

/*
 * By default, we disable all network interfaces and then only
 * bring up the ones the user wants.
 */
int writeDisabledNetInfo(void) {
    int i = 0;
    char *ofile = NULL;
    FILE *fp = NULL;
    struct device **devs = NULL;

    devs = getDevices(DEVICE_NETWORK);

    if (devs == NULL) {
        return 1;
    }

    for (i = 0; devs[i]; i++) {
        if (asprintf(&ofile, "/etc/sysconfig/network-scripts/ifcfg-%s",
                     devs[i]->device) == -1) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
            abort();
        }

        if ((fp = fopen(ofile, "w")) == NULL) {
            free(ofile);
            return 2;
        }

        fprintf(fp, "DEVICE=%s\n", devs[i]->device);
        fprintf(fp, "HWADDR=%s\n", iface_mac2str(devs[i]->device));
        fprintf(fp, "ONBOOT=no\n");
        fprintf(fp, "NM_CONTROLLED=no\n");

        if (ofile) {
            free(ofile);
        }

        if (fclose(fp) == EOF) {
            return 3;
        }
    }

    return 0;
}

/*
 * Write out network interface control files:
 *     /etc/sysconfig/network-scripts/ifcfg-DEVICE
 *     /etc/sysconfig/network
 */
int writeEnabledNetInfo(iface_t *iface) {
    int i = 0;
    FILE *fp = NULL;
    char buf[INET6_ADDRSTRLEN+1];
    char *ofile = NULL;

    memset(&buf, '\0', sizeof(buf));

    if (asprintf(&ofile, "/etc/sysconfig/network-scripts/ifcfg-%s",
                 iface->device) == -1) {
        return 1;
    }

    if ((fp = fopen(ofile, "w")) == NULL) {
        free(ofile);
        return 2;
    }

    fprintf(fp, "DEVICE=%s\n", iface->device);
    fprintf(fp, "HWADDR=%s\n", iface_mac2str(iface->device));
    fprintf(fp, "ONBOOT=yes\n");
    fprintf(fp, "NM_CONTROLLED=yes\n");

    if (!FL_NOIPV4(flags)) {
        if (iface->ipv4method == IPV4_DHCP_METHOD) {
            fprintf(fp, "BOOTPROTO=dhcp\n");
        } else if (iface->ipv4method == IPV4_MANUAL_METHOD) {
            if (iface_have_in_addr(&iface->ipaddr)) {
                if (inet_ntop(AF_INET, &iface->ipaddr, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    return 3;
                }

                fprintf(fp, "IPADDR=%s\n", buf);
            }

            if (iface_have_in_addr(&iface->netmask)) {
                if (inet_ntop(AF_INET, &iface->ipaddr, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    return 4;
                }

                fprintf(fp, "NETMASK=%s\n", buf);
            }

            if (iface_have_in_addr(&iface->broadcast)) {
                if (inet_ntop(AF_INET, &iface->ipaddr, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    return 5;
                }

                fprintf(fp, "BROADCAST=%s\n", buf);
            }

            /* XXX: this should not be here, but ifcfg-fedora
             * in NM does not currently read the global
             * /etc/sysconfig/network file.
             */
            if (iface_have_in_addr(&iface->gateway)) {
                if (inet_ntop(AF_INET, &iface->gateway, buf,
                              INET_ADDRSTRLEN) == NULL) {
                   free(ofile);
                   return 6;
                }

                fprintf(fp, "GATEWAY=%s\n", buf);
            }
        }
    }

    if (!FL_NOIPV6(flags)) {
        if (iface->ipv6method == IPV6_AUTO_METHOD ||
            iface->ipv6method == IPV6_DHCP_METHOD ||
            iface->ipv6method == IPV6_MANUAL_METHOD) {
            fprintf(fp, "IPV6INIT=yes\n");

            if (iface->ipv6method == IPV6_AUTO_METHOD) {
                fprintf(fp, "IPV6_AUTOCONF=yes\n");
            } else if (iface->ipv6method == IPV6_DHCP_METHOD) {
                fprintf(fp, "DHCPV6C=yes\n");
            } else if (iface->ipv6method == IPV6_MANUAL_METHOD) {
                if (iface_have_in6_addr(&iface->ip6addr)) {
                    if (inet_ntop(AF_INET6, &iface->ip6addr, buf,
                                  INET6_ADDRSTRLEN) == NULL) {
                        free(ofile);
                        return 7;
                    }

                    if (iface->ip6prefix) {
                        fprintf(fp, "IPV6ADDR=%s/%d\n", buf, iface->ip6prefix);
                    } else {
                        fprintf(fp, "IPV6ADDR=%s\n", buf);
                    }
                }
            }
        }
    }

    if (iface->numdns > 0) {
        for (i = 0; i < iface->numdns; i++) {
            fprintf(fp, "DNS%d=%s\n", i+1, iface->dns[i]);
        }
    }

    if (iface->hostname) {
        fprintf(fp, "HOSTNAME=%s\n", iface->hostname);
    }

    if (iface->domain) {
        fprintf(fp, "DOMAIN=%s\n", iface->domain);
    }

    if (iface->mtu) {
        fprintf(fp, "MTU=%d\n", iface->mtu);
    }

    if (iface->peerid) {
        fprintf(fp, "PEERID=%s\n", iface->peerid);
    }

    if (iface->subchannels) {
        fprintf(fp, "SUBCHANNELS=%s\n", iface->subchannels);
    }

    if (iface->portname) {
        fprintf(fp, "PORTNAME=%s\n", iface->portname);
    }

    if (iface->nettype) {
        fprintf(fp, "NETTYPE=%s\n", iface->nettype);
    }

    if (iface->ctcprot) {
        fprintf(fp, "CTCPROT=%s\n", iface->ctcprot);
    }

    if (ofile) {
        free(ofile);
    }

    if (fclose(fp) == EOF) {
        return 8;
    }

    /* Global settings */
    if ((fp = fopen("/etc/sysconfig/network", "w")) == NULL) {
        return 9;
    }

    if (!FL_NOIPV4(flags)) {
        fprintf(fp, "NETWORKING=yes\n");
    }

    if (!FL_NOIPV6(flags)) {
        fprintf(fp, "NETWORKING_IPV6=yes\n");
    }

    if (iface->hostname != NULL) {
        fprintf(fp, "HOSTNAME=%s\n", iface->hostname);
    }

    if (iface_have_in_addr(&iface->gateway)) {
        if (inet_ntop(AF_INET, &iface->gateway, buf,
                      INET_ADDRSTRLEN) == NULL) {
            return 10;
        }

        fprintf(fp, "GATEWAY=%s\n", buf);
    }

    if (iface_have_in6_addr(&iface->gateway6)) {
        if (inet_ntop(AF_INET6, &iface->gateway6, buf,
                      INET6_ADDRSTRLEN) == NULL) {
            return 11;
        }

        fprintf(fp, "IPV6_DEFAULTGW=%s\n", buf);
    }

    if (fclose(fp) == EOF) {
        return 12;
    }

    return 0;
}

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv) {
    char * arg, * bootProto = NULL, * device = NULL, *ethtool = NULL, * class = NULL;
    char * essid = NULL, * wepkey = NULL, * onboot = NULL;
    int mtu = 1500, noipv4 = 0, noipv6 = 0, dhcpTimeout = -1, noDns = 0, noksdev = 0;
    int rc;
    poptContext optCon;
    iface_t iface;

    struct poptOption ksOptions[] = {
        { "bootproto", '\0', POPT_ARG_STRING, &bootProto, 0, NULL, NULL },
        { "device", '\0', POPT_ARG_STRING, &device, 0, NULL, NULL },
        { "dhcpclass", '\0', POPT_ARG_STRING, &class, 0, NULL, NULL },
        { "gateway", '\0', POPT_ARG_STRING, NULL, 'g', NULL, NULL },
        { "ip", '\0', POPT_ARG_STRING, NULL, 'i', NULL, NULL },
        { "mtu", '\0', POPT_ARG_INT, &mtu, 0, NULL, NULL },
        { "nameserver", '\0', POPT_ARG_STRING, NULL, 'n', NULL, NULL },
        { "netmask", '\0', POPT_ARG_STRING, NULL, 'm', NULL, NULL },
        { "noipv4", '\0', POPT_ARG_NONE, &noipv4, 0, NULL, NULL },
        { "noipv6", '\0', POPT_ARG_NONE, &noipv6, 0, NULL, NULL },
        { "nodns", '\0', POPT_ARG_NONE, &noDns, 0, NULL, NULL },
        { "hostname", '\0', POPT_ARG_STRING, NULL, 'h', NULL, NULL},
        { "ethtool", '\0', POPT_ARG_STRING, &ethtool, 0, NULL, NULL },
        { "essid", '\0', POPT_ARG_STRING, &essid, 0, NULL, NULL },
        { "wepkey", '\0', POPT_ARG_STRING, &wepkey, 0, NULL, NULL },
        { "onboot", '\0', POPT_ARG_STRING, &onboot, 0, NULL, NULL },
        { "notksdevice", '\0', POPT_ARG_NONE, &noksdev, 0, NULL, NULL },
        { "dhcptimeout", '\0', POPT_ARG_INT, &dhcpTimeout, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    iface_init_iface_t(&iface);

    optCon = poptGetContext(NULL, argc, (const char **) argv, 
                            ksOptions, 0);    
    while ((rc = poptGetNextOpt(optCon)) >= 0) {
        arg = (char *) poptGetOptArg(optCon);

        switch (rc) {
        case 'g':
            loaderData->gateway = strdup(arg);
            break;
        case 'i':
            loaderData->ipv4 = strdup(arg);
            break;
        case 'n':
            loaderData->dns = strdup(arg);
            break;
        case 'm':
            loaderData->netmask = strdup(arg);
            break;
        case 'h':
            if (loaderData->hostname) 
                free(loaderData->hostname);
            loaderData->hostname = strdup(arg);
            break;
        }
    }

    if (rc < -1) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to kickstart network command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
    } else {
        poptFreeContext(optCon);
    }

    /* if they've specified dhcp/bootp or haven't specified anything, 
     * use dhcp for the interface */
    if ((bootProto && (!strncmp(bootProto, "dhcp", 4) || 
                       !strncmp(bootProto, "bootp", 4))) ||
        (!bootProto && !loaderData->ipv4)) {
        loaderData->ipv4 = strdup("dhcp");
        loaderData->ipinfo_set = 1;
    } else if (loaderData->ipv4) {
        /* JKFIXME: this assumes a bit... */
        loaderData->ipinfo_set = 1;
    }

    /* now make sure the specified bootproto is valid */
    if (bootProto && strcmp(bootProto, "dhcp") && strcmp(bootProto, "bootp") &&
        strcmp(bootProto, "static") && strcmp(bootProto, "query")) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad bootproto %s specified in network command"),
                       bootProto);
    }

    if (!noksdev) {
        if (device) {
            loaderData->netDev = strdup(device);
            loaderData->netDev_set = 1;
        }

        if (class) {
            loaderData->netCls = strdup(class);
            loaderData->netCls_set = 1;
        }

        if (ethtool) {
            if (loaderData->ethtool)
                free(loaderData->ethtool);
            loaderData->ethtool = strdup(ethtool);
            free(ethtool);
        }

        if (essid) {
            if (loaderData->essid)
                free(loaderData->essid);
            loaderData->essid = strdup(essid);
            free(essid);
        }

        if (wepkey) {
            if (loaderData->wepkey)
                free(loaderData->wepkey);
            loaderData->wepkey = strdup(wepkey);
            free(wepkey);
        }

        if (mtu) {
           loaderData->mtu = mtu;
        }

        if (noipv4)
            flags |= LOADER_FLAGS_NOIPV4;

        if (noipv6)
            flags |= LOADER_FLAGS_NOIPV6;
    }

    if (noDns) {
        loaderData->noDns = 1;
    }

    /* Make sure the network is always up if there's a network line in the
     * kickstart file, as %post/%pre scripts might require that.
     */
    if (loaderData->method != METHOD_NFS && loaderData->method != METHOD_URL) {
        if (kickstartNetworkUp(loaderData, &iface))
            logMessage(ERROR, "unable to bring up network");
    }
}

/* if multiple interfaces get one to use from user.   */
/* NOTE - uses kickstart data available in loaderData */
int chooseNetworkInterface(struct loaderData_s * loaderData) {
    int i, rc, ask, idrc, secs, deviceNums = 0, deviceNum, foundDev = 0;
    unsigned int max = 40;
    char **devices;
    char **deviceNames;
    char *ksMacAddr = NULL, *seconds = strdup("10"), *idstr = NULL;
    struct device **devs;
    struct newtWinEntry entry[] = {{N_("Seconds:"), (char **) &seconds, 0},
                                   {NULL, NULL, 0 }};

    devs = getDevices(DEVICE_NETWORK);
    if (!devs) {
        logMessage(ERROR, "no network devices in choose network device!");
        return LOADER_ERROR;
    }

    for (i = 0; devs[i]; i++);

    devices = alloca((i + 1) * sizeof(*devices));
    deviceNames = alloca((i + 1) * sizeof(*devices));
    if (loaderData->netDev && (loaderData->netDev_set) == 1) {
        if ((loaderData->bootIf && (loaderData->bootIf_set) == 1) && !strcasecmp(loaderData->netDev, "bootif")) {
            ksMacAddr = strdup(loaderData->bootIf);
        } else {
            ksMacAddr = strdup(loaderData->netDev);
        }

        ksMacAddr = str2upper(ksMacAddr);
    }

    for (i = 0; devs[i]; i++) {
        if (!devs[i]->device)
            continue;

        if (devs[i]->description) {
                deviceNames[deviceNums] = alloca(strlen(devs[i]->device) +
                                          strlen(devs[i]->description) + 4);
                sprintf(deviceNames[deviceNums],"%s - %s",
                        devs[i]->device, devs[i]->description);
                if (strlen(deviceNames[deviceNums]) > max)
                        max = strlen(deviceNames[deviceNums]);
                devices[deviceNums] = devs[i]->device;
        } else {
            devices[deviceNums] = devs[i]->device;
            deviceNames[deviceNums] = devs[i]->device;
        }

        deviceNums++;

        /* this device has been set and we don't really need to ask 
         * about it again... */
        if (loaderData->netDev && (loaderData->netDev_set == 1)) {
            if (!strcmp(loaderData->netDev, devs[i]->device)) {
                foundDev = 1;
            } else if (ksMacAddr != NULL) {
                /* maybe it's a mac address */
                char *devmacaddr = NULL;
                devmacaddr = iface_mac2str(devs[i]->device);
                if ((devmacaddr != NULL) && !strcmp(ksMacAddr, devmacaddr)) {
                    foundDev = 1;
                    free(loaderData->netDev);
                    loaderData->netDev = devs[i]->device;
                    if (devmacaddr != NULL)
                        free(devmacaddr);
                    break;
                }

                if (devmacaddr != NULL)
                    free(devmacaddr);
            }
        }
    }
    if (ksMacAddr)
        free(ksMacAddr);
    if (foundDev == 1)
        return LOADER_NOOP;

    devices[deviceNums] = NULL;
    deviceNames[deviceNums] = NULL;
    qsort(devices, deviceNums, sizeof(*devices), simpleStringCmp);
    qsort(deviceNames, deviceNums, sizeof(*devices), simpleStringCmp);

    /* ASSERT: we should *ALWAYS* have a network device when we get here */
    if (!deviceNums) {
        logMessage(CRITICAL, "no network device in chooseNetworkInterface");
        return LOADER_ERROR;
    }

    /* JKFIXME: if we only have one interface and it doesn't have link,
     * do we go ahead? */
    if (deviceNums == 1) {
        logMessage(INFO, "only have one network device: %s", devices[0]);
        loaderData->netDev = devices[0];
        return LOADER_NOOP;
    }

    if ((loaderData->netDev && (loaderData->netDev_set == 1)) &&
        !strcmp(loaderData->netDev, "link")) {
        logMessage(INFO, "looking for first netDev with link");
        for (rc = 0; rc < 5; rc++) {
            for (i = 0; i < deviceNums; i++) {
                if (get_link_status(devices[i]) == 1) {
                    loaderData->netDev = devices[i];
                    logMessage(INFO, "%s has link, using it", devices[i]);
                    return LOADER_NOOP;
                }
            }
            sleep(1);
        }
        logMessage(WARNING, "wanted netdev with link, but none present.  prompting");
    }

    startNewt();

    if (max > 70)
        max = 70;

    /* JKFIXME: should display link status */
    deviceNum = 0;
    ask = 1;
    while (ask) {
        rc = newtWinMenu(_("Networking Device"),
                         _("You have multiple network devices on this system. "
                           "Which would you like to install through?"),
                         max, 10, 10,
                         deviceNums < 6 ? deviceNums : 6, deviceNames,
                         &deviceNum, _("OK"), _("Identify"), _("Back"), NULL);

        if (rc == 2) {
            if (!devices[deviceNum]) {
                logMessage(ERROR, "NIC %d contains no device name", deviceNum);
                continue;
            }

            if (asprintf(&idstr, "%s %s %s",
                         _("You can identify the physical port for"),
                         devices[deviceNum],
                         _("by flashing the LED lights for a number of "
                           "seconds.  Enter a number between 1 and 30 to "
                           "set the duration to flash the LED port "
                           "lights.")) == -1) {
                logMessage(ERROR, "asprintf() failure in %s: %m", __func__);
                abort();
            }

            i = 1;
            while (i) {
                idrc = newtWinEntries(_("Identify NIC"), idstr, 50, 5, 15, 24,
                                      entry, _("OK"), _("Back"), NULL);

                if (idrc == 0 || idrc == 1) {
                    errno = 0;
                    secs = strtol((const char *) seconds, NULL, 10);
                    if (errno == EINVAL || errno == ERANGE) {
                        logMessage(ERROR, "strtol() failure in %s: %m",
                                   __func__);
                        continue;
                    }

                    if (secs <=0 || secs > 30) {
                        newtWinMessage(_("Invalid Duration"), _("OK"),
                                       _("You must enter the number of "
                                         "seconds as an integer between 1 "
                                         "and 30."));
                        continue;
                    }

                    idrc = 41 + strlen(devices[deviceNum]);
                    if (secs > 9) {
                        idrc += 1;
                    }

                    winStatus(idrc, 3, NULL,
                              _("Flashing %s port lights for %d seconds..."),
                              devices[deviceNum], secs);

                    if (identifyNIC(devices[deviceNum], secs)) {
                        logMessage(ERROR,
                                   "error during physical NIC identification");
                    }

                    newtPopWindow();
                    i = 0;
                } else if (idrc == 2) {
                    i = 0;
                }
            }
        } else if (rc == 3) {
            ask = 0;
            return LOADER_BACK;
        } else {
            ask = 0;
        }
    }

    loaderData->netDev = devices[deviceNum];
    return LOADER_OK;
}

/* JKFIXME: bad name.  this function brings up networking early on a 
 * kickstart install so that we can do things like grab the ks.cfg from
 * the network */
int kickstartNetworkUp(struct loaderData_s * loaderData, iface_t * iface) {
    int rc;

    /* we may have networking already, so return to the caller */
    if ((loaderData->ipinfo_set == 1) || (loaderData->ipv6info_set == 1))
        return 0;

    memset(iface, 0, sizeof(*iface));

    do {
        do {
            /* this is smart and does the right thing based on whether or not
             * we have ksdevice= specified */
            rc = chooseNetworkInterface(loaderData);

            if (rc == LOADER_ERROR) {
                /* JKFIXME: ask for a driver disk? */
                logMessage(ERROR, "no network drivers for doing kickstart");
                return -1;
            } else if (rc == LOADER_BACK) {
                return -1;
            }

            /* insert device into iface structure */
            strcpy(iface->device, loaderData->netDev);

            break;
        } while (1);

        /* we don't want to end up asking about interface more than once
         * if we're in a kickstart-ish case (#100724) */
        loaderData->netDev_set = 1;

        /* JKFIXME: this is kind of crufty, we depend on the fact that the
         * ip is set and then just get the network up.  we should probably
         * add a way to do asking about static here and not be such a hack */
        if (!loaderData->ipv4) {
            loaderData->ipv4 = strdup("dhcp");
        } 
        loaderData->ipinfo_set = 1;

        setupNetworkDeviceConfig(iface, loaderData);

        rc = readNetConfig(loaderData->netDev, iface, loaderData->netCls,
                           loaderData->method);

        if (rc == LOADER_ERROR) {
            logMessage(ERROR, "unable to setup networking");
            return -1;
        }
        else if (rc == LOADER_BACK) {
            /* Going back to the interface selection screen, so unset anything
             * we set before attempting to bring the incorrect interface up.
             */
            loaderData->netDev_set = 0;
            free(loaderData->ipv4);
            loaderData->ipinfo_set = 0;
        }
        else
            break;
    } while (1);

    return 0;
}

void splitHostname (char *str, char **host, char **port)
{
    char *rightbrack = strchr(str, ']');

    *host = NULL;
    *port = NULL;

    if (*str == '[' && rightbrack) {
        /* An IPv6 address surrounded by brackets, optionally with a colon and
         * port number.
         */
        char *colon = strrchr(rightbrack, ':');

        if (colon) {
            *host = strndup(str+1, rightbrack-1-str);
            *port = strdup(colon+1);
        }
        else
            *host = strndup(str+1, rightbrack-1-str);
    } else if (strcount(str, ':') > 1) {
        /* An IPv6 address without brackets.  Don't make the user surround the
         * address with brackets if there's no port number.
         */
        *host = strdup(str);
    } else {
        /* An IPv4 address, optionally with a colon and port number. */
        char *colon = strrchr(str, ':');

        if (colon) {
            *host = strndup(str, colon-str);
            *port = strdup(colon+1);
        }
        else
            *host = strdup(str);
    }
}

/*
 * Start NetworkManager and wait for a valid link, return non-zero on error.
 */
int get_connection(iface_t *iface) {
    int count = 0;
    DBusConnection *connection = NULL;
    DBusMessage *message = NULL;
    DBusMessage *reply = NULL;
    DBusError error;
    DBusMessageIter iter, variant_iter;
    dbus_uint32_t state = 0;
    char *nm_iface = "org.freedesktop.NetworkManager";
    char *property = "State";

    if (iface == NULL) {
        return 1;
    }

    logMessage(DEBUGLVL, "configuring device %s", iface->device);

    /* display status */
    if (FL_CMDLINE(flags)) {
        printf(_("Waiting for NetworkManager to configure %s...\n"),
               iface->device);
    } else {
        winStatus(55, 3, NULL,
                  _("Waiting for NetworkManager to configure %s...\n"),
                  iface->device, 0);
    }

    dbus_error_init(&error);
    connection = dbus_bus_get(DBUS_BUS_SYSTEM, &error);
    if (connection == NULL) {
        if (dbus_error_is_set(&error)) {
            logMessage(DEBUGLVL, "%s (%d): %s: %s", __func__,
                       __LINE__, error.name, error.message);
            dbus_error_free(&error);
        }

        return 2;
    }

    dbus_error_init(&error);
    message = dbus_message_new_method_call(NM_DBUS_SERVICE,
                                           NM_DBUS_PATH,
                                           "org.freedesktop.DBus.Properties",
                                           "Get");
    if (!message) {
        if (dbus_error_is_set(&error)) {
            logMessage(DEBUGLVL, "%s (%d): %s: %s", __func__,
                       __LINE__, error.name, error.message);
            dbus_error_free(&error);
        }

        return 4;
    }

    dbus_error_init(&error);
    if (!dbus_message_append_args(message,
                                  DBUS_TYPE_STRING, &nm_iface,
                                  DBUS_TYPE_STRING, &property,
                                  DBUS_TYPE_INVALID)) {
        if (dbus_error_is_set(&error)) {
            logMessage(DEBUGLVL, "%s (%d): %s: %s", __func__,
                       __LINE__, error.name, error.message);
            dbus_error_free(&error);
        }

        dbus_message_unref(message);
        return 5;
    }

    /* send message and block until a reply or error comes back */
    while (count < 45) {
        dbus_error_init(&error);
        reply = dbus_connection_send_with_reply_and_block(connection,
                                                          message, -1,
                                                          &error);
        if (!reply) {
            if (dbus_error_is_set(&error)) {
                logMessage(DEBUGLVL, "%s (%d): %s: %s", __func__,
                           __LINE__, error.name, error.message);
                dbus_error_free(&error);
            }

            dbus_message_unref(message);
            return 6;
        }

        /* extra uint32 'state' property from the returned variant type */
        dbus_message_iter_init(reply, &iter);
        if (dbus_message_iter_get_arg_type(&iter) != DBUS_TYPE_VARIANT) {
            logMessage(DEBUGLVL, "%s (%d): unexpected reply format",
                       __func__, __LINE__);
            dbus_message_unref(message);
            dbus_message_unref(reply);
            return 7;
        }

        /* open the variant */
        dbus_message_iter_recurse(&iter, &variant_iter);
        if (dbus_message_iter_get_arg_type(&variant_iter) != DBUS_TYPE_UINT32) {
            logMessage(DEBUGLVL, "%s (%d): unexpected reply format",
                       __func__, __LINE__);
            dbus_message_unref(message);
            dbus_message_unref(reply);
            return 8;
        }

        dbus_message_iter_get_basic(&variant_iter, &state);
        if (state == NM_STATE_CONNECTED) {
            logMessage(DEBUGLVL, "%s (%d): NetworkManager connected",
                       __func__, __LINE__);
            dbus_message_unref(message);
            dbus_message_unref(reply);
            return 0;
        }

        sleep(1);
        count++;
    }

    if (message) {
        dbus_message_unref(message);
    }

    if (reply) {
        dbus_message_unref(reply);
    }

    return 9;
}

/* vim:set shiftwidth=4 softtabstop=4: */
