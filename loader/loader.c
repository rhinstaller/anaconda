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
#include "isys/imount.h"

#define _(x) x

int main(int argc, char ** argv) {
    char * arg;
    poptContext optCon;
    int testing, rc;
    struct poptOption optionTable[] = {
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
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

    newtInit();
    newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));

    newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));

    newtFinished();
    
    execv(testing ? "../anaconda" : "/sbin/anaconda", argv);

    return 0;
}
