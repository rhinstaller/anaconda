/*****************************************************************************
 *  DASD setup                                                               *
 *  (c) 2000-2001 Bernhard Rosenkraenzer <bero@redhat.com>                   *
 *  Copyright (C) 2001 Florian La Roche <laroche@redhat.com>                 *
 *****************************************************************************/

#include <newt.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include "common.h"

#define MAX_DASD	26
#define DASD_FMT	"dasd%c"
#define DEV_DASD_FMT	"/dev/" DASD_FMT

int
main (int argc, char **argv)
{
	newtComponent form, tb, ok, cancel, ret, cb[MAX_DASD];
	int format[MAX_DASD], have_dasd[MAX_DASD];
	int w, h, i, dasds = 0;
	char dasd[sizeof (DEV_DASD_FMT) + 1], tmp[4096], error[4096];

	for (i = 0; i < MAX_DASD; i++) {
		int fd;
		sprintf (dasd, DEV_DASD_FMT, 'a' + i);
		if ((fd = open (dasd, O_RDONLY)) >= 0) {
			dasds++;
			have_dasd[i] = 1;
			close (fd);
		} else
			have_dasd[i] = 0;
	}

	doNewtInit (&w, &h);

	if (dasds == 0) {
		newtWinMessage ("Error", "Ok",
			"No DASD devices found.\nPlease check your setup.");
		newtFinished ();
		exit (EXIT_FAILURE);
	}

	newtCenteredWindow (w - 22, h - 6, "DASD initialization");
	form = newtForm (NULL, NULL, 0);
	tb = newtTextbox (1, 0, w - 23, 2, NEWT_FLAG_WRAP);
	newtTextboxSetText (tb, "Please choose which DASDs you would like to "
		"format.\nAll data on those DASDs will be lost.");
	newtFormAddComponent (form, tb);
	for (i = 0; i < MAX_DASD; i++) {
		if (! have_dasd[i])
			continue;
		sprintf (dasd, DEV_DASD_FMT, 'a' + i);
		cb[i] = newtCheckbox (6 + (i / 10) * 16, 3 + (i % 10),
			dasd, '*', NULL, NULL);
		newtFormAddComponent (form, cb[i]);
	}
	ok = newtButton ((w - 22) / 2 - 15, h - 10, "OK");
	newtFormAddComponent (form, ok);
	cancel = newtButton ((w - 22) / 2 + 5, h - 10, "Cancel");
	newtFormAddComponent (form, cancel);

	newtFormSetCurrent (form, ok);

	ret = newtRunForm (form);
	if (ret == cancel) {
		newtFinished ();
		exit (EXIT_FAILURE);
	}

	for (i = 0; i < MAX_DASD; i++)
		format[i] = (have_dasd[i] &&
			newtCheckboxGetValue (cb[i]) == '*');
	newtPopWindow ();

	for (i = 0; i < MAX_DASD; i++) {
		int format_dasd, err = 0;
		FILE *f;
		char proc[256];

		if (! format[i])
			continue;

		sprintf (dasd, DEV_DASD_FMT, 'a' + i);
		newtCenteredWindow (48, 2, "DASD initialization");
		form = newtForm (NULL, NULL, 0);
		tb = newtTextbox (1, 0, 46, 2, NEWT_FLAG_WRAP);
		sprintf (tmp, "Currently formatting DASD %s...\n"
			"This can take several minutes - Please wait.", dasd);
		newtTextboxSetText (tb, tmp);
		newtFormAddComponent (form, tb);
		newtDrawForm (form);
		newtRefresh ();

		/* Check if we need to run dasdfmt... */
		sprintf (tmp, DASD_FMT ":active", 'a' + i);
		f = fopen ("/proc/dasd/devices", "r");
		format_dasd = (f && !ferror (f));
		while (format_dasd && !feof (f)) {
			fgets (proc, sizeof proc, f);
			if (strstr (proc, tmp))
				format_dasd = 0;
		}
		if (f)
			fclose (f);

		if (format_dasd) {
			sprintf (tmp, "/sbin/dasdfmt -b 4096 -y -f %s", dasd);
			if ((err = system (tmp))) {
				sprintf (error,
					"Error %d while trying to run\n%s:\n%s",
					err, tmp, strerror (errno));
				newtWinMessage ("Error", "Ok", error);
				format_dasd = 0;
			}
		}
		if (err == 0) {
			sprintf (tmp, "Making %s filesystem on DASD %s...\n"
				"This can take a while - Please wait.",
				"ext2", dasd);
			newtTextboxSetText (tb, tmp);
			newtRefresh ();
			sprintf (tmp, "/sbin/mke2fs -b 4096 %s1 >>"
				"/tmp/mke2fs.log 2>&1", dasd);
			err = system (tmp);
			if (err != 0) {
				sprintf (error,
					"Error %u while trying to run\n%s:\n%s",
					err, tmp, strerror (errno));
				newtWinMessage ("Error", "Ok", error);
				newtPopWindow ();
				newtFinished ();
				exit (EXIT_FAILURE);
			}
		}
		newtPopWindow ();
	}
	newtFinished ();
	exit (EXIT_SUCCESS);
}
