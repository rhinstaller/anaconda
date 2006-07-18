#ifndef _LOG_H_
#define _LOG_H_

#include <stdio.h>
#include <stdarg.h>

#define DEBUGLVL 10
#define INFO     20
#define WARNING  30
#define ERROR    40
#define CRITICAL 50

void logMessageV(int level, const char * s, va_list ap)
	__attribute__ ((format (printf, 2, 0)));
void logMessage(int level, const char * s, ...)
	__attribute__ ((format (printf, 2, 3)));
void openLog(int useLocal);
void closeLog(void);
void setLogLevel(int minLevel);
int getLogLevel(void);

#endif /* _LOG_H_ */
