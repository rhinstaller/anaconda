#ifndef _LANG_H_
#define _LANG_H_

#define _(x) translateString (x)
#define N_(foo) (foo)

struct langInfo {
    char * lang, * key, * font, * map, * lc_all, * keyboard;
} ;


int chooseLanguage(char ** lang, int flags);
char * translateString(char * str);
void setLanguage (char * key, int flags);
int getLangInfo(struct langInfo **langs, int flags);


#endif /* _LANG_H_ */
