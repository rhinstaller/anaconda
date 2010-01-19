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
#include "ibft.h"

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
	    char *devmacaddr = iface_mac2str(loaderData->netDev);
	    iface->ipv4method = IPV4_IBFT_METHOD;
	    iface->isiBFT = 1;

	    /* Problems with getting the info from iBFT or iBFT uses dhcp*/
	    if(!devmacaddr || !ibft_present()){
		iface->ipv4method = IPV4_DHCP_METHOD;
		logMessage(INFO, "iBFT is not present");
	    }
	    /* MAC address doesn't match */
	    else if(strcasecmp(ibft_iface_mac(), devmacaddr)){
		iface->ipv4method = IPV4_DHCP_METHOD;
		logMessage(INFO, "iBFT doesn't know what NIC to use - falling back to DHCP");
	    }
	    else if(ibft_iface_dhcp()){
		iface->ipv4method = IPV4_IBFT_DHCP_METHOD;
		logMessage(INFO, "iBFT is configured to use DHCP");
	    }
	    if(devmacaddr) free(devmacaddr);
	}
        /* this is how we specify dhcp */
        else if (!strncmp(loaderData->ipv4, "dhcp", 4)) {
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

    /* iBFT configured DNS */
    if(iface->ipv4method == IPV4_IBFT_METHOD){
	if(iface->numdns<MAXNS){
	    if(ibft_iface_dns1() && inet_pton(AF_INET, ibft_iface_dns1(), &addr)>=1){
		iface->dns[iface->numdns] = strdup(ibft_iface_dns1());
		iface->numdns++;
		logMessage(INFO, "adding iBFT dns server %s", ibft_iface_dns1());
	    }
	}
	if(iface->numdns<MAXNS){
	    if(ibft_iface_dns2() && inet_pton(AF_INET, ibft_iface_dns2(), &addr)>=1){
		iface->dns[iface->numdns] = strdup(ibft_iface_dns2());
		iface->numdns++;
		logMessage(INFO, "adding iBFT dns server %s", ibft_iface_dns2());
	    }
	}
    }

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

    if (loaderData->layer2) {
        iface->layer2 = strdup(loaderData->layer2);
    }

    if (loaderData->portno) {
        iface->portno = strdup(loaderData->portno);
    }

    if (loaderData->noDns) {
        iface->flags |= IFACE_FLAGS_NO_WRITE_RESOLV_CONF;
    }

    iface->dhcptimeout = loaderData->dhcpTimeout;

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
#ifdef ENABLE_IPV6
    opts.ipv6Choice = 0;
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

        i = get_connection(iface);
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
    err = writeEnabledNetInfo(iface);
    if (err) {
        logMessage(ERROR, "failed to write %s data for %s (%d)",
                   SYSCONFIG_PATH, iface->device, err);
        iface->ipv4method = IPV4_UNUSED_METHOD;
        iface->ipv6method = IPV6_UNUSED_METHOD;
        return LOADER_BACK;
    }

    i = get_connection(iface);
    newtPopWindow();

    if (i > 0) {
        newtWinMessage(_("Network Error"), _("Retry"),
                       _("There was an error configuring your network "
                         "interface."));
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
    v4Method[0] = newtRadiobutton(-1, -1, DHCP_METHOD_STR, 1, NULL);
    v4Method[1] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, 0, v4Method[0]);

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
    v6Method[0] = newtRadiobutton(-1, -1, AUTO_METHOD_STR, 1, NULL);
    v6Method[1] = newtRadiobutton(-1, -1, DHCPV6_METHOD_STR, 0, v6Method[0]);
    v6Method[2] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, 0, v6Method[1]);
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
    if ((FL_IP_PARAM(flags) && FL_IPV6_PARAM(flags)) ||
        (FL_IP_PARAM(flags) && FL_NOIPV6(flags)) ||
        (FL_IPV6_PARAM(flags) && FL_NOIPV4(flags)) ||
        (FL_NOIPV4(flags) && FL_NOIPV6(flags))) {
        skipForm = 1;
        newtPopWindow();
    }
#else
    if (FL_IP_PARAM(flags) || FL_NOIPV4(flags)) {
        skipForm = 1;
        newtPopWindow();
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

        /* do interface configuration (call DHCP here, or return for manual) */
#ifdef ENABLE_IPV6
        if ((!FL_NOIPV4(flags) && iface->ipv4method == IPV4_DHCP_METHOD) ||
            (!FL_NOIPV6(flags) && (iface->ipv6method == IPV6_AUTO_METHOD ||
                                   iface->ipv6method == IPV6_DHCP_METHOD))) {
#else
        if (!FL_NOIPV4(flags) && iface->ipv4method == IPV4_DHCP_METHOD) {
#endif
            /* DHCP selected, exit the loop */
            ret = LOADER_NOOP;
            i = 1;
#ifdef ENABLE_IPV6
        } else if ((!FL_NOIPV4(flags) && iface->ipv4method == IPV4_MANUAL_METHOD) ||
                   (!FL_NOIPV6(flags) && iface->ipv6method == IPV6_MANUAL_METHOD)) {
#else
        } else if (!FL_NOIPV4(flags) && iface->ipv4method == IPV4_MANUAL_METHOD) {
#endif

            /* manual IP configuration selected */
            ret = LOADER_OK;
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
    struct in_addr addr;
#ifdef ENABLE_IPV6
    struct in6_addr addr6;
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
            if ((inet_pton(AF_INET, ipcomps->ns, &addr) >= 1) ||
                (inet_pton(AF_INET6, ipcomps->ns, &addr6) >= 1)) {
#else
            if (inet_pton(AF_INET, ipcomps->ns, &addr) >= 1) {
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
    int i = 0;
    char *ofile = NULL;
    char *nfile = NULL;
    FILE *fp = NULL;
    struct device **devs = NULL;

    devs = getDevices(DEVICE_NETWORK);

    if (devs == NULL) {
        return 1;
    }

    for (i = 0; devs[i]; i++) {
        /* remove dhclient-DEVICE.conf if we have it */
        if (asprintf(&ofile, "/etc/dhcp/dhclient-%s.conf", devs[i]->device) == -1) {
            return 5;
        }

        if (!access(ofile, R_OK|W_OK)) {
            if (unlink(ofile)) {
                logMessage(ERROR, "error removing %s", ofile);
            }
        }

        if (ofile) {
            free(ofile);
            ofile = NULL;
        }

        /* write disabled ifcfg-DEVICE file */
        
        checked_asprintf(&ofile, "%s/.ifcfg-%s",
                         NETWORK_SCRIPTS_PATH,
                         devs[i]->device);
        checked_asprintf(&nfile, "%s/ifcfg-%s",
                         NETWORK_SCRIPTS_PATH,
                         devs[i]->device);

        if ((fp = fopen(ofile, "w")) == NULL) {
            free(ofile);
            return 2;
        }

        fprintf(fp, "DEVICE=%s\n", devs[i]->device);
        fprintf(fp, "HWADDR=%s\n", iface_mac2str(devs[i]->device));
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
    }

    return 0;
}

/*
 * Write out network interface control files:
 *     /etc/sysconfig/network-scripts/ifcfg-DEVICE
 *     /etc/sysconfig/network
 */
int writeEnabledNetInfo(iface_t *iface) {
    int i = 0, osa_layer2 = 1, osa_portno = 0;
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
    fprintf(fp, "HWADDR=%s\n", iface_mac2str(iface->device));
    fprintf(fp, "ONBOOT=yes\n");

    if (!FL_NOIPV4(flags)) {
        if (iface->ipv4method == IPV4_IBFT_METHOD) {
	    /* When initrd and NM support iBFT, we should just write
	     * BOOTPROTO=ibft and let NM deal with it. Until than,
	     * just use static and do it ourselves. */
            fprintf(fp, "BOOTPROTO=static\n");
	    if(ibft_iface_ip()) fprintf(fp, "IPADDR=%s\n", ibft_iface_ip());
	    if(ibft_iface_mask()) fprintf(fp, "NETMASK=%s\n", ibft_iface_mask());
	    if(ibft_iface_gw()) fprintf(fp, "GATEWAY=%s\n", ibft_iface_gw());
        } else if (iface->ipv4method == IPV4_IBFT_DHCP_METHOD) {
            fprintf(fp, "BOOTPROTO=dhcp\n");
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
                fprintf(fp, "DHCPV6C=yes\n");
            } else if (iface->ipv6method == IPV6_MANUAL_METHOD) {
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

    if (iface->layer2 && !strcmp(iface->layer2, "1")) {
        osa_layer2 = 1;
    }

    if (iface->portno && !strcmp(iface->portno, "1")) {
        osa_portno = 1;
    }

    if (osa_layer2 || osa_portno) {
        fprintf(fp, "OPTIONS=\"");

        if (osa_layer2) {
            fprintf(fp, "layer2=1");
        }

        if (osa_layer2 && osa_portno) {
            fprintf(fp, " ");
        }

        if (osa_portno) {
            fprintf(fp, "portno=1");
        }

        fprintf(fp, "\"\n");
    }

    if (iface->macaddr) {
        fprintf(fp, "MACADDR=%s\n", iface->macaddr);
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

    /* Global settings */
    if ((fp = fopen(SYSCONFIG_PATH"/.network", "w")) == NULL) {
        return 9;
    }

    if (!FL_NOIPV4(flags)) {
        fprintf(fp, "NETWORKING=yes\n");
    }

#ifdef ENABLE_IPV6
    if (!FL_NOIPV6(flags)) {
        fprintf(fp, "NETWORKING_IPV6=yes\n");
    }
#endif

    if (iface->hostname != NULL) {
        fprintf(fp, "HOSTNAME=%s\n", iface->hostname);
    }

    if (iface_have_in_addr(&iface->gateway)) {
        if (inet_ntop(AF_INET, &iface->gateway, buf,
                      INET_ADDRSTRLEN) == NULL) {
            fclose(fp);
            return 10;
        }

        fprintf(fp, "GATEWAY=%s\n", buf);
    }

#ifdef ENABLE_IPV6
    if (iface_have_in6_addr(&iface->gateway6)) {
        if (inet_ntop(AF_INET6, &iface->gateway6, buf,
                      INET6_ADDRSTRLEN) == NULL) {
            fclose(fp);
            return 11;
        }

        fprintf(fp, "IPV6_DEFAULTGW=%s\n", buf);
    }
#endif

    if (fclose(fp) == EOF) {
        return 12;
    }

    if (rename(SYSCONFIG_PATH"/.network",
               SYSCONFIG_PATH"/network") == -1) {
        return 15;
    }

    return 0;
}

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv) {
    iface_t iface;
    gchar *bootProto = NULL, *device = NULL, *class = NULL, *ethtool = NULL;
    gchar *essid = NULL, *wepkey = NULL, *onboot = NULL;
    gint mtu = 1500, dhcpTimeout = -1;
    gboolean noipv4 = FALSE, noipv6 = FALSE, noDns = FALSE, noksdev = FALSE;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksOptions[] = {
        { "bootproto", 0, 0, G_OPTION_ARG_STRING, &bootProto, NULL, NULL },
        { "device", 0, 0, G_OPTION_ARG_STRING, &device, NULL, NULL },
        { "dhcpclass", 0, 0, G_OPTION_ARG_STRING, &class, NULL, NULL },
        { "gateway", 'g', 0, G_OPTION_ARG_STRING, &loaderData->gateway,
          NULL, NULL },
        { "ip", 'i', 0, G_OPTION_ARG_STRING, &loaderData->ipv4, NULL, NULL },
        { "mtu", 0, 0, G_OPTION_ARG_INT, &mtu, NULL, NULL },
        { "nameserver", 'n', 0, G_OPTION_ARG_STRING, &loaderData->dns,
          NULL, NULL },
        { "netmask", 'm', 0, G_OPTION_ARG_STRING, &loaderData->netmask,
          NULL, NULL },
        { "noipv4", 0, 0, G_OPTION_ARG_NONE, &noipv4, NULL, NULL },
        { "noipv6", 0, 0, G_OPTION_ARG_NONE, &noipv6, NULL, NULL },
        { "nodns", 0, 0, G_OPTION_ARG_NONE, &noDns, NULL, NULL },
        { "hostname", 'h', 0, G_OPTION_ARG_STRING, &loaderData->hostname,
          NULL, NULL },
        { "ethtool", 0, 0, G_OPTION_ARG_STRING, &ethtool, NULL, NULL },
        { "essid", 0, 0, G_OPTION_ARG_STRING, &essid, NULL, NULL },
        { "wepkey", 0, 0, G_OPTION_ARG_STRING, &wepkey, NULL, NULL },
        { "onboot", 0, 0, G_OPTION_ARG_STRING, &onboot, NULL, NULL },
        { "notksdevice", 0, 0, G_OPTION_ARG_NONE, &noksdev, NULL, NULL },
        { "dhcptimeout", 0, 0, G_OPTION_ARG_INT, &dhcpTimeout, NULL, NULL },
        { NULL },
    };

    iface_init_iface_t(&iface);

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to kickstart network command: %s"),
                       optErr->message);
        g_error_free(optErr);
    }

    g_option_context_free(optCon);

    /* if they've specified dhcp/bootp use dhcp for the interface */
    if (bootProto && (!strncmp(bootProto, "dhcp", 4) || 
                       !strncmp(bootProto, "bootp", 4))) {
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
            /* If --device=MAC was given, translate into a device name now. */
            if (index(device, ':') != NULL)
                loaderData->netDev = iface_mac2device(device);
            else
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

#ifdef ENABLE_IPV6
        if (noipv6)
            flags |= LOADER_FLAGS_NOIPV6;
#endif
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

    /* JKFIXME: if we only have one interface and it doesn't have link,
     * do we go ahead? */
    if (deviceNums == 1) {
        logMessage(INFO, "only have one network device: %s", devices[0]);
        loaderData->netDev = devices[0];
        return LOADER_NOOP;
    }

    while ((loaderData->netDev && (loaderData->netDev_set == 1)) &&
           !strcmp(loaderData->netDev, "ibft")) {
        char *devmacaddr = NULL;
        char *ibftmacaddr = "";

        /* get MAC from the iBFT table */
        if (!(ibftmacaddr = ibft_iface_mac())) { /* iBFT not present or error */
            lookForLink = 0;
            break;
        }

        logMessage(INFO, "looking for iBFT configured device %s with link",
                   ibftmacaddr);
        lookForLink = 0;

        for (i = 0; devs[i]; i++) {
            if (!devs[i]->device)
                continue;

            devmacaddr = iface_mac2str(devs[i]->device);

            if(!strcasecmp(devmacaddr, ibftmacaddr)){
                logMessage(INFO,
                           "%s has the right MAC (%s), checking for link",
                           devmacaddr, devices[i]);
                free(devmacaddr);

                if (get_link_status(devices[i]) == 1) {
                    lookForLink = 0;
                    loaderData->netDev = devices[i];
                    logMessage(INFO, "%s has link, using it", devices[i]);

                    /* set the IP method to ibft if not requested differently */
                    if (loaderData->ipv4 == NULL) {
                        loaderData->ipv4 = strdup("ibft");
                        logMessage(INFO,
                                   "%s will be configured using iBFT values",
                                   devices[i]);
                    }

                    return LOADER_NOOP;
                } else {
                    logMessage(INFO, "%s has no link, skipping it", devices[i]);
                }

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
    int rc, err;

    if (is_nm_connected() == TRUE)
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

        /* default to DHCP for IPv4 if nothing is provided */
        if (loaderData->ipv4 == NULL) {
            loaderData->ipv4 = strdup("dhcp");
            loaderData->ipinfo_set = 1;
        }

        setupIfaceStruct(iface, loaderData);
        rc = readNetConfig(loaderData->netDev, iface, loaderData->netCls,
                           loaderData->method);

        if (rc == LOADER_ERROR) {
            logMessage(ERROR, "unable to setup networking");
            return -1;
        } else if (rc == LOADER_BACK) {
            /* Going back to the interface selection screen, so unset anything
             * we set before attempting to bring the incorrect interface up.
             */
            if ((rc = writeDisabledNetInfo()) != 0) {
                logMessage(ERROR, "writeDisabledNetInfo failure (%s): %d",
                           __func__, rc);
            }

            loaderData->netDev_set = 0;
            loaderData->ipinfo_set = 0;
            free(loaderData->ipv4);
            loaderData->ipv4 = NULL;
            break;
        } else {
            break;
        }

        err = writeEnabledNetInfo(iface);
        if (err) {
            logMessage(ERROR,
                       "failed to write %s data for %s (%d)",
                       SYSCONFIG_PATH, iface->device, err);
            return -1;
        }

        err = get_connection(iface);
        newtPopWindow();

        if (err) {
            logMessage(ERROR, "failed to start NetworkManager (%d)", err);
            return -1;
        }
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
    NMClient *client = NULL;
    NMState state;
    GMainLoop *loop;
    GMainContext *ctx;

    if (iface == NULL) {
        return 1;
    }

    logMessage(DEBUGLVL, "configuring device %s", iface->device);

    /* display status */
    if (FL_CMDLINE(flags)) {
        printf(_("Waiting for NetworkManager to configure %s.\n"),
               iface->device);
    } else {
        winStatus(55, 3, NULL,
                  _("Waiting for NetworkManager to configure %s.\n"),
                  iface->device, 0);
    }

    g_type_init();

    client = nm_client_new();
    if (!client) {
        logMessage(ERROR, "%s (%d): could not connect to system bus",
                   __func__, __LINE__);
        return 2;
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
        state = nm_client_get_state(client);

        if (state == NM_STATE_CONNECTED) {
            logMessage(INFO, "%s (%d): NetworkManager connected",
                       __func__, __LINE__);
            res_init();
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

/* vim:set shiftwidth=4 softtabstop=4: */
