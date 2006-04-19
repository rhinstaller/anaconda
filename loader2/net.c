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

#include <arpa/inet.h>
#include <errno.h>
#include <popt.h>
#include <resolv.h>
#include <net/if.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "../isys/dns.h"
#include "../isys/isys.h"
#include "../isys/net.h"
#include "../isys/getmacaddr.h"

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

static void ipCallback(newtComponent co, void * dptr) {
    struct intfconfig_s * data = dptr;
    struct in_addr ipaddr, nmaddr, addr;
    char * ascii;
    int broadcast, network;

    if (co == data->ipEntry) {
        if (strlen(data->ip) && !strlen(data->nm)) {
            if (inet_aton(data->ip, &ipaddr)) {
                ipaddr.s_addr = ntohl(ipaddr.s_addr);
                ascii = "255.255.255.0";
                newtEntrySet(data->nmEntry, ascii, 1);
            }
        }
    } else if (co == data->nmEntry) {
        if (!strlen(data->ip) || !strlen(data->nm)) return;
        if (!inet_aton(data->ip, &ipaddr)) return;
        if (!inet_aton(data->nm, &nmaddr)) return;

        network = ipaddr.s_addr & nmaddr.s_addr;
        broadcast = (ipaddr.s_addr & nmaddr.s_addr) | (~nmaddr.s_addr);

        if (!strlen(data->gw)) {
            addr.s_addr = htonl(ntohl(broadcast) - 1);
            newtEntrySet(data->gwEntry, inet_ntoa(addr), 1);
        }

        if (!strlen(data->ns)) {
            addr.s_addr = htonl(ntohl(network) + 1);
            newtEntrySet(data->nsEntry, inet_ntoa(addr), 1);
        }
    }
}

static void fillInIpInfo(struct networkDeviceConfig * cfg) {
    int32 * i;
    char * nm;
   
    if (!(cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)) {
        i = (int32 *) &cfg->dev.ip;

        nm = "255.255.255.0";

        inet_aton(nm, &cfg->dev.netmask);
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
    int tries = 0;

    /* try to wait for a valid link -- if the status is unknown or
     * up continue, else sleep for 1 second and try again for up
     * to five times */
    logMessage("waiting for link...");

    /* Networks with STP set up will give link when the port
     * is isolated from the network, and won't forward packets
     * until they decide we're not a switch. */
    sleep(post_link_sleep);

    while (tries < num_link_checks) {
      if (get_link_status(dev) != 0)
            break;
        sleep(1);
        tries++;
    }
    logMessage("%d seconds.", tries);
    if (tries < num_link_checks)
        return 0;
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
                logMessage("Unknown duplex setting: %s", option + 7);
            option = strtok(NULL, " ");
        } else if (!strncmp("speed", option, 5)) {
            if (!strncmp(option + 6, "1000", 4))
                speed = ETHTOOL_SPEED_1000;
            else if (!strncmp(option + 6, "100", 3))
                speed = ETHTOOL_SPEED_100;
            else if (!strncmp(option + 6, "10", 2))
                speed = ETHTOOL_SPEED_10;
            else
                logMessage("Unknown speed setting: %s", option + 6);
            option = strtok(NULL, " ");
        } else {
            logMessage("Unknown ethtool setting: %s", option);
        }
        option = strtok(NULL, " ");
    }
    setEthtoolSettings(loaderData->netDev, speed, duplex);
    free(buf);
}

void initLoopback(void) {
    struct pumpNetIntf dev;

    strcpy(dev.device, "lo");
    inet_aton("127.0.0.1", &dev.ip);
    inet_aton("255.0.0.0", &dev.netmask);
    inet_aton("127.0.0.0", &dev.network);
    dev.set = PUMP_INTFINFO_HAS_NETMASK | PUMP_INTFINFO_HAS_IP
                | PUMP_INTFINFO_HAS_NETWORK;

    pumpSetupInterface(&dev);
}

static void dhcpBoxCallback(newtComponent co, void * ptr) {
    struct intfconfig_s * c = ptr;

    newtEntrySetFlags(c->ipEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->gwEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nmEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nsEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
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

        if (ns && *ns && !inet_aton(ns, &cfg->dev.dnsServers[0])) {
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
    logMessage("loaderData->ipinfo_set = %d", loaderData->ipinfo_set);
    logMessage("loaderData->ip         = %s", loaderData->ip);
    logMessage("loaderData->netmask    = %s", loaderData->netmask);
    logMessage("loaderData->gateway    = %s", loaderData->gateway);
    logMessage("loaderData->dns        = %s", loaderData->dns);
    logMessage("loaderData->hostname   = %s", loaderData->hostname);
    logMessage("loaderData->noDns      = %d", loaderData->noDns);
    logMessage("loaderData->netDev_set = %d", loaderData->netDev_set);
    logMessage("loaderData->netDev     = %s", loaderData->netDev);
}

/* given loader data from kickstart, populate network configuration struct */
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData, 
                              int flags) {
    struct in_addr addr;
    char * c;

    /* set to 1 to get ks network struct logged */
#if 0
    printLoaderDataIPINFO(loaderData);
#endif

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->ip) {
        /* this is how we specify dhcp */
        if (!strncmp(loaderData->ip, "dhcp", 4)) {
            char * chptr;

            /* JKFIXME: this soooo doesn't belong here.  and it needs to
             * be broken out into a function too */
            logMessage("sending dhcp request through device %s", loaderData->netDev);

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
                chptr = pumpDhcpRun(loaderData->netDev, 0, 0, NULL, &cfg->dev, NULL);
            } else {
                chptr = NULL;
            }

            if (!FL_CMDLINE(flags))
                newtPopWindow();

            if (chptr) {
                logMessage("pump told us: %s", chptr);
                return;
            }
            
            cfg->isDynamic = 1;
            cfg->preset = 1;
        } else if (inet_aton(loaderData->ip, &addr)) {
            cfg->dev.ip = addr;
            cfg->dev.set |= PUMP_INTFINFO_HAS_IP;
            cfg->isDynamic = 0;
            cfg->preset = 1;
        }
    }

    if (loaderData->netmask && (inet_aton(loaderData->netmask, &addr))) {
        cfg->dev.netmask = addr;
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (loaderData->gateway && (inet_aton(loaderData->gateway, &addr))) {
        cfg->dev.gateway = addr;
        cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
    }

    if (loaderData->dns) {
        char * buf;
        buf = strdup(loaderData->dns);

        /* Scan the dns parameter for multiple comma-separated IP addresses */
         c = strtok(buf, ",");  
         while ((cfg->dev.numDns < MAX_DNS_SERVERS) && (c != NULL) && 
                (inet_aton(c,&addr))) {
             cfg->dev.dnsServers[cfg->dev.numDns] = addr;
             cfg->dev.numDns++;
             logMessage("adding %s", inet_ntoa(addr));
             c = strtok(NULL, ",");
         }
         logMessage("dnsservers is %s", loaderData->dns);
         if (cfg->dev.numDns)
             cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
    }

    if (loaderData->hostname) {
        logMessage("setting specified hostname of %s", loaderData->hostname);
        cfg->dev.hostname = strdup(loaderData->hostname);
        cfg->dev.set |= PUMP_NETINFO_HAS_HOSTNAME;
    }

    if (loaderData->mtu) {
        cfg->dev.mtu = loaderData->mtu;
        cfg->dev.set |= PUMP_INTFINFO_HAS_MTU;
    }

    if (loaderData->ptpaddr && (inet_aton(loaderData->ptpaddr, &addr))) {
        cfg->dev.ptpaddr = addr;
        cfg->dev.set |= PUMP_INTFINFO_HAS_PTPADDR;
    }

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    cfg->noDns = loaderData->noDns;
}

int readNetConfig(char * device, struct networkDeviceConfig * cfg, int flags) {
    newtComponent text, f, okay, back, answer, dhcpCheckbox;
    newtGrid grid, subgrid, buttons;
    struct networkDeviceConfig newCfg;
    struct intfconfig_s c;
    int i;
    struct in_addr addr;
    char dhcpChoice;
    char * chptr;

    memset(&c, 0, sizeof(c));

    /* JKFIXME: we really need a way to override this and be able to change
     * our network config */
    if (!FL_TESTING(flags) && cfg->preset) {
        logMessage("doing kickstart... setting it up");
        configureNetwork(cfg);
        findHostAndDomain(cfg, flags);

        if (!cfg->noDns)
            writeResolvConf(cfg);
        return LOADER_NOOP;
    }        

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

    if (cfg->dev.set & PUMP_INTFINFO_HAS_IP)
        newtEntrySet(c.ipEntry, inet_ntoa(cfg->dev.ip), 1);

    if (cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)
        newtEntrySet(c.nmEntry, inet_ntoa(cfg->dev.netmask), 1);
    
    if (cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)
        newtEntrySet(c.gwEntry, inet_ntoa(cfg->dev.gateway), 1);
    
    if (cfg->dev.numDns)
        newtEntrySet(c.nsEntry, inet_ntoa(cfg->dev.dnsServers[0]), 1);

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
            if (*c.ip && inet_aton(c.ip, &addr)) {
                i++;
                newCfg.dev.ip = addr;
                newCfg.dev.set |= PUMP_INTFINFO_HAS_IP;
            }

            if (*c.nm && inet_aton(c.nm, &addr)) {
                i++;
                newCfg.dev.netmask = addr;
                newCfg.dev.set |= PUMP_INTFINFO_HAS_NETMASK;
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
                chptr = pumpDhcpRun(device, 0, 0, NULL, &newCfg.dev, NULL);
                newtPopWindow();
            } else {
                chptr = NULL;
            }

            if (!chptr) {
                newCfg.isDynamic = 1;
                if (!(newCfg.dev.set & PUMP_NETINFO_HAS_DNS)) {
                    logMessage("pump worked, but didn't return a DNS server");
                    i = getDnsServers(&newCfg);
                    i = i ? 0 : 2;
                } else {
                    i = 2; 
                }
            } else {
                logMessage("pump told us: %s", chptr);
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
        if (c.gw && *c.gw && inet_aton(c.gw, &addr)) {
            cfg->dev.gateway = addr;
            cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
        }
    }

    if (!(cfg->dev.numDns)) {
        if (c.ns && *c.ns && inet_aton(c.ns, &addr)) {
            cfg->dev.dnsServers[0] = addr;
            cfg->dev.numDns = 1;
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

int configureNetwork(struct networkDeviceConfig * dev) {
    char *rc;

    rc = pumpSetupInterface(&dev->dev);
    if (rc)
	logMessage("result of pumpSetupInterface is %s", rc);

    if (dev->dev.set & PUMP_NETINFO_HAS_GATEWAY)
        pumpSetupDefaultGateway(&dev->dev.gateway);

    /* we need to wait for a link after setting up the interface as some
     * switches decide to reconfigure themselves after that (#115825)
     */
    waitForLink((char *)&dev->dev.device);
    return 0;
}

int writeNetInfo(const char * fn, struct networkDeviceConfig * dev,
                 struct knownDevices * kd) {
    FILE * f;
    int i;

    for (i = 0; i < kd->numKnown; i++)
        if (!strcmp(kd->known[i].name, dev->dev.device)) break;
    
    if (!(f = fopen(fn, "w"))) return -1;

    fprintf(f, "DEVICE=%s\n", dev->dev.device);

    /* JKFIXME: this used kd->known[i].code == CODE_PCMCIA to toggle onboot */
    fprintf(f, "ONBOOT=yes\n");

    if (dev->isDynamic) {
        fprintf(f, "BOOTPROTO=dhcp\n");
    } else {
        fprintf(f, "BOOTPROTO=static\n");
        fprintf(f, "IPADDR=%s\n", inet_ntoa(dev->dev.ip));
        fprintf(f, "NETMASK=%s\n", inet_ntoa(dev->dev.netmask));
        if (dev->dev.set & PUMP_NETINFO_HAS_GATEWAY)
            fprintf(f, "GATEWAY=%s\n", inet_ntoa(dev->dev.gateway));
        if (dev->dev.set & PUMP_INTFINFO_HAS_BROADCAST)
          fprintf(f, "BROADCAST=%s\n", inet_ntoa(dev->dev.broadcast));    
    }

    if (dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)
        fprintf(f, "HOSTNAME=%s\n", dev->dev.hostname);
    if (dev->dev.set & PUMP_NETINFO_HAS_DOMAIN)
        fprintf(f, "DOMAIN=%s\n", dev->dev.domain);
    if (dev->dev.set & PUMP_INTFINFO_HAS_MTU)
        fprintf(f, "MTU=%d\n", dev->dev.mtu);
    if (dev->dev.set & PUMP_INTFINFO_HAS_PTPADDR)
        fprintf(f, "REMIP=%s\n", inet_ntoa(dev->dev.ptpaddr));
    
    fclose(f);

    return 0;
}

int writeResolvConf(struct networkDeviceConfig * net) {
    char * filename = "/etc/resolv.conf";
    FILE * f;
    int i;
#if defined(__s390__) || defined(__s390x__)
    return 0;
#endif

    if (!(net->dev.set & PUMP_NETINFO_HAS_DOMAIN) && !net->dev.numDns)
        return LOADER_ERROR;

    f = fopen(filename, "w");
    if (!f) {
        logMessage("Cannot create %s: %s\n", filename, strerror(errno));
        return LOADER_ERROR;
    }

    if (net->dev.set & PUMP_NETINFO_HAS_DOMAIN)
        fprintf(f, "search %s\n", net->dev.domain);

    for (i = 0; i < net->dev.numDns; i++) 
        fprintf(f, "nameserver %s\n", inet_ntoa(net->dev.dnsServers[i]));

    fclose(f);

    res_init();         /* reinit the resolver so DNS changes take affect */

    return 0;
}

int findHostAndDomain(struct networkDeviceConfig * dev, int flags) {
    char * name, * chptr;

    if (!FL_TESTING(flags)) {
        writeResolvConf(dev);
    }

    if (!(dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)) {
        if (!FL_CMDLINE(flags))
            winStatus(50, 3, _("Hostname"), 
                      _("Determining host name and domain..."));
        else
            printf("Determining host name and domain...\n");

        name = mygethostbyaddr(inet_ntoa(dev->dev.ip));

        if (!FL_CMDLINE(flags))
            newtPopWindow();

        if (!name) {
            logMessage("reverse name lookup failed");
            return 1;
        }

        logMessage("reverse name lookup worked");

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

void setKickstartNetwork(struct knownDevices * kd, 
                         struct loaderData_s * loaderData, int argc, 
                         char ** argv, int * flagsPtr) {
    char * arg, * bootProto = NULL, * device = NULL, *ethtool = NULL;
    int noDns = 0, rc;
    poptContext optCon;

    struct poptOption ksOptions[] = {
        { "bootproto", '\0', POPT_ARG_STRING, &bootProto, 0 },
        { "device", '\0', POPT_ARG_STRING, &device, 0 },
        { "gateway", '\0', POPT_ARG_STRING, NULL, 'g' },
        { "ip", '\0', POPT_ARG_STRING, NULL, 'i' },
        { "nameserver", '\0', POPT_ARG_STRING, NULL, 'n' },
        { "netmask", '\0', POPT_ARG_STRING, NULL, 'm' },
        { "nodns", '\0', POPT_ARG_NONE, &noDns, 0 },
        { "hostname", '\0', POPT_ARG_STRING, NULL, 'h'},
        { "ethtool", '\0', POPT_ARG_STRING, &ethtool, 0 },
        { 0, 0, 0, 0, 0 }
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

    if (device) {
        loaderData->netDev = strdup(device);
        loaderData->netDev_set = 1;
    }

    if (ethtool) {
        if (loaderData->ethtool)
            free(loaderData->ethtool);
        loaderData->ethtool = strdup(ethtool);
        free(ethtool);
    }

    if (noDns) {
        loaderData->noDns = 1;
    }
}

/* if multiple interfaces get one to use from user.   */
/* NOTE - uses kickstart data available in loaderData */
int chooseNetworkInterface(struct knownDevices * kd, 
                           struct loaderData_s * loaderData,
                           int flags) {
    int i, rc, max = 40;
    int deviceNums = 0;
    int deviceNum;
    char ** devices;
    char ** deviceNames;
    int foundDev = 0;

    /* JKFIXME: this is a lot bigger than it has to be.. */
    devices = alloca((kd->numKnown + 1) * sizeof(*devices));
    deviceNames = alloca((kd->numKnown + 1) * sizeof(*devices));
    for (i = 0; i < kd->numKnown; i++) {
        if (kd->known[i].class != CLASS_NETWORK)
            continue;

        if (kd->known[i].model) {
                deviceNames[deviceNums] = alloca(strlen(kd->known[i].name) +
                                          strlen(kd->known[i].model) + 4);
                sprintf(deviceNames[deviceNums],"%s - %s",
                        kd->known[i].name, kd->known[i].model);
                if (strlen(deviceNames[deviceNums]) > max)
                        max = strlen(deviceNames[deviceNums]);
                devices[deviceNums++] = kd->known[i].name;
        } else {
            devices[deviceNums] = kd->known[i].name;
            deviceNames[deviceNums++] = kd->known[i].name;
        }

        /* this device has been set and we don't really need to ask 
         * about it again... */
        if (loaderData->netDev && (loaderData->netDev_set == 1)) {
            if (!strcmp(loaderData->netDev, kd->known[i].name)) {
                foundDev = 1;
            } else {
                /* maybe it's a mac address */
                char * mac1, * mac2;
                mac1 = sanitizeMacAddr(loaderData->netDev);
                mac2 = sanitizeMacAddr(getMacAddr(kd->known[i].name));
                if ((mac1 != NULL) && (mac2 != NULL) &&
                    !strcmp(mac1, mac2)) {
                    foundDev = 1;
                    free(loaderData->netDev);
                    loaderData->netDev = kd->known[i].name;
                }
            }
        }
    }
    if (foundDev == 1)
        return LOADER_NOOP;

    devices[deviceNums] = NULL;
    deviceNames[deviceNums] = NULL;

    /* ASSERT: we should *ALWAYS* have a network device when we get here */
    if (!deviceNums) {
        logMessage("ASSERT: no network device in chooseNetworkInterface");
        return LOADER_ERROR;
    }

    /* JKFIXME: if we only have one interface and it doesn't have link,
     * do we go ahead? */
    if (deviceNums == 1) {
        loaderData->netDev = devices[0];
        return LOADER_NOOP;
    }

    if ((loaderData->netDev && (loaderData->netDev_set) == 1) &&
        !strcmp(loaderData->netDev, "link")) {
        logMessage("looking for first netDev with link");
        for (rc = 0; rc < 5; rc++) {
            for (i = 0; i < deviceNums; i++) {
                if (get_link_status(devices[i]) == 1) {
                    loaderData->netDev = devices[i];
                    logMessage("%s has link, using it", devices[i]);
                    return LOADER_NOOP;
                }
            }
            sleep(1);
        }
        logMessage("wanted netdev with link, but none present.  prompting");
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
    for (i = 0; i < deviceNums; i++) {
        if (strcmp(loaderData->netDev, devices[i]))
            pumpDisableInterface(kd->known[i].name);
    }

    return LOADER_OK;
}

/* JKFIXME: bad name.  this function brings up networking early on a 
 * kickstart install so that we can do things like grab the ks.cfg from
 * the network */
int kickstartNetworkUp(struct knownDevices * kd, 
                       struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr,
                       int flags) {
    int rc;

    initLoopback();

    memset(netCfgPtr, 0, sizeof(*netCfgPtr));
    netCfgPtr->isDynamic = 1;

    do {
        /* this is smart and does the right thing based on whether or not
         * we have ksdevice= specified */
        rc = chooseNetworkInterface(kd, loaderData, flags);
        
        if (rc == LOADER_ERROR) {
            /* JKFIXME: ask for a driver disk? */
            logMessage("no network drivers for doing kickstart");
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

    rc = readNetConfig(loaderData->netDev, netCfgPtr, flags);
    if ((rc == LOADER_BACK) || (rc == LOADER_ERROR)) {
        logMessage("unable to setup networking");
        return -1;
    }

    return 0;
}
