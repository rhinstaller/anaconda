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

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1


struct loaderState {
    enum {
	INTERFACE_TEXT,
	INTERFACE_GUI,
    } interface;
};

typedef int (*loaderStepFn)(struct loaderState *);

struct loaderStep {
    char * name;
    loaderStepFn fn;
    int skipOnLocal;
};

static int welcomeScreen(struct loaderState * state);
static int detectHardware(struct loaderState * state);
static int selectMedia(struct loaderState * state);
static int selectInterface(struct loaderState * state);

static struct loaderStep loaderSteps[] = { 
    { N_("Welcome"), welcomeScreen, 0 },
    { N_("Hardware Detection"), detectHardware, 1 },
    { N_("Select Media"), selectMedia, 0 },
    { N_("Select Interface"), selectInterface, 0 },
};

static int numSteps = sizeof(loaderSteps) / sizeof(struct loaderStep);
int testing;

static int welcomeScreen(struct loaderState *state) {
    newtWinMessage(_("Red Hat Linux"), _("OK"), 
		   _("Welcome to Red Hat Linux!\n\n"
		     "This short process is outlined in detail in the "
		     "Official Red Hat Linux Installation Guide available from "
		     "Red Hat Software. If you have access to this manual, you "
		     "should read the installation section before continuing.\n\n"
		     "If you have purchased Official Red Hat Linux, be sure to "
		     "register your purchase through our web site, "
		     "http://www.redhat.com."));

    return LOADER_OK;
}

static int detectHardware(struct loaderState *state) {
    char ** modules, *module;

    if (probePciReadDrivers(testing ? "../isys/pci/pcitable" :
			              "/etc/pcitable")) {
	newtWinMessage(_("Error"), _("OK"),
		       _("An error occured while reading the PCI ID table"));
	return LOADER_ERROR;
    }
    
    modules = probePciDriverList();
    if (modules == NULL) {
	printf("No PCI devices found :(\n");
    } else {
	while ((module = *modules++)) {
	    if (!testing) {
		winStatus(60, 3, "Module Insertion", "Inserting module %s", module);
		insmod(module, NULL);
		newtPopWindow();
	    } else {
		newtWinMessage("Testing", "OK",
			       "Test mode: I would run insmod(%s, args);\n", module);
	    }
	}
    }
    return LOADER_OK;
}

static int selectMedia(struct loaderState *state) {
    return LOADER_OK;
}

static int selectInterface(struct loaderState *state) {
    int rc;
    
    rc = newtWinChoice(_("Install Interface"), _("Text"), _("Graphical"),
		       _("You can install Red Hat Linux using one of two "
			 "interfaces, Text or Graphical.  The text mode "
			 "is similar to older Red Hat Linux installers. "
			 "The Graphical installer is new and offers point "
			 "and click installation of Red Hat Linux."));
    if (rc == 1 || rc == 0)
	state->interface = INTERFACE_TEXT;
    else
	state->interface = INTERFACE_GUI;
    
    return LOADER_OK;
}

int main(int argc, char ** argv) {
    char ** argptr;
    char * anacondaArgs[30];
    char * arg;
    poptContext optCon;
    int network, local, rc;
    struct intfInfo eth0;    
    struct loaderState state;
    struct poptOption optionTable[] = {
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
	    { "network", '\0', POPT_ARG_NONE, &network, 0 },
	    { "local", '\0', POPT_ARG_NONE, &local, 0 },
	    { 0, 0, 0, 0, 0 }
    };
    int step = 0;

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

    openLog(testing);
    
    newtInit();
    newtCls();
    newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));
    
    newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));

    while (step < numSteps) {
	rc = loaderSteps[step].fn(&state);
	switch (rc) {
	case LOADER_OK:
	    step++;
	    break;
	case LOADER_BACK:
	    step--;
	    break;
	case LOADER_ERROR:
	    newtWinMessage(_("Error"), _("OK"),
			   _("An error occured while running the '%s' step"),
			   loaderSteps[step].name);
	    break;
	}
    }
    
    if (!testing) {
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
    *argptr++ = (state.interface == INTERFACE_GUI) ? "-g" : "-T";

    newtFinished();
    
    printf("Launching anaconda (%s), please wait...\n", anacondaArgs[0]);

    execv(anacondaArgs[0], anacondaArgs);
    perror("exec");
 
    return 1;
}

