#include <wchar.h>
#include <stdio.h>

int main () {
    printf("%zu\n", sizeof(mbstate_t));
    return 0;
}
