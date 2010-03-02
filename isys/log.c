/*
 * log.c - logging functionality
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002  Red Hat, Inc.
 * All rights reserved.
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
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <sys/time.h>
#include <syslog.h>

#include "log.h"

static FILE * tty_logfile = NULL;
static FILE * file_logfile = NULL;
static int minLevel = INFO;
static const char * syslog_facility = "loader";

/* maps our loglevel to syslog loglevel */
static int mapLogLevel(int level)
{
    switch (level) {
    case DEBUGLVL:
        return LOG_DEBUG;
    case INFO:
        return LOG_INFO;
    case WARNING:
        return LOG_WARNING;
    case CRITICAL:
        return LOG_CRIT;
    case ERROR:
    default:
        /* if someone called us with an invalid level value, log it as an error
           too. */
        return LOG_ERR;
    }
}

static void printLogHeader(int level, FILE *outfile) {
    struct timeval current_time;
    struct tm *t;
    int msecs;

    gettimeofday(&current_time, NULL);
    t = gmtime(&current_time.tv_sec);
    msecs = current_time.tv_usec / 1000;
    switch (level) {
        case DEBUGLVL:
            fprintf (outfile, "%02d:%02d:%02d,%03d DEBUG %s: ", t->tm_hour,
                     t->tm_min, t->tm_sec, msecs, syslog_facility);
            break;

        case INFO:
            fprintf (outfile, "%02d:%02d:%02d,%03d INFO %s: ", t->tm_hour,
                     t->tm_min, t->tm_sec, msecs, syslog_facility);
            break;

        case WARNING:
            fprintf (outfile, "%02d:%02d:%02d,%03d WARNING %s: ", t->tm_hour,
                     t->tm_min, t->tm_sec, msecs, syslog_facility);
            break;

        case ERROR:
            fprintf (outfile, "%02d:%02d:%02d,%03d ERROR %s: ", t->tm_hour,
                     t->tm_min, t->tm_sec, msecs, syslog_facility);
            break;

        case CRITICAL:
            fprintf (outfile, "%02d:%02d:%02d,%03d CRITICAL %s: ", t->tm_hour,
                     t->tm_min, t->tm_sec, msecs, syslog_facility);
            break;
    }
}

void logMessageV(int level, const char * s, va_list ap) {
    va_list apc;
    /* Log everything into syslog */
    va_copy(apc, ap);
    vsyslog(mapLogLevel(level), s, apc);
    va_end(apc);

    /* Only log to the screen things that are above the minimum level. */
    if (tty_logfile && level >= minLevel) {
        printLogHeader(level, tty_logfile);
        va_copy(apc, ap);
        vfprintf(tty_logfile, s, apc);
        va_end(apc);
        fprintf(tty_logfile, "\n");
        fflush(tty_logfile);
    }

    /* But log everything to the file. */
    if (file_logfile) {
        printLogHeader(level, file_logfile);
        va_copy(apc, ap);
        vfprintf(file_logfile, s, apc);
        va_end(apc);
        fprintf(file_logfile, "\n");
        fflush(file_logfile);
    }
}

void logMessage(int level, const char * s, ...) {
    va_list args;

    va_start(args, s);
    logMessageV(level, s, args);
    va_end(args);
}

int tty_logfd = -1;
int file_logfd = -1;

void openLog() {
    /* init syslog logging (so loader messages can also be forwarded to a remote
       syslog daemon */
    openlog(syslog_facility, 0, LOG_LOCAL1);

    int flags;
    tty_logfile = fopen("/dev/tty3", "w");
    file_logfile = fopen("/tmp/anaconda.log", "w");

    if (tty_logfile) {
        tty_logfd = fileno(tty_logfile);
        flags = fcntl(tty_logfd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(tty_logfd, F_SETFD, flags);
    }

    if (file_logfile) {
        file_logfd = fileno(file_logfile);
        flags = fcntl(file_logfd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(file_logfd, F_SETFD, flags);
    }
}

void closeLog(void) {
    if (tty_logfile)
        fclose(tty_logfile);

    if (file_logfile)
        fclose(file_logfile);
    /* close syslog logger */
    closelog();
}

/* set the level.  higher means you see more verbosity */
void setLogLevel(int level) {
    minLevel = level;
}

int getLogLevel(void) {
    return minLevel;
}

/* vim:set shiftwidth=4 softtabstop=4: */
