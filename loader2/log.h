#ifndef _LOG_H_
#define _LOG_H_

#include <stdio.h>

void logMessage(const char * s, ...) __attribute__ ((format (printf, 1, 2)));;
void openLog(int useLocal);
void closeLog(void);
void setLogLevel(int level);

#endif /* _LOG_H_ */
