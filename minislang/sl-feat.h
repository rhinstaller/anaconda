/* Set this to 1 to enable Kanji support */
#define SLANG_HAS_KANJI_SUPPORT 0

#define SLANG_HAS_COMPLEX	1
#define SLANG_HAS_FLOAT		1

#define _SLANG_OPTIMIZE_FOR_SPEED	1

/* This is experimental.  It adds extra information for tracking down
 * errors.
 */
#define _SLANG_HAS_DEBUG_CODE	1

/* Setting this to one will map 8 bit vtxxx terminals to 7 bit.
 * This affects just input characters in the range 128-160 on non PC
 * systems.
 */
#define _SLANG_MAP_VTXXX_8BIT	1
