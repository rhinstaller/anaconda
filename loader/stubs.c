#include <gconv.h>

/* hj's gconv stubs, a little modified */

/* Define ALIASNAME as a strong alias for NAME.  */
# define strong_alias(name, aliasname) _strong_alias(name, aliasname)
# define _strong_alias(name, aliasname) \
  extern __typeof (name) aliasname __attribute__ ((alias (#name)));

/* Don't drag in the dynamic linker. */
void *__libc_stack_end;

int
__gconv_OK () {
#if __GLIBC__ > 2 || __GLIBC_MINOR__ > 1
    return __GCONV_OK;
#else
    return GCONV_OK;
#endif
}

int
__gconv_NOCONV () {
#if __GLIBC__ > 2 || __GLIBC_MINOR__ > 1
    return __GCONV_NOCONV;
#else
    return GCONV_NOCONV;
#endif
}

strong_alias (__gconv_OK,
	      __gconv_close_transform);
strong_alias (__gconv_OK,
	      __gconv_close);

strong_alias (__gconv_NOCONV,
	      __gconv);
strong_alias (__gconv_NOCONV,
	      __gconv_find_transform);
strong_alias (__gconv_NOCONV,
	      __gconv_open);

/* These transformations should not fail in normal conditions */
strong_alias (__gconv_OK,
	      __gconv_transform_ascii_internal);
strong_alias (__gconv_OK,
	      __gconv_transform_ucs2little_internal);
strong_alias (__gconv_OK,
	      __gconv_transform_utf16_internal);
strong_alias (__gconv_OK,
	      __gconv_transform_utf8_internal);
strong_alias (__gconv_OK,
	      __gconv_transform_ucs2_internal);

/* We can assume no conversion for these ones */
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_ascii);
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_ucs2);
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_ucs2little);
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_ucs4);
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_utf16);
strong_alias (__gconv_NOCONV,
	      __gconv_transform_internal_utf8);

strong_alias (__gconv_OK,
	      __gconv_transliterate);
