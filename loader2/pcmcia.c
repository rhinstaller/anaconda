/*
 * pcmcia.c - pcmcia functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1999 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "loader.h"
#include "modules.h"

int pcmciaInitialize(moduleList modLoaded, moduleDeps modDeps,
		     moduleInfoSet modInfo, int flags) {
    if (FL_NOPCMCIA(flags))
	return 0;

    /* JKFIXME: obviously we need real code here... */
    return 0;
}
