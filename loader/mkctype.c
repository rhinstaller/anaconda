#include <ctype.h>
#include <stdio.h>

int main(int argc, char ** argv) {
    int i;

    printf("#include <sys/types.h>\n\n");

    printf("static const unsigned short int __ctype_b_internal[] = {");

    for (i = -128; i < 256; i++) {
	if (!(i % 8)) {
	    printf("\n");
	}

	printf("\t0x%x,", __ctype_b[i]);
    }

    printf("\n};\n\n");
    printf("const unsigned short int * __ctype_b = __ctype_b_internal + 128;\n\n");

    printf("const int __ctype_toupper_internal[] = {");
    for (i = -128; i < 256; i++) {
	if (!(i % 8)) {
	    printf("\n");
	}

	printf("\t0x%x,", __ctype_toupper[i]);
    }

    printf("\n};\n\n");
    printf("const int * __ctype_toupper = __ctype_toupper_internal + 128;\n\n");

    printf("const int __ctype_tolower_internal[] = {");
    for (i = -128; i < 256; i++) {
	if (!(i % 8)) {
	    printf("\n");
	}

	printf("\t0x%x,", __ctype_tolower[i]);
    }

    printf("\n};\n\n");
    printf("const int * __ctype_tolower = __ctype_tolower_internal + 128;\n\n");

    return 0;
};
