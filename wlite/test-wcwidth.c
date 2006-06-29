#include <errno.h>
#include <stdio.h>
#include <locale.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "wlite_wchar.h"

int main(int argc, char **argv) {
    int c;
    wchar_t u = L'\0';
    unsigned char s[7] = { 0 }; /* max utf-8 segment + nul char */
    size_t length = 0;
    ssize_t n = 0;
    mbstate_t ps = { 0 };
    const char *ctype;

    ctype = setlocale(LC_CTYPE, "");
    if (ctype == NULL) {
        fputs("unsupported LC_CTYPE locale\n", stderr);
    }
    errno = 0;        /* XXX: why does errno get set to 2 by 7.3's glibc here? */
    for (;;) {
            c = fgetc(stdin);
            if (c == EOF) {
                if (ferror(stdin)) perror(NULL);
                break;
            }
            if (length >= sizeof(s)) abort();
            s[length++] = c;
            n = (ssize_t) mbrtowc(&u, s, length, &ps);
            if (n == -1 || errno != 0) {
                char msg[80];

                /* skip over the bad byte */
                if (sprintf(msg, "*** bad mbc skipped: \\x%02X\n",
                    (unsigned) (*s & 0xFF)) >= sizeof(msg)) abort();
                perror(msg);
                errno = 0;
                length -= 1;
                memmove(s, s + 1, sizeof(s) - n);
                memset(s + length, 0, sizeof(s) - length); // debugger friendly
            }
            else if (n > 0) {
                const char *fmt = NULL;
                int uwidth = wcwidth(u);

                length -= n;
                memmove(s, s + n, sizeof(s) - n);
                memset(s + length, 0, sizeof(s) - length); // debugger friendly
                if (u < 0x20) 
                    switch (u) {
                    case L'\a': fmt = "(U+%04lX)\t%d\t\\a\n"; break;
                    case L'\e': fmt = "(U+%04lX)\t%d\t\\e\n"; break;
                    case L'\f': fmt = "(U+%04lX)\t%d\t\\f\n"; break;
                    case L'\n': fmt = "(U+%04lX)\t%d\t\\n\n"; break;
                    case L'\t': fmt = "(U+%04lX)\t%d\t\\t\n"; break;
                    case L'\r': fmt = "(U+%04lX)\t%d\t\\r\n"; break;
                    case L'\v': fmt = "(U+%04lX)\t%d\t\\v\n"; break;
                    default: fmt = "(U+%04lX)\t%d\t\n"; break;
                    }
                else if (u <= 0xFFFF) fmt = "(U+%04lX)\t%d\t%lc\n";
                else fmt = "(U-%06lX)\t%d\t%lc\n";
                if (printf(fmt, (unsigned long) u, uwidth, (wint_t) u) < 0) {
                    if (errno == EILSEQ) {
                        /* it's ok if we couldn't print a character within
                         * the current locale.
                         */ 
                        printf("(unprintable with LC_CTYPE \"%s\")\n", ctype);
                        errno = 0;
                    }
                    else {
                        perror(NULL);
                        abort();
                    }
                }
            }
    }
    return 0;
}
