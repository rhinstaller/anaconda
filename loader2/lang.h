#ifndef _LANG_H_
#define _LANG_H_

#include "loader.h"
#include "../isys/probe.h"

#define _(x) translateString (x)
#define N_(foo) (foo)

struct langInfo {
    char * lang, * key, * font, * lc_all, * keyboard, * instlang;
} ;


int chooseLanguage(char ** lang, int flags);
char * translateString(char * str);
int setLanguage (char * key, int flags);
int getLangInfo(struct langInfo **langs, int flags);

void setKickstartLanguage(struct knownDevices * kd, 
                          struct loaderData_s * loaderData, int argc, 
                          char ** argv, int * flagsPtr);

#endif /* _LANG_H_ */
