/*
 * kbd.c - keyboard handling
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

#include <alloca.h>
#include <errno.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>

#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "windows.h"

#include "../isys/stubs.h"
#include "../isys/lang.h"

/* boot flags */
extern uint64_t flags;

int chooseKeyboard(struct loaderData_s * loaderData, char ** kbdtypep) {
    int num = -1;
    int rc;
    gzFile f;
    struct kmapHeader hdr;
    struct kmapInfo * infoTable;
    struct langInfo * languages;
    int numLanguages;
    char ** kbds;
    char buf[16384]; 			/* I hope this is big enough */
    int i;
    char * defkbd = loaderData->kbd ? loaderData->kbd : NULL;
    char *lang;

#if defined(__s390__) || defined(__s390x__)
    return LOADER_NOOP;
#endif

    if (FL_SERIAL (flags) || FL_VIRTPCONSOLE(flags)) return LOADER_NOOP;

#ifdef __sparc__
    {
        int fd;
        
	fd = open("/dev/kbd", O_RDWR);
	if (fd < 0)
	    kbdtype = KBDTYPE_PC; /* if PC keyboard, then there is no driver for /dev/kbd */
	else {
	    close(fd);
	    kbdtype = KBDTYPE_SUN;
	}
    }
#endif /* sparc */

    numLanguages = getLangInfo(&languages);

    lang = getenv("LANG");
    if (!lang)
       lang = loaderData->lang;

    if (!defkbd && lang) {
	for (i = 0; i < numLanguages; i++) {
	    if (!strncmp(languages[i].lc_all, lang, 2)) {
		defkbd = languages[i].keyboard;
		break;
	    }
	}
    }

    if (!defkbd)
#ifdef __sparc__
	if (kbdtype == KBDTYPE_SUN)
	    defkbd = "sunkeymap";
	else
#endif /* sparc drain bamage */
	    defkbd = "us";

    f = gunzip_open("/etc/keymaps.gz");
    if (!f) {
	errorWindow("cannot open /etc/keymaps.gz: %s");
	return LOADER_ERROR;
    }

    if (gunzip_read(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	errorWindow("failed to read keymaps header: %s");
	gunzip_close(f);
	return LOADER_ERROR;
    }

    logMessage(INFO, "%d keymaps are available", hdr.numEntries);

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gunzip_read(f, infoTable, i) != i) {
	errorWindow("failed to read keymap information: %s");
	gunzip_close(f);
	return LOADER_ERROR;
    }

    if (num == -1 ) {
	kbds = alloca(sizeof(*kbds) * (hdr.numEntries + 1));
	for (i = 0; i < hdr.numEntries; i++)  {
	    kbds[i] = infoTable[i].name;
	}

	kbds[i] = NULL;
	qsort(kbds, i, sizeof(*kbds), simpleStringCmp);

	for (i = 0; i < hdr.numEntries; i++) 
	    if (!strcmp(kbds[i], defkbd)) 
		num = i;

	rc = newtWinMenu(_("Keyboard Type"), 
			_("What type of keyboard do you have?"),
		        40, 5, 5, 8, kbds, &num, _("OK"), _("Back"), NULL);
	if (rc == 2) return LOADER_BACK;

	/* num needs to index the right keyboard infoTable */
	for (i = 0; i < hdr.numEntries; i++)
	    if (!strcmp(kbds[num], infoTable[i].name)) break;
	num = i;
    }

    rc = 0;

    for (i = 0; i < num; i++) {
	if (gunzip_read(f, buf, infoTable[i].size) != infoTable[i].size) {
	    logMessage(ERROR, "error reading %d bytes from file: %s", 
		       infoTable[i].size, strerror(errno));
	    gunzip_close(f);
	    rc = LOADER_ERROR;
	}
    }

    if (!rc) rc = loadKeymap(f);

    /* normalize the error condition */
    /* MSWFIXME - do we want to warn the user that setting the
       keyboard didn't work?
    */
    if (rc != 0)
	rc = LOADER_ERROR;
    
    gunzip_close(f);

    loaderData->kbd = strdup(infoTable[num].name);

#ifdef __sparc__
    if (kbdtypep) *kbdtypep = (kbdtype == KBDTYPE_SUN) ? "sun" : "pc";
#endif

    return rc;
}

void setKickstartKeyboard(struct loaderData_s * loaderData, int argc, 
                          char ** argv) {
    if (argc < 2) {
        logMessage(ERROR, "no argument passed to keyboard kickstart command");
        return;
    }

    loaderData->kbd = argv[1];
    loaderData->kbd_set = 1;
}
