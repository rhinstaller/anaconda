/*
 * Copyright (c) 2001 Red Hat, Inc. All rights reserved.
 * 
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 * 
 * Author: Karsten Hopp <karsten@redhat.de>
 *
 * Package selection
 */

#include <newt.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include "common.h"


struct s_packages {
	char *name;
	char *suffix;
	char *filename;
};

struct s_packages packages[] = {
	{ "Minimal    - Install just a base system", "minimal", "packages.minimal" },
	{ "Desktop    - Install packages for desktop use", "desktop", "packages.desktop" },
	{ "Default    - A selection of the most common packages", "default", "packages.default" },
	{ "Server     - A selection best suited for servers", "server", "packages.server" },
	{ "Everything - Install everything", "all", "packages.all" }
};

#define NUM_PACKAGES (sizeof(packages) / sizeof(struct s_packages))

int
main (int argc, char **argv)
{
	newtGrid grid, subgrid, buttons;
	newtComponent label, listbox, text_b, form, okay, cancel, answer;
	char *defcomp;
	int i;
  	int width, height, selection;
	FILE *f;
   
	defcomp = "default";
	if (argc >= 2 && argv[1][0]) {
			for(i=0; i<NUM_PACKAGES; i++) {
				printf("FN: %s , PN: %s\n", argv[1], packages[i].suffix);
				if(!strncmp(packages[i].suffix, argv[1], strlen(packages[i].suffix))) {
	    			defcomp = argv[1];
					break;
				}
			}
	}
	printf("defcomp ist %s\n", defcomp);

	doNewtInit (&width, &height);
	width -= 7;

	form = newtForm (NULL, NULL, 0);
	label = newtLabel(-1, -1, ("Please select a set of preconfigured packages from this list"));

	listbox = newtListbox(1, 1, NUM_PACKAGES >= 8 ? 8 : NUM_PACKAGES, \
		  	NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);
	for(i=0; i<NUM_PACKAGES; i++) {
		  newtListboxAddEntry(listbox, packages[i].name, (void **) i);
		  if(!strncmp(packages[i].suffix, defcomp, strlen(defcomp)))
			  newtListboxSetCurrent(listbox, i);
	}
	/* text_b = newtTextbox(1, 1, 20, 5, NEWT_FLAG_WRAP);
		* newtTextboxSetText(text_b, packages[(int)newtListboxGetCurrent(listbox)].description);
	   * newtPushHelpLine(packages[(int)newtListboxGetCurrent(listbox)].description);
		*
		* subgrid = newtGridHStacked(NEWT_GRID_COMPONENT, listbox, NEWT_GRID_COMPONENT, text_b, NULL);
	*/

	subgrid = newtGridHStacked(NEWT_GRID_COMPONENT, listbox, NULL);
	buttons = newtButtonBar(("Ok"), &okay, ("Cancel"), &cancel, NULL);

	if (argc >= 2 && argv[1][0] && defcomp && *defcomp)
		newtFormSetCurrent (form, okay);

	grid = newtGridBasicWindow(label, subgrid, buttons);
	newtGridWrappedWindow(grid, ("Package selection"));
	newtGridAddComponentsToForm(grid, form, 1);
	newtGridFree(grid, 1);


	while ((answer = newtRunForm(form)) != okay && (answer != NULL)) {
		if (answer == cancel) {
			newtPopWindow();
			newtFormDestroy(form);
			newtFinished ();
			return 1;
		} else {
			/* must have pressed F12 */
			break;
		}
	} 
	selection = (int) newtListboxGetCurrent(listbox);
   if (!(f=fopen("/tmp/selection", "w"))) {
		perror("Couldn't write to /tmp/selection");
		exit(1);
	}
	fprintf(f, "%s", packages[selection].suffix);
	fclose(f);
	newtFinished ();

	exit (EXIT_SUCCESS);
}
/* vim:ts=3:sw=3
 */
