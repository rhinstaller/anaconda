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
static FILE * program_log_file = NULL;
static loglevel_t minLevel = INFO;
static const char * main_tag = "anaconda";
static const char * program_tag = "program";
static const int syslog_facility = LOG_LOCAL1;

/* maps our loglevel to syslog loglevel */
static int mapLogLevel(loglevel_t level)
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

const char *log_level_to_str[] = {
    [DEBUGLVL] = "DEBUG",
    [INFO] = "INFO",
    [WARNING] = "WARN",
    [ERROR] = "ERR",
    [CRITICAL] = "CRIT"
};

static void printLogHeader(loglevel_t level, const char *tag, FILE *outfile) {
    struct timeval current_time;
    struct tm *t;
    int msecs;
    const char *level_name;

    gettimeofday(&current_time, NULL);
    t = gmtime(&current_time.tv_sec);
    msecs = current_time.tv_usec / 1000;
    level_name = log_level_to_str[level];
    fprintf(outfile, "%02d:%02d:%02d,%03d %s %s: ", t->tm_hour,
            t->tm_min, t->tm_sec, msecs, level_name, tag);
}

static void printLogMessage(loglevel_t level, const char *tag, FILE *outfile, const char *s, va_list ap)
{
    printLogHeader(level, tag, outfile);

    va_list apc;
    va_copy(apc, ap);
    vfprintf(outfile, s, apc);
    va_end(apc);

    fprintf(outfile, "\n");
    fflush(outfile);
}

static void retagSyslog(const char* new_tag)
{
    closelog();
    openlog(new_tag, 0, syslog_facility);
}

void logMessageV(enum logger_t logger, loglevel_t level, const char * s, va_list ap) {
    FILE *log_tty = main_log_tty;
    FILE *log_file = main_log_file;
    const char *tag = main_tag;
    if (logger == PROGRAM_LOG) {
        /* tty output is done directly for programs */
        log_tty = NULL;
        log_file = program_log_file;
        tag = program_tag;
        /* close and reopen syslog so we get the tagging right */
        retagSyslog(tag);
    }

    va_list apc;
    /* Log everything into syslog */
    va_copy(apc, ap);
    vsyslog(mapLogLevel(level), s, apc);
    va_end(apc);

    /* Only log to the screen things that are above the minimum level. */
    if (main_log_tty && level >= minLevel && log_tty) {
        printLogMessage(level, tag, log_tty, s, ap);
    }

    /* But log everything to the file. */
    if (main_log_file) {
        printLogMessage(level, tag, log_file, s, ap);
    }

    /* change the syslog tag back to the default again */
    if (logger == PROGRAM_LOG)
        retagSyslog(main_tag);
}

void logMessage(loglevel_t level, const char * s, ...) {
    va_list args;

    va_start(args, s);
    logMessageV(MAIN_LOG, level, s, args);
    va_end(args);
}

void logProgramMessage(loglevel_t level, const char * s, ...) {
    va_list args;

    va_start(args, s);
    logMessageV(PROGRAM_LOG, level, s, args);
    va_end(args);
}

int tty_logfd = -1;
int file_logfd = -1;

void openLog() {
    /* init syslog logging (so log messages can also be forwarded to a remote
       syslog daemon */
    openlog(main_tag, 0, syslog_facility);

    int flags;
    main_log_tty = fopen("/dev/tty3", "a");
    main_log_file = fopen("/tmp/anaconda.log", "a");
    program_log_file = fopen("/tmp/program.log", "a");

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
    
    if (program_log_file) {
        int fd;
        fd = fileno(program_log_file);
        flags = fcntl(fd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(file_logfd, F_SETFD, flags);
    }
}

void closeLog(void) {
    if (main_log_tty)
        fclose(main_log_tty);
    if (main_log_file)
        fclose(main_log_file);
    if (program_log_file)
        fclose(program_log_file);
    main_log_tty = main_log_file = program_log_file = NULL;
    
    /* close syslog logger */
    closelog();
}

/* set the level.  higher means you see more verbosity */
void setLogLevel(loglevel_t level) {
    minLevel = level;
}

loglevel_t getLogLevel(void) {
    return minLevel;
}

/* returns non-null if logging has been initialized */
int loggingReady(void)
{
    return main_log_tty != NULL;
}

/* vim:set shiftwidth=4 softtabstop=4: */
