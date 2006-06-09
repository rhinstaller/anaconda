/*
 * Copyright 1999-2004 Red Hat, Inc.
 * 
 * All Rights Reserved.
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
 * OPEN GROUP BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
 * AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 * 
 * Except as contained in this notice, the name of Red Hat shall not be
 * used in advertising or otherwise to promote the sale, use or other dealings
 * in this Software without prior written authorization from Red Hat.
 *
 */

#include <sys/types.h>
#include <sys/socket.h>
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
#include <kudzu/kudzu.h>

#include "../isys/dns.h"
#include "../isys/isys.h"
#include "../isys/net.h"
#include "../isys/wireless.h"
#include "../isys/nl.h"

#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "net.h"
#include "windows.h"

char *netServerPrompt = \
    N_("Please enter the following information:\n"
       "\n"
       "    o the name or IP number of your %s server\n" 
       "    o the directory on that server containing\n" 
       "      %s for your architecture\n");

struct intfconfig_s {
    newtComponent ipEntry, nmEntry, gwEntry, nsEntry;
    const char * ip, * nm, * gw, * ns;
};

typedef int int32;

static int setupWireless(struct networkDeviceConfig *dev);

static void ipCallback(newtComponent co, void * dptr) {
    struct intfconfig_s * data = dptr;
    struct in_addr ipaddr, nmaddr, addr, naddr;
    char * ascii;
    int broadcast, network;
    int af = AF_INET;                 /* accept as a parameter */
    int l = 0;

    if (co == data->ipEntry) {
        if (strlen(data->ip) && !strlen(data->nm)) {
            if (inet_pton(af, data->ip, &ipaddr)) {
                ipaddr.s_addr = ntohl(ipaddr.s_addr);
                switch (af) {
                    case AF_INET:
                        ascii = "255.255.255.0";
                        /* does this line need to be for each case? */
                        newtEntrySet(data->nmEntry, ascii, 1);
                        break;
                    case AF_INET6:
                        /* FIXME: writeme? */
                        break;
                }
            }
        }
    } else if (co == data->nmEntry) {
        if (!strlen(data->ip) || !strlen(data->nm)) return;
        if (!inet_pton(af, data->ip, &ipaddr)) return;
        if (!inet_pton(af, data->nm, &nmaddr)) return;

        if (af == AF_INET) {
            l = INET_ADDRSTRLEN;
        } else if (af == AF_INET6) {
            l = INET6_ADDRSTRLEN;
        }

        if (af == AF_INET || af == AF_INET6) {
            network = ipaddr.s_addr & nmaddr.s_addr;
            broadcast = (ipaddr.s_addr & nmaddr.s_addr) | (~nmaddr.s_addr) ;

            if (!strlen(data->gw)) {
                char gw[l]; 
                addr.s_addr = htonl(ntohl(broadcast) - 1);
                inet_ntop(af, &addr, gw, sizeof(gw));
                newtEntrySet(data->gwEntry, gw, 1);
            }

            if (!strlen(data->ns)) {
                char ns[l];
                naddr.s_addr = network;
                naddr.s_addr |= htonl(1);
                inet_ntop(af, &naddr, ns, sizeof(ns));
                newtEntrySet(data->nsEntry, ns, 1);
            }
        }
    }
}

static void fillInIpInfo(struct networkDeviceConfig * cfg) {
    int32 * i;
    char * nm;
   
    if (!(cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)) {
        i = (int32 *) &cfg->dev.ip;

        nm = "255.255.255.0";

        inet_pton(AF_INET, nm, &cfg->dev.netmask);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (!(cfg->dev.set & PUMP_INTFINFO_HAS_BROADCAST)) {
        *((int32 *) &cfg->dev.broadcast) = (*((int32 *) &cfg->dev.ip) & 
                           *((int32 *) &cfg->dev.netmask)) | 
                           ~(*((int32 *) &cfg->dev.netmask));
        cfg->dev.set |= PUMP_INTFINFO_HAS_BROADCAST;
    }

    if (!(cfg->dev.set & PUMP_INTFINFO_HAS_NETWORK)) {
        *((int32 *) &cfg->dev.network) = 
                *((int32 *) &cfg->dev.ip) &
                *((int32 *) &cfg->dev.netmask);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETWORK;
    }
}

static int waitForLink(char * dev) {
    extern int num_link_checks;
    int tries = 0;

    /* try to wait for a valid link -- if the status is unknown or
     * up continue, else sleep for 1 second and try again for up
     * to five times */
    logMessage(DEBUGLVL, "waiting for link...");
    while (tries < num_link_checks) {
      if (get_link_status(dev) != 0)
            break;
        sleep(1);
        tries++;
    }
    logMessage(DEBUGLVL, "%d seconds.", tries);
    if (tries < num_link_checks)
        return 0;
    logMessage(WARNING, "no network link detected on %s", dev);
    return 1;
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

void initLoopback(void) {
    NLH_t nh;
    NIC_t nic;
    uint32_t flags;

    /* open nic handle and set device name */
    nh = nic_open(nic_sys_logger);
    nic = nic_by_name(nh, "lo");

    /* bring the interface up */
    flags = nic_get_flags(nic);
    if ((flags & (IFF_UP | IFF_RUNNING)) == 0) {
        nic_set_flags(nic, flags | IFF_UP | IFF_RUNNING);
        nic_update(nic);
    }

    /* clean up */
    nic_close(&nh);

    return;
}

static void dhcpBoxCallback(newtComponent co, void * ptr) {
    struct intfconfig_s * c = ptr;

    newtEntrySetFlags(c->ipEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->gwEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nmEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nsEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
}

static int getWirelessConfig(struct networkDeviceConfig *cfg, char * ifname) {
    char * wepkey = "";
    char * essid = "";
    int rc = 0;
    char * buf;

    if (cfg->wepkey != NULL) {
        wepkey = strdup(cfg->wepkey);
    }
    if (cfg->essid != NULL) {
        essid = strdup(cfg->essid);
    } else {
        essid = get_essid(ifname);
    }

    buf = sdupprintf(_("%s is a wireless network adapter.  Please "
                       "provide the ESSID and encryption key needed "
                       "to access your wireless network.  If no key "
                       "is needed, leave this field blank and the "
                       "install will continue."), ifname);
    do {
        struct newtWinEntry entry[] = { { N_("ESSID"), (const char **)&essid, 0 },
                                        { N_("Encryption Key"), (const char **) &wepkey, 0 },
                                        { NULL, NULL, 0 } };

        rc = newtWinEntries(_("Wireless Settings"), buf,
                            40, 5, 10, 30, entry, _("OK"), _("Back"), NULL);
        if (rc == 2) return LOADER_BACK;

        /* set stuff up */
    } while (rc == 2);

    if (cfg->wepkey != NULL) 
        free(cfg->wepkey);

    if (wepkey && (strlen(wepkey) > 0))
        cfg->wepkey = strdup(wepkey);
    else
        cfg->wepkey = NULL;

    if (cfg->essid != NULL)
        free(cfg->essid);

    if (essid && (strlen(essid) > 0))
        cfg->essid = strdup(essid);
    else
        cfg->essid = NULL;

    return LOADER_OK;
}

static int getDnsServers(struct networkDeviceConfig * cfg) {
    int rc;
    const char * ns = "";
    struct newtWinEntry entry[] = { { N_("Nameserver IP"), &ns, 0 },
                                      { NULL, NULL, 0 } };

    do {
        rc = newtWinEntries(_("Nameserver"), 
                _("Your dynamic IP request returned IP configuration "
                  "information, but it did not include a DNS nameserver. "
                  "If you know what your nameserver is, please enter it "
                  "now. If you don't have this information, you can leave "
                  "this field blank and the install will continue."),
                40, 5, 10, 25, entry, _("OK"), _("Back"), NULL);

        if (rc == 2) return LOADER_BACK;

        if (ns && *ns && !inet_pton(AF_INET, ns, &cfg->dev.dnsServers[0])) {
            newtWinMessage(_("Invalid IP Information"), _("Retry"),
                        _("You entered an invalid IP address."));
            rc = 2;
        } 

    } while (rc == 2);

    cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
    cfg->dev.numDns = 1;

    return LOADER_OK;
}

void printLoaderDataIPINFO(struct loaderData_s *loaderData) {
    logMessage(DEBUGLVL, "loaderData->ipinfo_set = %d", loaderData->ipinfo_set);
    logMessage(DEBUGLVL, "loaderData->ip         = %s", loaderData->ip);
    logMessage(DEBUGLVL, "loaderData->netmask    = %s", loaderData->netmask);
    logMessage(DEBUGLVL, "loaderData->gateway    = %s", loaderData->gateway);
    logMessage(DEBUGLVL, "loaderData->dns        = %s", loaderData->dns);
    logMessage(DEBUGLVL, "loaderData->hostname   = %s", loaderData->hostname);
    logMessage(DEBUGLVL, "loaderData->noDns      = %d", loaderData->noDns);
    logMessage(DEBUGLVL, "loaderData->netDev_set = %d", loaderData->netDev_set);
    logMessage(DEBUGLVL, "loaderData->netDev     = %s", loaderData->netDev);
    logMessage(DEBUGLVL, "loaderData->netCls_set = %d", loaderData->netCls_set);
    logMessage(DEBUGLVL, "loaderData->netCls     = %s", loaderData->netCls);
}

/* given loader data from kickstart, populate network configuration struct */
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData, 
                              int flags) {
    struct in_addr addr;
    struct in6_addr addr6;
    char * c;

    /* set to 1 to get ks network struct logged */
#if 0
    printLoaderDataIPINFO(loaderData);
#endif

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->ip) {
        if (is_wireless_interface(loaderData->netDev)) {
            if (loaderData->essid) {
                logMessage(INFO, "setting specified essid of %s",
                           loaderData->essid);
                cfg->essid = strdup(loaderData->essid);
            }
            if (loaderData->wepkey) {
                logMessage(INFO, "setting specified wepkey");
                cfg->wepkey = strdup(loaderData->wepkey);
            }
            /* go ahead and set up the wireless interface in case 
             * we're using dhcp */
            setupWireless(cfg);
        }

        /* this is how we specify dhcp */
        if (!strncmp(loaderData->ip, "dhcp", 4)) {
            char *ret = NULL;

            /* JKFIXME: this soooo doesn't belong here.  and it needs to
             * be broken out into a function too */
            logMessage(INFO, "sending dhcp request through device %s",
                       loaderData->netDev);

            if (!FL_CMDLINE(flags)) {
                startNewt(flags);
                winStatus(55, 3, _("Dynamic IP"), 
                          _("Sending request for IP information for %s..."), 
                          loaderData->netDev, 0);
            } else {
                printf("Sending request for IP information for %s...\n", 
                       loaderData->netDev);
            }

            if (!FL_TESTING(flags)) {
                waitForLink(loaderData->netDev);
                ret = doDhcp(cfg);
            }

            if (!FL_CMDLINE(flags))
                newtPopWindow();

            if (ret != NULL) {
                logMessage(DEBUGLVL, "dhcp: %s", ret);
                return;
            }
            
            cfg->isDynamic = 1;
            cfg->preset = 1;
        } else if (inet_pton(AF_INET, loaderData->ip, &addr)) {
            cfg->dev.ip = ip_addr_in(&addr);
            cfg->dev.set |= PUMP_INTFINFO_HAS_IP;
            cfg->isDynamic = 0;
            cfg->preset = 1;
        } else if (inet_pton(AF_INET6, loaderData->ip, &addr6)) {
            cfg->dev.ip = ip_addr_in6(&addr6);
            cfg->dev.set |= PUMP_INTFINFO_HAS_IP;
            cfg->isDynamic = 0;
            cfg->preset = 1;
        } else { /* invalid ip information, disable the setting of ip info */
            loaderData->ipinfo_set = 0;
            loaderData->ip = NULL;
        }
    }

    if (loaderData->netmask && (inet_pton(AF_INET, loaderData->netmask, &addr))) {
        cfg->dev.netmask = ip_addr_in(&addr);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (loaderData->netmask && (inet_pton(AF_INET6, loaderData->netmask, &addr6))) {
        cfg->dev.netmask = ip_addr_in6(&addr6);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (loaderData->gateway && (inet_pton(AF_INET, loaderData->gateway, &addr))) {
        cfg->dev.gateway = ip_addr_in(&addr);
        cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
    }

    if (loaderData->gateway && (inet_pton(AF_INET6, loaderData->gateway, &addr6))) {
        cfg->dev.gateway = ip_addr_in6(&addr6);
        cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
    }

    if (loaderData->dns) {
        char * buf;
        buf = strdup(loaderData->dns);

        /* Scan the dns parameter for multiple comma-separated IP addresses */
         c = strtok(buf, ",");  
         while ((cfg->dev.numDns < MAX_DNS_SERVERS) && (c != NULL)) {
             if (inet_pton(AF_INET, c, &addr)) {
                 cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in(&addr);
                 cfg->dev.numDns++;
                 logMessage(DEBUGLVL, "adding %s", inet_ntoa(addr));
                 c = strtok(NULL, ",");
             } else if (inet_pton(AF_INET6, c, &addr6)) {
                 cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in6(&addr6);
                 cfg->dev.numDns++;
                 logMessage(DEBUGLVL, "adding %s", inet_ntoa(addr));
                 c = strtok(NULL, ",");
             }
         }
         logMessage(INFO, "dnsservers is %s", loaderData->dns);
         if (cfg->dev.numDns)
             cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
    }

    if (loaderData->hostname) {
        logMessage(INFO, "setting specified hostname of %s",
                   loaderData->hostname);
        cfg->dev.hostname = strdup(loaderData->hostname);
        cfg->dev.set |= PUMP_NETINFO_HAS_HOSTNAME;
    }

    if (loaderData->mtu) {
        cfg->mtu = loaderData->mtu;
        cfg->dev.mtu = loaderData->mtu;
        cfg->dev.set |= PUMP_INTFINFO_HAS_MTU;
    }

    if (loaderData->peerid) {
        cfg->peerid = strdup(loaderData->peerid);
    }

    if (loaderData->subchannels) {
        cfg->subchannels = strdup(loaderData->subchannels);
    }

    if (loaderData->ctcprot) {
        cfg->ctcprot = strdup(loaderData->ctcprot);
    }

    if (loaderData->portname) {
        cfg->portname = strdup(loaderData->portname);
    }

    if (loaderData->nettype) {
        cfg->nettype = strdup(loaderData->nettype);
    }

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    cfg->noDns = loaderData->noDns;
}

int readNetConfig(char * device, struct networkDeviceConfig * cfg, 
                  char * dhcpclass, int flags) {
    newtComponent text, f, okay, back, answer, dhcpCheckbox;
    newtGrid grid, subgrid, buttons;
    struct networkDeviceConfig newCfg;
    struct intfconfig_s c;
    int i;
    struct in_addr addr;
    struct in6_addr addr6;
    char dhcpChoice;
    char *dret = NULL;
    char ret[47];
    ip_addr_t *tip;

    memset(&c, 0, sizeof(c));

    /* JKFIXME: we really need a way to override this and be able to change
     * our network config */
    if (!FL_TESTING(flags) && cfg->preset) {
        logMessage(INFO, "doing kickstart... setting it up");
        configureNetwork(cfg);
        findHostAndDomain(cfg, flags);

        if (!cfg->noDns)
            writeResolvConf(cfg);
        return LOADER_NOOP;
    }        

    if (is_wireless_interface(device)) {
        logMessage(INFO, "%s is a wireless adaptor", device);
        if (getWirelessConfig(cfg, device) == LOADER_BACK)
            return LOADER_BACK;
        /* FIXME: this is a bit of a hack */
        strcpy(newCfg.dev.device, device);
        newCfg.essid = cfg->essid;
        newCfg.wepkey = cfg->wepkey;
    }
    else
        logMessage(INFO, "%s isn't a wireless adaptor", device);

    text = newtTextboxReflowed(-1, -1, 
                _("Please enter the IP configuration for this machine. Each "
                  "item should be entered as an IP address in dotted-decimal "
                  "notation (for example, 1.2.3.4)."), 50, 5, 10, 0);

    subgrid = newtCreateGrid(2, 4);
    newtGridSetField(subgrid, 0, 0, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("IP address:")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 1, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Netmask:")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 2, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Default gateway (IP):")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(subgrid, 0, 3, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Primary nameserver:")),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    c.ipEntry = newtEntry(-1, -1, NULL, 16, &c.ip, 0);
    c.nmEntry = newtEntry(-1, -1, NULL, 16, &c.nm, 0);
    c.gwEntry = newtEntry(-1, -1, NULL, 16, &c.gw, 0);
    c.nsEntry = newtEntry(-1, -1, NULL, 16, &c.ns, 0);

    if (cfg->dev.set & PUMP_INTFINFO_HAS_IP) {
        tip = &(cfg->dev.ip);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(c.ipEntry, ret, 1);
    }

    if (cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK) {
        tip = &(cfg->dev.netmask);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(c.nmEntry, ret, 1);
    }
    
    if (cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY) {
        tip = &(cfg->dev.gateway);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(c.gwEntry, ret, 1);
    }
    
    if (cfg->dev.numDns) {
        tip = &(cfg->dev.dnsServers[0]);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(c.nsEntry, ret, 1);
    }

    if (!cfg->isDynamic) {
        dhcpChoice = ' ';
    } else {
        dhcpChoice = '*';
    }

    dhcpCheckbox = newtCheckbox(-1, -1, 
                _("Use dynamic IP configuration (BOOTP/DHCP)"),
                dhcpChoice, NULL, &dhcpChoice);
    newtComponentAddCallback(dhcpCheckbox, dhcpBoxCallback, &c);
    if (dhcpChoice == '*') dhcpBoxCallback(dhcpCheckbox, &c);

    newtGridSetField(subgrid, 1, 0, NEWT_GRID_COMPONENT, c.ipEntry,
                     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 1, NEWT_GRID_COMPONENT, c.nmEntry,
                     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 2, NEWT_GRID_COMPONENT, c.gwEntry,
                     1, 0, 0, 0, 0, 0);
    newtGridSetField(subgrid, 1, 3, NEWT_GRID_COMPONENT, c.nsEntry,
                     1, 0, 0, 0, 0, 0);

    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

    grid = newtCreateGrid(1, 4);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, dhcpCheckbox,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, subgrid,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 3, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Configure TCP/IP"));
    newtGridFree(grid, 1);
   
    newtComponentAddCallback(c.ipEntry, ipCallback, &c);
    newtComponentAddCallback(c.nmEntry, ipCallback, &c);
    
    do {
        answer = newtRunForm(f);

        if (answer == back) {
            newtFormDestroy(f);
            newtPopWindow();
            return LOADER_BACK;
        } 

        if (dhcpChoice == ' ') {
            i = 0;
            memset(&newCfg, 0, sizeof(newCfg));
            if (*c.ip) {
                if (inet_pton(AF_INET, c.ip, &addr)) {
                    i++;
                    newCfg.dev.ip = ip_addr_in(&addr);
                    newCfg.dev.set |= PUMP_INTFINFO_HAS_IP;
                } else if (inet_pton(AF_INET6, c.ip, &addr6)) {
                    i++;
                    newCfg.dev.ip = ip_addr_in6(&addr6);
                    newCfg.dev.set |= PUMP_INTFINFO_HAS_IP;
                }
            }

            if (*c.nm) {
                if (inet_pton(AF_INET, c.nm, &addr)) {
                    i++;
                    newCfg.dev.netmask = ip_addr_in(&addr);
                    newCfg.dev.set |= PUMP_INTFINFO_HAS_NETMASK;
                } else if (inet_pton(AF_INET6, c.nm, &addr6)) {
                    i++;
                    newCfg.dev.netmask = ip_addr_in6(&addr6);
                    newCfg.dev.set |= PUMP_INTFINFO_HAS_NETMASK;
                }
            }

            if (c.ns && *c.ns) {
                if (inet_pton(AF_INET, c.ns, &addr)) {
                    cfg->dev.dnsServers[0] = ip_addr_in(&addr);
                    if (cfg->dev.numDns < 1)
                        cfg->dev.numDns = 1;
                } else if (inet_pton(AF_INET6, c.ns, &addr6)) {
                    cfg->dev.dnsServers[0] = ip_addr_in6(&addr6);
                    if (cfg->dev.numDns < 1)
                        cfg->dev.numDns = 1;
                }
            }

            if (i != 2) {
                newtWinMessage(_("Missing Information"), _("Retry"),
                            _("You must enter both a valid IP address and a "
                              "netmask."));
            }

            strcpy(newCfg.dev.device, device);
            newCfg.isDynamic = 0;
        } else {
            if (!FL_TESTING(flags)) {
                winStatus(55, 3, _("Dynamic IP"), 
                          _("Sending request for IP information for %s..."), 
                          device, 0);
                waitForLink(device);
                dret = doDhcp(&newCfg);
                newtPopWindow();
            }

            if (dret==NULL) {
                newCfg.isDynamic = 1;
                if (!(newCfg.dev.set & PUMP_NETINFO_HAS_DNS)) {
                    logMessage(WARNING, "dhcp worked, but did not return a DNS server");
                    i = getDnsServers(&newCfg);
                    i = i ? 0 : 2;
                } else {
                    i = 2; 
                }
            } else {
                logMessage(DEBUGLVL, "dhcp: %s", dret);
                i = 0;
            }
        }
    } while (i != 2);

    /* preserve extra dns servers for the sake of being nice */
    if (cfg->dev.numDns > newCfg.dev.numDns) {
        for (i = newCfg.dev.numDns; i < cfg->dev.numDns; i++) {
            newCfg.dev.dnsServers[i] = cfg->dev.dnsServers[i];
        }
        newCfg.dev.numDns = cfg->dev.numDns;
    }

    cfg->isDynamic = newCfg.isDynamic;
    memcpy(&cfg->dev,&newCfg.dev,sizeof(newCfg.dev));

    fillInIpInfo(cfg);

    if (!(cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)) {
        if (c.gw && *c.gw) {
            if (inet_pton(AF_INET, c.gw, &addr)) {
                cfg->dev.gateway = ip_addr_in(&addr);
                cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            } else if (inet_pton(AF_INET6, c.gw, &addr6)) {
                cfg->dev.gateway = ip_addr_in6(&addr6);
                cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            }
        }
    }

    newtPopWindow();

    if (!FL_TESTING(flags)) {
        configureNetwork(cfg);
        findHostAndDomain(cfg, flags);
        writeResolvConf(cfg);
    }

    return 0;
}

static int setupWireless(struct networkDeviceConfig *dev) {
    /* wireless config needs to be set up before we can bring the interface
     * up */
    if (!is_wireless_interface(dev->dev.device))
        return 0;

    if (dev->essid) {
        logMessage(INFO, "setting essid for %s to %s", dev->dev.device,
                   dev->essid);
        if (set_essid(dev->dev.device, dev->essid) < 0) {
            logMessage(ERROR, "failed to set essid: %s", strerror(errno));
        }
        if (dev->wepkey) {
            logMessage(INFO, "setting encryption key for %s", dev->dev.device);
            if (set_wep_key(dev->dev.device, dev->wepkey) < 0) {
                logMessage(ERROR, "failed to set wep key: %s", strerror(errno));
        }

        }
    }

    return 0;
}

char *setupInterface(struct networkDeviceConfig *dev) {
    setupWireless(dev);
    return pumpSetupInterface(&dev->dev);
}

void netlogger(void *arg, int priority, char *fmt, va_list va) {
    logMessage(priority, fmt, va);
}

char *doDhcp(struct networkDeviceConfig *dev) {
   struct pumpNetIntf *i;
   char *r = NULL;

   i = &dev->dev;

   if (dev->useipv6)
      r = pumpDhcpClassRun(i,0L,0L,0,0,10,netlogger,LOG_DEBUG);
   else
      r = pumpDhcpClassRun(i,0L,0L,DHCPv6_DISABLE,0,10,netlogger,LOG_DEBUG);

   return r;
}

int configureNetwork(struct networkDeviceConfig * dev) {
    char *rc;

    rc = setupInterface(dev);
    if (rc)
        logMessage(INFO, "result of setupInterface is %s", rc);

    /* we need to wait for a link after setting up the interface as some
     * switches decide to reconfigure themselves after that (#115825)
     */
    waitForLink((char *)&dev->dev.device);
    return 0;
}

int writeNetInfo(const char * fn, struct networkDeviceConfig * dev) {
    FILE * f;
    int i;
    struct device ** devices;
    char ret[47];
    ip_addr_t *tip;

    devices = probeDevices(CLASS_NETWORK, BUS_UNSPEC, PROBE_LOADED);
    if (!devices)
        return 0;

    for (i = 0; devices[i]; i++)
        if (!strcmp(devices[i]->device, dev->dev.device)) break;
    
    if (!(f = fopen(fn, "w"))) return -1;

    fprintf(f, "DEVICE=%s\n", dev->dev.device);

    fprintf(f, "ONBOOT=yes\n");

    if (dev->isDynamic) {
        fprintf(f, "BOOTPROTO=dhcp\n");
    } else {
        fprintf(f, "BOOTPROTO=static\n");

        tip = &(dev->dev.ip);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        fprintf(f, "IPADDR=%s\n", ret);

        tip = &(dev->dev.netmask);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        fprintf(f, "NETMASK=%s\n", ret);

        if (dev->dev.set & PUMP_NETINFO_HAS_GATEWAY) {
            tip = &(dev->dev.gateway);
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            fprintf(f, "GATEWAY=%s\n", ret);
        }

        if (dev->dev.set & PUMP_INTFINFO_HAS_BROADCAST) {
          tip = &(dev->dev.broadcast);
          inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
          fprintf(f, "BROADCAST=%s\n", ret);
        }
    }

    if (dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)
        fprintf(f, "HOSTNAME=%s\n", dev->dev.hostname);
    if (dev->dev.set & PUMP_NETINFO_HAS_DOMAIN)
        fprintf(f, "DOMAIN=%s\n", dev->dev.domain);
    if (dev->mtu)
        fprintf(f, "MTU=%d\n", dev->mtu);
    if (dev->peerid)
        fprintf(f, "PEERID=%s\n", dev->peerid);
    if (dev->subchannels)
        fprintf(f, "SUBCHANNELS=%s\n", dev->subchannels);
    if (dev->portname)
        fprintf(f, "PORTNAME=%s\n", dev->portname);
    if (dev->nettype)
        fprintf(f, "NETTYPE=%s\n", dev->nettype);
    if (dev->ctcprot)
        fprintf(f, "CTCPROT=%s\n", dev->ctcprot);

    if (dev->essid)
        fprintf(f, "ESSID=%s\n", dev->essid);
    if (dev->wepkey)
        fprintf(f, "KEY=%s\n", dev->wepkey);
    
    fclose(f);

    return 0;
}

int writeResolvConf(struct networkDeviceConfig * net) {
    char * filename = "/etc/resolv.conf";
    FILE * f;
    int i;
    char ret[47];
    ip_addr_t *tip;
#if defined(__s390__) || defined(__s390x__)
    return 0;
#endif

    if (!(net->dev.set & PUMP_NETINFO_HAS_DOMAIN) && !net->dev.numDns)
        return LOADER_ERROR;

    f = fopen(filename, "w");
    if (!f) {
        logMessage(ERROR, "Cannot create %s: %s\n", filename, strerror(errno));
        return LOADER_ERROR;
    }

    if (net->dev.set & PUMP_NETINFO_HAS_DOMAIN)
        fprintf(f, "search %s\n", net->dev.domain);

    for (i = 0; i < net->dev.numDns; i++) {
        tip = &(net->dev.dnsServers[i]);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        fprintf(f, "nameserver %s\n", ret);
    }

    fclose(f);

    res_init();         /* reinit the resolver so DNS changes take affect */

    return 0;
}

int findHostAndDomain(struct networkDeviceConfig * dev, int flags) {
    char * name, * chptr;
    char ret[47];
    ip_addr_t *tip;

    if (!FL_TESTING(flags)) {
        writeResolvConf(dev);
    }

    if (dev->dev.numDns == 0) {
        logMessage(ERROR, "no DNS servers, can't look up hostname");
        return 1;
    }

    if (!(dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)) {
        if (!FL_CMDLINE(flags))
            winStatus(50, 3, _("Hostname"), 
                      _("Determining host name and domain..."));
        else
            printf("Determining host name and domain...\n");

        tip = &(dev->dev.ip);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        name = mygethostbyaddr(ret);

        if (!FL_CMDLINE(flags))
            newtPopWindow();

        if (!name) {
            logMessage(WARNING, "reverse name lookup failed");
            return 1;
        }

        logMessage(INFO, "reverse name lookup worked");

        dev->dev.hostname = strdup(name);
        dev->dev.set |= PUMP_NETINFO_HAS_HOSTNAME;
    } else {
        name = dev->dev.hostname;
    }

    if (!(dev->dev.set & PUMP_NETINFO_HAS_DOMAIN)) {
        for (chptr = name; *chptr && (*chptr != '.'); chptr++) ;
        if (*chptr == '.') {
            if (dev->dev.domain) free(dev->dev.domain);
            dev->dev.domain = strdup(chptr + 1);
            dev->dev.set |= PUMP_NETINFO_HAS_DOMAIN;
        }
    }

    return 0;
}

void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv, int * flagsPtr) {
    char * arg, * bootProto = NULL, * device = NULL, *ethtool = NULL, * class = NULL;
    char * essid = NULL, * wepkey = NULL, * onboot = NULL;
    int noDns = 0, noksdev = 0, rc, mtu = 0;
    poptContext optCon;

    struct poptOption ksOptions[] = {
        { "bootproto", '\0', POPT_ARG_STRING, &bootProto, 0, NULL, NULL },
        { "device", '\0', POPT_ARG_STRING, &device, 0, NULL, NULL },
        { "dhcpclass", '\0', POPT_ARG_STRING, &class, 0, NULL, NULL },
        { "gateway", '\0', POPT_ARG_STRING, NULL, 'g', NULL, NULL },
        { "ip", '\0', POPT_ARG_STRING, NULL, 'i', NULL, NULL },
        { "mtu", '\0', POPT_ARG_INT, &mtu, 0, NULL, NULL },
        { "nameserver", '\0', POPT_ARG_STRING, NULL, 'n', NULL, NULL },
        { "netmask", '\0', POPT_ARG_STRING, NULL, 'm', NULL, NULL },
        { "nodns", '\0', POPT_ARG_NONE, &noDns, 0, NULL, NULL },
        { "hostname", '\0', POPT_ARG_STRING, NULL, 'h', NULL, NULL},
        { "ethtool", '\0', POPT_ARG_STRING, &ethtool, 0, NULL, NULL },
        { "essid", '\0', POPT_ARG_STRING, &essid, 0, NULL, NULL },
        { "wepkey", '\0', POPT_ARG_STRING, &wepkey, 0, NULL, NULL },
        { "onboot", '\0', POPT_ARG_STRING, &onboot, 0, NULL, NULL },
        { "notksdevice", '\0', POPT_ARG_NONE, &noksdev, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };
    
    optCon = poptGetContext(NULL, argc, (const char **) argv, 
                            ksOptions, 0);    
    while ((rc = poptGetNextOpt(optCon)) >= 0) {
        arg = (char *) poptGetOptArg(optCon);

        switch (rc) {
        case 'g':
            loaderData->gateway = strdup(arg);
            break;
        case 'i':
            loaderData->ip = strdup(arg);
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
        (!bootProto && !loaderData->ip)) {
        loaderData->ip = strdup("dhcp");
        loaderData->ipinfo_set = 1;
    } else if (loaderData->ip) {
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
    }

    if (noDns) {
        loaderData->noDns = 1;
    }
}

/* if multiple interfaces get one to use from user.   */
/* NOTE - uses kickstart data available in loaderData */
int chooseNetworkInterface(struct loaderData_s * loaderData,
                           int flags) {
    int i, rc;
    unsigned int max = 40;
    int deviceNums = 0;
    int deviceNum;
    char ** devices;
    char ** deviceNames;
    int foundDev = 0;
    struct device ** devs;
    char * ksMacAddr = NULL;

    devs = probeDevices(CLASS_NETWORK, BUS_UNSPEC, PROBE_LOADED);
    if (!devs) {
        logMessage(ERROR, "no network devices in choose network device!");
        return LOADER_ERROR;
    }

    for (i = 0; devs[i]; i++);

    devices = alloca((i + 1) * sizeof(*devices));
    deviceNames = alloca((i + 1) * sizeof(*devices));
    if (loaderData->netDev && (loaderData->netDev_set) == 1) {
        if ((loaderData->bootIf && (loaderData->bootIf_set) == 1) && !strcasecmp(loaderData->netDev, "bootif")) {
            ksMacAddr = netlink_format_mac_addr(ksMacAddr, (unsigned char *) loaderData->bootIf);
        } else {
            ksMacAddr = netlink_format_mac_addr(ksMacAddr, (unsigned char *) loaderData->netDev);
        }
    }

    for (i = 0; devs[i]; i++) {
        if (!devs[i]->device)
	    continue;
        if (devs[i]->desc) {
                deviceNames[deviceNums] = alloca(strlen(devs[i]->device) +
                                          strlen(devs[i]->desc) + 4);
                sprintf(deviceNames[deviceNums],"%s - %s",
                        devs[i]->device, devs[i]->desc);
                if (strlen(deviceNames[deviceNums]) > max)
                        max = strlen(deviceNames[deviceNums]);
                devices[deviceNums++] = devs[i]->device;
        } else {
            devices[deviceNums] = devs[i]->device;
            deviceNames[deviceNums++] = devs[i]->device;
        }

        /* this device has been set and we don't really need to ask 
         * about it again... */
        if (loaderData->netDev && (loaderData->netDev_set == 1)) {
            if (!strcmp(loaderData->netDev, devs[i]->device)) {
                foundDev = 1;
            } else if (ksMacAddr != NULL) {
                /* maybe it's a mac address */
                char * devmacaddr;
                devmacaddr = netlink_interfaces_mac2str(devs[i]->device);
                if ((devmacaddr != NULL) && !strcmp(ksMacAddr, devmacaddr)) {
                    foundDev = 1;
                    free(loaderData->netDev);
                    loaderData->netDev = devs[i]->device;
                }
            }
        }
    }
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

    if ((loaderData->netDev && (loaderData->netDev_set) == 1) &&
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

    startNewt(flags);

    if (max > 70)
        max = 70;

    /* JKFIXME: should display link status */
    deviceNum = 0;
    rc = newtWinMenu(_("Networking Device"), 
		     _("You have multiple network devices on this system. "
		       "Which would you like to install through?"), max, 10, 10,
		     deviceNums < 6 ? deviceNums : 6, deviceNames,
		     &deviceNum, _("OK"), _("Back"), NULL);
    if (rc == 2)
        return LOADER_BACK;

    loaderData->netDev = devices[deviceNum];

    /* turn off the non-active interface.  this should keep things from
     * breaking when we need the interface to do the install as long as
     * you keep using that device */
    for (i = 0; devs[i]; i++) {
        if (strcmp(loaderData->netDev, devices[i]))
            if (!FL_TESTING(flags))
                pumpDisableInterface(devs[i]->device);
    }

    return LOADER_OK;
}

/* JKFIXME: bad name.  this function brings up networking early on a 
 * kickstart install so that we can do things like grab the ks.cfg from
 * the network */
int kickstartNetworkUp(struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr,
                       int flags) {
    int rc;

    initLoopback();

    memset(netCfgPtr, 0, sizeof(*netCfgPtr));
    netCfgPtr->isDynamic = 1;

    do {
        /* this is smart and does the right thing based on whether or not
         * we have ksdevice= specified */
        rc = chooseNetworkInterface(loaderData, flags);
        
        if (rc == LOADER_ERROR) {
            /* JKFIXME: ask for a driver disk? */
            logMessage(ERROR, "no network drivers for doing kickstart");
            return -1;
        } else if (rc == LOADER_BACK) {
            return -1;
        }

	/* insert device into pump structure */
	strcpy(netCfgPtr->dev.device, loaderData->netDev);

        break;
    } while (1);

    /* we don't want to end up asking about interface more than once
     * if we're in a kickstart-ish case (#100724) */
    loaderData->netDev_set = 1;

    /* JKFIXME: this is kind of crufty, we depend on the fact that the
     * ip is set and then just get the network up.  we should probably
     * add a way to do asking about static here and not be such a hack */
    if (!loaderData->ip) {
        loaderData->ip = strdup("dhcp");
    } 
    loaderData->ipinfo_set = 1;

    setupNetworkDeviceConfig(netCfgPtr, loaderData, flags);

    rc = readNetConfig(loaderData->netDev, netCfgPtr, loaderData->netCls, 
                       flags);
    if ((rc == LOADER_BACK) || (rc == LOADER_ERROR)) {
        logMessage(ERROR, "unable to setup networking");
        return -1;
    }

    return 0;
}
