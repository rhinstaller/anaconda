#ifndef _LOG_H_
#define _LOG_H_

#include <stdio.h>

extern FILE * log;
extern int logfd;

void logMessage(const char * s, ...);
void openLog(int useLocal);
void closeLog(void);

#endif /* _LOG_H_ */
