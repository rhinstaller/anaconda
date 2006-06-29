#include <stdio.h>
#include <stdlib.h>

#include "wlite_wchar.h"

#define test(expr) check((expr),__FILE__,__LINE__,#expr)

void check(int expr, const char *file, unsigned line, const char *s) {
    const char *ok = "PASS (%s:%u) ** %d == %s\n";
    const char *ng = "FAIL (%s:%u) ** %d == %s\n";

    if (fprintf(stderr, (expr ? ok : ng), file, line, expr, s) < 0) abort();
    if (!expr) exit(EXIT_FAILURE);
}

int main(int argc, char **argv) {
    wchar_t s[20], *ptr;
    size_t n;
    static const wchar_t abcde[] = L"abcde";
    static const wchar_t abcdx[] = L"abcdx";

    test(wmemchr(abcde, L'c', 5) == &abcde[2]);
    test(wmemchr(abcde, L'e', 4) == NULL);
    test(wmemcmp(abcde, abcdx, 5) != 0);
    test(wmemcmp(abcde, abcdx, 4) == 0);
    test(wcsncpy(s, abcde, 6) == s && s[2] == L'c');
    test(wmemmove(s, s + 1, 3) == s);
    test(wmemcmp(wmemmove(s, s + 1, 3), L"aabce", 6));
    test(wmemcmp(wmemmove(s + 2, s, 3) - 2, L"bcece", 6));
    test(wmemset(s, L'*', 10) == s && s[9] == L'*');
    test(wmemset(s + 2, L'%', 0) == s + 2 && s[2] == L'*');
    test(wcscat(wmemcpy(s, abcde, 6), L"fg") == s);
    test(s[6] == L'g');
    test(wcschr(abcde, L'x') == NULL);
    test(wcschr(abcde, L'c') == &abcde[2]);
    test(wcschr(abcde, L'\0') == &abcde[5]);
    test(wcscmp(abcde, abcdx) != 0);
    test(wcscmp(abcde, L"abcde") == 0);
    test(wcscoll(abcde, L"abcde") == 0);
    test(wcscpy(s, abcde) == s && wcscmp(s, abcde) == 0);
    test(wcscspn(abcde, L"xdy") == 3);
    test(wcscspn(abcde, L"xzy") == 5);
    test(wcslen(abcde) == 5);
    test(wcslen(L"") == 0);
    test(wcsncat(wcscpy(s, abcde), L"fg", 1) == s && wcscmp(s, L"abcdef") == 0);
    test(wcsncmp(abcde, L"abcde", 30) == 0);
    test(wcsncmp(abcde, abcdx, 30) != 0);
    test(wcsncmp(abcde, abcdx, 4) == 0);
    test(wcsncpy(s, abcde, 7) == s && wmemcmp(s, L"abcde\0", 7) == 0);
    test(wcsncpy(s, L"xyz", 2) == s && wcscmp(s, L"xycde") == 0);
    test(wcspbrk(abcde, L"xdy") == &abcde[3]);
    test(wcspbrk(abcde, L"xyz") == NULL);
    test(wcsrchr(abcde, L'x') == NULL);
    test(wcscmp(wcsrchr(L"ababa", L'b'), L"ba") == 0);
    test(wcsspn(abcde, L"abce") == 3);
    test(wcsspn(abcde, abcde) == 5);
    test(wcsstr(abcde, L"xyz") == NULL);
    test(wcsstr(abcde, L"cd") == &abcde[2]);
    test(wcstok(wcscpy(s, abcde), L"ac", &ptr) == &s[1]);
    test(wcstok(NULL, L"ace", &ptr) == &s[3]);
    test(wcstok(NULL, L"ace", &ptr) == NULL && wmemcmp(s, L"ab\0d\0", 6) == 0);
    n = wcsxfrm(NULL, abcde, 0);
    if (n < sizeof(s) - 1)
        test(wcsxfrm(s, abcde, n + 1) == n && wcslen(s) == n);
    return 0;
}
