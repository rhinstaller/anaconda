#include <arpa/inet.h>
#include <errno.h>
#include <popt.h>
#include <resolv.h>
#include <net/if.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <pump.h>

#ifdef __STANDALONE__
#include <netdb.h>
#include <libintl.h>
#include <locale.h>

#define _(String) gettext((String))

#define LOADER_BACK 2
#define LOADER_ERROR -1;

#include "net.h"

#else

# include "isys/dns.h"

#include "kickstart.h"
#include "lang.h"
#include "loader.h"
#include "log.h"
#include "net.h"
#include "windows.h"

#endif /* __STANDALONE__ */

struct intfconfig_s {
    newtComponent ipEntry, nmEntry, gwEntry, nsEntry;
    char * ip, * nm, * gw, * ns;
};

typedef int int32;

#ifdef __STANDALONE__
static FILE * logfile = NULL;

#define FL_TESTING(foo) 0

void logMessage(const char * s, ...) {
	va_list args;
	
	if (!logfile) return;
	va_start(args, s);

	fprintf(logfile, "* ");
	vfprintf(logfile, s, args);
	fprintf(logfile, "\n");
	fflush(logfile);

	va_end(args);

	return;
}

/* yawn. This really should be in newt. */
void winStatus(int width, int height, char * title,
	                       char * text, ...) {
	newtComponent t, f;
	char * buf = NULL;
	int size = 0;
	int i = 0;
	va_list args;
	
	va_start(args, text);
	
	do {
		size += 1000;
		if (buf) free(buf);
		buf = malloc(size);
		i = vsnprintf(buf, size, text, args);
	} while (i == size);
	
	va_end(args);
	
	newtCenteredWindow(width, height, title);
	
	t = newtTextbox(1, 1, width - 2, height - 2, NEWT_TEXTBOX_WRAP);
	newtTextboxSetText(t, buf);
	f = newtForm(NULL, NULL, 0);
	
	free(buf);
	
	newtFormAddComponent(f, t);
	
	newtDrawForm(f);
	newtRefresh();
	newtFormDestroy(f);
}

#endif

static void ipCallback(newtComponent co, void * dptr) {
    struct intfconfig_s * data = dptr;
    struct in_addr ipaddr, nmaddr, addr;
    char * ascii;
    int broadcast, network;

    if (co == data->ipEntry) {
	if (strlen(data->ip) && !strlen(data->nm)) {
	    if (inet_aton(data->ip, &ipaddr)) {
		ipaddr.s_addr = ntohl(ipaddr.s_addr);
		if (((ipaddr.s_addr & 0xFF000000) >> 24) <= 127)
		    ascii = "255.0.0.0";
		else if (((ipaddr.s_addr & 0xFF000000) >> 24) <= 191)
		    ascii = "255.255.0.0";
		else 
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

#ifndef __STANDALONE__
int nfsGetSetup(char ** hostptr, char ** dirptr) {
    struct newtWinEntry entries[3];
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;
    entries[1].text = _("Red Hat directory:");
    entries[1].value = &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = NULL;
    entries[2].value = NULL;
    
    rc = newtWinEntries(_("NFS Setup"), 
		_("Please enter the following information:\n"
		  "\n"
		  "    o the name or IP number of your NFS server\n"
		  "    o the directory on that server containing\n"
		  "      Red Hat Linux for your architecture"), 60, 5, 15,
		24, entries, _("OK"), _("Back"), NULL);

    if (rc == 2) {
	if (newServer) free(newServer);
	if (newDir) free(newDir);
	return LOADER_BACK;
    }

    if (*hostptr) free(*hostptr);
    if (*dirptr) free(*dirptr);
    *hostptr = newServer;
    *dirptr = newDir;

    return 0;
}
#endif

static void fillInIpInfo(struct networkDeviceConfig * cfg) {
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

#ifndef __STANDALONE__
void initLoopback(void) {
    struct pumpNetIntf dev;

    strcpy(dev.device, "lo");
    inet_aton("127.0.0.1", &dev.ip);
    inet_aton("255.0.0.0", &dev.netmask);
    dev.set = PUMP_INTFINFO_HAS_NETMASK | PUMP_INTFINFO_HAS_IP;

    pumpSetupInterface(&dev);
}
#endif

static void dhcpBoxCallback(newtComponent co, void * ptr) {
    struct intfconfig_s * c = ptr;

    newtEntrySetFlags(c->ipEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->gwEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nmEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
    newtEntrySetFlags(c->nsEntry, NEWT_FLAG_DISABLED, NEWT_FLAGS_TOGGLE);
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

    if (!cfg->isDynamic) {
	if (cfg->dev.set & PUMP_INTFINFO_HAS_IP)
	    newtEntrySet(c.ipEntry, inet_ntoa(cfg->dev.ip), 1);

	if (cfg->dev.set & PUMP_INTFINFO_HAS_NETMASK)
	    newtEntrySet(c.nmEntry, inet_ntoa(cfg->dev.netmask), 1);

	if (cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)
	    newtEntrySet(c.gwEntry, inet_ntoa(cfg->dev.gateway), 1);

	if (cfg->dev.numDns)
	    newtEntrySet(c.nsEntry, inet_ntoa(cfg->dev.dnsServers[0]), 1);

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
		winStatus(50, 3, _("Dynamic IP"), 
			  _("Sending request for IP information..."),
			    0);
		chptr = pumpDhcpRun(device, 0, 0, NULL, &newCfg.dev, NULL);
		newtPopWindow();
	    } else {
	    	chptr = NULL;
	    }

	    if (!chptr) {
		i = 2; 
		newCfg.isDynamic = 1;
	    } else {
		logMessage("pump told us: %s", chptr);
		i = 0;
	    }
	}
    } while (i != 2);

    cfg->dev = newCfg.dev;
    cfg->isDynamic = newCfg.isDynamic;

    fillInIpInfo(cfg);

    if (!(cfg->dev.set & PUMP_NETINFO_HAS_GATEWAY)) {
	if (*c.gw && inet_aton(c.gw, &addr)) {
	    cfg->dev.gateway = addr;
	    cfg->dev.set |= PUMP_NETINFO_HAS_GATEWAY;
	}
    }

    if (!(cfg->dev.numDns)) {
	if (*c.ns && inet_aton(c.ns, &addr)) {
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
    pumpSetupInterface(&dev->dev);

    if (dev->dev.set & PUMP_NETINFO_HAS_GATEWAY)
	pumpSetupDefaultGateway(&dev->dev.gateway);

    return 0;
}

int writeNetInfo(const char * fn, struct networkDeviceConfig * dev) {
    FILE * f;

    if (!(f = fopen(fn, "w"))) return -1;

    fprintf(f, "DEVICE=%s\n", dev->dev.device);
    if (dev->isDynamic) {
	fprintf(f, "BOOTPROTO=dhcp\n");
    } else {
	fprintf(f, "BOOTPROTO=static\n");
	fprintf(f, "IPADDR=%s\n", inet_ntoa(dev->dev.ip));
	fprintf(f, "NETMASK=%s\n", inet_ntoa(dev->dev.netmask));
	if (dev->dev.set & PUMP_NETINFO_HAS_GATEWAY)
	    fprintf(f, "GATEWAY=%s\n", inet_ntoa(dev->dev.gateway));
    }
    if (dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)
	fprintf(f, "HOSTNAME=%s\n", dev->dev.hostname);
    if (dev->dev.set & PUMP_NETINFO_HAS_DOMAIN)
	fprintf(f, "DOMAIN=%s\n", dev->dev.domain);

    fclose(f);

    return 0;
}

int writeResolvConf(struct networkDeviceConfig * net) {
    char * filename = "/etc/resolv.conf";
    FILE * f;
    int i;

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

    res_init();		/* reinit the resolver so DNS changes take affect */

    return 0;
}

int findHostAndDomain(struct networkDeviceConfig * dev, int flags) {
    char * name, * chptr;
#ifdef __STANDALONE__
    struct hostent * he;
#endif

    if (!FL_TESTING(flags)) {
	writeResolvConf(dev);
    }

    if (!(dev->dev.set & PUMP_NETINFO_HAS_HOSTNAME)) {
	winStatus(40, 3, _("Hostname"), 
		  _("Determining host name and domain..."));
#ifdef __STANDALONE__
	he = gethostbyaddr( (char *) &dev->dev.ip, sizeof (dev->dev.ip), AF_INET);
	name = he ? he->h_name : 0;
#else
	name = mygethostbyaddr(inet_ntoa(dev->dev.ip));
#endif
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

#ifndef __STANDALONE__
int kickstartNetwork(char * device, struct networkDeviceConfig * netDev, 
		     char * bootProto, int flags) {
    char ** ksArgv;
    int ksArgc;
    int netSet, rc;
    char * arg, * chptr;
    poptContext optCon;
    struct in_addr * parseAddress;
    int noDns = 0;
    struct poptOption ksOptions[] = {
	    { "bootproto", '\0', POPT_ARG_STRING, &bootProto, 0 },
	    { "gateway", '\0', POPT_ARG_STRING, NULL, 'g' },
	    { "ip", '\0', POPT_ARG_STRING, NULL, 'i' },
	    { "nameserver", '\0', POPT_ARG_STRING, NULL, 'n' },
	    { "netmask", '\0', POPT_ARG_STRING, NULL, 'm' },
	    { "nodns", '\0', POPT_ARG_NONE, &noDns, 0 },
	    { 0, 0, 0, 0, 0 }
    };

    if (!bootProto) {
	if (ksGetCommand(KS_CMD_NETWORK, NULL, &ksArgc, &ksArgv)) {
	    /* This is for compatibility with RH 5.0 */
	    ksArgv = alloca(sizeof(*ksArgv) * 1);
	    ksArgv[0] = "network";
	    ksArgc = 1;
	}

	optCon = poptGetContext(NULL, ksArgc, (const char **) ksArgv, ksOptions, 0);
	while ((rc = poptGetNextOpt(optCon)) >= 0) {
	    parseAddress = NULL;
	    netSet = 0;

	    arg = (char *) poptGetOptArg(optCon);

	    switch (rc) {
	      case 'g':
		parseAddress = &netDev->dev.gateway;
		netSet = PUMP_NETINFO_HAS_GATEWAY;
		break;
		    
	      case 'i':
		parseAddress = &netDev->dev.ip;
		netSet = PUMP_INTFINFO_HAS_IP;
		break;
		    
	      case 'n':
		parseAddress = &netDev->dev.dnsServers[netDev->dev.numDns++];
		netSet = PUMP_NETINFO_HAS_DNS;
		break;

	      case 'm':
		parseAddress = &netDev->dev.netmask;
		netSet = PUMP_INTFINFO_HAS_NETMASK;
		break;
	    }

	    if (!inet_aton(arg, parseAddress)) {
		logMessage("bad ip number in network command: %s", arg);
		return -1;
	    }

	    netDev->dev.set |= netSet;
	}

	if (rc < -1) {
	    newtWinMessage(_("kickstart"),  _("OK"),
		       _("bad argument to kickstart network command %s: %s"),
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	} else {
	    poptFreeContext(optCon);
	}
    }

    if (!bootProto)
	bootProto = "dhcp";

    if (!strcmp(bootProto, "dhcp") || !strcmp(bootProto, "bootp")) {
	logMessage("sending dhcp request through device %s", device);
	winStatus(50, 3, _("Dynamic IP"), 
		  _("Sending request for IP information..."),
		    0);

	chptr = pumpDhcpRun(device, 0, 0, NULL, &netDev->dev, NULL);
	newtPopWindow();
	if (chptr) {
	    logMessage("pump told us: %s", chptr);
	    return -1;
	}
	netDev->isDynamic = 1;
    } else if (!strcmp(bootProto, "static")) {
       strcpy(netDev->dev.device, device);
    } else if (!strcmp(bootProto, "query")) {
	strcpy(netDev->dev.device, device);
	readNetConfig("eth0", netDev, flags);
    } else {
	newtWinMessage(_("kickstart"), _("OK"),
		    _("Bad bootproto %s specified in network command"),
		    bootProto);
	return -1;
    }

    fillInIpInfo(netDev);
    configureNetwork(netDev);

    logMessage("nodns is %d", noDns);

    if (!noDns)
	findHostAndDomain(netDev, flags);

    writeResolvConf(netDev);
    
    return 0;
}
#endif

#ifdef __STANDALONE__
int main(int argc, const char **argv) {
    int netSet, rc;
    int x;
    char * bootProto = NULL;
    char * device = NULL;
    char * hostname = NULL;
    char * domain = NULL;
    const char * arg;
    char path[256];
    char roottext[80];
    poptContext optCon;
    struct networkDeviceConfig *netDev;
    struct in_addr * parseAddress;
    struct poptOption Options[] = {
	    POPT_AUTOHELP
	    { "bootproto", '\0', POPT_ARG_STRING, &bootProto, 0,
	      _("Boot protocol to use"), "(dhcp|bootp|none)" },
	    { "gateway", '\0', POPT_ARG_STRING, NULL, 'g',
	      _("Network gateway"), NULL },
	    { "ip", '\0', POPT_ARG_STRING, NULL, 'i',
	      _("IP address"), NULL },
	    { "nameserver", '\0', POPT_ARG_STRING, NULL, 'n',
	      _("Nameserver"), NULL },
	    { "netmask", '\0', POPT_ARG_STRING, NULL, 'm',
	      _("Netmask"), NULL },
	    { "hostname", '\0', POPT_ARG_STRING, &hostname, 0,
	      _("Hostname"), NULL 
	    },
	    { "domain", '\0', POPT_ARG_STRING, &domain, 0,
	      _("Domain name"), NULL
	    },
	    { "device", 'd', POPT_ARG_STRING, &device, 0,
	      _("Network device"), NULL 
	    },
	    { 0, 0, 0, 0, 0 }
    };

	
    netDev = malloc(sizeof(struct networkDeviceConfig));
    memset(netDev,'\0',sizeof(struct networkDeviceConfig));
    optCon = poptGetContext("netconfig", argc, argv, Options, 0);
    while ((rc = poptGetNextOpt(optCon)) >= 0) {
	parseAddress = NULL;
	netSet = 0;

	arg = poptGetOptArg(optCon);

	switch (rc) {
	  case 'g':
	    parseAddress = &netDev->dev.gateway;
	    netSet = PUMP_NETINFO_HAS_GATEWAY;
	    break;
		
	  case 'i':
	    parseAddress = &netDev->dev.ip;
	    netSet = PUMP_INTFINFO_HAS_IP;
	    break;
		
	  case 'n':
	    parseAddress = &netDev->dev.dnsServers[netDev->dev.numDns++];
	    netSet = PUMP_NETINFO_HAS_DNS;
	    break;

	  case 'm':
	    parseAddress = &netDev->dev.netmask;
	    netSet = PUMP_INTFINFO_HAS_NETMASK;
	    break;
	}

	if (!inet_aton(arg, parseAddress)) {
	    logMessage("bad ip number in network command: %s", arg);
	    return -1;
	}

	netDev->dev.set |= netSet;
    }

    if (rc < -1) {
	fprintf(stderr, "%s: %s\n",
		   poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		   poptStrerror(rc));
    } else {
	poptFreeContext(optCon);
    }
	
    if (netDev->dev.set || 
	(bootProto && (!strcmp(bootProto, "dhcp") || !strcmp(bootProto, "bootp")))) {
	    if (!device) device="eth0";
	    if (bootProto && (!strcmp(bootProto, "dhcp") || !strcmp(bootProto, "bootp")))
		netDev->isDynamic++;
	    strncpy(netDev->dev.device,device,10);
	    if (hostname) {
		    netDev->dev.hostname=strdup(hostname);
		    netDev->dev.set |= PUMP_NETINFO_HAS_HOSTNAME;
	    }
	    if (domain) {
		    netDev->dev.domain=strdup(domain);
		    netDev->dev.set |= PUMP_NETINFO_HAS_DOMAIN;
	    }
	    snprintf(path,256,"/etc/sysconfig/network-scripts/ifcfg-%s",device);
	    writeNetInfo(path,netDev);
    } else {
	    newtInit();
	    newtCls();
	    newtPushHelpLine(_(" <Tab>/<Alt-Tab> between elements   |   <Space> selects  |   <F12> next screen"));
	    snprintf(roottext,80,_("netconfig %s  (C) 1999 Red Hat, Inc."), VERSION);
	    newtDrawRootText(0, 0, roottext);
	    x=newtWinChoice(_("Network configuration"),_("Yes"),_("No"),
			  _("Would you like to set up networking?"));
	    if (x==2) { 
		    newtFinished();
		    exit(0);
	    }
	    if (!device) device="eth0";
	    if (readNetConfig(device,netDev,0) != LOADER_BACK) {
		    snprintf(path,256,"/etc/sysconfig/network-scripts/ifcfg-%s",device);
		    writeNetInfo(path,netDev);
	    }
	    newtFinished();
    }
    exit(0);
}
#endif
