/* unpack the payload of RPM package to the current directory
 *
 * File name: rpmutils.c
 * Based on:  loader/rpmextract.c from RHEL6 Anaconda
 * Date:      2012/06/29
 * Author:    Martin Sivak <msivak at redhat dot com>
 *
 * Copyright (C) 2012-2013 Red Hat, Inc. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 * */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <rpm/rpmlib.h>		/* rpmReadPackageFile .. */
#include <rpm/rpmtag.h>
#include <rpm/rpmio.h>
#include <rpm/rpmpgp.h>

#include <rpm/rpmts.h>

#include <stdio.h>
#include <archive.h>
#include <archive_entry.h>

#include "rpmutils.h"

/*
 * internal structure to pass to libarchive callbacks
 */

struct cpio_mydata {
    FD_t gzdi;
    char *buffer;
};

/*
 * libarchive callbacks
 */

ssize_t rpm_myread(struct archive *a, void *client_data, const void **buff)
{
    struct cpio_mydata *mydata = client_data;
    *buff = mydata->buffer;
    return Fread(mydata->buffer, 1, BUFFERSIZE, mydata->gzdi);
}

int rpm_myclose(struct archive *a, void *client_data)
{
    struct cpio_mydata *mydata = client_data;
    if (mydata->gzdi > 0)
        Fclose(mydata->gzdi);
    return ARCHIVE_OK;
}

/**
 * Handle any rpm library related setup
 *
 * Call this once at program start.
 */
int init_rpm() {
    return rpmReadConfigFiles(NULL, NULL);
}


/* read data from RPM header */

const char * headerGetString(Header h, rpmTag tag)
{
    const char *res = NULL;
    struct rpmtd_s td;

    if (headerGet(h, tag, &td, HEADERGET_MINMEM)) {
        if (rpmtdCount(&td) == 1) {
            res = rpmtdGetString(&td);
        }
        rpmtdFreeData(&td);
    }
    return res;
}

/*
 *
 */

int matchVersions(const char *version, uint32_t sense, const char *senseversion)
{
    int r = rpmvercmp(version, senseversion);

    if(r<0 && !(sense & RPMSENSE_LESS)) return 1;
    else if(r==0 && !(sense & RPMSENSE_EQUAL)) return 1;
    else if(r>0 && !(sense & RPMSENSE_GREATER)) return 1;

    return 0;
}

static int readRPM(const char *source, FD_t *fdi, Header *h)
{
    rpmts ts;
    rpmVSFlags vsflags;
    rpmRC rc;

    if (strcmp(source, "-") == 0)
        *fdi = fdDup(STDIN_FILENO);
    else
        *fdi = Fopen(source, "r.ufdio");

    if (Ferror(*fdi)) {
        //const char *srcname = (strcmp(source, "-") == 0) ? "<stdin>" : source;
        //logMessage(ERROR, "%s: %s\n", srcname, Fstrerror(*fdi));
        return EXIT_FAILURE;
    }

    /* Initialize RPM transaction */
    ts = rpmtsCreate();
    vsflags = 0;

    /* Do not check digests, signatures or headers */
    vsflags |= _RPMVSF_NODIGESTS;
    vsflags |= _RPMVSF_NOSIGNATURES;
    vsflags |= RPMVSF_NOHDRCHK;
    (void) rpmtsSetVSFlags(ts, vsflags);

    rc = rpmReadPackageFile(ts, *fdi, "rpm2dir", h);

    ts = rpmtsFree(ts);

    switch (rc) {
        case RPMRC_OK:
        case RPMRC_NOKEY:
        case RPMRC_NOTTRUSTED:
            break;
        case RPMRC_NOTFOUND:
            //logMessage(ERROR, "%s is not an RPM package", source);
            return EXIT_FAILURE;
            break;
        case RPMRC_FAIL:
        default:
            //logMessage(ERROR, "error reading header from %s package\n", source);
            return EXIT_FAILURE;
            break;
    }

    return RPMRC_OK;
}

/*
 * Check if the RPM is a properly formated driver
 * update package. Call ok(Header*) if it is.
 */
int checkDDRPM(const char *source,
             dependencyfunc provides,
             dependencyfunc deps,
             okfunc ok,
             void* userptr)
{
    FD_t fdi;
    Header h;
    rpmRC rc;
    int packageflags = 0;

    rc = readRPM(source, &fdi, &h);
    Fclose(fdi);
    fdi = NULL;

    if (rc != RPM_OK) {
        return rc;
    }

    /* Retrieve all dependencies and run them through deps function */
    while (deps) {
        struct rpmtd_s tddep;
        struct rpmtd_s tdver;
        struct rpmtd_s tdsense;

        const char *depname;
        const char *depversion;
        uint32_t depsense;

        if (!headerGet(h, RPMTAG_REQUIRES, &tddep, HEADERGET_MINMEM))
            break;

        if (!headerGet(h, RPMTAG_REQUIREVERSION, &tdver, HEADERGET_MINMEM)){
            rpmtdFreeData(&tddep);
            break;
        }

        if (!headerGet(h, RPMTAG_REQUIREFLAGS, &tdsense, HEADERGET_MINMEM)){
            rpmtdFreeData(&tddep);
            rpmtdFreeData(&tdver);
            break;
        }

        /* iterator */
        while ((depname = rpmtdNextString(&tddep))) {
            depversion = rpmtdNextString(&tdver);
            depsense = *(rpmtdNextUint32(&tdsense));
            if (deps(depname, depversion, depsense, userptr)) {
                rpmtdFreeData(&tddep);
                rpmtdFreeData(&tdver);
                rpmtdFreeData(&tdsense);
                return EXIT_BADDEPS;
            }
        }

        rpmtdFreeData(&tddep);
        rpmtdFreeData(&tdver);
        rpmtdFreeData(&tdsense);

        break;
    }

    /* Retrieve all provides and run them through provides function */
    while (provides) {
        struct rpmtd_s tddep;
        struct rpmtd_s tdver;
        struct rpmtd_s tdsense;

        const char *depname;
        const char *depversion;
        uint32_t depsense;

        if (!headerGet(h, RPMTAG_PROVIDES, &tddep, HEADERGET_MINMEM))
            break;

        if (!headerGet(h, RPMTAG_PROVIDEVERSION, &tdver, HEADERGET_MINMEM)){
            rpmtdFreeData(&tddep);
            break;
        }

        if (!headerGet(h, RPMTAG_PROVIDEFLAGS, &tdsense, HEADERGET_MINMEM)){
            rpmtdFreeData(&tddep);
            rpmtdFreeData(&tdver);
            break;
        }

        /* iterator */
        while ((depname = rpmtdNextString(&tddep))) {
            depversion = rpmtdNextString(&tdver);
            depsense = *(rpmtdNextUint32(&tdsense));
            packageflags |= provides(depname, depversion, depsense, userptr);
        }

        rpmtdFreeData(&tddep);
        rpmtdFreeData(&tdver);
        rpmtdFreeData(&tdsense);

        if (packageflags == 0) {
            return EXIT_BADDEPS;
        }
        break;
    }

    ok(source, &h, packageflags);

    headerFree(h);
    return RPM_OK;
}

/*
 * explode source RPM into the current directory
 * use filters to skip files we do not need
 */
int explodeDDRPM(const char *source,
                  filterfunc filter,
                  int packageflags,
                  void* userptr)
{
    char buffer[BUFFERSIZE+1]; /* make space for trailing \0 */
    FD_t fdi;
    Header h;
    char * rpmio_flags = NULL;
    rpmRC rc;
    FD_t gzdi;
    const char *compr;
    struct archive *cpio;
    struct archive_entry *cpio_entry;
    struct cpio_mydata cpio_mydata;

    rc = readRPM(source, &fdi, &h);

    if (rc != RPM_OK) {
        Fclose(fdi);
        return rc;
    }

    /* Retrieve type of payload compression. */
    compr = headerGetString(h, RPMTAG_PAYLOADCOMPRESSOR);
    if (compr && strcmp(compr, "gzip")) {
        checked_asprintf(&rpmio_flags, "r.%sdio", compr);
    }
    else {
        checked_asprintf(&rpmio_flags, "r.gzdio");
    }

    /* Open uncompressed cpio stream */
    gzdi = Fdopen(fdi, rpmio_flags);
    free(rpmio_flags);

    if (gzdi == NULL) {
        //logMessage(ERROR, "cannot re-open payload: %s", Fstrerror(gzdi));
        headerFree(h);
        return EXIT_FAILURE;
    }

    /* initialize cpio decompressor */
    cpio = archive_read_new();
    if (cpio==NULL) {
        Fclose(gzdi);
        headerFree(h);
        return -1;
    }

    cpio_mydata.gzdi = gzdi;
    cpio_mydata.buffer = buffer;
    archive_read_support_filter_all(cpio);
    archive_read_support_format_all(cpio);
    rc = archive_read_open(cpio, &cpio_mydata, NULL, rpm_myread, rpm_myclose);

    /* check the status of archive_open */
    if (rc != ARCHIVE_OK){
        Fclose(gzdi);
        headerFree(h);
        return -1;
    }

    /* read all files in cpio archive */
    while ((rc = archive_read_next_header(cpio, &cpio_entry)) == ARCHIVE_OK) {
        const struct stat *fstat;
        int64_t fsize;
        const char* filename;
        int needskip = 1; /* do we need to read the data to get to the next header? */
        int offset = 0;
        int towrite = 0;

        filename = archive_entry_pathname(cpio_entry);
        fstat = archive_entry_stat(cpio_entry);
        fsize = archive_entry_size(cpio_entry);

        /* Strip leading slashes */
        while (filename[offset] == '/')
            offset+=1;

        /* Strip leading ./ */
        while (filename[offset] == '.' && filename[offset+1] == '/')
            offset+=2;

        /* Other file type - we do not care except special cases */
        if (!S_ISREG(fstat->st_mode))
            towrite = 1;
        else
            towrite = 2;

        if (filter && (!filter(filename+offset, fstat, packageflags, userptr))) {
            /* filter this file */
            towrite = 0;
        }

        /* Create directories */
        char* dirname = strdup(filename+offset);

        /* If the dup fails, let's hope the dirs already exist */
        if (dirname){
            char* dirptr = dirname;
            while (dirptr && *dirptr) {
                dirptr = strchr(dirptr, '/');
                if (dirptr) {
                    *dirptr = 0;
                    mkdir(dirname, 0700);
                    *dirptr = '/';
                    dirptr++;
                }
            }
            free(dirname);
        }

        /* Regular file */
        if (towrite>=2) {
            FILE *fdout = fopen(filename+offset, "w");

            if (fdout==NULL){
                rc = 33;
                break;
            }

            rc = archive_read_data_into_fd(cpio, fileno(fdout));
            if (rc!=ARCHIVE_OK) {
                /* XXX We didn't get the file.. well.. */
                needskip = 0;
            } else {
                needskip = 0;
            }

            fclose(fdout);
        }

        /* symlink, we assume that the path contained in symlink
         * is shorter than BUFFERSIZE */
        while (towrite && S_ISLNK(fstat->st_mode)) {
            char symlinkbuffer[BUFFERSIZE-1];

            needskip = 0;
            if ((rc = archive_read_data(cpio, symlinkbuffer, fsize))!=ARCHIVE_OK) {
                /* XXX We didn't get the file.. well.. */
                break;
            }

            if (symlink(buffer, filename+offset)) {
                //logMessage(ERROR, "Failed to create symlink %s -> %s", filename+offset, buffer);
            }

            break;
        }

        if(needskip)
            archive_read_data_skip(cpio);
    }

    rc = archive_read_free(cpio); /* Also closes the RPM stream using callback */

    headerFree(h);
    return rc != ARCHIVE_OK;
}
