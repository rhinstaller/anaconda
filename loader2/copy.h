#ifndef H_COPY
#define H_COPY

int copyDirectory (char *from, char *to, void (*warnFn)(char *),
                   void (*errorFn)(char *));

#endif
