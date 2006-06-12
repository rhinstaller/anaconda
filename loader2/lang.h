#ifndef _LANG_H_
#define _LANG_H_

#include "loader.h"

#define _(x) translateString (x)
#define N_(foo) (foo)

struct langInfo {
    char * lang, * key, * font, * lc_all, * keyboard;
} ;


int chooseLanguage(char ** lang);
char * translateString(char * str);
int setLanguage (char * key);
int getLangInfo(struct langInfo **langs);

void setKickstartLanguage(struct loaderData_s * loaderData, int argc, 
                          char ** argv);

#endif /* _LANG_H_ */
