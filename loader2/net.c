/*
 * Copyright 1999-2006 Red Hat, Inc.
 *
 * David Cantrell <dcantrell@redhat.com>
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
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
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
#include <netinet/in.h>
#include <netlink/netlink.h>
#include <netlink/route/addr.h>
#include <netlink/route/link.h>

#include "../isys/dns.h"
#include "../isys/isys.h"
#include "../isys/net.h"
#include "../isys/wireless.h"
#include "../isys/nl.h"
#include "../isys/str.h"

#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "windows.h"

#if !defined(__s390__) && !defined(__s390x__)
#include "ibft.h"
#endif

/* boot flags */
extern uint64_t flags;

char *netServerPrompt = \
    N_("Please enter the following information:\n"
       "\n"
       "    o the name or IP number of your %s server\n" 
       "    o the directory on that server containing\n" 
       "      %s for your architecture\n");

char *nfsServerPrompt = \
    N_("Please enter the following information:\n"
       "\n"
       "    o the name or IP number of your NFS server\n" 
       "    o the directory on that server containing\n" 
       "      %s for your architecture\n"
       "    o optionally, parameters for the NFS mount\n");

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

        cidr = atoi(data->cidr4);
        upper = 32;
    } else if (co == data->cidr6Entry) {
        if (data->cidr6 == NULL && data->ipv6 == NULL)
            return;

        cidr = atoi(data->cidr6);
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
            i = atoi(octet);

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

static int waitForLink(char * dev) {
    extern int num_link_checks;
    extern int post_link_sleep;
    int tries = 0;

    /* try to wait for a valid link -- if the status is unknown or
     * up continue, else sleep for 1 second and try again for up
     * to five times */
    logMessage(DEBUGLVL, "waiting for link %s...", dev);

    while (tries < num_link_checks) {
      if (get_link_status(dev) != 0)
            break;
        sleep(1);
        tries++;
    }

    logMessage(DEBUGLVL, "   %d seconds.", tries);

    if (tries < num_link_checks) {
        /* Networks with STP set up will give link when the port
         * is isolated from the network, and won't forward packets
         * until they decide we're not a switch. */
        logMessage(DEBUGLVL, "sleep (nicdelay) for %d secs first",
                   post_link_sleep);
        sleep(post_link_sleep);
        logMessage(DEBUGLVL, "continuing...");
        return 0;
    }

    logMessage(WARNING, "    no network link detected on %s", dev);
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
    struct ifreq req;
    int s;

    s = socket(AF_INET, SOCK_DGRAM, 0);

    memset(&req, 0, sizeof(req));
    strcpy(req.ifr_name, "lo");

    if (ioctl(s, SIOCGIFFLAGS, &req)) {
        logMessage(LOG_ERR, "ioctl SIOCGIFFLAGS failed: %d %s\n", errno,
                   strerror(errno));
        close(s);
        return;
    }

    req.ifr_flags |= (IFF_UP | IFF_RUNNING);
    if (ioctl(s, SIOCSIFFLAGS, &req)) {
        logMessage(LOG_ERR, "ioctl SIOCSIFFLAGS failed: %d %s\n", errno,
                   strerror(errno));
        close(s);
        return;
    }

    close(s);

    return;
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
    struct in_addr addr;
    struct in6_addr addr6;
    const char * ns = "";
    struct newtWinEntry entry[] = { { N_("Nameserver IP"), &ns, 0 },
                                      { NULL, NULL, 0 } };

    do {
        rc = newtWinEntries(_("Missing Nameserver"), 
                _("Your IP address request returned configuration "
                  "information, but it did not include a nameserver address. "
                  "If you do not have this information, you can leave "
                  "the field blank and the install will continue."),
                61, 0, 0, 45, entry, _("OK"), _("Back"), NULL);

        if (rc == 2) return LOADER_BACK;

        rc = 0;
        if (!ns || !*ns) {
            cfg->dev.numDns = 0;
            break;
        } else {
            if (inet_pton(AF_INET, ns, &addr) >= 1)
                cfg->dev.dnsServers[0] = ip_addr_in(&addr);
            else if (inet_pton(AF_INET6, ns, &addr6) >= 1)
                cfg->dev.dnsServers[0] = ip_addr_in6(&addr6);
            else
                rc = 2;
        }

        if (rc) {
            newtWinMessage(_("Invalid IP Information"), _("Retry"),
                           _("You entered an invalid IP address."));
        } else {
            cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
            cfg->dev.numDns = 1;
        }
    } while (rc == 2);

    return LOADER_OK;
}

void printLoaderDataIPINFO(struct loaderData_s *loaderData) {
    logMessage(DEBUGLVL, "loaderData->ipinfo_set   = |%d|", loaderData->ipinfo_set);
    logMessage(DEBUGLVL, "loaderData->ip           = |%s|", loaderData->ip);
    logMessage(DEBUGLVL, "loaderData->ipv6info_set = |%d|", loaderData->ipv6info_set);
    logMessage(DEBUGLVL, "loaderData->ipv6         = |%s|", loaderData->ipv6);
    logMessage(DEBUGLVL, "loaderData->dhcpTimeout  = |%d|", loaderData->dhcpTimeout);
    logMessage(DEBUGLVL, "loaderData->netmask      = |%s|", loaderData->netmask);
    logMessage(DEBUGLVL, "loaderData->gateway      = |%s|", loaderData->gateway);
    logMessage(DEBUGLVL, "loaderData->dns          = |%s|", loaderData->dns);
    logMessage(DEBUGLVL, "loaderData->hostname     = |%s|", loaderData->hostname);
    logMessage(DEBUGLVL, "loaderData->noDns        = |%d|", loaderData->noDns);
    logMessage(DEBUGLVL, "loaderData->netDev_set   = |%d|", loaderData->netDev_set);
    logMessage(DEBUGLVL, "loaderData->netDev       = |%s|", loaderData->netDev);
    logMessage(DEBUGLVL, "loaderData->netCls_set   = |%d|", loaderData->netCls_set);
    logMessage(DEBUGLVL, "loaderData->netCls       = |%s|", loaderData->netCls);
}


#ifndef MAX_DNS_SERVERS
#define MAX_DNS_SERVERS MAXNS
#endif

/* given loader data from kickstart, populate network configuration struct */
void setupNetworkDeviceConfig(struct networkDeviceConfig * cfg, 
                              struct loaderData_s * loaderData) {
    int dhcp_failed = 0;
    struct in_addr addr;
    struct in6_addr addr6;
    char *c;
    enum{USE_DHCP, USE_IBFT_STATIC, USE_STATIC} configMode = USE_STATIC;

    /* set to 1 to get ks network struct logged */
#if 0
    printLoaderDataIPINFO(loaderData);
#endif

    if (loaderData->ethtool) {
        parseEthtoolSettings(loaderData);
    }

    if (loaderData->netCls_set) {
        cfg->vendor_class = loaderData->netCls;
    } else {
        cfg->vendor_class = NULL;
    }

    if (loaderData->ipinfo_set && loaderData->ip != NULL) {
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

#if !defined(__s390__) && !defined(__s390x__)
	if (!strncmp(loaderData->ip, "ibft", 4)) {
	    char *devmacaddr = nl_mac2str(loaderData->netDev);
	    configMode = USE_IBFT_STATIC;
            cfg->isiBFT = 1;

	    /* Problems with getting the info from iBFT or iBFT uses dhcp*/
	    if(!devmacaddr || !ibft_present() || ibft_iface_dhcp()){
		configMode = USE_DHCP;
                logMessage(INFO, "iBFT is not present or is configured to use DHCP");
	    }
	    /* MAC address doesn't match */
	    else if(strcasecmp(ibft_iface_mac(), devmacaddr)){
		configMode = USE_DHCP;
                logMessage(INFO, "iBFT doesn't know what NIC to use - falling back to DHCP");
	    }

	    if(devmacaddr) free(devmacaddr);
	}
#endif

        /* this is how we specify dhcp */
        if (!strncmp(loaderData->ip, "dhcp", 4)) {
	    configMode = USE_DHCP;
	}

#if !defined(__s390__) && !defined(__s390x__)
	if (configMode == USE_IBFT_STATIC){
	    /* Problems with getting the info from iBFT */
	    if(!ibft_iface_ip() || !ibft_iface_mask() || !ibft_iface_gw()){
		configMode = USE_DHCP;
                logMessage(INFO, "iBFT doesn't have necessary information - falling back to DHCP");
	    }
	    else{
		/* static setup from iBFT table */
		if(inet_pton(AF_INET, ibft_iface_ip(), &addr)>=1){
		    cfg->dev.ip = ip_addr_in(&addr);
		    cfg->dev.ipv4 = ip_addr_in(&addr);
		    cfg->dev.set |= PUMP_INTFINFO_HAS_IP|PUMP_INTFINFO_HAS_IPV4_IP;
		    cfg->isDynamic = 0;
		    logMessage(INFO, "iBFT: setting IP to %s", ibft_iface_ip());
		}
		
		if(inet_pton(AF_INET, ibft_iface_mask(), &addr)>=1){
		    cfg->dev.netmask = ip_addr_in(&addr);
		    cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
		    logMessage(INFO, "iBFT: setting NETMASK to %s", ibft_iface_mask());
		}
        
		if(inet_pton(AF_INET, ibft_iface_gw(), &addr)>=1){
		    cfg->dev.gateway = ip_addr_in(&addr);
		    cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
		    logMessage(INFO, "iBFT: setting GW to %s", ibft_iface_gw());
		}
                
		if(cfg->dev.numDns<MAX_DNS_SERVERS){
		    if(ibft_iface_dns1() && inet_pton(AF_INET, ibft_iface_dns1(), &addr)>=1){
			cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in(&addr);
			cfg->dev.numDns++;
			logMessage(INFO, "iBFT: setting DNS1 to %s", ibft_iface_dns1());
		    }
		}
		if(cfg->dev.numDns<MAX_DNS_SERVERS){
		    if(ibft_iface_dns2() && inet_pton(AF_INET, ibft_iface_dns2(), &addr)>=1){
			cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in(&addr);
			cfg->dev.numDns++;
			logMessage(INFO, "iBFT: setting DNS2 to %s", ibft_iface_dns2());
		    }
		}
	    
		if (cfg->dev.numDns)
		    cfg->dev.set |= PUMP_NETINFO_HAS_DNS;

		cfg->preset = 1;
	    }
	}
#endif
	
	if (configMode == USE_IBFT_STATIC){
	    /* do nothing, already done */
	} else if (configMode == USE_DHCP) {
            /* JKFIXME: this soooo doesn't belong here.  and it needs to
             * be broken out into a function too */
            logMessage(INFO, "sending dhcp request through device %s",
                       loaderData->netDev);

            if (!FL_CMDLINE(flags)) {
                startNewt();
                winStatus(55, 3, NULL, 
                          _("Sending request for IP information for %s..."), 
                          loaderData->netDev, 0);
            } else {
                printf("Sending request for IP information for %s...\n", 
                       loaderData->netDev);
            }

            if (!FL_TESTING(flags)) {
                waitForLink(loaderData->netDev);
                cfg->noDns = loaderData->noDns;
                cfg->dhcpTimeout = loaderData->dhcpTimeout;
                dhcp_failed = doDhcp(cfg);
            }

            if (!FL_CMDLINE(flags))
                newtPopWindow();

            if (dhcp_failed) {
                return;
            }

            cfg->isDynamic = 1;
            cfg->preset = 1;
        } else if (inet_pton(AF_INET, loaderData->ip, &addr) >= 1) {
            cfg->dev.ip = ip_addr_in(&addr);
            cfg->dev.ipv4 = ip_addr_in(&addr);
            cfg->dev.set |= PUMP_INTFINFO_HAS_IP|PUMP_INTFINFO_HAS_IPV4_IP;
            cfg->isDynamic = 0;
            cfg->preset = 1;
        } else if (inet_pton(AF_INET6, loaderData->ip, &addr6) >= 1) {
            cfg->dev.ip = ip_addr_in6(&addr6);
            cfg->dev.ipv6 = ip_addr_in6(&addr6);
            cfg->dev.set |= PUMP_INTFINFO_HAS_IP|PUMP_INTFINFO_HAS_IPV6_IP;
            cfg->isDynamic = 0;
            cfg->preset = 1;
        } else { /* invalid ip information, disable the setting of ip info */
            loaderData->ipinfo_set = 0;
            cfg->isDynamic = 0;
            loaderData->ip = NULL;
        }
    }

    if (loaderData->netmask && (inet_pton(AF_INET, loaderData->netmask, &addr) >= 1)) {
        cfg->dev.netmask = ip_addr_in(&addr);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (loaderData->netmask && (inet_pton(AF_INET6, loaderData->netmask, &addr6) >= 1)) {
        cfg->dev.netmask = ip_addr_in6(&addr6);
        cfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
    }

    if (loaderData->gateway && (inet_pton(AF_INET, loaderData->gateway, &addr) >= 1)) {
        cfg->dev.gateway = ip_addr_in(&addr);
        cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
    }

    if (loaderData->gateway && (inet_pton(AF_INET6, loaderData->gateway, &addr6) >= 1)) {
        cfg->dev.gateway = ip_addr_in6(&addr6);
        cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
    }

    if (loaderData->dns) {
        char * buf;
        char ret[48];
        buf = strdup(loaderData->dns);

        /* Scan the dns parameter for multiple comma-separated IP addresses */
        c = strtok(buf, ",");  
        while ((cfg->dev.numDns < MAX_DNS_SERVERS) && (c != NULL)) {
            if (inet_pton(AF_INET, c, &addr) >= 1) {
                cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in(&addr);
                cfg->dev.numDns++;
                inet_ntop(AF_INET, &addr, ret, INET_ADDRSTRLEN);
                logMessage(DEBUGLVL, "adding dns4 %s", ret);
                c = strtok(NULL, ",");
            } else if (inet_pton(AF_INET6, c, &addr6) >= 1) {
                cfg->dev.dnsServers[cfg->dev.numDns] = ip_addr_in6(&addr6);
                cfg->dev.numDns++;
                inet_ntop(AF_INET6, &addr6, ret, INET6_ADDRSTRLEN);
                logMessage(DEBUGLVL, "adding dns6 %s", ret);
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

    if (loaderData->layer2) {
        cfg->layer2 = strdup(loaderData->layer2);
    }

    if (loaderData->portno) {
        cfg->portno = strdup(loaderData->portno);
    }

    if (loaderData->macaddr) {
        cfg->macaddr = strdup(loaderData->macaddr);
    }

    cfg->noDns = loaderData->noDns;
    cfg->dhcpTimeout = loaderData->dhcpTimeout;
}

int readNetConfig(char * device, struct networkDeviceConfig * cfg,
                  char * dhcpclass, int methodNum, int query) {
    struct networkDeviceConfig newCfg;
    int ret;
    int i = 0;
    struct netconfopts opts;
    struct in_addr addr, nm, nw;
    struct in6_addr addr6;
    struct intfconfig_s ipcomps;

    memset(&ipcomps, '\0', sizeof(ipcomps));
    ipcomps.ipv4 = NULL;
    ipcomps.ipv6 = NULL;
    ipcomps.cidr4 = NULL;
    ipcomps.cidr6 = NULL;
    ipcomps.gw = NULL;
    ipcomps.ns = NULL;

    /* init opts */
    opts.ipv4Choice = 0;
    opts.ipv6Choice = 0;

    /* init newCfg */
    memset(&newCfg, '\0', sizeof(newCfg));
    strcpy(newCfg.dev.device, device);
    newCfg.essid = NULL;
    newCfg.wepkey = NULL;
    newCfg.isDynamic = cfg->isDynamic;
    newCfg.isiBFT = cfg->isiBFT;
    newCfg.noDns = cfg->noDns;
    newCfg.dhcpTimeout = cfg->dhcpTimeout;
    newCfg.preset = cfg->preset;
    if (dhcpclass) {
        newCfg.vendor_class = strdup(dhcpclass);
    } else {
        newCfg.vendor_class = NULL;
    }

    /* JKFIXME: we really need a way to override this and be able to change
     * our network config */
    if (!FL_TESTING(flags) && cfg->preset) {
        logMessage(INFO, "doing kickstart... setting it up");
        if (configureNetwork(cfg)) {
            newtWinMessage(_("Network Error"), _("Retry"),
                           _("There was an error configuring your network "
                             "interface."));
            return LOADER_BACK;
        }

        findHostAndDomain(cfg);

        if (!cfg->noDns)
            writeResolvConf(cfg);

        cfg->preset = 0;
        return LOADER_NOOP;
    }

    /* handle wireless device configuration */
    if (is_wireless_interface(device)) {
        logMessage(INFO, "%s is a wireless adapter", device);
        if (getWirelessConfig(cfg, device) == LOADER_BACK)
            return LOADER_BACK;

        if (cfg->essid != NULL)
            newCfg.essid = strdup(cfg->essid);

        if (cfg->wepkey != NULL)
            newCfg.wepkey = strdup(cfg->wepkey);
    } else {
        logMessage(INFO, "%s is not a wireless adapter", device);
    }

    /* dhcp/manual network configuration loop */
    i = 1;
    while (i == 1) {
        ret = configureTCPIP(device, cfg, &newCfg, &opts, methodNum, query);

        cfg->ipv4method = newCfg.ipv4method;
        cfg->ipv6method = newCfg.ipv6method;

        if (ret == LOADER_NOOP) {
            /* dhcp selected, proceed */
            i = 0;
        } else if (ret == LOADER_OK) {
            /* do manual configuration */
            ret = manualNetConfig(device, cfg, &newCfg, &ipcomps, &opts);

            if (ret == LOADER_BACK) {
                continue;
            } else if (ret == LOADER_OK) {
                i = 0;
            }
        } else if (ret == LOADER_BACK) {
            return LOADER_BACK;
        }
    }

    /* preserve extra dns servers for the sake of being nice */
    if (cfg->dev.numDns > newCfg.dev.numDns) {
        for (i = newCfg.dev.numDns; i < cfg->dev.numDns; i++) {
            memcpy(&newCfg.dev.dnsServers[i], &cfg->dev.dnsServers[i],
                sizeof (newCfg.dev.dnsServers[i]));
        }
        newCfg.dev.numDns = cfg->dev.numDns;
    }

    cfg->isDynamic = newCfg.isDynamic;
    cfg->isiBFT = newCfg.isiBFT;
    memcpy(&cfg->dev,&newCfg.dev,sizeof(newCfg.dev));

    if (!(cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)) {
        if (ipcomps.gw && *ipcomps.gw) {
            if (inet_pton(AF_INET, ipcomps.gw, &addr) >= 1) {
                cfg->dev.gateway = ip_addr_in(&addr);
                cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            } else if (inet_pton(AF_INET6, ipcomps.gw, &addr6) >= 1) {
                cfg->dev.gateway = ip_addr_in6(&addr6);
                cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            }
        }
    }

    /* calculate any missing IPv4 pieces */
    if (opts.ipv4Choice == NEWT_CHECKBOXTREE_SELECTED) {
        addr = ip_in_addr(&cfg->dev.ipv4);
        nm = ip_in_addr(&cfg->dev.netmask);

        if (!(cfg->dev.set & PUMP_INTFINFO_HAS_NETWORK)) {
            cfg->dev.network = ip_addr_v4(ntohl((addr.s_addr) & nm.s_addr));
            cfg->dev.set |= PUMP_INTFINFO_HAS_NETWORK;
        }

        if (!(cfg->dev.set & PUMP_INTFINFO_HAS_BROADCAST)) {
            nw = ip_in_addr(&cfg->dev.network);
            cfg->dev.broadcast = ip_addr_v4(ntohl(nw.s_addr | ~nm.s_addr));
            cfg->dev.set |= PUMP_INTFINFO_HAS_BROADCAST;
        }
    }

    /* make sure we don't have a dhcp_nic handle for static */
    if ((cfg->isDynamic == 0) && (cfg->dev.dhcp_nic != NULL)) {
        dhcp_nic_free(cfg->dev.dhcp_nic);
        cfg->dev.dhcp_nic = NULL;
    }

    /* dump some network debugging info */
    debugNetworkInfo(cfg);

    /* bring up the interface */
    if (!FL_TESTING(flags)) {
        if (configureNetwork(cfg)) {
            newtWinMessage(_("Network Error"), _("Retry"),
                           _("There was an error configuring your network "
                             "interface."));
            return LOADER_BACK;
        }

        findHostAndDomain(cfg);
        writeResolvConf(cfg);
    }

    return LOADER_OK;
}

int configureTCPIP(char * device, struct networkDeviceConfig * cfg,
                   struct networkDeviceConfig * newCfg,
                   struct netconfopts * opts, int methodNum,
                   int query) {
    int i = 0, z = 0, skipForm = 0, dhcp_failed = 0;
    newtComponent f, okay, back, answer;
    newtComponent ipv4Checkbox, ipv6Checkbox, v4Method[2], v6Method[3];
    newtGrid grid, checkgrid, buttons;

    /* UI WINDOW 1: ask for ipv4 choice, ipv6 choice, and conf methods */

    /* IPv4 checkbox */
    if (!opts->ipv4Choice) {
        if (FL_NOIPV4(flags) && !FL_IP_PARAM(flags))
            opts->ipv4Choice = NEWT_CHECKBOXTREE_UNSELECTED;
        else
            opts->ipv4Choice = NEWT_CHECKBOXTREE_SELECTED;
    }

    ipv4Checkbox = newtCheckbox(-1, -1, _("Enable IPv4 support"),
                                opts->ipv4Choice, NULL, &(opts->ipv4Choice));
    v4Method[0] = newtRadiobutton(-1, -1, DHCP_METHOD_STR, 1, NULL);
    v4Method[1] = newtRadiobutton(-1, -1, MANUAL_METHOD_STR, 0, v4Method[0]);

    /* IPv6 checkbox */
    if (!opts->ipv6Choice) {
        if (FL_NOIPV6(flags) && !FL_IPV6_PARAM(flags))
            opts->ipv6Choice = NEWT_CHECKBOXTREE_UNSELECTED;
        else
            opts->ipv6Choice = NEWT_CHECKBOXTREE_SELECTED;
    }

    ipv6Checkbox = newtCheckbox(-1, -1, _("Enable IPv6 support"),
                                opts->ipv6Choice, NULL, &(opts->ipv6Choice));
    v6Method[0] = newtRadiobutton(-1, -1, AUTO_METHOD_STR, 1, NULL);
    v6Method[1] = newtRadiobutton(-1, -1, DHCP_METHOD_STR, 0, v6Method[0]);
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
    if (opts->ipv4Choice == NEWT_CHECKBOXTREE_UNSELECTED)
        setMethodSensitivity(&v4Method, 2);

    if (opts->ipv6Choice == NEWT_CHECKBOXTREE_UNSELECTED)
        setMethodSensitivity(&v6Method, 3);

    for (i=0; i<2; i++) {
        if (i == cfg->ipv4method) {
            newtCheckboxSetValue(v4Method[i], NEWT_CHECKBOXTREE_SELECTED);
        } else {
            newtCheckboxSetValue(v4Method[i], NEWT_CHECKBOXTREE_UNSELECTED);
        }
    }

    for (i=0; i<3; i++) {
        if (i == cfg->ipv6method) {
            newtCheckboxSetValue(v6Method[i], NEWT_CHECKBOXTREE_SELECTED);
        } else {
            newtCheckboxSetValue(v6Method[i], NEWT_CHECKBOXTREE_UNSELECTED);
        }
    }

    /* If the user provided any of the following boot paramters, skip
     * prompting for network configuration information:
     *     ip=<val> ipv6=<val>
     *     noipv4 noipv6
     *     ip=<val> noipv6
     *     ipv6=<val> noipv4
     * we also skip this form for anyone doing a kickstart install,
     * but only if they also didn't specify --bootproto=query
     */
    if ((FL_IP_PARAM(flags) && FL_IPV6_PARAM(flags)) ||
        (FL_IP_PARAM(flags) && FL_NOIPV6(flags)) ||
        (FL_IPV6_PARAM(flags) && FL_NOIPV4(flags)) ||
        (FL_NOIPV4(flags) && FL_NOIPV6(flags)) ||
        (FL_IS_KICKSTART(flags) && !query)) {
        skipForm = 1;
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
            if (opts->ipv4Choice == NEWT_CHECKBOXTREE_UNSELECTED &&
                opts->ipv6Choice == NEWT_CHECKBOXTREE_UNSELECTED) {
                newtWinMessage(_("Missing Protocol"), _("Retry"),
                               _("You must select at least one protocol (IPv4 "
                                 "or IPv6)."));
                continue;
            }

            /* NFS only works over IPv4 */
            if (opts->ipv4Choice == NEWT_CHECKBOXTREE_UNSELECTED &&
                methodNum == METHOD_NFS) {
                newtWinMessage(_("IPv4 Needed for NFS"), _("Retry"),
                           _("NFS installation method requires IPv4 support."));
                continue;
            }
        }

        /* what TCP/IP stacks do we use? what conf methods? */
        if (opts->ipv4Choice == NEWT_CHECKBOXTREE_SELECTED) {
            flags &= ~LOADER_FLAGS_NOIPV4;
            for (z = 0; z < 2; z++)
                if (newtRadioGetCurrent(v4Method[0]) == v4Method[z])
                    newCfg->ipv4method = z;
        } else {
            flags |= LOADER_FLAGS_NOIPV4;
        }

        if (opts->ipv6Choice == NEWT_CHECKBOXTREE_SELECTED) {
            flags &= ~LOADER_FLAGS_NOIPV6;
            for (z = 0; z < 3; z++)
                if (newtRadioGetCurrent(v6Method[0]) == v6Method[z])
                    newCfg->ipv6method = z;
        } else {
            flags |= LOADER_FLAGS_NOIPV6;
        }

        /* do interface configuration (call DHCP here, or return for manual) */
        if ((!FL_NOIPV4(flags) && newCfg->ipv4method == IPV4_DHCP_METHOD) ||
            (!FL_NOIPV6(flags) && (newCfg->ipv6method == IPV6_AUTO_METHOD ||
                                 newCfg->ipv6method == IPV6_DHCP_METHOD))) {
            /* do DHCP if selected */
            if (!FL_TESTING(flags)) {
                winStatus(55, 3, NULL,
                          _("Sending request for IP information for %s..."),
                          device, 0);
                waitForLink(device);
                dhcp_failed = doDhcp(newCfg);
                newtPopWindow();
            }

            if (!dhcp_failed) {
                newCfg->isDynamic = 1;
                if (!(newCfg->dev.set & PUMP_NETINFO_HAS_DNS)) {
                    logMessage(WARNING,
                        "dhcp worked, but did not return a DNS server");

                    /*
                     * prompt for a nameserver IP address when:
                     * - DHCP for IPv4, DHCP/AUTO for IPv6 and both enabled
                     * - IPv4 disabled and DHCP/AUTO for IPv6
                     * - IPv6 disabled and DHCP for IPv4
                     */
                    if ((newCfg->ipv4method == IPV4_DHCP_METHOD
                         && (newCfg->ipv6method == IPV6_AUTO_METHOD ||
                             newCfg->ipv6method == IPV6_DHCP_METHOD))
                        || (newCfg->ipv4method == IPV4_DHCP_METHOD
                            && FL_NOIPV6(flags))
                        || (FL_NOIPV4(flags)
                            && (newCfg->ipv6method == IPV6_AUTO_METHOD ||
                                newCfg->ipv6method == IPV6_DHCP_METHOD))) {
                        i = getDnsServers(newCfg);
                        i = i ? 0 : 1;
                    } else {
                        i = 1;
                    }
                } else {
                    i = 1;
                }
            } else {
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

    if ((!FL_NOIPV4(flags) && newCfg->ipv4method == IPV4_MANUAL_METHOD) ||
        (!FL_NOIPV6(flags) && newCfg->ipv6method == IPV6_MANUAL_METHOD))
        return LOADER_OK;
    else
        return LOADER_NOOP;
}

int manualNetConfig(char * device, struct networkDeviceConfig * cfg,
                    struct networkDeviceConfig * newCfg,
                    struct intfconfig_s * ipcomps, struct netconfopts * opts) {
    int i, rows, pos, prefix, cidr, q, have[2], stack[2];
    char *buf = NULL;
    char ret[48];
    ip_addr_t *tip;
    struct in_addr addr;
    struct in6_addr addr6;
    newtComponent f, okay, back, answer;
    newtGrid egrid = NULL;
    newtGrid qgrid = NULL;
    newtGrid rgrid = NULL;
    newtGrid buttons, grid;
    newtComponent text = NULL;

    /* so we don't perform this test over and over */
    stack[IPV4] = opts->ipv4Choice == NEWT_CHECKBOXTREE_SELECTED
                  && newCfg->ipv4method == IPV4_MANUAL_METHOD;
    stack[IPV6] = opts->ipv6Choice == NEWT_CHECKBOXTREE_SELECTED
                  && newCfg->ipv6method == IPV6_MANUAL_METHOD;

    /* UI WINDOW 2 (optional): manual IP config for non-DHCP installs */
    rows = 2;
    for (i = 0; i < 2; i++)
        if (stack[i]) rows++;
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
        tip = NULL;
        if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV4_IP)
            tip = &(cfg->dev.ipv4);
        else if (newCfg->dev.set & PUMP_INTFINFO_HAS_IPV4_IP)
            tip = &(newCfg->dev.ipv4);

        if (tip) {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            newtEntrySet(ipcomps->ipv4Entry, ret, 1);
        }

        tip = NULL;
        if (cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)
            tip = &(cfg->dev.netmask);
        else if (newCfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)
            tip = &(newCfg->dev.netmask);

        if (tip) {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
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
        tip = NULL;
        if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV6_IP)
            tip = &(cfg->dev.ipv6);
        else if (newCfg->dev.set & PUMP_INTFINFO_HAS_IPV6_IP)
            tip = &(newCfg->dev.ipv6);

        if (tip) {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            newtEntrySet(ipcomps->ipv6Entry, ret, 1);
        }

        if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV6_PREFIX)
            q = asprintf(&buf, "%d", cfg->dev.ipv6_prefixlen);
        else if (newCfg->dev.set & PUMP_INTFINFO_HAS_IPV6_PREFIX)
            q = asprintf(&buf, "%d", newCfg->dev.ipv6_prefixlen);

        if (buf) {
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

    tip = NULL;
    if (cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)
        tip = &(cfg->dev.gateway);
    else if (newCfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)
        tip = &(newCfg->dev.gateway);

    if (tip) {
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(ipcomps->gwEntry, ret, 1);
    }

    tip = NULL;
    if (cfg->dev.numDns)
        tip = &(cfg->dev.dnsServers[0]);
    else if (newCfg->dev.numDns)
        tip = &(newCfg->dev.dnsServers[0]);

    if (tip) {
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        newtEntrySet(ipcomps->nsEntry, ret, 1);
    }

    newtComponentAddCallback(ipcomps->gwEntry, ipCallback, ipcomps);
    newtComponentAddCallback(ipcomps->nsEntry, ipCallback, ipcomps);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

    /* main window layout */
    grid = newtCreateGrid(1, 3);

    buf = sdupprintf(_("Enter the IPv4 and/or the IPv6 address and prefix "
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

    /* run the form */
    while ((have[IPV4] != 2) || (have[IPV6] != 2)) {
        have[IPV4] = 0;
        have[IPV6] = 0;

        for (i = 0; i < 2; i++)
            if (!stack[i]) have[i] = 2;

        answer = newtRunForm(f);
        /* memset(newCfg, 0, sizeof(*newCfg)); */

        /* collect IPv4 data */
        if (stack[IPV4]) {
            if (ipcomps->ipv4) {
                if (inet_pton(AF_INET, ipcomps->ipv4, &addr) >= 1) {
                    newCfg->dev.ipv4 = ip_addr_in(&addr);
                    newCfg->dev.set |= PUMP_INTFINFO_HAS_IPV4_IP;
                    have[IPV4]++;
                }
            }

            if (ipcomps->cidr4) {
                if (inet_pton(AF_INET, ipcomps->cidr4, &addr) >= 1) {
                    newCfg->dev.netmask = ip_addr_in(&addr);
                    newCfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
                    have[IPV4]++;
                } else {
                    cidr = atoi(ipcomps->cidr4);
                    if (cidr >= 1 && cidr <= 32) {
                        if (inet_pton(AF_INET, "255.255.255.255", &addr) >= 1) {
                            addr.s_addr = htonl(ntohl(addr.s_addr) << (32 - cidr));
                            newCfg->dev.netmask = ip_addr_in(&addr);
                            newCfg->dev.set |= PUMP_INTFINFO_HAS_NETMASK;
                            have[IPV4]++;
                        }
                    }
                }
            }
        }

        /* collect IPv6 data */
        if (stack[IPV6]) {
            if (ipcomps->ipv6) {
                if (inet_pton(AF_INET6, ipcomps->ipv6, &addr6) >= 1) {
                    newCfg->dev.ipv6 = ip_addr_in6(&addr6);
                    newCfg->dev.set |= PUMP_INTFINFO_HAS_IPV6_IP;
                    have[IPV6]++;
                }
            }

            if (ipcomps->cidr6) {
                prefix = atoi(ipcomps->cidr6);
                if (prefix > 0 || prefix <= 128) {
                    newCfg->dev.ipv6_prefixlen = prefix;
                    newCfg->dev.set |= PUMP_INTFINFO_HAS_IPV6_PREFIX;
                    have[IPV6]++;
                }
            }
        }

        /* collect common network settings */
        if (ipcomps->gw) {
            if (inet_pton(AF_INET, ipcomps->gw, &addr) >= 1) {
                newCfg->dev.gateway = ip_addr_in(&addr);
                newCfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            } else if (inet_pton(AF_INET6, ipcomps->gw, &addr6) >= 1) {
                newCfg->dev.gateway = ip_addr_in6(&addr6);
                newCfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
            }
        }

        /* The cfg->dev.ip field needs to store the IPv4 address if
         * there is one.
         */
        if (ipcomps->ipv4) {
            if (inet_pton(AF_INET, ipcomps->ipv4, &addr) >= 1) {
                newCfg->dev.ip = ip_addr_in(&addr);
                newCfg->dev.set |= PUMP_INTFINFO_HAS_IP;
            }
        }

        /* gather nameservers */
        if (ipcomps->ns) {
            if (inet_pton(AF_INET, ipcomps->ns, &addr) >= 1) {
                cfg->dev.dnsServers[0] = ip_addr_in(&addr);
                cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
                if (cfg->dev.numDns < 1)
                    cfg->dev.numDns = 1;
            } else if (inet_pton(AF_INET6, ipcomps->ns, &addr6) >= 1) {
                cfg->dev.dnsServers[0] = ip_addr_in6(&addr6);
                cfg->dev.set |= PUMP_NETINFO_HAS_DNS;
                if (cfg->dev.numDns < 1)
                    cfg->dev.numDns = 1;
            }
        }

        /* user selected back, but we've saved what they entered already */
        if (answer == back) {
            newtFormDestroy(f);
            newtPopWindow();
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

        strcpy(newCfg->dev.device, device);
        newCfg->isDynamic = 0;
    }

    newtFormDestroy(f);
    newtPopWindow();

    return LOADER_OK;
}

void debugNetworkInfo(struct networkDeviceConfig *cfg) {
    int i;
    char *buf = NULL;

    logMessage(DEBUGLVL, "device = %s", cfg->dev.device);

    if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV4_IP)
        logMessage(DEBUGLVL, "ipv4 = %s", ip_text(cfg->dev.ipv4, buf, 0));

    if (cfg->dev.set & PUMP_INTFINFO_HAS_BROADCAST)
        logMessage(DEBUGLVL,"broadcast = %s",ip_text(cfg->dev.broadcast,buf,0));

    if (cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)
        logMessage(DEBUGLVL, "netmask = %s", ip_text(cfg->dev.netmask, buf, 0));

    if (cfg->dev.set & PUMP_INTFINFO_HAS_NETWORK)
        logMessage(DEBUGLVL, "network = %s", ip_text(cfg->dev.network, buf, 0));

    if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV6_IP)
        logMessage(DEBUGLVL, "ipv6 = %s", ip_text(cfg->dev.ipv6, buf, 0));

    if (cfg->dev.set & PUMP_INTFINFO_HAS_IPV6_PREFIX)
        logMessage(DEBUGLVL, "ipv6_prefixlen = %d", cfg->dev.ipv6_prefixlen);

    if (cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)
        logMessage(DEBUGLVL, "gateway = %s", ip_text(cfg->dev.gateway, buf, 0));

    if (cfg->dev.set & PUMP_NETINFO_HAS_DNS)
        for (i=0; i < cfg->dev.numDns; i++)
            logMessage(DEBUGLVL, "dns[%d] = %s", i,
                       ip_text(cfg->dev.dnsServers[i], buf, 0));
}

int setupWireless(struct networkDeviceConfig *dev) {
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

void netlogger(void *arg, int priority, char *fmt, va_list va) {
    int p;
    char *buf = NULL;

    if (priority == LOG_ERR)
        p = ERROR;
    else if (priority == LOG_INFO)
        p = INFO;
    else if (priority == LOG_DEBUG)
        p = DEBUGLVL;
    else if (priority == LOG_FATAL)
        p = CRITICAL;
    else
        p = INFO;

    if (vasprintf(&buf, fmt, va) != -1) {
        logMessage(p, "%s", buf);
        free(buf);
    } else {
        logMessage(ERROR, "unable to log network message");
    }

    return;
}

/* Clear existing IP addresses from the interface using libnl */
void clearInterface(char *device) {
    int status;
    int ifindex = -1;
    pid_t pid = 0;
    struct nl_cache *cache = NULL;
    struct nl_handle *handle = NULL;
    struct nl_object *obj = NULL;
    struct rtnl_addr *raddr = NULL;

    if (device == NULL)
        return;

    pid = fork();
    if (pid == 0) {
        pumpDisableInterface(device);

        if ((handle = nl_handle_alloc()) == NULL) {
            logMessage(DEBUGLVL, "nl_handle_allow() in %s: %s", __func__,
                       nl_geterror());
            return;
        }

        if (nl_connect(handle, NETLINK_ROUTE)) {
            logMessage(DEBUGLVL, "nl_connect() in %s: %s", __func__,
                       nl_geterror());
            nl_handle_destroy(handle);
            return;
        }

        if ((cache = rtnl_link_alloc_cache(handle)) == NULL) {
            logMessage(DEBUGLVL, "rtnl_link_alloc_cache() in %s: %s", __func__,
                       nl_geterror());
            nl_close(handle);
            nl_handle_destroy(handle);
            return;
        }

        ifindex = rtnl_link_name2i(cache, device);

        if ((cache = rtnl_addr_alloc_cache(handle)) == NULL) {
            logMessage(DEBUGLVL, "rtnl_addr_alloc_cache() in %s: %s", __func__,
                       nl_geterror());
            nl_close(handle);
            nl_handle_destroy(handle);
            return;
        }

        obj = nl_cache_get_first(cache);
        while (obj) {
            raddr = (struct rtnl_addr *) obj;

            if (rtnl_addr_get_ifindex(raddr) == ifindex) {
                rtnl_addr_delete(handle, raddr, 0);
                rtnl_addr_put(raddr);
            }

            obj = nl_cache_get_next(obj);
        }

        nl_close(handle);
        nl_handle_destroy(handle);

        pumpEnableInterface(device);

        exit(0);
    } else if (pid == -1) {
        logMessage(DEBUGLVL, "fork() failure in %s", __func__);
    } else {
        if (waitpid(pid, &status, 0) == -1) {
            logMessage(DEBUGLVL, "waitpid() failure in %s", __func__);
        }

        if (!WIFEXITED(status)) {
            logMessage(DEBUGLVL, "%d exit status: %d",pid,WEXITSTATUS(status));
        }
    }

    return;
}

int doDhcp(struct networkDeviceConfig *dev) {
    struct pumpNetIntf *pumpdev = NULL;
    char *r = NULL, *class = NULL;
    char namebuf[HOST_NAME_MAX];
    time_t timeout;
    int loglevel, status, ret = 0, i, sz = 0;
    int shmpump;
    DHCP_Preference pref = 0;
    pid_t pid;
    key_t key;
    int mturet;
    int culvert[2], domainp[2];
    char buf[PATH_MAX];

    /* clear existing IP addresses */
    clearInterface(dev->dev.device);

    if (dev->dhcpTimeout < 0)
        timeout = 45;
    else
        timeout = dev->dhcpTimeout;

    if (dev->vendor_class != NULL)
        class = dev->vendor_class;
    else
        class = "anaconda";

    if (getLogLevel() == DEBUGLVL)
        loglevel = LOG_DEBUG;
    else
        loglevel = LOG_INFO;

    /* dhcp preferences are in /usr/include/libdhcp/dhcp_nic.h */

    /* calling function should catch ipv4Choice & ipv6Choice both being ' ' */
    if (FL_NOIPV4(flags) || dev->ipv4method == IPV4_MANUAL_METHOD) {
        /* IPv4 disabled entirely -or- manual IPv4 config selected */
        pref |= DHCPv4_DISABLE;
    }

    if (!FL_NOIPV6(flags) && dev->ipv6method == IPV6_AUTO_METHOD) {
        /* IPv6 enabled -and- auto neighbor discovery selected */
        pref |= DHCPv6_DISABLE | DHCPv6_DISABLE_ADDRESSES;
    } else if (FL_NOIPV6(flags) || dev->ipv6method == IPV6_MANUAL_METHOD) {
        /* IPv6 disabled entirely -or- manual IPv6 config selected */
        pref |= DHCPv6_DISABLE;
    }

    /* disable some things for this DHCP call */
    pref |= DHCPv6_DISABLE_RESOLVER | DHCPv4_DISABLE_HOSTNAME_SET;

    /* don't try to run the client if DHCPv4 and DHCPv6 are disabled */
    if (!(pref & DHCPv4_DISABLE) || !(pref & DHCPv6_DISABLE)) {
        logMessage(INFO, "requesting dhcp timeout %ld", (long) timeout);

        /* shm segment for pumpNetIntf structure */
        if ((key = ftok("/tmp", 'P')) == -1) {
            logMessage(ERROR, "%s: ftok() 'P' failure", __func__);
            return 1;
        }

        shmpump = shmget(key, 4096, IPC_CREAT | IPC_EXCL | 0600);
        if (shmpump == -1) {
            logMessage(ERROR, "%s: shmget() segment P exists", __func__);
            return 1;
        }

        pumpdev = (struct pumpNetIntf *) shmat(shmpump, (void *) pumpdev,
                                               SHM_RND);
        if (((void *) pumpdev) == ((void *) -1)) {
            logMessage(ERROR, "%s: shmat() pumpdev: %s", __func__,
                       strerror(errno));
            return 1;
        }

        strncpy(pumpdev->device, dev->dev.device, IF_NAMESIZE);

        if (pipe(culvert) == -1) {
            logMessage(ERROR, "%s: culvert pipe(): %s", __func__, strerror(errno));
            return 1;
        }
        if (pipe(domainp) == -1) {
            logMessage(ERROR, "%s: domainp pipe(): %s", __func__, strerror(errno));
            return 1;
        }

        /* call libdhcp in a separate process because libdhcp is bad */
        pid = fork();
        if (pid == 0) {
            close(culvert[0]);
            close(domainp[0]);

            if (pumpdev->set & PUMP_INTFINFO_HAS_MTU) {
                mturet = nl_set_device_mtu((char *) pumpdev->device, pumpdev->mtu);

                if (mturet) {
                    logMessage(ERROR, "unable to set %s mtu to %d (code %d)",
                               (char *) pumpdev->device, pumpdev->mtu, mturet);
                }
            }

            r = pumpDhcpClassRun(pumpdev, NULL, class, pref, 0,
                                 timeout, netlogger, loglevel);

            if (r != NULL) {
                logMessage(INFO, "dhcp: %s", r);
                exit(1);
            }

            if (pumpdev->dhcp_nic) {
                i = dhcp_nic_configure(pumpdev->dhcp_nic);

                dhcp_nic_free(pumpdev->dhcp_nic);
                pumpdev->dhcp_nic = NULL;

                if (i < 0) {
                    logMessage(ERROR, "DHCP configuration failed - %d %s", -i,
                               strerror(-i));
                    exit(1);
                }
            }

            findHostAndDomain(dev);
            writeResolvConf(dev);

            if (pumpdev->set & PUMP_NETINFO_HAS_HOSTNAME) {
                if (pumpdev->hostname) {
                    if (sethostname(pumpdev->hostname,
                                    strlen(pumpdev->hostname)) == -1) {
                        logMessage(ERROR, "failed to set hostname in %s: %s",
                                   __func__, strerror(errno));
                    }
                }
            }

            if (pumpdev->set & PUMP_NETINFO_HAS_DOMAIN) {
                if (pumpdev->domain) {
                    if (write(domainp[1], pumpdev->domain,
                              strlen(pumpdev->domain) + 1) == -1) {
                        logMessage(ERROR, "failed to send domain name to parent "
                                          "in %s: %s", __func__,
                                   strerror(errno));
                    }
                }
            }

            if (pumpdev->set & PUMP_INTFINFO_HAS_BOOTFILE) {
                if (pumpdev->bootFile) {
                    if (write(culvert[1], pumpdev->bootFile,
                              strlen(pumpdev->bootFile) + 1) == -1) {
                        logMessage(ERROR, "failed to send bootFile to parent "
                                          "in %s: %s", __func__,
                                   strerror(errno));
                    }
                }
            }

            close(culvert[1]);
            close(domainp[1]);
            exit(0);
        } else if (pid == -1) {
            logMessage(CRITICAL, "dhcp client failed to start");
        } else {
            close(culvert[1]);
            close(domainp[1]);

            if (waitpid(pid, &status, 0) == -1) {
                logMessage(ERROR, "waitpid() failure in %s", __func__);
            }

            ret = WEXITSTATUS(status);
            if (!WIFEXITED(status)) {
                logMessage(ERROR, "%d exit status: %d", pid, ret);
            }

            /* gather configuration info from dhcp client */
            strncpy(dev->dev.device, pumpdev->device, IF_NAMESIZE);

            dev->dev.ip = pumpdev->ip;
            dev->dev.ipv4 = pumpdev->ipv4;
            dev->dev.ipv6 = pumpdev->ipv6;
            dev->dev.netmask = pumpdev->netmask;
            dev->dev.broadcast = pumpdev->broadcast;
            dev->dev.network = pumpdev->network;
            dev->dev.gateway = pumpdev->gateway;
            dev->dev.nextServer = pumpdev->nextServer;
            dev->dev.set = pumpdev->set;
            dev->dev.mtu = pumpdev->mtu;
            dev->dev.numDns = pumpdev->numDns;
            dev->dev.ipv6_prefixlen = pumpdev->ipv6_prefixlen;
            dev->dev.nh = dev->dev.nh;
            dev->dev.dhcp_nic = NULL;

            for (i=0; i < dev->dev.numDns; i++) {
                dev->dev.dnsServers[i] = pumpdev->dnsServers[i];
            }

            if (dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME) {
                if (dev->dev.hostname) {
                    free(dev->dev.hostname);
                    dev->dev.hostname = NULL;
                }

                memset(namebuf, '\0', HOST_NAME_MAX);

                if (gethostname(namebuf, HOST_NAME_MAX) == -1) {
                    logMessage(ERROR, "unable to get hostname %s: %s",
                               __func__, strerror(errno));
                }

                if (namebuf != NULL) {
                    dev->dev.hostname = strdup(namebuf);
                }
            }

            if (dev->dev.set & PUMP_NETINFO_HAS_DOMAIN) {
                memset(&buf, '\0', sizeof(buf));
                if (dev->dev.domain) {
                    free(dev->dev.domain);
                    dev->dev.domain = NULL;
                }

                while ((sz = read(domainp[0], &buf, sizeof(buf))) > 0) {
                    if (dev->dev.domain == NULL) {
                        dev->dev.domain = calloc(sizeof(char), sz + 1);
                        if (dev->dev.domain == NULL) {
                            logMessage(ERROR, "unable to read domain name");
                            break;
                        }

                        dev->dev.domain = strncpy(dev->dev.domain, buf, sz);
                    } else {
                        dev->dev.domain = realloc(dev->dev.domain,
                                                    strlen(dev->dev.domain) +
                                                    sz + 1);
                        if (dev->dev.domain == NULL) {
                            logMessage(ERROR, "unable to read domain name");
                            break;
                        }

                        dev->dev.domain = strncat(dev->dev.domain, buf, sz);
                    }
                }
            }

            if (dev->dev.set & PUMP_INTFINFO_HAS_BOOTFILE) {
                memset(&buf, '\0', sizeof(buf));
                free(dev->dev.bootFile);
                dev->dev.bootFile = NULL;

                while ((sz = read(culvert[0], &buf, sizeof(buf))) > 0) {
                    if (dev->dev.bootFile == NULL) {
                        dev->dev.bootFile = calloc(sizeof(char), sz + 1);
                        if (dev->dev.bootFile == NULL) {
                            logMessage(ERROR, "unable to read bootfile");
                            break;
                        }

                        dev->dev.bootFile = strncpy(dev->dev.bootFile, buf, sz);
                    } else {
                        dev->dev.bootFile = realloc(dev->dev.bootFile,
                                                    strlen(dev->dev.bootFile) +
                                                    sz + 1);
                        if (dev->dev.bootFile == NULL) {
                            logMessage(ERROR, "unable to read bootfile");
                            break;
                        }

                        dev->dev.bootFile = strncat(dev->dev.bootFile, buf, sz);
                    }
                }
            }

            close(culvert[0]);
            close(domainp[0]);

            if (shmdt(pumpdev) == -1) {
                logMessage(ERROR, "%s: shmdt() pumpdev: %s", __func__,
                           strerror(errno));
                return 1;
            }

            if (shmctl(shmpump, IPC_RMID, 0) == -1) {
                logMessage(ERROR, "%s: shmctl() shmpump: %s", __func__,
                           strerror(errno));
                return 1;
            }
        }
    }

    return ret;
}

int configureNetwork(struct networkDeviceConfig * dev) {
    int mturet;
    char *rc = NULL;

    if (!dev->isDynamic) {
        clearInterface(dev->dev.device);
        setupWireless(dev);

        if (dev->dev.set & PUMP_INTFINFO_HAS_MTU) {
            mturet = nl_set_device_mtu((char *) &dev->dev.device, dev->dev.mtu);

            if (mturet) {
                logMessage(ERROR, "unable to set %s mtu to %d (code %d)",
                           (char *) &dev->dev.device, dev->dev.mtu, mturet);
            }
        }

        rc = pumpSetupInterface(&dev->dev);
        if (rc != NULL) {
            logMessage(INFO, "result of pumpSetupInterface is %s", rc);
            return 1;
        }
    }

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
    char ret[48];
    ip_addr_t *tip;
    char osa_opts[512] = "";

    devices = probeDevices(CLASS_NETWORK, BUS_UNSPEC, PROBE_LOADED);
    if (!devices)
        return 0;

    for (i = 0; devices[i]; i++)
        if (!strcmp(devices[i]->device, dev->dev.device)) break;

    if (!(f = fopen(fn, "w"))) return -1;

    fprintf(f, "DEVICE=%s\n", dev->dev.device);

    fprintf(f, "ONBOOT=yes\n");

    if (dev->isiBFT) {
	fprintf(f, "BOOTPROTO=ibft\n");
    } else if (dev->isDynamic) {
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

    if (dev->layer2 && !strcmp(dev->layer2, "1"))
	strcat(osa_opts, "layer2=1");
    else if (dev->subchannels && !strcmp(dev->nettype, "qeth"))
	fprintf(f, "ARP=no\n");
    if (dev->portno && !strcmp(dev->portno, "1")) {
	if (strlen(osa_opts) != 0) {
	    strcat(osa_opts, " ");
	}
	strcat(osa_opts, "portno=1");
    } 
    if ((strlen(osa_opts) > 0))
        fprintf(f, "OPTIONS=\"%s\"\n", osa_opts);

    if (dev->macaddr)
        fprintf(f, "MACADDR=%s\n", dev->macaddr);

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
    char ret[48];
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

int findHostAndDomain(struct networkDeviceConfig * dev) {
    char * name, * chptr;
    char ret[48];
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
            winStatus(50, 3, NULL, 
                      _("Determining host name and domain..."));
        else
            printf("Determining host name and domain...\n");

        tip = &(dev->dev.ip);
        inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
        name = mygethostbyaddr(ret, tip->sa_family);

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
                         char ** argv) {
    char * arg, * bootProto = NULL, * device = NULL, *ethtool = NULL, * class = NULL;
    char * essid = NULL, * wepkey = NULL, * onboot = NULL;
    int noDns = 0, noksdev = 0, rc, mtu = 0, noipv4 = 0, noipv6 = 0, dhcpTimeout = -1;
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
    if (bootProto && !strncmp(bootProto, "query", 3)) {
        loaderData->ip = strdup("query");
        loaderData->ipinfo_set = 0;
    } else if ((bootProto && (!strncmp(bootProto, "dhcp", 4) || 
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

        if (noipv4)
            flags |= LOADER_FLAGS_NOIPV4;

        if (noipv6)
            flags |= LOADER_FLAGS_NOIPV6;
    }

    if (noDns) {
        loaderData->noDns = 1;
    }
}

/* if multiple interfaces get one to use from user.   */
/* NOTE - uses kickstart data available in loaderData */
int chooseNetworkInterface(struct loaderData_s * loaderData) {
    int i, rc, ask, idrc, secs, deviceNums = 0, deviceNum, foundDev = 0;
    unsigned int max = 40;
    int lookForLink = 0;
    char **devices;
    char **deviceNames;
    char *ksMacAddr = NULL, *seconds = strdup("10"), *idstr = NULL;
    struct device **devs;
    struct newtWinEntry entry[] = {{_("Seconds:"), (const char **) &seconds, 0},
                                   {NULL, NULL, 0 }};

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
            ksMacAddr = strdup(loaderData->bootIf);
        } else {
            ksMacAddr = strdup(loaderData->netDev);
        }

        ksMacAddr = str2upper(ksMacAddr);
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
                char *devmacaddr = NULL;
                devmacaddr = nl_mac2str(devs[i]->device);
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

#if !defined(__s390__) && !defined(__s390x__)
    /* set the netDev method to ibft if not requested differently */
    if(loaderData->netDev==NULL && ibft_present()){
	loaderData->netDev = strdup("ibft");
	loaderData->netDev_set = 1;
	logMessage(INFO, "networking will be configured using iBFT values");
    }
#endif

    while((loaderData->netDev && (loaderData->netDev_set == 1)) &&
	!strcmp(loaderData->netDev, "ibft")){
        char *devmacaddr = NULL;
	char *ibftmacaddr = "";
	
#if !defined(__s390__) && !defined(__s390x__)
	/* get MAC from the iBFT table */
	if(!(ibftmacaddr = ibft_iface_mac())){ /* iBFT not present or error */
	    lookForLink = 0; /* the iBFT defaults to ask? */
	    break;
	}
#endif

        logMessage(INFO, "looking for iBFT configured device %s with link", ibftmacaddr);
	lookForLink = 0;

	for (i = 0; devs[i]; i++) {
	    if (!devs[i]->device)
		continue;
            devmacaddr = nl_mac2str(devs[i]->device);
	    if(!strcasecmp(devmacaddr, ibftmacaddr)){
                logMessage(INFO, "%s has the right MAC (%s), checking for link", devmacaddr, devices[i]);
		free(devmacaddr);
		if(get_link_status(devices[i]) == 1){
		    lookForLink = 0;
		    loaderData->netDev = devices[i];
                    logMessage(INFO, "%s has link, using it", devices[i]);

		    /* set the IP method to ibft if not requested differently */
		    if(loaderData->ip==NULL){
			loaderData->ip = strdup("ibft");
			logMessage(INFO, "%s will be configured using iBFT values", devices[i]);
		    }
                    return LOADER_NOOP;
		}
		else{
                    logMessage(INFO, "%s has no link, skipping it", devices[i]);
		}
		break;
	    }
	    else{
                logMessage(DEBUGLVL, "%s (%s) is not it...", devices[i], devmacaddr);
		free(devmacaddr);
	    }
	}

	break;
    }

    if ((loaderData->netDev && (loaderData->netDev_set == 1)) &&
        !strcmp(loaderData->netDev, "link")) {
	lookForLink = 1;
    }

    if (lookForLink){
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
                           "seconds.  Enter a number between 1 and 300 to "
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

                    if (secs <= 0 || secs > 300) {
                        newtWinMessage(_("Invalid Duration"), _("OK"),
                                       _("You must enter the number of "
                                         "seconds as an integer between 1 "
                                         "and 300."));
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

    /* turn off the non-active interface.  this should keep things from
     * breaking when we need the interface to do the install as long as
     * you keep using that device */
    for (i = 0; devs[i]; i++) {
        if (strcmp(loaderData->netDev, devices[i]))
            if (!FL_TESTING(flags))
                clearInterface(devs[i]->device);
    }

    return LOADER_OK;
}

/* JKFIXME: bad name.  this function brings up networking early on a 
 * kickstart install so that we can do things like grab the ks.cfg from
 * the network */
int kickstartNetworkUp(struct loaderData_s * loaderData,
                       struct networkDeviceConfig *netCfgPtr) {
    int rc, query;
    static struct networkDeviceConfig netCfgStore;

    /* we may have networking already, so return to the caller */
    if ((loaderData->ipinfo_set == 1) || (loaderData->ipv6info_set == 1)) {
        logMessage(INFO, "networking already configured in kickstartNetworkUp");
    
        /* Give the network information to the caller (#495042) */
        memcpy(netCfgPtr, &netCfgStore, sizeof(netCfgStore));
        return 0;
    }

    initLoopback();

    memset(netCfgPtr, 0, sizeof(*netCfgPtr));

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

        query = !strncmp(loaderData->ip, "query", 5);

        if (!query) {
            loaderData->ipinfo_set = 1;
        }

        setupNetworkDeviceConfig(netCfgPtr, loaderData);

        rc = readNetConfig(loaderData->netDev, netCfgPtr, loaderData->netCls,
                           loaderData->method, query);

        if (rc == LOADER_ERROR) {
            logMessage(ERROR, "unable to setup networking");
            return -1;
        }
        else if (rc == LOADER_BACK) {
            /* Going back to the interface selection screen, so unset anything
             * we set before attempting to bring the incorrect interface up.
             */
            loaderData->netDev_set = 0;
            free(loaderData->ip);
            loaderData->ipinfo_set = 0;
        }
        else
            break;
    } while (1);

    /* Store all information for possible subsequent calls (#495042) */
    memcpy(&netCfgStore, netCfgPtr, sizeof(netCfgStore));

    return 0;
}

static int strcount (char *str, int ch)
{
    int retval = 0;
    char *tmp = str;

    do {
        if ((tmp = index(tmp, ch)) != NULL) {
            tmp++;
            retval++;
        }
    } while (tmp != NULL);

    return retval;
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

/* vim:set shiftwidth=4 softtabstop=4: */
