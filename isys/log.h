/*
 * log.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#ifndef _LOG_H_
#define _LOG_H_

#include <stdio.h>
#include <stdarg.h>

#define DEBUGLVL 10
#define INFO     20
#define WARNING  30
#define ERROR    40
#define CRITICAL 50

enum logger_t {
    MAIN_LOG = 1,
    PROGRAM_LOG = 2
};

void logMessageV(enum logger_t logger, int level, const char * s, va_list ap)
    __attribute__ ((format (printf, 3, 0)));
void logMessage(int level, const char * s, ...)
    __attribute__ ((format (printf, 2, 3)));
void logProgramMessage(int level, const char * s, ...)
    __attribute__ ((format (printf, 2, 3)));
void openLog();
void closeLog(void);
void setLogLevel(int minLevel);
int getLogLevel(void);

extern int tty_logfd;
extern int file_logfd;

#endif /* _LOG_H_ */
