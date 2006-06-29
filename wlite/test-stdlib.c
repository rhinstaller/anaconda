#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "wlite_wchar.h"
#include "wlite_stdlib.h"

#define test(expr) check((expr),__FILE__,__LINE__,#expr)

void check(int expr, const char *file, unsigned line, const char *s) {
    const char *ok = "PASS (%s:%u) ** %d == %s\n";
    const char *ng = "FAIL (%s:%u) ** %d == %s\n";

    if (fprintf(stderr, (expr ? ok : ng), file, line, expr, s) < 0) abort();
    if (!expr) exit(EXIT_FAILURE);
}

int main(int argc, char **argv) {
    wchar_t *s, wcs[10];
    char mbs[10];

    test(1 <= MB_CUR_MAX && MB_CUR_MAX <= MB_LEN_MAX);

    // test(wcstod(L"28G", &s) == 28.0 && s != NULL && *s == L'G');

    test(wcstol(L"-a0", &s, 11) == -110 && s != NULL && *s == L'\0');
    test(wcstoul(L"54", &s, 4) == 0 && s != NULL && *s == L'5');
    test(wcstoul(L"0xFfg", &s, 16) == 255 && s != NULL && *s == L'g');

    test(mbstowcs(wcs, "abc", 4) == 3 && wcs[1] == L'b');
    test(wcstombs(mbs, wcs, 10) == 3 && strcmp(mbs, "abc") == 0);

    mblen(NULL, 0);
    wctomb(NULL, 0);

    test(mblen("abc", 4) == 1);
    test(mbtowc(&wcs[0], "abc", 4) == 1 && wcs[0] == L'a');
    test(wctomb(mbs, wcs[0]) == 1 && mbs[0] == L'a');
    test(mblen("", 1) == 0);
    test(mbtowc(&wcs[0], "", 1) == 0 && wcs[0] == 0);
    test(wctomb(mbs, wcs[0]) == 1 && mbs[0] == '\0');

    printf("MB_CUR_MAX = %u\n", MB_CUR_MAX);
    puts(mbtowc(NULL, NULL, 0) ? "mbs shift states" : "mbs stateless");

    return 0;
}
