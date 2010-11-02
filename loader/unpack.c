/*
 * unpack.c - libarchive helper functions
 *
 * Copyright (C) 2010  Red Hat, Inc.
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
 * Author(s): David Cantrell <dcantrell@redhat.com>
 */

#include <limits.h>
#include <unistd.h>

#include <archive.h>
#include <archive_entry.h>
#include <glib.h>

#include "../pyanaconda/isys/log.h"

/*
 * Initialize libarchive object for unpacking an archive file.
 * Args:
 *     struct archive **a      The archive object to use.
 * Returns: ARCHIVE_OK on success, ARCHIVE_* on failure
 */
int unpack_init(struct archive **a) {
    int r = ARCHIVE_OK;

    if ((*a = archive_read_new()) == NULL)
        return ARCHIVE_FATAL;

    if ((r = archive_read_support_compression_all(*a)) != ARCHIVE_OK)
        return r;

    if ((r = archive_read_support_format_all(*a)) != ARCHIVE_OK)
        return r;

    return r;
}

/*
 * Extract all of the archive members of the specified archive
 * object.  If dest is not NULL, extract archive members to that
 * directory.  If dest is not NULL and does not exist as a directory,
 * create it first.  Return ARCHIVE_OK on success, ARCHIVE_* otherwise.
 */
int unpack_members_and_finish(struct archive *a, char *dest) {
    int restore = 0;
    char prevcwd[PATH_MAX];
    struct archive_entry *e = NULL;

    if (getcwd(prevcwd, PATH_MAX) == NULL) {
        logMessage(ERROR, "unable to getcwd() (%s:%d): %m", __func__,
                                                            __LINE__);
        return ARCHIVE_FATAL;
    } else {
        restore = 1;
    }

    if (dest != NULL) {
        if (access(dest, R_OK|W_OK|X_OK)) {
            if (g_mkdir_with_parents(dest, 0755) == -1) {
                logMessage(ERROR, "unable to mkdir %s (%s:%d): %m",
                           dest, __func__, __LINE__);
                return ARCHIVE_FATAL;
            }
        } else if (chdir(dest) == -1) {
            logMessage(ERROR, "unable to chdir %s (%s:%d): %m",
                       dest, __func__, __LINE__);
            return ARCHIVE_FATAL;
        }
    }

    while (archive_read_next_header(a, &e) == ARCHIVE_OK) {
        if (archive_read_extract(a, e, 0) != ARCHIVE_OK) {
            logMessage(ERROR, "error unpacking %s (%s:%d): %s",
                       archive_entry_pathname(e), __func__, __LINE__,
                       archive_error_string(a));
            return ARCHIVE_FATAL;
        }
    }

    if (restore && chdir(prevcwd) == -1) {
        logMessage(ERROR, "unable to chdir %s (%s:%d): %m",
                   dest, __func__, __LINE__);
        return ARCHIVE_FATAL;
    }

    if (archive_read_finish(a) != ARCHIVE_OK) {
        logMessage(ERROR, "error closing archive (%s:%d): %s",
                   __func__, __LINE__, archive_error_string(a));
        return ARCHIVE_FATAL;
    }

    return ARCHIVE_OK;
}

/*
 * Extract an archive (optionally compressed).
 * Args:
 *     filename      Full path to archive to unpack.
 *     dest          Directory to unpack in, or NULL for current dir.
 * Returns ARCHIVE_OK on success, or appropriate ARCHIVE_* value
 * on failure (see /usr/include/archive.h).
 */
int unpack_archive_file(char *filename, char *dest) {
    int rc = 0;
    struct archive *a = NULL;

    if (filename == NULL || access(filename, R_OK) == -1) {
        logMessage(ERROR, "unable to read %s (%s:%d): %m",
                   filename, __func__, __LINE__);
        return ARCHIVE_FATAL;
    }

    if ((rc = unpack_init(&a)) != ARCHIVE_OK) {
        logMessage(ERROR, "unable to initialize libarchive");
        return rc;
    }

    rc = archive_read_open_filename(a, filename,
                                    ARCHIVE_DEFAULT_BYTES_PER_BLOCK);
    if (rc != ARCHIVE_OK) {
        logMessage(ERROR, "error opening %s (%s:%d): %s",
                   filename, __func__, __LINE__,
                   archive_error_string(a));
        return rc;
    }

    return unpack_members_and_finish(a, dest);
}
