#ifndef _LANG_H_
#define _LANG_H_

#define _(x) translateString (x)
#define N_(foo) (foo)

int chooseLanguage(int flags);
char * translateString(char * str);

#endif /* _LANG_H_ */
