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

static const char shortopts[] = "k:d:r:vbmlfh";
static const char *usage = "Usage: dd_extract [-vbmlfh] -k <kernel> -d <directory> -r <rpm>\n";

enum {
    OPT_NONE = 0,
};

static const struct option longopts[] = {
    //{name, no_argument | required_argument | optional_argument, *flag, val}
    {"directory", required_argument, NULL, 'd'},
    {"rpm",       required_argument, NULL, 'r'},
    {"kernel",    required_argument, NULL, 'k'},
    {"verbose",   no_argument,       NULL, 'v'},
    {"binaries",  no_argument,       NULL, 'b'},
    {"modules",   no_argument,       NULL, 'm'},
    {"libraries", no_argument,       NULL, 'l'},
    {"firmwares", no_argument,       NULL, 'f'},
    {"help",      no_argument,       NULL, 'h'},
    {NULL,        0,                 NULL, 0 }
};

static const char *options_help [][2] = {
    {"directory", "Directory to extract into"},
    {"rpm",       "rpm to extract"},
    {"kernel",    "kernel version"},
    {"verbose",   "Verbose output"},
    {"binaries",  "Extract binaries"},
    {"modules",   "Extract modules"},
    {"libraries", "Extract libraries"},
    {"firmwares", "Extract firmwares"},
    {"help",      "Show this help"},
    {NULL,        NULL}
};

/**
 * Show the available options and their help strings
 */
void show_help() {
    int i;

    printf(usage);
    for (i=0; options_help[i][0]; i++) {
        printf("  -%c, --%-20s %s\n", options_help[i][0][0],
                                      options_help[i][0],
                                      options_help[i][1]);
    }
}

/*
 * during cpio extraction, only extract files we need
 * eg. module .ko files and firmware directory
 */
int dlabelFilter(const char* name, const struct stat *fstat, int packageflags, void *userptr)
{
    int l = strlen(name);

    logMessage(DEBUGLVL, "Unpacking %s with flags %02x\n", name, packageflags);

    /* unpack bin and sbin if the package was marked as installer-enhancement */
    if ((packageflags & dup_binaries)) {
        if(!strncmp("bin/", name, 4))
            return 1;
        else if (!strncmp("sbin/", name, 5))
            return 1;
        else if (!strncmp("usr/bin/", name, 8))
            return 1;
        else if (!strncmp("usr/sbin/", name, 9))
            return 1;
    }

    /* unpack lib and lib64 if the package was marked as installer-enhancement */
    if ((packageflags & dup_libraries)) {
        if(!strncmp("lib/", name, 4))
            return 1;
        else if (!strncmp("lib64/", name, 6))
            return 1;
        else if (!strncmp("usr/lib/", name, 8))
            return 1;
        else if (!strncmp("usr/lib64/", name, 10))
            return 1;
    }

    /* we want firmware files */
    if ((packageflags & dup_firmwares) && !strncmp("lib/firmware/", name, 13))
        return 1;

    /* we do not want kernel files */
    if (!(packageflags & dup_modules))
        return 0;

    /* check if the file has at least four chars eg X.SS */
    if (l<3)
        return 0;
    l-=3;

    /* and we want only .ko files here */
    if (strcmp(".ko", name+l))
        return 0;

    /* we are unpacking kernel module.. */

    return 1;
}

int main(int argc, char *argv[])
{
    int rc = 0;
    int option;
    int option_index;

    char *rpm = NULL;
    char *directory = NULL;
    char *kernel = NULL;

    int packageflags = 0;

    int verbose = 0;
    char *oldcwd = NULL;

    while ((option = getopt_long(argc, argv, shortopts, longopts, &option_index)) != -1) {
        switch (option) {
        case 0:
            /* long option */
            break;

        case 'd':
            directory = strdup(optarg);
            break;

        case 'k':
            kernel = strdup(optarg);
            break;

        case 'r':
            rpm = strdup(optarg);
            break;

        case 'v':
            verbose = 1;
            break;

        case 'f':
            packageflags |= dup_firmwares;
            break;

        case 'm':
            packageflags |= dup_modules;
            break;

        case 'b':
            packageflags |= dup_binaries;
            break;

        case 'l':
            packageflags |= dup_libraries;
            break;

        case 'h':
            show_help();
            rc = 0;
            goto cleanup;
        }

    }

    if (!directory || !kernel || !rpm) {
        logMessage(ERROR, "Missing argument\n");
        show_help();
        rc = 1;
        goto cleanup;
    }

    if (verbose) {
        printf("Extracting DUP RPM to %s\n", directory);
    }

    /* get current working directory */
    oldcwd = getcwd(NULL, 0);
    if (!oldcwd) {
        logMessage(ERROR, "getcwd() failed: %m\n");
        rc = 1;
        goto cleanup;
    }

    /* set the cwd to destination */
    if (chdir(directory)) {
        logMessage(ERROR, "We weren't able to CWD to \"%s\": %m\n", directory);
        rc = 1;
        goto cleanup;
    }

    init_rpm();
    explodeDDRPM(rpm, dlabelFilter, packageflags, kernel);

    /* restore CWD */
    if (chdir(oldcwd)) {
        logMessage(WARNING, "We weren't able to restore CWD to \"%s\": %m\n", oldcwd);
    }

cleanup:
    free(directory);
    free(kernel);
    free(rpm);
    free(oldcwd);

    return rc;
}
