/*****************************************************************************
 *  Network configuration                                                    *
 *  (c) 2001 Bernhard Rosenkraenzer <bero@redhat.com>                        *
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
	newtComponent form, ok, cancel, ret, host, domains, dns;
	char *d, *ip, *tmp, *txt_hostname, *txt_search, *txt_dns;
	char error[4096];
	int w, h;
	FILE *f;

	/* XXX should be passed in argv instead */
	txt_hostname = getenv ("HNAME");
	txt_search = getenv ("SEARCHDNS");
	txt_dns = getenv ("DNS");

	doNewtInit (&w, &h);
	newtCenteredWindow (w - 7, 11, "Network setup");

	form = newtForm (NULL, NULL, 0);
	newtFormAddComponent (form, newtLabel (1, 0, "Your full hostname:"));
	host = newtEntry (1, 1, txt_hostname, w - 9, NULL, NEWT_ENTRY_SCROLL);
	newtFormAddComponent (form, host);
	newtFormAddComponent (form, newtLabel (1, 2,
		"Domain name search list:"));
	domains = newtEntry (1, 3, txt_search, w - 9, NULL, NEWT_ENTRY_SCROLL);
	newtFormAddComponent (form, domains);
	newtFormAddComponent (form, newtLabel (1, 4,
		"IP(s) of your DNS server(s), separated by spaces:"));
	dns = newtEntry (1, 5, txt_dns, w - 9, NULL, NEWT_ENTRY_SCROLL);
	newtFormAddComponent (form, dns);

	ok = newtButton ((w - 7) / 2 - 15, 7, "OK");
	cancel = newtButton ((w - 7) / 2 + 5, 7, "Cancel");
	newtFormAddComponent (form, ok);
	newtFormAddComponent (form, cancel);

	newtFormSetCurrent (form, ok);

	ret = newtRunForm (form);
	if (ret == cancel) {
		newtPopWindow ();
		newtFinished ();
		exit (EXIT_FAILURE);
	}

	f = fopen ("/etc/resolv.conf", "w");
	if (!f) {
		int err = errno;
		sprintf (error,
			"Error %d while trying to write /etc/resolv.conf\n%s",
			err, strerror (err));
		newtWinMessage ("Error", "Ok", error);
		newtPopWindow ();
		newtFinished ();
		exit (EXIT_FAILURE);
	}
	fprintf (f, "search %s\n", newtEntryGetValue (domains));
	d = newtEntryGetValue (dns);
	ip = strtok (d, " ");
	while (ip) {
		fprintf (f, "nameserver %s\n", ip);
		ip = strtok (NULL, " ");
	}
	fclose (f);

	f = fopen ("/etc/HOSTNAME", "w");
	if (!f) {
		int err = errno;
		sprintf (error,
			"Error %d while trying to write /etc/HOSTNAME\n%s",
			err, strerror (err));
		newtWinMessage ("Error", "Ok", error);
		newtPopWindow ();
		newtFinished ();
		exit (EXIT_FAILURE);
	}
	fputs (newtEntryGetValue (host), f);
	fclose (f);
	newtPopWindow ();
	newtFinished ();
	exit (EXIT_SUCCESS);
}
