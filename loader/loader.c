/*
 * loader.c
 * 
 * This is the installer loader.  Its job is to somehow load the rest
 * of the installer into memory and run it.  This may require setting
 * up some devices and networking, etc. The main point of this code is
 * to stay SMALL! Remember that, live by that, and learn to like it.
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 1999 Red Hat Software 
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <unistd.h>
#include <popt.h>
#include <newt.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <net/route.h>
#include <sys/ioctl.h>
#include <fcntl.h>

#include "isys/imount.h"
#include "isys/isys.h"
#include "isys/pci/pciprobe.h"

#define _(x) x

struct intfInfo {
    char device[10];
    int isPtp, isUp;
    int set, manuallySet;
    struct in_addr ip, netmask, broadcast, network;
    struct in_addr bootServer;
    char * bootFile;
    int bootProto;
};

static int configureNetDevice(struct intfInfo * intf) {
    struct ifreq req;
    struct rtentry route;
    int s;
    struct sockaddr_in addr;
    struct in_addr ia;
    char ip[20], nm[20], nw[20], bc[20];

    addr.sin_family = AF_INET;
    addr.sin_port = 0;

    memcpy(&ia, &intf->ip, sizeof(intf->ip));
    strcpy(ip, inet_ntoa(ia));

    memcpy(&ia, &intf->netmask, sizeof(intf->netmask));
    strcpy(nm, inet_ntoa(ia));

    memcpy(&ia, &intf->broadcast, sizeof(intf->broadcast));
    strcpy(bc, inet_ntoa(ia));

    memcpy(&ia, &intf->network, sizeof(intf->network));
    strcpy(nw, inet_ntoa(ia));

    printf("configuring %s ip: %s nm: %s nw: %s bc: %s\n", intf->device,
	   ip, nm, nw, bc);

    s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) {
	perror("socket");
        return 1;
    }
    
    strcpy(req.ifr_name, intf->device);
    req.ifr_flags &= ~(IFF_UP | IFF_RUNNING); /* Take down iface */
    if (ioctl(s, SIOCSIFFLAGS, &req)) {
        perror("SIOCSIFFLAGS");
        close(s);
        return 1;
    }

    addr.sin_port = 0;
    memcpy(&addr.sin_addr, &intf->ip, sizeof(intf->ip));
    memcpy(&req.ifr_addr, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFADDR, &req)) {
        perror("SIOCSIFADDR");
        close(s);
        return 1;
    }

    memcpy(&addr.sin_addr, &intf->broadcast, sizeof(intf->broadcast));
    memcpy(&req.ifr_broadaddr, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFBRDADDR, &req)) {
        perror("SIOCSIFNETMASK");
        close(s);
        return 1;
    }

    memcpy(&addr.sin_addr, &intf->netmask, sizeof(intf->netmask));
    memcpy(&req.ifr_netmask, &addr, sizeof(addr));
    if (ioctl(s, SIOCSIFNETMASK, &req)) {
        perror("SIOCSIFNETMASK\n");
        close(s);
        return 1;
    }

    if (intf->isPtp)
        req.ifr_flags = IFF_UP | IFF_RUNNING | IFF_POINTOPOINT | IFF_NOARP;
    else
        req.ifr_flags = IFF_UP | IFF_RUNNING | IFF_BROADCAST;

    if (ioctl(s, SIOCSIFFLAGS, &req)) {
        perror("SIOCSIFFLAGS");
        close(s);
        return 1;
    }

#if 0 /* kernel 2.0 only */
    memset(&route, 0, sizeof(route));
    route.rt_dev = intf->device;
    route.rt_flags = RTF_UP;

    memcpy(&addr.sin_addr, &intf->network, sizeof(intf->netmask));
    memcpy(&route.rt_dst, &addr, sizeof(addr));

    memcpy(&addr.sin_addr, &intf->netmask, sizeof(intf->netmask));
    memcpy(&route.rt_genmask, &addr, sizeof(addr));

    if (ioctl(s, SIOCADDRT, &route)) {
        perror("SIOCADDRT");
        close(s);
        return 1;

    }
#endif
    
    intf->isUp = 1;

    return 0;
}

int main(int argc, char ** argv) {
    char * arg, **args;
    poptContext optCon;
    int testing, network, local, rc;
    char ** modules, *module;
    struct intfInfo eth0;    
    struct poptOption optionTable[] = {
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
	    { "network", '\0', POPT_ARG_NONE, &network, 0 },
	    { "local", '\0', POPT_ARG_NONE, &local, 0 },
	    { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext(NULL, argc, argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    if ((arg = poptGetArg(optCon))) {
	fprintf(stderr, "unexpected argument: %s\n", arg);
	exit(1);
    }

    if (probePciReadDrivers(testing ? "../isys/pci/pcitable" :
			              "/etc/pcitable")) {
	perror("error reading pci table");
	return 1;
    }
    
    modules = probePciDriverList();
    if (modules == NULL) {
	printf("No PCI devices found :(\n");
    } else {
	while (module = *modules++) {
	    if (!testing) {
		printf("Inserting module %s\n", module);
		insmod(module, NULL);
	    } else {
		printf("Test mode: I would run insmod(%s, args);\n",
		       module);
	    }
	}
    }
    
    /*
    newtInit();
    newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));

    newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));

    newtFinished();
    */

    strcpy(eth0.device, "eth0");
    eth0.isPtp=0;
    eth0.isUp=0;
    eth0.ip.s_addr=inet_addr("207.175.42.47");
    eth0.netmask.s_addr=htonl(0xffffff00);
    eth0.broadcast.s_addr=inet_addr("207.175.42.255");
    eth0.network.s_addr=inet_addr("207.175.42.0");

    configureNetDevice(&eth0);

    mkdir("/mnt", 777);
    mkdir("/mnt/source", 777);

    insmod("sunrpc.o", NULL);
    insmod("lockd.o", NULL);
    insmod("nfs.o", NULL);
    
    doPwMount("207.175.42.68:/mnt/test/msw/i386",
	      "/mnt/source", "nfs", 1, 0, NULL, NULL);

    symlink("/mnt/source/RedHat/instimage/usr", "/usr");
    
    execv(testing ? "../anaconda" : "/usr/sbin/anaconda", argv);

    sleep(5);
    
    return 0;
}
