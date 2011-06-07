/*
 * net.c
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005  Red Hat, Inc.
 *               2006, 2007, 2008, 2009
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
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/utsname.h>
#include <arpa/inet.h>
#include <errno.h>
#include <resolv.h>
#include <net/if.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#include <glib.h>
#include <NetworkManager.h>
#include <nm-client.h>
#include <nm-device-wifi.h>

#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/ethtool.h"
#include "../pyanaconda/isys/iface.h"
#include "../pyanaconda/isys/log.h"

#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "method.h"
#include "net.h"
#include "windows.h"
#include "ibft.h"

#include <nm-device.h>
#include <nm-setting-connection.h>
#include <nm-setting-wireless.h>
#include <nm-setting-ip4-config.h>
#include <nm-utils.h>
#include <dbus/dbus.h>
#include <dbus/dbus-glib.h>

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

    if (co == data->cidr4Entry) {
        if (data->cidr4 == NULL && data->ipv4 == NULL)
            return;

        if (isValidIPv4Address(data->cidr4))
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
#ifdef ENABLE_IPV6
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
#endif
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
#ifdef ENABLE_IPV6
    } else if (co == data->ipv6Entry) {
        /* users must provide a mask, we can't guess for ipv6 */
        return;
#endif
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

#ifdef ENABLE_IPV6
static void v6MethodCallback(newtComponent co, void *dptr) {
    setMethodSensitivity(dptr, 3);
    return;
}
#endif

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
void setupIfaceStruct(iface_t * iface, struct loaderData_s * loaderData) {
    struct in_addr addr;
    struct in6_addr addr6;
    char * c;

    memset(&addr, 0, sizeof(addr));
    memset(&addr6, 0, sizeof(addr6));

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->netCls_set) {
        iface->vendorclass = loaderData->netCls;
    } else {
        iface->vendorclass = NULL;
    }

    if (loaderData->ipinfo_set && loaderData->ipv4 != NULL) {
	/* this is iBFT configured device */
	if (!strncmp(loaderData->ipv4, "ibft", 4)) {
	    iface->ipv4method = IPV4_IBFT_METHOD;
        /* this is how we specify dhcp */
        } else if (!strncmp(loaderData->ipv4, "dhcp", 4)) {
            iface->dhcptimeout = loaderData->dhcpTimeout;
            iface->ipv4method = IPV4_DHCP_METHOD;
        } else if (inet_pton(AF_INET, loaderData->ipv4, &addr) >= 1) {
            iface->ipaddr.s_addr = addr.s_addr;
            iface->ipv4method = IPV4_MANUAL_METHOD;
        } else { /* invalid ip information, disable the setting of ip info */
            loaderData->ipinfo_set = 0;
            iface->ipv4method = 0;
            loaderData->ipv4 = NULL;
        }
     }

    if (loaderData->netmask != NULL) {
        if (inet_pton(AF_INET, loaderData->netmask, &iface->netmask) <= 0) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }

    if (loaderData->gateway != NULL) {
        if (inet_pton(AF_INET, loaderData->gateway, &iface->gateway) <= 0) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }

#ifdef ENABLE_IPV6
    if (loaderData->ipv6info_set && loaderData->ipv6 != NULL) {
        if (!strncmp(loaderData->ipv6, "dhcp", 4)) {
            iface->ipv6method = IPV6_DHCP_METHOD;
        } else if (!strncmp(loaderData->ipv6, "auto", 4)) {
            iface->ipv6method = IPV6_AUTO_METHOD;
        } else if (inet_pton(AF_INET6, loaderData->ipv6, &addr6) >= 1) {
            memcpy(&iface->ip6addr, &addr6, sizeof(struct in6_addr));
            iface->ipv6method = IPV6_MANUAL_METHOD;

            iface->ip6prefix = 0;
            if (loaderData->ipv6prefix) {
                int prefix;

                errno = 0;
                prefix = strtol(loaderData->ipv6prefix, NULL, 10);
                if ((errno == ERANGE && (prefix == LONG_MIN ||
                                         prefix == LONG_MAX)) ||
                    (errno != 0 && prefix == 0)) {
                    logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                    abort();
                }

                if (prefix > 0 || prefix <= 128) {
                    iface->ip6prefix = prefix;
                }
            }
        } else {
            iface->ipv6method = 0;
            loaderData->ipv6info_set = 0;
            loaderData->ipv6 = NULL;
        }
    }

    if (loaderData->gateway6 != NULL) {
        if (inet_pton(AF_INET6, loaderData->gateway6, &iface->gateway6) <= 0) {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }
#endif

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

    if (loaderData->domain) {
        logMessage(INFO, "dnsdomains is %s", loaderData->domain);
        iface->domain = strdup(loaderData->domain);
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

    if (loaderData->options) {
        iface->options = strdup(loaderData->options);
    }

    if (loaderData->wepkey) {
        if (is_wireless_device(loaderData->netDev)) {
            iface->wepkey = strdup(loaderData->wepkey);
        } else {
            iface->wepkey = NULL;
        }
    }

    if (loaderData->essid) {
        if (is_wireless_device(loaderData->netDev)) {
            iface->ssid = strdup(loaderData->essid);
        } else {
            iface->ssid = NULL;
        }
    }

    if (loaderData->noDns) {
        iface->flags |= IFACE_FLAGS_NO_WRITE_RESOLV_CONF;
    }

    iface->dhcptimeout = loaderData->dhcpTimeout;

    if (loaderData->macaddr) {
        iface->macaddr = strdup(loaderData->macaddr);
    }

    return;
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
    ipcomps.cidr4 = NULL;
    ipcomps.gw = NULL;
#ifdef ENABLE_IPV6
    ipcomps.ipv6 = NULL;
    ipcomps.cidr6 = NULL;
    ipcomps.gw6 = NULL;
#endif
    ipcomps.ns = NULL;

    /* init opts */
    opts.ipv4Choice = 0;
    opts.v4Method = 0;
#ifdef ENABLE_IPV6
    opts.ipv6Choice = 0;
    opts.v6Method = 0;
#endif

    /* JKFIXME: we really need a way to override this and be able to change
     * our network config */
    if (!FL_ASKNETWORK(flags) &&
        ((iface->ipv4method > IPV4_UNUSED_METHOD) ||
         (iface->ipv6method > IPV4_UNUSED_METHOD))) {
        logMessage(INFO, "doing kickstart... setting it up");

        err = writeEnabledNetInfo(iface);
        if (err) {
            logMessage(ERROR, "failed to write %s data for %s (%d)",
                       SYSCONFIG_PATH, iface->device, err);
            return LOADER_BACK;
        }

        i = wait_for_iface_activation(iface->device);
        newtPopWindow();

        if (i > 0) {
            if (FL_CMDLINE(flags)) {
                fprintf(stderr, _("There was an error configuring your network "
                                  "interface."));
                fprintf(stderr, _("\nThis cannot be corrected in cmdline mode.\n"
                                  "Halting.\n"));
                exit(1);
            }

            newtWinMessage(_("Network Error"), _("Retry"),
                           _("There was an error configuring your network "
                             "interface."));
            /* Clear out ip selections to allow for re-entry */
            iface->ipv4method = IPV4_UNUSED_METHOD;
            iface->ipv6method = IPV6_UNUSED_METHOD;
            return LOADER_ERROR;
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
    err = writeEnabledNetInfo(iface);
    if (err) {
        logMessage(ERROR, "failed to write %s data for %s (%d)",
                   SYSCONFIG_PATH, iface->device, err);
        iface->ipv4method = IPV4_UNUSED_METHOD;
        iface->ipv6method = IPV6_UNUSED_METHOD;
        return LOADER_BACK;
    }

    i = wait_for_iface_activation(iface->device);
    newtPopWindow();

    if (i > 0) {
        newtWinMessage(_("Network Error"), _("Retry"),
                       _("There was an error configuring your network "
                         "interface."));
        /* Clear out selections to allow for re-entry */
        iface->ipv4method = IPV4_UNUSED_METHOD;
        iface->ipv6method = IPV6_UNUSED_METHOD;
        return LOADER_ERROR;
    }

    return LOADER_OK;
}

int configureTCPIP(char * device, iface_t * iface,
                   struct netconfopts * opts, int methodNum) {
    int i = 0, z = 0, skipForm = 0, ret;
    newtComponent f, okay, back, answer;
    newtComponent ipv4Checkbox, v4Method[2];
#ifdef ENABLE_IPV6
    newtComponent ipv6Checkbox, v6Method[3];
#endif
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
    v4Method[0] = newtRadiobutton(-1, -1, DHCP_METHOD_STR, (opts->v4Method == 0), NULL);
    v4Method[1] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, (opts->v4Method == 1), v4Method[0]);

#ifdef ENABLE_IPV6
    /* IPv6 checkbox */
    if (!opts->ipv6Choice) {
        if (FL_NOIPV6(flags) && !FL_IPV6_PARAM(flags))
            opts->ipv6Choice = ' ';
        else
            opts->ipv6Choice = '*';
    }

    ipv6Checkbox = newtCheckbox(-1, -1, _("Enable IPv6 support"),
                                opts->ipv6Choice, NULL, &(opts->ipv6Choice));
    v6Method[0] = newtRadiobutton(-1, -1, AUTO_METHOD_STR, (opts->v6Method == 0), NULL);
    v6Method[1] = newtRadiobutton(-1, -1, DHCPV6_METHOD_STR, (opts->v6Method == 1), v6Method[0]);
    v6Method[2] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, (opts->v6Method == 2), v6Method[1]);
#endif

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

    /* checkgrid contains the toggle options for net configuration */
#ifdef ENABLE_IPV6
    checkgrid = newtCreateGrid(1, 8);
#else
    checkgrid = newtCreateGrid(1, 3);
#endif

    newtGridSetField(checkgrid, 0, 0, NEWT_GRID_COMPONENT, ipv4Checkbox,
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    for (i = 1; i < 3; i++)
        newtGridSetField(checkgrid, 0, i, NEWT_GRID_COMPONENT, v4Method[i-1],
                         7, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

#ifdef ENABLE_IPV6
    newtGridSetField(checkgrid, 0, 4, NEWT_GRID_COMPONENT, ipv6Checkbox,
                     0, 1, 0, 0, NEWT_ANCHOR_LEFT, 0);
    for (i = 5; i < 8; i++)
        newtGridSetField(checkgrid, 0, i, NEWT_GRID_COMPONENT, v6Method[i-5],
                         7, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
#endif

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
#ifdef ENABLE_IPV6
    newtComponentAddCallback(ipv6Checkbox, v6MethodCallback, &v6Method);
#endif

    /* match radio button sensitivity to initial checkbox choices */
    if (opts->ipv4Choice == ' ')
        setMethodSensitivity(&v4Method, 2);

#ifdef ENABLE_IPV6
    if (opts->ipv6Choice == ' ')
        setMethodSensitivity(&v6Method, 3);
#endif

#ifdef ENABLE_IPV6
    /* If the user provided any of the following boot paramters, skip
     * prompting for network configuration information:
     *     ip=<val> ipv6=<val>
     *     noipv4 noipv6
     *     ip=<val> noipv6
     *     ipv6=<val> noipv4
     */
    if ((iface->ipv4method > IPV4_UNUSED_METHOD && iface->ipv6method > IPV6_UNUSED_METHOD) || /* both */
        (iface->ipv4method > IPV4_UNUSED_METHOD && FL_NOIPV6(flags)) || /* only ipv4 */
        (FL_NOIPV4(flags) && iface->ipv6method > IPV6_UNUSED_METHOD) || /* only ipv6 */
        (FL_NOIPV4(flags) && FL_NOIPV6(flags))) { /* neither ipv4 or ipv6 -- what else? */
        skipForm = 1;
        newtPopWindow();
        logMessage(DEBUGLVL, "in configureTCPIP(), detected network boot args, skipping form");
    }
#else
    if (iface->ipv4method > IPV4_UNUSED_METHOD || FL_NOIPV4(flags)) {
        skipForm = 1;
        newtPopWindow();
        logMessage(DEBUGLVL, "in configureTCPIP(), detected network boot args, skipping form");
    }
#endif

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
#ifdef ENABLE_IPV6
            if (opts->ipv4Choice == ' ' && opts->ipv6Choice == ' ') {
#else
            if (opts->ipv4Choice == ' ') {
#endif
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

#ifdef ENABLE_IPV6
        if (opts->ipv6Choice == '*') {
            flags &= ~LOADER_FLAGS_NOIPV6;
            for (z = IPV6_FIRST_METHOD; z <= IPV6_LAST_METHOD; z++)
                if (newtRadioGetCurrent(v6Method[0]) == v6Method[z-1])
                    iface->ipv6method = z;
        } else {
            flags |= LOADER_FLAGS_NOIPV6;
        }
#endif

        /* update opts keeping method choice for UI */
        for (z = IPV4_FIRST_METHOD; z <= IPV4_LAST_METHOD; z++) {
            if (newtRadioGetCurrent(v4Method[0]) == v4Method[z-1])
                opts->v4Method = z-1;
        }
#ifdef ENABLE_IPV6
        for (z = IPV6_FIRST_METHOD; z <= IPV6_LAST_METHOD; z++) {
            if (newtRadioGetCurrent(v6Method[0]) == v6Method[z-1])
                opts->v6Method = z-1;
        }
#endif

        /* do interface configuration (call DHCP here, or return for manual) */
#ifdef ENABLE_IPV6
        if ((!FL_NOIPV4(flags) && iface->ipv4method == IPV4_MANUAL_METHOD) ||
            (!FL_NOIPV6(flags) && iface->ipv6method == IPV6_MANUAL_METHOD)) {
#else
        if (!FL_NOIPV4(flags) && iface->ipv4method == IPV4_MANUAL_METHOD) {
#endif
            /* manual IP configuration selected */
            ret = LOADER_OK;
            i = 1;
#ifdef ENABLE_IPV6
        } else if (!FL_NOIPV4(flags) || !FL_NOIPV6(flags)) {
#else
        } else if (!FL_NOIPV4(flags)) {
#endif
            /* only auto configuration selected, exit the loop */
            ret = LOADER_NOOP;
            i = 1;
        }
    } while (i != 1);

    newtFormDestroy(f);
    newtPopWindow();
    return ret;
}

int manualNetConfig(char * device, iface_t * iface,
                    struct intfconfig_s * ipcomps, struct netconfopts * opts) {
    int i, rows, pos, cidr, have[2], stack[2];
    char *buf = NULL;
    char ret[48];
#ifdef ENABLE_IPV6
    int prefix;
#endif
    struct in_addr *tmpaddr = NULL;
    newtComponent f, okay, back, answer;
    newtGrid egrid = NULL;
    newtGrid qgrid = NULL;
#ifdef ENABLE_IPV6
    newtGrid rgrid = NULL;
#endif
    newtGrid buttons, grid;
    newtComponent text = NULL;

    memset(ret, '\0', INET6_ADDRSTRLEN+1);

    /* so we don't perform this test over and over */
    stack[IPV4] = opts->ipv4Choice == '*' &&
                  iface->ipv4method == IPV4_MANUAL_METHOD;
#ifdef ENABLE_IPV6
    stack[IPV6] = opts->ipv6Choice == '*' &&
                  iface->ipv6method == IPV6_MANUAL_METHOD;
#endif

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
        }

        if (*ret) {
            newtEntrySet(ipcomps->cidr4Entry, ret, 1);
        }

        pos++;
    }

#ifdef ENABLE_IPV6
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
#endif

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

    checked_asprintf(&buf,
                     _("Enter the IPv4 and/or the IPv6 address and prefix "
                       "(address / prefix).  For IPv4, the dotted-quad "
                       "netmask or the CIDR-style prefix are acceptable. "
                       "The gateway and name server fields must be valid IPv4 "
                       "or IPv6 addresses."));

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

    have[IPV4] = 0;
    have[IPV6] = 0;

    for (i = IPV4; i <= IPV6; i++) {
        if (!stack[i]) {
            have[i] = 2;
        }
    }

    /* run the form */
    while ((have[IPV4] != 2) || (have[IPV6] != 2)) {
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
                if (inet_pton(AF_INET, ipcomps->cidr4, &iface->netmask) >= 1) {
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

#ifdef ENABLE_IPV6
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
#endif

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
#ifdef ENABLE_IPV6
            if (isValidIPv4Address(ipcomps->ns) ||
                isValidIPv6Address(ipcomps->ns)) {
#else
            if (isValidIPv4Address(ipcomps->ns)) {
#endif
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
        if (stack[IPV4] && have[IPV4] != 2) {
            have[IPV4] = 0;
            newtWinMessage(_("Missing Information"), _("Retry"),
                           _("You must enter both a valid IPv4 address and a "
                             "network mask or CIDR prefix."));
        }

#ifdef ENABLE_IPV6
        if (stack[IPV6] && have[IPV6] != 2) {
            have[IPV6] = 0;
            newtWinMessage(_("Missing Information"), _("Retry"),
                           _("You must enter both a valid IPv6 address and a "
                             "CIDR prefix."));
        }
#endif

        strcpy(iface->device, device);
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
    int i = 0, rc;
    struct device **devs = NULL;

    devs = getDevices(DEVICE_NETWORK);

    if (devs == NULL) {
        return 1;
    }

    for (i = 0; devs[i]; i++) {
        /* remove dhclient-DEVICE.conf if we have it */
        if ((rc = removeDhclientConfFile(devs[i]->device)) != 0) {
            return rc;
        }
        /* write disabled ifcfg-DEVICE file */
        if (!is_wireless_device(devs[i]->device))
            if ((rc = writeDisabledIfcfgFile(devs[i]->device)) != 0)
                return rc;
    }
    return 0;
}

int removeIfcfgFile(char *device) {
    char *fname = NULL;
    checked_asprintf(&fname, "%s/ifcfg-%s",
                     NETWORK_SCRIPTS_PATH,
                     device);

    if (!access(fname, R_OK|W_OK)) {
        if (unlink(fname)) {
            logMessage(ERROR, "error removing %s", fname);
        }
    }

    free(fname);
    return 0;
}

int removeDhclientConfFile(char *device) {
    char *ofile = NULL;
    if (asprintf(&ofile, "/etc/dhcp/dhclient-%s.conf", device) == -1) {
        return 5;
    }

    if (!access(ofile, R_OK|W_OK)) {
        if (unlink(ofile)) {
            logMessage(ERROR, "error removing %s", ofile);
        }
    }

    free(ofile);
    return 0;
}

int writeDisabledIfcfgFile(char *device) {
    char *ofile = NULL;
    char *nfile = NULL;
    FILE *fp = NULL;

    checked_asprintf(&ofile, "%s/.ifcfg-%s",
                     NETWORK_SCRIPTS_PATH,
                     device);
    checked_asprintf(&nfile, "%s/ifcfg-%s",
                     NETWORK_SCRIPTS_PATH,
                     device);

    if ((fp = fopen(ofile, "w")) == NULL) {
        free(ofile);
        return 2;
    }
    fprintf(fp, "DEVICE=%s\n", device);
    fprintf(fp, "HWADDR=%s\n", iface_mac2str(device));
    fprintf(fp, "ONBOOT=no\n");
    fprintf(fp, "NM_CONTROLLED=no\n");

    if (fclose(fp) == EOF) {
        return 3;
    }

    if (rename(ofile, nfile) == -1) {
        free(ofile);
        free(nfile);
        return 4;
    }

    if (ofile) {
        free(ofile);
        ofile = NULL;
    }

    if (nfile) {
        free(nfile);
        nfile = NULL;
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
    mode_t mode = S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP | S_IROTH | S_IWOTH;
    FILE *fp = NULL;
    char buf[INET6_ADDRSTRLEN+1];
    char *ofile = NULL;
    char *nfile = NULL;
    struct utsname kv;

    memset(&buf, '\0', sizeof(buf));

    if ((mkdir(NETWORK_SCRIPTS_PATH, mode) == -1) && (errno != EEXIST)) {
        return 16;
    }

    /* write vendor class */
    if (iface->vendorclass == NULL) {
        if (uname(&kv) == -1) {
            iface->vendorclass = "anaconda";
        } else {
            if (asprintf(&iface->vendorclass, "anaconda-%s %s %s",
                         kv.sysname, kv.release, kv.machine) == -1 ) {
                return 20;
            }
        }
    }

    if (asprintf(&ofile, "/etc/dhcp/dhclient-%s.conf", iface->device) == -1) {
        return 17;
    }

    if ((fp = fopen(ofile, "w")) == NULL) {
        free(ofile);
        return 18;
    }

    fprintf(fp, "send vendor-class-identifier \"%s\";\n",
            iface->vendorclass);

    if (fclose(fp) == EOF) {
        free(ofile);
        return 19;
    }

    if (ofile) {
        free(ofile);
        ofile = NULL;
    }

    /* write out new ifcfg-DEVICE file */
    if (asprintf(&ofile, "%s/.ifcfg-%s",
                 NETWORK_SCRIPTS_PATH, iface->device) == -1) {
        return 1;
    }

    if (asprintf(&nfile, "%s/ifcfg-%s",
                 NETWORK_SCRIPTS_PATH, iface->device) == -1) {
        return 13;
    }

    if ((fp = fopen(ofile, "w")) == NULL) {
        free(ofile);
        return 2;
    }

    fprintf(fp, "DEVICE=%s\n", iface->device);
#if !defined(__s390__) && !defined(__s390x__)
    fprintf(fp, "HWADDR=%s\n", iface_mac2str(iface->device));
#endif
    fprintf(fp, "ONBOOT=yes\n");

    if (!FL_NOIPV4(flags)) {
        if (iface->ipv4method == IPV4_IBFT_METHOD) {
            fprintf(fp, "BOOTPROTO=ibft\n");
        } else if (iface->ipv4method == IPV4_DHCP_METHOD) {
            fprintf(fp, "BOOTPROTO=dhcp\n");
        } else if (iface->ipv4method == IPV4_MANUAL_METHOD) {
            fprintf(fp, "BOOTPROTO=static\n");

            if (iface_have_in_addr(&iface->ipaddr)) {
                if (inet_ntop(AF_INET, &iface->ipaddr, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    fclose(fp);
                    return 3;
                }

                fprintf(fp, "IPADDR=%s\n", buf);
            }

            if (iface_have_in_addr(&iface->netmask)) {
                if (inet_ntop(AF_INET, &iface->netmask, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    fclose(fp);
                    return 4;
                }

                fprintf(fp, "NETMASK=%s\n", buf);
            }

            if (iface_have_in_addr(&iface->broadcast)) {
                if (inet_ntop(AF_INET, &iface->broadcast, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    fclose(fp);
                    return 5;
                }

                fprintf(fp, "BROADCAST=%s\n", buf);
            }

            if (iface_have_in_addr(&iface->gateway)) {
                if (inet_ntop(AF_INET, &iface->gateway, buf,
                              INET_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    fclose(fp);
                    return 6;
                }

                fprintf(fp, "GATEWAY=%s\n", buf);
            }
        }
    }

#ifdef ENABLE_IPV6
    if (!FL_NOIPV6(flags)) {
        if (iface->ipv6method == IPV6_AUTO_METHOD ||
            iface->ipv6method == IPV6_DHCP_METHOD ||
            iface->ipv6method == IPV6_MANUAL_METHOD) {
            fprintf(fp, "IPV6INIT=yes\n");

            if (iface->ipv6method == IPV6_AUTO_METHOD) {
                fprintf(fp, "IPV6_AUTOCONF=yes\n");
            } else if (iface->ipv6method == IPV6_DHCP_METHOD) {
                fprintf(fp, "IPV6_AUTOCONF=no\n");
                fprintf(fp, "DHCPV6C=yes\n");
            } else if (iface->ipv6method == IPV6_MANUAL_METHOD) {
                fprintf(fp, "IPV6_AUTOCONF=no\n");
                if (iface_have_in6_addr(&iface->ip6addr)) {
                    if (inet_ntop(AF_INET6, &iface->ip6addr, buf,
                                  INET6_ADDRSTRLEN) == NULL) {
                        free(ofile);
                        fclose(fp);
                        return 7;
                    }

                    if (iface->ip6prefix) {
                        fprintf(fp, "IPV6ADDR=%s/%d\n", buf, iface->ip6prefix);
                    } else {
                        fprintf(fp, "IPV6ADDR=%s\n", buf);
                    }
                }
            }

            if (iface_have_in6_addr(&iface->gateway6)) {
                if (inet_ntop(AF_INET6, &iface->gateway6, buf,
                              INET6_ADDRSTRLEN) == NULL) {
                    free(ofile);
                    fclose(fp);
                    return 8;
                }

                fprintf(fp, "IPV6_DEFAULTGW=%s\n", buf);
            }
        }
    }
#endif

    if (iface->numdns > 0) {
        for (i = 0; i < iface->numdns; i++) {
            fprintf(fp, "DNS%d=%s\n", i+1, iface->dns[i]);
        }
    }

    if (iface->hostname && iface->ipv4method == IPV4_DHCP_METHOD) {
        fprintf(fp, "DHCP_HOSTNAME=%s\n", iface->hostname);
    }

    if (iface->domain) {
        fprintf(fp, "DOMAIN=\"%s\"\n", iface->domain);
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

    if (iface->options) {
        fprintf(fp, "OPTIONS=\'%s\'\n", iface->options);
    }

    if (iface->macaddr) {
        fprintf(fp, "MACADDR=%s\n", iface->macaddr);
    }

    if (!iface->defroute) {
        fprintf(fp, "DEFROUTE=no\n");
        logMessage(INFO, "not setting default route via %s", iface->device);
    }

    if (iface->ssid) {
        fprintf(fp, "ESSID=%s\n", iface->ssid);
    }

    if (iface->wepkey) {
        fprintf(fp, "DEFAULTKEY=1");
    }

    if (fclose(fp) == EOF) {
        free(ofile);
        free(nfile);
        return 8;
    }

    if (rename(ofile, nfile) == -1) {
        free(ofile);
        free(nfile);
        return 14;
    }

    if (ofile) {
        free(ofile);
    }

    if (nfile) {
        free(nfile);
    }

    /* wireless wepkey: keys-DEVICE file */
    if (iface->wepkey) {
        if (asprintf(&ofile, "%s/.keys-%s",
                     NETWORK_SCRIPTS_PATH, iface->device) == -1) {
            return 21;
        }

        if (asprintf(&nfile, "%s/keys-%s",
                     NETWORK_SCRIPTS_PATH, iface->device) == -1) {
            return 22;
        }

        if ((fp = fopen(ofile, "w")) == NULL) {
            free(ofile);
            return 23;
        }

        fprintf(fp, "KEY1=%s\n", iface->wepkey);


        if (fclose(fp) == EOF) {
            free(ofile);
            free(nfile);
            return 24;
        }

        if (rename(ofile, nfile) == -1) {
            free(ofile);
            free(nfile);
            return 25;
        }

        if (ofile) {
            free(ofile);
        }

        if (nfile) {
            free(nfile);
        }
    }


    return 0;
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
    int lookForLink = 0;
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
        if ((loaderData->bootIf && (loaderData->bootIf_set) == 1) &&
            !strcasecmp(loaderData->netDev, "bootif")) {
            ksMacAddr = g_ascii_strup(loaderData->bootIf, -1);
        } else {
            ksMacAddr = g_ascii_strup(loaderData->netDev, -1);
        }
    }

    for (i = 0; devs[i]; i++) {
        if (!devs[i]->device)
            continue;

        if (devs[i]->description) {
            deviceNames[deviceNums] = alloca(strlen(devs[i]->device) +
                                      strlen(devs[i]->description) + 4);
            sprintf(deviceNames[deviceNums],"%s - %.50s",
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
                char *devmacaddr = iface_mac2str(devs[i]->device);

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

    /* If there is iBFT table and ksdevice doesn't say otherwise, use it */
    while (!loaderData->netDev_set || !strcmp(loaderData->netDev, "ibft")) {
        char *devmacaddr = NULL;
        char *ibftmacaddr = "";

        /* get MAC from the iBFT table */
        if (!(ibftmacaddr = ibft_iface_mac())) { /* iBFT not present or error */
            logMessage(INFO, "No iBFT table detected.");
            break;
        }

        logMessage(INFO, "looking for iBFT configured device %s with link",
                   ibftmacaddr);

        for (i = 0; devs[i]; i++) {
            if (!devs[i]->device)
                continue;

            devmacaddr = iface_mac2str(devs[i]->device);

            if(!strcasecmp(devmacaddr, ibftmacaddr)){
                logMessage(INFO,
                           "%s has the right MAC (%s), checking for link",
                           devs[i]->device, devmacaddr);
                free(devmacaddr);

                /* wait for the link (max 5s) */
                for (rc = 0; rc < 5; rc++) {
                    if (get_link_status(devs[i]->device) == 0) {
                        logMessage(INFO, "%s still has no link, waiting", devs[i]->device);
                        sleep(1);                 
                    } else {
                        lookForLink = 0;
                        loaderData->netDev = devs[i]->device;
                        loaderData->netDev_set = 1;
                        logMessage(INFO, "%s has link, using it", devs[i]->device);

                        /* set the IP method to ibft if not requested differently */
                        if (loaderData->ipv4 == NULL) {
                            loaderData->ipv4 = strdup("ibft");
                            loaderData->ipinfo_set = 1;
                            logMessage(INFO,
                                       "%s will be configured using iBFT values",
                                       devices[i]);
                        }

                        return LOADER_NOOP;
                    }
                }

                logMessage(INFO, "%s has no link, skipping it", devices[i]);

                break;
            } else {
                free(devmacaddr);
            }
        }

        break;
    }

    if ((loaderData->netDev && (loaderData->netDev_set == 1)) &&
        !strcmp(loaderData->netDev, "link")) {
        lookForLink = 1;
    }

    if (lookForLink) {
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

        logMessage(WARNING,
                   "wanted netdev with link, but none present.  prompting");
    }

    /* JKFIXME: if we only have one interface and it doesn't have link,
     * do we go ahead? */
    if (deviceNums == 1) {
        logMessage(INFO, "only have one network device: %s", devices[0]);
        loaderData->netDev = devices[0];
        loaderData->netDev_set = 1;
        return LOADER_NOOP;
    }

    if (FL_CMDLINE(flags)) {
        fprintf(stderr, "No way to determine which NIC to use, and cannot "
                        "prompt in cmdline\nmode.  Halting.\n");
        fprintf(stderr, "Please use the ksdevice= parameter to specify the "
                        "device name (e.g., eth0)\n or the MAC address of "
                        "the NIC to use for installation.\n");
        exit(1);
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

            checked_asprintf(&idstr, "%s %s %s",
                             _("You can identify the physical port for"),
                             devices[deviceNum],
                             _("by flashing the LED lights for a number of "
                               "seconds.  Enter a number between 1 and 30 to "
                               "set the duration to flash the LED port "
                               "lights."));

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

                    if (secs <=0 || secs > 300) {
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
                              _("Flashing %s port lights for %d seconds."),
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
    int rc = -1;

    if ((is_nm_connected() == TRUE) &&
        (loaderData->netDev != NULL) && (loaderData->netDev_set == 1))
        return 0;

    iface_init_iface_t(iface);

    if (loaderData->essid != NULL) {
        checkIPsettings(&(loaderData->ipinfo_set), &(loaderData->ipv4), &(loaderData->gateway),
                &(loaderData->netmask));
        if (loaderData->wepkey != NULL)
            rc = add_and_activate_wifi_connection(&(loaderData->netDev),
                    loaderData->essid, WIFI_PROTECTION_WEP, loaderData->wepkey,
                    loaderData->ipinfo_set, loaderData->ipv4, loaderData->gateway,
                    loaderData->dns, loaderData->netmask);

        else if (loaderData->wpakey != NULL)
            rc = add_and_activate_wifi_connection(&(loaderData->netDev),
                    loaderData->essid, WIFI_PROTECTION_WPA, loaderData->wpakey,
                    loaderData->ipinfo_set, loaderData->ipv4, loaderData->gateway,
                    loaderData->dns, loaderData->netmask);

        else
            rc = add_and_activate_wifi_connection(&(loaderData->netDev),
                    loaderData->essid, WIFI_PROTECTION_UNPROTECTED, NULL,
                    loaderData->ipinfo_set, loaderData->ipv4, loaderData->gateway,
                    loaderData->dns, loaderData->netmask);

        if (rc == WIFI_ACTIVATION_OK) {
            loaderData->netDev_set = 1;
            return 0;
        }
        else logMessage(ERROR, "wifi activation failed");
    }

    return activateDevice(loaderData, iface);
}

int disconnectDevice(char *device) {
    int rc;

    if ((rc = removeDhclientConfFile(device)) != 0) {
        logMessage(ERROR, "removeDhclientConfFile failure (%s): %d",
                   __func__, rc);
    }

    /*
     * This will disconnect the device
     */
    if ((rc = removeIfcfgFile(device)) != 0) {
        logMessage(ERROR, "removeIfcfgFile failure (%s): %d",
                   __func__, rc);
        return rc;
    }

    if ((rc = wait_for_iface_disconnection(device)) != 0) {
        return rc;
    }

    if ((rc = writeDisabledIfcfgFile(device)) != 0) {
        logMessage(ERROR, "writeDisabledIfcfgFile failure (%s): %d",
                   __func__, rc);
        return rc;
    }
    return 0;
}

int activateDevice(struct loaderData_s * loaderData, iface_t * iface) {
    int rc;

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

        if (is_iface_activated(iface->device)) {
            logMessage(INFO, "device %s is already activated", iface->device);
            if ((rc = disconnectDevice(iface->device)) != 0) {
                logMessage(ERROR, "device disconnection failed with return code %d", rc);
                return -1;
            }
        }

        /* we don't want to end up asking about interface more than once
         * if we're in a kickstart-ish case (#100724) */
        loaderData->netDev_set = 1;

        /* default to DHCP for IPv4 if nothing is provided */
        if (loaderData->ipv4 == NULL) {
            loaderData->ipv4 = strdup("dhcp");
            loaderData->ipinfo_set = 1;
        }

        setupIfaceStruct(iface, loaderData);
        rc = readNetConfig(loaderData->netDev, iface, loaderData->netCls,
                           loaderData->method);

        if (rc == LOADER_ERROR) {
            logMessage(ERROR, "unable to activate device %s", iface->device);
            return -1;
        } else if (rc == LOADER_BACK) {
            /* Going back to the interface selection screen, so unset anything
             * we set before attempting to bring the incorrect interface up.
             */
            logMessage(ERROR, "unable to activate device %s", iface->device);
            if ((rc = removeDhclientConfFile(iface->device)) != 0) {
                logMessage(ERROR, "removeDhclientConfFile failure (%s): %d",
                           __func__, rc);
            }
            if ((rc = writeDisabledIfcfgFile(iface->device)) != 0) {
                logMessage(ERROR, "writeDisabledIfcfgFile failure (%s): %d",
                           __func__, rc);
            }

            /* Forget network device so we prompt the user */
            loaderData->netDev_set = 0;
            /* Forget IP information so we prompt the user */
            loaderData->ipinfo_set = 0;
            free(loaderData->ipv4);
            loaderData->ipv4 = NULL;
            break;
        } else {
            break;
        }
    } while (1);

    return 0;
}

void splitHostname (char *str, char **host, char **port)
{
    char *rightbrack = strchr(str, ']');
    char *firstcolon = strchr(str, ':');
    char *secondcolon = strrchr(str, ':');

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
    } else if (firstcolon && secondcolon && firstcolon != secondcolon) {
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
 * Wait for activation of iface by NetworkManager, return non-zero on error.
 */
int wait_for_iface_activation(char *ifname) {
    int count = 0, i;
    NMClient *client = NULL;
    GMainLoop *loop;
    GMainContext *ctx;
    const GPtrArray *devices;
    NMDevice *device = NULL;

    if (ifname == NULL) {
        return 1;
    }

    logMessage(DEBUGLVL, "activating device %s", ifname);

    /* display status */
    if (FL_CMDLINE(flags)) {
        printf(_("Waiting for NetworkManager to configure %s.\n"),
               ifname);
    } else {
        winStatus(55, 3, NULL,
                  _("Waiting for NetworkManager to configure %s.\n"),
                  ifname, 0);
    }

    g_type_init();

    client = nm_client_new();
    if (!client) {
        logMessage(ERROR, "%s (%d): could not connect to system bus",
                   __func__, __LINE__);
        return 2;
    }

    devices = nm_client_get_devices(client);
    for (i = 0; i < devices->len; i++) {
        NMDevice *candidate = g_ptr_array_index(devices, i);
        const char *name = nm_device_get_iface(candidate);
        if (!strcmp(name, ifname)) {
            device = candidate;
            break;
        }
    }
    if (device == NULL) {
        logMessage(ERROR, "%s (%d): network device %s not found",
                   __func__, __LINE__, ifname);
        g_object_unref(client);
        return 3;
    }

    /* Create a loop for processing dbus signals */
    loop = g_main_loop_new(NULL, FALSE);
    ctx = g_main_loop_get_context(loop);

    /* pump the loop until all the messages are clear */
    while (g_main_context_pending (ctx)) {
        g_main_context_iteration (ctx, FALSE);
    }

    /* send message and block until a reply or error comes back */
    while (count < 45) {
        /* pump the loop again to clear the messages */
        while (g_main_context_pending (ctx)) {
            g_main_context_iteration (ctx, FALSE);
        }
        if (nm_device_get_state(device) == NM_DEVICE_STATE_ACTIVATED) {
            logMessage(INFO, "%s (%d): device %s activated",
                       __func__, __LINE__, ifname);
            res_init();
            g_main_loop_unref(loop);
            g_object_unref(client);
            return 0;
        }

        sleep(1);
        count++;
    }

    g_main_loop_unref(loop);
    g_object_unref(client);
    return 3;
}

/*
 * Wait for disconnection of iface by NetworkManager, return non-zero on error.
 */
int wait_for_iface_disconnection(char *ifname) {
    int count = 0, i;
    NMClient *client = NULL;
    GMainLoop *loop;
    GMainContext *ctx;
    const GPtrArray *devices;
    NMDevice *device = NULL;

    if (ifname == NULL) {
        return 1;
    }

    logMessage(INFO, "disconnecting device %s", ifname);

    g_type_init();

    client = nm_client_new();
    if (!client) {
        logMessage(ERROR, "%s (%d): could not connect to system bus",
                   __func__, __LINE__);
        return 2;
    }

    devices = nm_client_get_devices(client);
    for (i = 0; i < devices->len; i++) {
        NMDevice *candidate = g_ptr_array_index(devices, i);
        const char *name = nm_device_get_iface(candidate);
        if (!strcmp(name, ifname)) {
            device = candidate;
            break;
        }
    }
    if (device == NULL) {
        logMessage(ERROR, "%s (%d): network device %s not found",
                   __func__, __LINE__, ifname);
        g_object_unref(client);
        return 3;
    }

    /* Create a loop for processing dbus signals */
    loop = g_main_loop_new(NULL, FALSE);
    ctx = g_main_loop_get_context(loop);

    /* pump the loop until all the messages are clear */
    while (g_main_context_pending (ctx)) {
        g_main_context_iteration (ctx, FALSE);
    }

    /* send message and block until a reply or error comes back */
    while (count < 5) {
        /* pump the loop again to clear the messages */
        while (g_main_context_pending (ctx)) {
            g_main_context_iteration (ctx, FALSE);
        }
        if (nm_device_get_state(device) == NM_DEVICE_STATE_DISCONNECTED) {
            logMessage(INFO, "%s (%d): device %s disconnected",
                       __func__, __LINE__, ifname);
            res_init();
            g_main_loop_unref(loop);
            g_object_unref(client);
            return 0;
        }

        sleep(1);
        count++;
    }

    g_main_loop_unref(loop);
    g_object_unref(client);
    return 3;
}

int isValidIPv4Address(const char *address) {
    int rc;
    struct in_addr addr;
    if ((rc = inet_pton(AF_INET, address, &addr)) >= 1) {
        return 1;
    } else if (rc == 0) {
        return 0;
    } else {
        logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
        strerror(errno));
        return 0;
    }
}

#ifdef ENABLE_IPV6
int isValidIPv6Address(const char *address) {
    int rc;
    struct in6_addr addr;
    if ((rc = inet_pton(AF_INET6, address, &addr)) >= 1) {
        return 1;
    } else if (rc == 0) {
        return 0;
    } else {
        logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
        strerror(errno));
        return 0;
    }
}
#endif

int isURLRemote(char *url) {
    if (url == NULL) {
        return 0;
    }

    if (!strncmp(url, "http", 4) ||
        !strncmp(url, "ftp://", 6) ||
        !strncmp(url, "nfs:", 4)) {
        return 1;
    } else {
        return 0;
    }
}

gboolean byte_array_cmp(const GByteArray *array, char *string) {
    //returns TRUE if array and char* contain the same strings
    int i=0;
    gboolean ret = TRUE;
    if (array->len != strlen(string)) {
        return FALSE;
    }
    while (i<array->len && ret) {
        ret = ret && array->data[i] == string[i];
        i++;
    }
    return ret;
}

NMAccessPoint* get_best_ap(NMDeviceWifi *device, char *ssid) {
    const GPtrArray *aps;
    int i;
    NMAccessPoint *candidate = NULL;
    guint8 max = 0;
    aps = nm_device_wifi_get_access_points(device);

    if (!aps) return NULL;

    for (i = 0; i < aps->len; i++) {
        NMAccessPoint *ap = g_ptr_array_index(aps, i);
        const GByteArray *byte_ssid = nm_access_point_get_ssid(ap);
        if (byte_array_cmp(byte_ssid, ssid)) {
            if (nm_access_point_get_strength(ap) > max) {
                max = nm_access_point_get_strength(ap);
                candidate = ap;
            }
        }
    }
    return candidate;
}

gboolean get_device_and_ap(NMClient *client, char **iface, char *ssid,
            NMDeviceWifi **device, NMAccessPoint **ap) {
    //returns TRUE if device and ap (according to iface and ssid)
    //were found
    //iface, device and ap are used for storing the results
    //iface is also used as argument

    const GPtrArray *devices;
    int i;
    NMAccessPoint *candidate_ap = NULL;
    NMDevice *candidate = NULL;
    char *tmp_iface = NULL;
    char *dev_iface = NULL;

    devices = nm_client_get_devices(client);

    for (i = 0; i < devices->len; i++) {
        candidate = g_ptr_array_index(devices, i);
        tmp_iface = (char *)nm_device_get_iface(candidate);

        if (!tmp_iface) continue;
        dev_iface = strdup((char *)tmp_iface);
        if (strcmp(*iface, "") && strcmp(dev_iface, *iface)) continue;
        if (NM_IS_DEVICE_WIFI(candidate)) {
            candidate_ap = get_best_ap((NMDeviceWifi*)candidate, ssid);
            if (candidate_ap != NULL) {
                *device = (NMDeviceWifi*)candidate;
                *ap = candidate_ap;
                *iface = dev_iface;
                return TRUE;
            }
        }
        else free(dev_iface);
    }
    return FALSE;
}


static void
add_cb(NMClient *client,
        const char *connection_path,
        const char *active_path,
        GError *error,
        gpointer user_data) {
    if (error) logMessage(ERROR, "Error adding wifi connection: %s", error->message);
}

gboolean ip_str_to_nbo(char* ip, guint32 *result) {
    //get NBO representation of ip address
    struct in_addr tmp_addr = { 0 };

    if (inet_pton(AF_INET, ip, &tmp_addr) == 1) {
        *result = tmp_addr.s_addr;
        return TRUE;
    } else return FALSE;
}


int add_and_activate_wifi_connection(char **iface, char *ssid,
    int protection, char *password, int ip_method_manual, char *address,
    char *gateway, char *dns, char *netmask) {

    NMClient *client = NULL;
    NMDeviceWifi *device = NULL;
    NMAccessPoint *ap = NULL;
    GMainLoop *loop;
    GMainContext *ctx;
    DBusGConnection *DBconnection;
    GError *error;
    GByteArray *ssid_ba;
    int ssid_len;
    gboolean success = FALSE;
    gint8 count = 0, ret;
    NMConnection *connection;
    NMSettingConnection *s_con;
    NMSettingWireless *s_wireless;
    NMSettingWirelessSecurity *s_sec;
    NMSettingIP4Config *s_ip;
    char *uuid;
    char *buf;

    if (*iface == NULL) *iface = "";
    error = NULL;
    DBconnection = dbus_g_bus_get(DBUS_BUS_SYSTEM, &error);
    if (DBconnection == NULL) {
      g_error_free(error);
      return WIFI_ACTIVATION_DBUS_ERROR;
    }

    client = nm_client_new();
    if (!client) return WIFI_ACTIVATION_NM_CLIENT_ERROR;

    if (!nm_client_wireless_hardware_get_enabled(client))
        return WIFI_ACTIVATION_WIFI_HW_DISABLED;

    if (!nm_client_wireless_get_enabled(client))
        nm_client_wireless_set_enabled(client, TRUE);

    if (!ssid) return WIFI_ACTIVATION_BAD_SSID;
    ssid_len = strlen(ssid);
    if (!ssid_len || ssid_len > 32) return WIFI_ACTIVATION_BAD_SSID;
    ssid_ba = g_byte_array_sized_new(ssid_len);
    g_byte_array_append(ssid_ba, (unsigned char *) ssid, ssid_len);

    loop = g_main_loop_new(NULL, FALSE);
    ctx = g_main_loop_get_context(loop);

    while (g_main_context_pending(ctx))
        g_main_context_iteration(ctx, FALSE);

    /* display status */
    if (FL_CMDLINE(flags))
        printf(_("Waiting for NetworkManager to activate wifi.\n"));
    else
        winStatus(55, 3, NULL,
                  _("Waiting for NetworkManager to activate wifi.\n"), 0);

    while (count < 45 && !success) {
        while (g_main_context_pending(ctx))
            g_main_context_iteration(ctx, FALSE);
        success = get_device_and_ap(client, iface, ssid, &device, &ap);
        sleep(1);
        count++;
    }

    if (!FL_CMDLINE(flags)) newtPopWindow();

    if (!success) return WIFI_ACTIVATION_CANNOT_FIND_AP;

    connection = nm_connection_new();

    s_con = (NMSettingConnection*) nm_setting_connection_new();
    uuid = nm_utils_uuid_generate();
    g_object_set(G_OBJECT (s_con),
        NM_SETTING_CONNECTION_UUID, uuid,
        NM_SETTING_CONNECTION_ID, ssid,
        NM_SETTING_CONNECTION_TYPE, "802-11-wireless",
        NULL);
    g_free(uuid);
    nm_connection_add_setting(connection, NM_SETTING (s_con));

    s_wireless = (NMSettingWireless*) nm_setting_wireless_new();
    g_object_set(G_OBJECT (s_wireless),
        NM_SETTING_WIRELESS_SSID, ssid_ba,
        NM_SETTING_WIRELESS_MODE, "infrastructure",
        NULL);
    g_byte_array_free(ssid_ba, TRUE);
    if ((protection == WIFI_PROTECTION_WEP) || protection == WIFI_PROTECTION_WPA) {
        g_object_set(G_OBJECT (s_wireless),
            NM_SETTING_WIRELESS_SEC, "802-11-wireless-security",
            NULL);
    }
    nm_connection_add_setting(connection, NM_SETTING (s_wireless));

    if (protection == WIFI_PROTECTION_WEP) {
        s_sec = (NMSettingWirelessSecurity*) nm_setting_wireless_security_new();
        g_object_set (G_OBJECT (s_sec),
            NM_SETTING_WIRELESS_SECURITY_KEY_MGMT, "none",
            NM_SETTING_WIRELESS_SECURITY_WEP_TX_KEYIDX, 0,
            NM_SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE, 1,
            NM_SETTING_WIRELESS_SECURITY_WEP_KEY0, password,
            NULL);
        if (strlen(password) == 32) {
            g_object_set(G_OBJECT (s_sec),
                NM_SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE, 2,
                NULL);
        }
        nm_connection_add_setting(connection, NM_SETTING (s_sec));

    } else if (protection == WIFI_PROTECTION_WPA) {
        s_sec = (NMSettingWirelessSecurity*) nm_setting_wireless_security_new();
        g_object_set(G_OBJECT (s_sec),
            NM_SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk",
            NM_SETTING_WIRELESS_SECURITY_PSK, password,
            NULL);
        nm_connection_add_setting(connection, NM_SETTING (s_sec));
    }

    if (ip_method_manual) {
        GPtrArray *addresses = g_ptr_array_new();
        GArray *address_array = g_array_new(FALSE, FALSE, sizeof(guint32));
        guint32 nbo_ip = 0;
        guint32 nbo_gw = 0;
        guint32 nbo_dns = 0;
        guint32 nbo_netmask = 0;
        guint32 nbo_prefix = 0;
        char *dns_addr = NULL;

        ip_str_to_nbo(address, &nbo_ip);

        if (gateway) ip_str_to_nbo(gateway, &nbo_gw);

        nbo_prefix = nm_utils_ip4_get_default_prefix(nbo_ip);
        if (netmask && ip_str_to_nbo(netmask, &nbo_netmask))
                nbo_prefix = nm_utils_ip4_netmask_to_prefix(nbo_netmask);

        g_array_append_val(address_array, nbo_ip);
        g_array_append_val(address_array, nbo_prefix);
        g_array_append_val(address_array, nbo_gw);

        g_ptr_array_add(addresses, address_array);

        s_ip = (NMSettingIP4Config*) nm_setting_ip4_config_new();
        g_object_set(G_OBJECT (s_ip),
            NM_SETTING_IP4_CONFIG_METHOD, NM_SETTING_IP4_CONFIG_METHOD_MANUAL,
            NM_SETTING_IP4_CONFIG_ADDRESSES, addresses,
            NULL);
        if (dns) {
            count = 0;
            buf = strdup(dns);
            dns_addr = strtok(buf, ",");
            while (dns_addr && count <= MAXNS) {
                if (ip_str_to_nbo(dns_addr, &nbo_dns)) {
                    nm_setting_ip4_config_add_dns(s_ip, nbo_dns);
                    count++;
                }
                dns_addr = strtok(NULL, ",");
            }
        }
        nm_connection_add_setting(connection, NM_SETTING (s_ip));
        g_array_free(address_array, TRUE);
        g_ptr_array_free(addresses, TRUE);
    }

    const char *ap_path = nm_object_get_path((NMObject*) ap);
    nm_client_add_and_activate_connection(client, connection,
            (NMDevice*) device, ap_path, (NMClientAddActivateFn) add_cb,
            NULL);

    ret = wait_for_iface_activation(*iface);
    if (!FL_CMDLINE(flags)) newtPopWindow();
    if (ret == 0) {
        g_main_loop_unref(loop);
        return WIFI_ACTIVATION_OK;
    }

    *iface = NULL;
    g_main_loop_unref(loop);
    return WIFI_ACTIVATION_TIMED_OUT;
}

gboolean checkIPsettings (int *ip_info_set, char **ip, char **gateway, char **netmask) {
    gboolean ok = TRUE;
    guint32 tmp = 0;

    if (*ip && !ip_str_to_nbo(*ip, &tmp)) {
        free(*ip);
        *ip = NULL;
        *ip_info_set = 0;
        ok = FALSE;
    }
    if (*gateway && !ip_str_to_nbo(*gateway, &tmp)) {
        free(*gateway);
        *gateway = NULL;
        ok = FALSE;
    }
    if (*netmask && !ip_str_to_nbo(*netmask, &tmp)) {
        free(*netmask);
        *netmask = NULL;
        ok = FALSE;
    }
    return ok;
}

/* vim:set shiftwidth=4 softtabstop=4: */
