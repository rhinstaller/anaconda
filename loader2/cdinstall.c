/*
 * cdinstall.c - code to set up cdrom installs
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <sys/mount.h>
#include <unistd.h>

#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "cdinstall.h"

#include "../isys/probe.h"
#include "../isys/imount.h"
#include "../isys/isys.h"

/* JKFIXME: this needs implementing.  can probably just be copied from
 * queryMediaCheck() in loader/loader.c.  although it will need splitting
 * out a little bit of setupCdrom into its own function */
static void queryCDMediaCheck(char * dev, int flags) {
    return;
}

/* set up a cdrom, nominally for installation 
 *
 * location: where to mount the cdrom at JKFIXME: ignored
 * flags: usual loader flags
 * interactive: whether or not to prompt about questions/errors (1 is yes)
 *
 * side effect: found cdrom is mounted as /mnt/source.  stage2 mounted
 * as /mnt/runtime.
 */
char * setupCdrom(char * location, 
                  struct knownDevices * kd, 
                  moduleInfoSet modInfo, 
                  moduleList modLoaded, 
                  moduleDeps modDeps, 
                  int flags,
                  int interactive) {
    int i, rc;
    int foundinvalid = 0;
    char * buf;

    /* JKFIXME: ASSERT -- we have a cdrom device when we get here */
    do {
        for (i = 0; i < kd->numKnown; i++) {
            if (kd->known[i].class != CLASS_CDROM) continue;

            logMessage("trying to mount device %s", kd->known[i].name);
            devMakeInode(kd->known[i].name, "/tmp/cdrom");
            if (!doPwMount("/tmp/cdrom", "/mnt/source", "iso9660", 1, 0, 
                           NULL, NULL)) {
                if (!access("/mnt/source/RedHat/base/stage2.img", R_OK)) {
                    rc = mountStage2("/mnt/source/RedHat/base/stage2.img");
                    /* if we failed, umount /mnt/source and keep going */
                    if (rc) {
                        umount("/mnt/source");
                        if (rc == -1) foundinvalid = 1;
                        continue;
                    }

                    /* do the media check */
                    queryCDMediaCheck(kd->known[i].name, flags);

                    buf = malloc(200);
                    sprintf(buf, "cdrom://%s/mnt/source", kd->known[i].name);
                    return buf;
                }
                unlink("/tmp/cdrom");
            } 
        } 

        if (interactive) {
            char * buf;
            if (foundinvalid)
                buf = sdupprintf(_("No %s CD was found which matches your "
                                   "boot media.  Please insert the %s CD "
                                   "and press %s to retry."), PRODUCTNAME,
                                 PRODUCTNAME, _("OK"));
            else
                buf = sdupprintf(_("The %s CD was not found in any of your "
                                   "CDROM drives. Please insert the %s CD "
                                   "and press %s to retry."), PRODUCTNAME,
                                 PRODUCTNAME, _("OK"));

            rc = newtWinChoice(_("CD Not Found"),
                               _("OK"), _("Back"), buf, _("OK"));
            free(buf);
            if (rc == 2) return NULL;
        } else {
            /* we can't ask them about it, so just return not found */
            return NULL;
        }
    } while (1);
    return NULL;
}

/* try to find a Red Hat CD non-interactively */
char * findRedHatCD(char * location, 
                    struct knownDevices * kd, 
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags) {
    return setupCdrom(location, kd, modInfo, modLoaded, modDeps, flags, 0);
}



/* look for a Red Hat CD and mount it.  if we have problems, ask */
char * mountCdromImage(struct installMethod * method,
                       char * location, struct knownDevices * kd,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags) {

    setupCdrom(location, kd, modInfo, modLoaded, *modDepsPtr, flags, 1);
}
