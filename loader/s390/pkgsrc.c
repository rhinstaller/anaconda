/*****************************************************************************
 *  Package source selection                                                 *
 *  (c) 2000 Bernhard Rosenkraenzer <bero@redhat.com>                        *
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

int
main (int argc, char **argv)
{
	newtComponent form, ok, cancel, ret, path, lbl, *cur;
	char *server;
	int width, height;
	FILE *f;

	server = "ftp://ftp.localdomain.com/pub/s390";
	if (argc >= 2 && argv[1][0])
	    server = argv[1];

	doNewtInit (&width, &height);
	width -= 7;

	newtCenteredWindow (width, 12, "Package source");
	form = newtForm (NULL, NULL, 0);

	lbl = newtTextbox(1, 1, width - 1, 4, NEWT_FLAG_WRAP);
	newtTextboxSetText(lbl, "Please enter the full path to the Red Hat "
		"Linux for S/390 RPMs. This can be an FTP, HTTP or NFS URL.\n"
		"(Examples: ftp://ftp.local.com/pub/s390, "
		"http://www.local.com/s390, nfs.local.com:/mnt/s390)");
	newtFormAddComponent (form, lbl);

	path = newtEntry (2, 6, server, width - 4, NULL, NEWT_ENTRY_SCROLL);
	newtFormAddComponent (form, path);

	ok = newtButton (width / 2 - 15, 8, "OK");
	newtFormAddComponent (form, ok);
	cancel = newtButton (width / 2 + 5, 8, "Cancel");
	newtFormAddComponent (form, cancel);

	if (argc >= 2 && argv[1][0] && server && *server)
		newtFormSetCurrent (form, ok);
	else
		newtFormSetCurrent (form, path);

	ret = newtRunForm (form);
	newtPopWindow ();
	newtFinished ();

	if (ret == cancel || !(f = fopen ("/tmp/rpmserver", "w")))
		exit (EXIT_FAILURE);

	fprintf (f, "RPMSERVER=\"%s\"\n", newtEntryGetValue (path));
	fclose (f);
	
	exit (EXIT_SUCCESS);
}
