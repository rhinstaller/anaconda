/*****************************************************************************
 *  DASD mount point setup                                                   *
 *  (c) 2000-2001 Bernhard Rosenkraenzer <bero@redhat.com>                   *
 *  v 0.2.1 - 2001/04/25 Helge Deller <hdeller@redhat.de>                    *
 *	- added commandline-parsing of the initial mountpoints               *
 *	- exit program if user press the Cancel-button                       *
 *	- added check for existance of root-fs                               *
 *  v 0.2.0 - 2000/12/18                                                     *
 *	initial release                                                      *
 *	TODO: sanity checks:                                                 *
 *	      you can't mount different DASDs at the same mount point.       *
 *****************************************************************************/

#include <newt.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include "common.h"

#define MAX_DASD        26
#define DASD_FMT        "dasd%c"
#define DASD_FMT_P1	DASD_FMT "1"
#define DEV_DASD_FMT    "/dev/" DASD_FMT
#define DEV_DASD_FMT_P1	DEV_DASD_FMT "1"

int
main (int argc, char **argv)
{
	newtComponent form, ok, cancel, ret, mountPoint[MAX_DASD];
	char *mp[MAX_DASD], dasd[13];
	int have_dasd[MAX_DASD], num_dasds = 0, w, h, i, fd, root_found;
	FILE *f;

	for (i = 0; i < MAX_DASD; i++) {
		sprintf (dasd, DEV_DASD_FMT_P1, 'a' + i);
		mp[i] = NULL;
		have_dasd[i] = 0;
		fd = open (dasd, O_RDONLY);
		if (fd >= 0) {
			num_dasds++;
			have_dasd[i] = 1;
			close (fd);
		}
	}

	doNewtInit (&w, &h);
	if (num_dasds == 0) {
		newtWinMessage ("Error", "Ok", "No DASD devices found.\n"
			"Please check your setup.");
		newtFinished ();
		exit (EXIT_FAILURE);
	}

	/* analyze the initial mountpoint from the commandline,
	 * which should be given as argv's in the style:
	 * /dev/dasda1:/usr /dev/dasdb1:/tmp
	 */
	for (i = 2; i < argc; i++) {
		int n;
		char *d = argv[i];
		char *p = strchr (d, ':');
		char msg[1024];

		if (!p) {
			snprintf (msg, sizeof msg, "Invalid parameter: %s\n"
				"Usage is: %s <dasd-partition>:<mountpoint>",
				d, argv[0]);
			newtWinMessage ("Error", "Ok", msg);
			continue;
		}

		*p++ = '\0';
		for (n = 0; n < MAX_DASD; n++) {
			sprintf (dasd, DEV_DASD_FMT_P1, 'a' + n);
			if (strncmp (d, dasd, strlen (dasd)) == 0)
				break;
		}

		if (n >= MAX_DASD) {
			snprintf (msg, sizeof msg,
				"Invalid %s DASD device in command-line.", d);
			newtWinMessage ("Error", "Ok", msg);
			continue;
		}

		if (p[0] != '/') {
			snprintf (msg, sizeof msg, "Invalid path '%s' for "
				"DASD device %s in command-line.", p, d);
			newtWinMessage ("Error", "Ok", msg);
			continue;
		}

		if (!have_dasd[n]) {
			snprintf (msg, sizeof msg,
				"DASD device %s is not on-line.", d);
			newtWinMessage ("Error", "Ok", msg);
			continue;
		}

		/* save this mountpoint */
		mp[n] = p;
	}

	newtCenteredWindow (73, 18, "Mount points");
	form = newtForm (NULL, NULL, 0);
	newtFormAddComponent (form, newtLabel (1, 0,
		"Please choose the mount points for your DASDs."));
	for (i = 0; i < MAX_DASD; i++) {
		if (have_dasd[i]) {
			sprintf (dasd, DASD_FMT_P1 ":", 'a' + i);
			newtFormAddComponent (form, newtLabel (1 + (i / 11)
				* 24, 2 + (i % 11), dasd));
			mountPoint[i] = newtEntry (1 + (i / 11) * 24 + 8, 2
				+ (i % 11), mp[i], 15, NULL, NEWT_ENTRY_SCROLL);
			newtFormAddComponent (form, mountPoint[i]);
		}
	}
	ok = newtButton (73 / 2 - 15, 14, "OK");
	cancel = newtButton (73 / 2 + 5, 14, "Cancel");
	newtFormAddComponent (form, ok);
	newtFormAddComponent (form, cancel);
	newtFormSetCurrent (form, ok);

	do {
		ret = newtRunForm (form);
		if (ret == cancel) {
			newtPopWindow ();
			newtFinished ();
			exit (EXIT_FAILURE);
		}

		/* check for a root-fs */
		root_found = 0;
		for (i = 0; i < MAX_DASD; i++) {
			char *mp;
			if (!have_dasd[i])
				continue;
			mp = newtEntryGetValue (mountPoint[i]);
			if (mp && strcmp (mp, "/") == 0)
				root_found = 1;
		}
		if (!root_found)
			newtWinMessage ("Error", "Ok",
				"You need at least one root-filesystem.\n");
	} while (!root_found);

	f = fopen (argv[1], "w");
	for (i = 0; i < MAX_DASD; i++) {
		if (have_dasd[i]) {
			char tmp[512];
			sprintf (dasd, DEV_DASD_FMT_P1, 'a' + i);
			mp[i] = newtEntryGetValue (mountPoint[i]);
			if (mp[i] && strlen (mp[i])) {
				int err;
				fprintf (f, "%s:%s\n", dasd, mp[i]);
				snprintf (tmp, sizeof (tmp),
					"/sbin/tune2fs -L %s %s"
					" >/dev/null 2>&1", mp[i], dasd);
				err = system (tmp);
				if (err != 0) {
					char s[2048];
					snprintf (s, sizeof (s),
						"Error %u while "
						"running\n%s:\n%s", err, tmp,
						strerror (errno));
					newtWinMessage ("Error", "Ok", s);
				}
			}
		}
	}
	fclose (f);

	newtPopWindow ();
	newtFinished ();
	exit (EXIT_SUCCESS);
}
