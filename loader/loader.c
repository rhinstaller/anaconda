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
#include <fcntl.h>
#include <arpa/inet.h>

#include "isys/imount.h"
#include "isys/inet.h"
#include "isys/isys.h"
#include "isys/pci/pciprobe.h"

#include "windows.h"
#include "log.h"
#include "lang.h"

int main(int argc, char ** argv) {
    char ** argptr;
    char * anacondaArgs[30];
    char * arg;
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

    openLog(testing);
    
    newtInit();
    newtCls();
    newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));
    
    newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
	
    if (!testing) {
	modules = probePciDriverList();
	if (modules == NULL) {
	    printf("No PCI devices found :(\n");
	} else {
	    while ((module = *modules++)) {
		if (!testing) {
		    winStatus(60, 5, "Module Insertion",
			      "Inserting module %s", module);
		    insmod(module, NULL);
		    newtPopWindow();
		} else {
		    printf("Test mode: I would run insmod(%s, args);\n",
			   module);
		}
	    }
	}
    

	strcpy(eth0.device, "eth0");
	eth0.isPtp=0;
	eth0.isUp=0;
	eth0.ip.s_addr=inet_addr("207.175.42.47");
	eth0.netmask.s_addr=inet_addr("255.255.254.0");
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

	symlink("mnt/source/RedHat/instimage/usr", "/usr");
	symlink("mnt/source/RedHat/instimage/lib", "/lib");

	if (access("/usr/bin/anaconda", R_OK)) {
	    perror("NFS mount does not appear to be a Red Hat 6.1 tree:");
	    exit (1);
	}
    }
    argptr = anacondaArgs;
    *argptr++ = testing ? "../anaconda" : "/usr/bin/anaconda";
    *argptr++ = "-p";
    *argptr++ = "/mnt/source";

    newtFinished();
    
    printf("Launching anaconda (%s), please wait...\n", anacondaArgs[0]);
    
    execv(anacondaArgs[0], anacondaArgs);
    perror("exec");
 
    return 1;
}

