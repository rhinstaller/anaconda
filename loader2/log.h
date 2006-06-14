#ifndef _LOG_H_
#define _LOG_H_

#include <stdio.h>

#define DEBUGLVL 10
#define INFO     20
#define WARNING  30
#define ERROR    40
#define CRITICAL 50

void logMessage(int level, const char * s, ...)
	__attribute__ ((format (printf, 2, 3)));
void openLog(int useLocal);
void closeLog(void);
void setLogLevel(int minLevel);

#endif /* _LOG_H_ */
