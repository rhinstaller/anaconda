#include <gconv.h>
 
#if !defined(UNKNOWN_10646_CHAR) && defined(__UNKNOWN_10646_CHAR)
/* Newer glibcs use underscores in gconv.h */
#define GCONV_OK       __GCONV_OK
#define GCONV_NOCONV   __GCONV_NOCONV
#endif

#define ASM_GLOBAL_DIRECTIVE .globl
#define __SYMBOL_PREFIX

/* Define ALIAS as a strong alias for ORIGINAL.  */
#define strong_alias(original, alias) \
  asm (__string_1 (ASM_GLOBAL_DIRECTIVE) " " __SYMBOL_PREFIX #alias "\n" \
       ".set " __SYMBOL_PREFIX #alias "," __SYMBOL_PREFIX #original);

/* Helper macros used above.  */
#define __string_1(x) __string_0(x)
#define __string_0(x) #x

/* Don't drag in the dynamic linker. */
void *__libc_stack_end;

int
__gconv_OK () {return GCONV_OK;}

/*
int
__gconv_NOCONV () {return GCONV_NOCONV;}
*/

strong_alias (__gconv_OK, __gconv_close_transform); 
strong_alias (__gconv_OK, __gconv);
strong_alias (__gconv_OK, __gconv_find_transform);
strong_alias (__gconv_OK, __gconv_open);
strong_alias (__gconv_OK, __gconv_transform_ascii_internal);
strong_alias (__gconv_OK, __gconv_transform_internal_ascii);
strong_alias (__gconv_OK, __gconv_transform_internal_ucs2);
strong_alias (__gconv_OK, __gconv_transform_internal_ucs2little);
strong_alias (__gconv_OK, __gconv_transform_internal_ucs4);
strong_alias (__gconv_OK, __gconv_transform_internal_utf16);
strong_alias (__gconv_OK, __gconv_transform_internal_utf8);
strong_alias (__gconv_OK, __gconv_transform_ucs2_internal);
strong_alias (__gconv_OK, __gconv_transform_ucs2little_internal);
strong_alias (__gconv_OK, __gconv_transform_utf16_internal);
strong_alias (__gconv_OK, __gconv_transform_utf8_internal);

