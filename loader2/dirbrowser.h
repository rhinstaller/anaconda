#ifndef DIRBROWSER_H
#define DIRBROWSER_H

#include <dirent.h>

char * newt_select_file(char * title, char * text, char * dirname,
                        int (*filterfunc)(char *, struct dirent *));

#endif
