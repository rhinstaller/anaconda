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

static FILE * main_log_tty = NULL;
static FILE * main_log_file = NULL;
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
    if (main_log_tty && level >= minLevel) {
        printLogHeader(level, main_log_tty);
        va_copy(apc, ap);
        vfprintf(main_log_tty, s, apc);
        va_end(apc);
        fprintf(main_log_tty, "\n");
        fflush(main_log_tty);
    }

    /* But log everything to the file. */
    if (main_log_file) {
        printLogHeader(level, main_log_file);
        va_copy(apc, ap);
        vfprintf(main_log_file, s, apc);
        va_end(apc);
        fprintf(main_log_file, "\n");
        fflush(main_log_file);
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
    main_log_tty = fopen("/dev/tty3", "w");
    main_log_file = fopen("/tmp/anaconda.log", "w");

    if (main_log_tty) {
        tty_logfd = fileno(main_log_tty);
        flags = fcntl(tty_logfd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(tty_logfd, F_SETFD, flags);
    }

    if (main_log_file) {
        file_logfd = fileno(main_log_file);
        flags = fcntl(file_logfd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(file_logfd, F_SETFD, flags);
    }
}

void closeLog(void) {
    if (main_log_tty)
        fclose(main_log_tty);

    if (main_log_file)
        fclose(main_log_file);
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
