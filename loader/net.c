#include <arpa/inet.h>
#include <net/if.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>

#include "pump/pump.h"

#include "lang.h"
#include "loader.h"
#include "log.h"
#include "net.h"

struct intfconfig_s {
    newtComponent ipEntry, nmEntry, gwEntry, nsEntry;
    char * ip, * nm, * gw, * ns;
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
		24, entries, _("Ok"), _("Back"), NULL);

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

    buttons = newtButtonBar(_("Ok"), &okay, _("Back"), &back, NULL);

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
		chptr = pumpDhcpRun(device, 0, 0, NULL, &newCfg.dev, NULL);
		logMessage("pump told us: %s", chptr);
	    } else {
	    	chptr = NULL;
	    }

	    if (!chptr) {
		i = 2; 
		cfg->isDynamic = 1;
	    } else {
		i = 0;
	    }
	}
    } while (i != 2);

    cfg->dev = newCfg.dev;

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
	if (dev->dev.numDns) 
	    fprintf(f, "NS1=%s\n", inet_ntoa(dev->dev.dnsServers[0]));
    }

    fclose(f);

    return 0;
}
