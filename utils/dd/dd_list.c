/*
 * Copyright (C) 2011-2013  Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s):   Martin Sivak <msivak@redhat.com>
 *              Brian C. Lane <bcl@redhat.com>
 */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <getopt.h>
#include <glob.h>

#include "rpmutils.h"
#include "dd_utils.h"

static const char shortopts[] = "a:d:k:v";
static const char *usage = "Usage: dd_list [-vh] -k <kernel> -d <directory> -a <anaconda>\n";

enum {
    OPT_NONE = 0,
};

static const struct option longopts[] = {
    //{name, no_argument | required_argument | optional_argument, *flag, val}
    {"directory", required_argument, NULL, 'd'},
    {"kernel",    required_argument, NULL, 'k'},
    {"anaconda",  required_argument, NULL, 'a'},
    {"verbose",   no_argument,       NULL, 'v'},
    {"help",      no_argument,       NULL, 'h'},
    {NULL,        0,                 NULL, 0}
};

static const char *options_help [][2] = {
    {"directory", "Directory to search for *.rpm files"},
    {"kernel",    "kernel version"},
    {"anaconda",  "anaconda version"},
    {"verbose",   "Verbose output"},
    {"help",      "Show this help"},
    {NULL,        NULL}
};

struct _version_struct {
    char* kernel;
    char* anaconda;
};

int globErrFunc(const char *epath, int eerrno)
{
    /* TODO check fatal errors */

    return 0;
}


/**
 * Show the available options and their help strings
 */
void show_help() {
    int i;

    printf("%s", usage);
    for (i=0; options_help[i][0]; i++) {
        printf("  -%c, --%-20s %s\n", options_help[i][0][0],
                                      options_help[i][0],
                                      options_help[i][1]);
    }
}

/**
 * check if the RPM in question provides
 * Provides: <dep> = <version>
 * we use it to check if kernel-modules = <kernel version>
 * and installer-enhancement = <anaconda version>
 */
int dlabelProvides(const char* dep, const char* version, uint32_t sense, void *userptr)
{
    char *kernelver = ((struct _version_struct*)userptr)->kernel;
    char *anacondaver = ((struct _version_struct*)userptr)->anaconda;

    int packageflags = 0;

    logMessage(DEBUGLVL, "Provides: %s = %s\n", dep, version);

    if (version == NULL)
        return 0;

    /* is it a modules package? */
    if (!strcmp(dep, "kernel-modules")) {

        /*
         * exception for 6.0 and 6.1 DDs, we changed the logic a bit and need to maintain compatibility.
         */
        if ((!strncmp(version, "2.6.32-131", 10)) || (!strncmp(version, "2.6.32-71", 9)))
            packageflags |= dup_modules | dup_firmwares;

        /*
         * Use this package only if the version match string is true for this kernel version
         */
        if (!matchVersions(kernelver, sense, version))
            packageflags |= dup_modules | dup_firmwares;
    }

    /* is it an app package? */
    if (!strcmp(dep, "installer-enhancement")) {

        /*
         * If the version string matches anaconda version, unpack binaries to /tmp/DD
         */
        if (!matchVersions(anacondaver, sense, version))
            packageflags |= dup_binaries | dup_libraries;
    }

    return packageflags;
}

/**
 * Print information about the rpm to stdout
 */
int dlabelOK(const char* source, Header *h, int packageflags)
{
    struct rpmtd_s tdname;
    struct rpmtd_s tddesc;

    const char *name;
    const char *description;

    if (!headerGet(*h, RPMTAG_NAME, &tdname, HEADERGET_MINMEM))
        return 0;

    if (!headerGet(*h, RPMTAG_DESCRIPTION, &tddesc, HEADERGET_MINMEM)){
        rpmtdFreeData(&tdname);
        return 0;
    }

    /* iterator */
    name = rpmtdNextString(&tdname);
    description = rpmtdNextString(&tddesc);

    fprintf(stdout, "%s\n%s\n", source, name);

    if (packageflags & dup_modules) fprintf(stdout, "modules ");
    if (packageflags & dup_firmwares) fprintf(stdout, "firmwares ");
    if (packageflags & dup_binaries) fprintf(stdout, "binaries ");
    if (packageflags & dup_libraries) fprintf(stdout, "libraries ");

    fprintf(stdout, "\n%s\n---\n", description);

    rpmtdFreeData(&tdname);
    rpmtdFreeData(&tddesc);

    return 0;
}

int main(int argc, char *argv[])
{
    int rc = 0;
    int option;
    int option_index;

    char *directory = NULL;
    int verbose = 0;

    struct _version_struct versions = {NULL, NULL};

    while ((option = getopt_long(argc, argv, shortopts, longopts, &option_index)) != -1) {
        switch (option) {
        case 0:
            /* long option */
            break;

        case 'd':
            directory = strdup(optarg);
            break;

        case 'k':
            versions.kernel = strdup(optarg);
            break;

        case 'a':
            versions.anaconda = strdup(optarg);
            break;

        case 'v':
            verbose = 1;
            break;

        case 'h':
            show_help();
            rc = 0;
            goto cleanup;
        }

    }

    if (!directory || !versions.kernel || !versions.anaconda) {
        show_help();
        rc = 1;
        goto cleanup;
    }

    if (verbose) {
        printf("Listing DD dir %s\n", directory);
    }

    init_rpm();

    char *globpattern;
    checked_asprintf(&globpattern, "%s/*.rpm", directory);

    glob_t globres;
    char** globitem;

    if (!glob(globpattern, GLOB_NOSORT|GLOB_NOESCAPE, globErrFunc, &globres)) {
        /* iterate over all rpm files */
        globitem = globres.gl_pathv;
        while (globres.gl_pathc>0 && globitem != NULL && *globitem != NULL) {
            checkDDRPM(*globitem, dlabelProvides, NULL, dlabelOK, &versions);
            globitem++;
        }
        globfree(&globres);
        /* end of iteration */
    }
    free(globpattern);

cleanup:
    free(directory);
    free(versions.kernel);
    free(versions.anaconda);

    return rc;
}
