#include <popt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>

#include "../isys/isys.h"
#include "modules.h"

void setFloppyDevice(int flags) {
}

char *translateString(char *str) {
	return NULL;
}

int extractModules(int location, char * modName) {
    return 0;
}

void scsiWindow(const char * foo) {
}

void startNewt(int flags) {
}

void newtPopWindow(void) {
}

void newtWinChoice(void) {
}

void newtWinMessage(void) {
}

void eject(void) {
}

void winStatus(void) {
}

int main(int argc, char ** argv) {
    poptContext optCon;
    char * modDepsFile = NULL;
    char * mod;
    int rc;
    char ** list, ** l;
    struct utsname ut;
    moduleDeps ml;
    struct poptOption optionTable[] = {
	    { "moddeps", 'm', POPT_ARG_STRING, &modDepsFile, 0 },
	    POPT_AUTOHELP
	    { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext(NULL, argc, (const char **) argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    if (!modDepsFile) {
        modDepsFile = malloc(100);
	uname(&ut);
	sprintf(modDepsFile, "/lib/modules/%s/modules.dep",
		ut.release);
    }

    ml = mlNewDeps();
    if (mlLoadDeps(&ml, modDepsFile)) {
        fprintf(stderr, "Failed to read %s\n", modDepsFile);
	exit(1);
    }

    while ((mod = (char *) poptGetArg(optCon))) {
        list = mlGetDeps(ml, mod);
	if (list) {
	    for (l = list; *l; l++)
	        printf("%s%s", l == list ? "" : " ", *l);
	    printf("\n");
	}
    }

    return 0;
}

void logMessage(const char * s, ...) {
}
