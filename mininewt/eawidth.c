/* #define TEST_GET_EAST_ASIA_STR_WIDTH 1 */

#include <assert.h>
#include <locale.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

#include "eawidth.h"

/*
 *  If the amount of columns the cursor advances on a TAB character depends
 *  on the current position, set this to a negative number (i.e. -8 for tab
 *  stops every eight columns. If static, set to a positive number. Zero if
 *  tabs are ignored.
 */
static const int tab_width = -8;

typedef struct {
  unsigned short start, end;
  east_asia_type type;
} eaw_db_type;

static const eaw_db_type eaw_db[] = {
  { 0x0020,0x007E,narrow },
  { 0x00A1,0x00A1,ambiguous },	/*INVERTED EXCLAMATION MARK*/
  { 0x00A2,0x00A3,narrow },
  { 0x00A4,0x00A4,ambiguous },	/*CURRENCY SIGN*/
  { 0x00A5,0x00A6,narrow },
  { 0x00A7,0x00A8,ambiguous },
  { 0x00AA,0x00AA,ambiguous },	/*FEMININE ORDINAL INDICATOR*/
  { 0x00AC,0x00AC,narrow },	/*NOT SIGN*/
  { 0x00AD,0x00AD,ambiguous },	/*SOFT HYPHEN*/
  { 0x00AF,0x00AF,narrow },	/*MACRON*/
  { 0x00B0,0x00B4,ambiguous },
  { 0x00B6,0x00BA,ambiguous },
  { 0x00BC,0x00BF,ambiguous },
  { 0x00C6,0x00C6,ambiguous },	/*LATIN CAPITAL LETTER AE*/
  { 0x00D0,0x00D0,ambiguous },	/*LATIN CAPITAL LETTER ETH*/
  { 0x00D7,0x00D8,ambiguous },
  { 0x00DE,0x00E1,ambiguous },
  { 0x00E6,0x00E6,ambiguous },	/*LATIN SMALL LETTER AE*/
  { 0x00E8,0x00EA,ambiguous },
  { 0x00EC,0x00ED,ambiguous },
  { 0x00F0,0x00F0,ambiguous },	/*LATIN SMALL LETTER ETH*/
  { 0x00F2,0x00F3,ambiguous },
  { 0x00F7,0x00FA,ambiguous },
  { 0x00FC,0x00FC,ambiguous },	/*LATIN SMALL LETTER U WITH DIAERESIS*/
  { 0x00FE,0x00FE,ambiguous },	/*LATIN SMALL LETTER THORN*/
  { 0x0101,0x0101,ambiguous },	/*LATIN SMALL LETTER A WITH MACRON*/
  { 0x0111,0x0111,ambiguous },	/*LATIN SMALL LETTER D WITH STROKE*/
  { 0x0113,0x0113,ambiguous },	/*LATIN SMALL LETTER E WITH MACRON*/
  { 0x011B,0x011B,ambiguous },	/*LATIN SMALL LETTER E WITH CARON*/
  { 0x0126,0x0127,ambiguous },
  { 0x012B,0x012B,ambiguous },	/*LATIN SMALL LETTER I WITH MACRON*/
  { 0x0131,0x0133,ambiguous },
  { 0x0138,0x0138,ambiguous },	/*LATIN SMALL LETTER KRA*/
  { 0x013F,0x0142,ambiguous },
  { 0x0144,0x0144,ambiguous },	/*LATIN SMALL LETTER N WITH ACUTE*/
  { 0x0148,0x014A,ambiguous },
  { 0x014D,0x014D,ambiguous },	/*LATIN SMALL LETTER O WITH MACRON*/
  { 0x0152,0x0153,ambiguous },
  { 0x0166,0x0167,ambiguous },
  { 0x016B,0x016B,ambiguous },	/*LATIN SMALL LETTER U WITH MACRON*/
  { 0x01CE,0x01CE,ambiguous },	/*LATIN SMALL LETTER A WITH CARON*/
  { 0x01D0,0x01D0,ambiguous },	/*LATIN SMALL LETTER I WITH CARON*/
  { 0x01D2,0x01D2,ambiguous },	/*LATIN SMALL LETTER O WITH CARON*/
  { 0x01D4,0x01D4,ambiguous },	/*LATIN SMALL LETTER U WITH CARON*/
  { 0x01D6,0x01D6,ambiguous },	/*LATIN SMALL LETTER U W/DIAERESIS+MACRON*/
  { 0x01D8,0x01D8,ambiguous },	/*LATIN SMALL LETTER U W/DIAERESIS+ACUTE*/
  { 0x01DA,0x01DA,ambiguous },	/*LATIN SMALL LETTER U W/DIAERESIS+CARON*/
  { 0x01DC,0x01DC,ambiguous },	/*LATIN SMALL LETTER U W/DIAERESIS+GRAVE*/
  { 0x0251,0x0251,ambiguous },	/*LATIN SMALL LETTER ALPHA*/
  { 0x0261,0x0261,ambiguous },	/*LATIN SMALL LETTER SCRIPT G*/
  { 0x02C7,0x02C7,ambiguous },	/*CARON*/
  { 0x02C9,0x02CB,ambiguous },
  { 0x02CD,0x02CD,ambiguous },	/*MODIFIER LETTER LOW MACRON*/
  { 0x02D0,0x02D0,ambiguous },	/*MODIFIER LETTER TRIANGULAR COLON*/
  { 0x02D8,0x02DB,ambiguous },
  { 0x02DD,0x02DD,ambiguous },	/*DOUBLE ACUTE ACCENT*/
  { 0x0300,0x0362,ambiguous },
  { 0x0391,0x03A9,ambiguous },
  { 0x03B1,0x03C1,ambiguous },
  { 0x03C3,0x03C9,ambiguous },
  { 0x0401,0x0401,ambiguous },	/*CYRILLIC CAPITAL LETTER IO*/
  { 0x0410,0x044F,ambiguous },
  { 0x0451,0x0451,ambiguous },	/*CYRILLIC SMALL LETTER IO*/
  { 0x1100,0x115F,wide },
  { 0x2010,0x2010,ambiguous },	/*HYPHEN*/
  { 0x2013,0x2016,ambiguous },
  { 0x2018,0x2019,ambiguous },
  { 0x201C,0x201D,ambiguous },
  { 0x2020,0x2021,ambiguous },
  { 0x2025,0x2027,ambiguous },
  { 0x2030,0x2030,ambiguous },	/*PER MILLE SIGN*/
  { 0x2032,0x2033,ambiguous },
  { 0x2035,0x2035,ambiguous },	/*REVERSED PRIME*/
  { 0x203B,0x203B,ambiguous },	/*REFERENCE MARK*/
  { 0x2074,0x2074,ambiguous },	/*SUPERSCRIPT FOUR*/
  { 0x207F,0x207F,ambiguous },	/*SUPERSCRIPT LATIN SMALL LETTER N*/
  { 0x2081,0x2084,ambiguous },
  { 0x20A9,0x20A9,half_width },	/*WON SIGN*/
  { 0x20AC,0x20AC,ambiguous },	/*EURO SIGN*/
  { 0x2103,0x2103,ambiguous },	/*DEGREE CELSIUS*/
  { 0x2105,0x2105,ambiguous },	/*CARE OF*/
  { 0x2109,0x2109,ambiguous },	/*DEGREE FAHRENHEIT*/
  { 0x2113,0x2113,ambiguous },	/*SCRIPT SMALL L*/
  { 0x2121,0x2122,ambiguous },
  { 0x2126,0x2126,ambiguous },	/*OHM SIGN*/
  { 0x212B,0x212B,ambiguous },	/*ANGSTROM SIGN*/
  { 0x2154,0x2155,ambiguous },
  { 0x215B,0x215B,ambiguous },	/*VULGAR FRACTION ONE EIGHTH*/
  { 0x215E,0x215E,ambiguous },	/*VULGAR FRACTION SEVEN EIGHTHS*/
  { 0x2160,0x216B,ambiguous },
  { 0x2170,0x2179,ambiguous },
  { 0x2190,0x2199,ambiguous },
  { 0x21D2,0x21D2,ambiguous },	/*RIGHTWARDS DOUBLE ARROW*/
  { 0x21D4,0x21D4,ambiguous },	/*LEFT RIGHT DOUBLE ARROW*/
  { 0x2200,0x2200,ambiguous },	/*FOR ALL*/
  { 0x2202,0x2203,ambiguous },
  { 0x2207,0x2208,ambiguous },
  { 0x220B,0x220B,ambiguous },	/*CONTAINS AS MEMBER*/
  { 0x220F,0x220F,ambiguous },	/*N-ARY PRODUCT*/
  { 0x2211,0x2211,ambiguous },	/*N-ARY SUMMATION*/
  { 0x2215,0x2215,ambiguous },	/*DIVISION SLASH*/
  { 0x221A,0x221A,ambiguous },	/*SQUARE ROOT*/
  { 0x221D,0x2220,ambiguous },
  { 0x2223,0x2223,ambiguous },	/*DIVIDES*/
  { 0x2225,0x2225,ambiguous },	/*PARALLEL TO*/
  { 0x2227,0x222C,ambiguous },
  { 0x222E,0x222E,ambiguous },	/*CONTOUR INTEGRAL*/
  { 0x2234,0x2237,ambiguous },
  { 0x223C,0x223D,ambiguous },
  { 0x2248,0x2248,ambiguous },	/*ALMOST EQUAL TO*/
  { 0x224C,0x224C,ambiguous },	/*ALL EQUAL TO*/
  { 0x2252,0x2252,ambiguous },	/*APPROXIMATELY EQUAL TO OR THE IMAGE OF*/
  { 0x2260,0x2261,ambiguous },
  { 0x2264,0x2267,ambiguous },
  { 0x226A,0x226B,ambiguous },
  { 0x226E,0x226F,ambiguous },
  { 0x2282,0x2283,ambiguous },
  { 0x2286,0x2287,ambiguous },
  { 0x2295,0x2295,ambiguous },	/*CIRCLED PLUS*/
  { 0x2299,0x2299,ambiguous },	/*CIRCLED DOT OPERATOR*/
  { 0x22A5,0x22A5,ambiguous },	/*UP TACK*/
  { 0x22BF,0x22BF,ambiguous },	/*RIGHT TRIANGLE*/
  { 0x2312,0x2312,ambiguous },	/*ARC*/
  { 0x2460,0x24BF,ambiguous },
  { 0x24D0,0x24E9,ambiguous },
  { 0x2500,0x254B,ambiguous },
  { 0x2550,0x2574,ambiguous },
  { 0x2580,0x258F,ambiguous },
  { 0x2592,0x25A1,ambiguous },
  { 0x25A3,0x25A9,ambiguous },
  { 0x25B2,0x25B3,ambiguous },
  { 0x25B6,0x25B7,ambiguous },
  { 0x25BC,0x25BD,ambiguous },
  { 0x25C0,0x25C1,ambiguous },
  { 0x25C6,0x25C8,ambiguous },
  { 0x25CB,0x25CB,ambiguous },	/*WHITE CIRCLE*/
  { 0x25CE,0x25D1,ambiguous },
  { 0x25E2,0x25E5,ambiguous },
  { 0x25EF,0x25EF,ambiguous },	/*LARGE CIRCLE*/
  { 0x2605,0x2606,ambiguous },
  { 0x2609,0x2609,ambiguous },	/*SUN*/
  { 0x260E,0x260F,ambiguous },
  { 0x261C,0x261C,ambiguous },	/*WHITE LEFT POINTING INDEX*/
  { 0x261E,0x261E,ambiguous },	/*WHITE RIGHT POINTING INDEX*/
  { 0x2640,0x2640,ambiguous },	/*FEMALE SIGN*/
  { 0x2642,0x2642,ambiguous },	/*MALE SIGN*/
  { 0x2660,0x2661,ambiguous },
  { 0x2663,0x2665,ambiguous },
  { 0x2667,0x266A,ambiguous },
  { 0x266C,0x266D,ambiguous },
  { 0x266F,0x266F,ambiguous },	/*MUSIC SHARP SIGN*/
  { 0x2E80,0x3009,wide },
  { 0x300A,0x300B,ambiguous },
  { 0x300C,0x3019,wide },
  { 0x301A,0x301B,ambiguous },
  { 0x301C,0x303E,wide },
  { 0x3041,0xD7A3,wide },
  { 0xE000,0xF8FF,ambiguous },
  { 0xF900,0xFA2D,wide },
  { 0xFE30,0xFE6B,wide },
  { 0xFF01,0xFF5E,full_width },
  { 0xFF61,0xFFDC,half_width },
  { 0xFFE0,0xFFE6,full_width },
  { 0xFFE8,0xFFEE,half_width },
};

static int
eaw_db_cmp (const void *ck, const void *ce) {
  const eaw_db_type *key = ck, *element = ce;

  assert(key != NULL);
  assert(element != NULL);
  if (key->start < element->start) return -1;
  else if (key->end > element->end) return 1;
  return 0;
}

static int
is_cjk_locale (const char *locale_name) {
  static const char c[] = "zh"; /* Chinese */
  static const char j[] = "ja"; /* Japanese */
  static const char k[] = "ko"; /* Korean */

  if (NULL == locale_name) return 0;
  if (strncmp(locale_name, c, sizeof(c)) == 0) return 1;
  if (strncmp(locale_name, j, sizeof(j)) == 0) return 1;
  if (strncmp(locale_name, k, sizeof(k)) == 0) return 1;
  return 0;
}

east_asia_type
get_east_asia_type (wchar_t unicode) {
  assert(0xFFFF != unicode && 0xFFFE != unicode);

  if (unicode > 0xFFFF) {

    /*
     *  Plane 2 is intended for CJK ideographs
     */
    if (unicode >= 0x20000 && unicode <= 0x2FFFD) return wide;
    return ambiguous;
  }
  else {
    eaw_db_type *pos, key;
    size_t n;

    n = sizeof(eaw_db) / sizeof(eaw_db_type);
    key.start = key.end = (unsigned short) unicode;
    pos = bsearch(&key, eaw_db, n, sizeof(eaw_db_type), eaw_db_cmp);
    if (NULL != pos) return pos->type;
  }
  return neutral;
}

int
east_asia_mblen (const char *locale_name, const char *s, size_t n, int x)
{
	wchar_t *wcs, *p;
	int width = 0;

	if (NULL == s) s = "";

	/*
	 *  Getting the locale name via setlocale() is expensive, so we prefer
	 *  to have it passed to us.
	 */
	if (NULL == locale_name) {
		locale_name = setlocale(LC_CTYPE, NULL);
		if (NULL == locale_name) return INT_MAX;
	}

	wcs = (wchar_t *) calloc(n, sizeof(wchar_t));
	if (NULL == wcs) return INT_MAX;

#if defined __GLIBC__ && !__GLIBC_PREREQ(2,2)
#warning wide character support is broken. Glibc 2.2 or better needed.
#endif

	if ((size_t) -1 == mbstowcs(wcs, s, n)) return INT_MAX;

	switch (get_east_asia_type(*wcs)) {
		case neutral:

			/*
			 *  Put characters that print nothing here.
			 *
			 *  XXX: Yes, I know there are a lot more than this in ISO-10646, but
			 *  this function is intended to calculate the width of strings for
			 *  fixed width terminals displaying legacy CJK character sets.
			 *  State-of-the-art Unicode handling terminals probably won't need
			 *  this function anyway.
			 */
			if (0x0000 == *wcs) break; /* NULL */
			if (0x0007 == *wcs) break; /* BELL */
			
			/*  FIXME: there will probably be ASCII chars after the escape
			 *  code, which will be counted as part of the width even though they
			 *  aren't displayed.
			 */
			if (0x001B == *wcs) break; /* ESC */
			if (0xFEFF == *wcs) break; /* ZWNBSP aka BOM (magic, signature) */
			
			/*
			 *  Special characters go here
			 */
			if (0x0008 == *wcs) { /* BACKSPACE */
				width = -1;
				break;
			}
			if (0x0009 == *wcs) { /* TAB */
				if (tab_width < 0) width = x % abs(tab_width);
				else width = tab_width;
				break;
			}
			
			/*FALLTHRU*/
		case narrow:
		case half_width:
			width = 1;
			break;
		case wide:
		case full_width:
			width = 2;
			break;
		case ambiguous:
			width = is_cjk_locale(locale_name) ? 2 : 1;
			break;
		default:
			width = INT_MAX;
    }
	free(wcs);
	return width;
}

int
get_east_asia_str_n_width (const char *locale_name, const char *s, size_t n, int x)
{
  int total_width = 0;
  wchar_t *wcs, *p;

  if (NULL == s) s = "";

  /*
   *  Getting the locale name via setlocale() is expensive, so we prefer
   *  to have it passed to us.
   */
  if (NULL == locale_name) {
    locale_name = setlocale(LC_CTYPE, NULL);
    if (NULL == locale_name) return INT_MAX;
  }

  wcs = (wchar_t *) calloc(n, sizeof(wchar_t));
  if (NULL == wcs) return INT_MAX;

#if defined __GLIBC__ && !__GLIBC_PREREQ(2,2)
#warning wide character support is broken. Glibc 2.2 or better needed.
#endif

  if ((size_t) -1 == mbstowcs(wcs, s, n)) return INT_MAX;

  for (p = wcs; L'\0' != *p; p++) {
    int width = 0;

    switch (get_east_asia_type(*p)) {
    case neutral:

      /*
       *  Put characters that print nothing here.
       *
       *  XXX: Yes, I know there are a lot more than this in ISO-10646, but
       *  this function is intended to calculate the width of strings for
       *  fixed width terminals displaying legacy CJK character sets.
       *  State-of-the-art Unicode handling terminals probably won't need
       *  this function anyway.
       */
      if (0x0000 == *p) break; /* NULL */
      if (0x0007 == *p) break; /* BELL */

      /*  FIXME: there will probably be ASCII chars after the escape
       *  code, which will be counted as part of the width even though they
       *  aren't displayed.
       */
      if (0x001B == *p) break; /* ESC */
      if (0xFEFF == *p) break; /* ZWNBSP aka BOM (magic, signature) */

      /*
       *  Special characters go here
       */
      if (0x0008 == *p) { /* BACKSPACE */
        width = -1;
        break;
      }
      if (0x0009 == *p) { /* TAB */
        if (tab_width < 0) width = x % abs(tab_width);
        else width = tab_width;
        break;
      }

      /*FALLTHRU*/
    case narrow:
    case half_width:
      width = 1;
      break;
    case wide:
    case full_width:
      width = 2;
      break;
    case ambiguous:
      width = is_cjk_locale(locale_name) ? 2 : 1;
      break;
    default: abort(); /* Doh! */
    }
    x += width;
    total_width += width;
  }
  free(wcs);
  return total_width;
}

int
get_east_asia_str_width (const char *locale_name, const char *s, int x) {
  size_t n;
  int rc;

  n = strlen(s) + 1;
  rc = get_east_asia_str_n_width (locale_name, s, n, x);
  if (rc == INT_MAX)
      return strlen (s);
  return rc;
}

#if TEST_GET_EAST_ASIA_STR_WIDTH

#include <stdio.h>

int
main (int argc, char *argv[]) {
  int i;
  char *lc;
  const char *fmt = "word #%d ('%s') length is %zu, width is %u\n";

  lc = setlocale(LC_CTYPE, "");
  if (NULL == lc) {
    fputs("couldn't set the default locale for LC_CTYPE\n", stderr);
    exit(EXIT_FAILURE);
  }
  if (printf("character type locale is '%s'\n", lc) < 0) {
    perror(NULL);
    exit(EXIT_FAILURE);
  }
  for (i = 1; argc < 2 || i < argc; i++) {
    char *s;
    size_t length;
    unsigned width;

    if (argc < 2) {
      if (scanf("%as", &s) < 1 && ferror(stdin)) {
        perror(NULL);
        exit(EXIT_FAILURE);
      }
      else if (feof(stdin)) break;
    }
    else s = strdup(argv[(size_t) i]);
    if (NULL == s) {
      perror(NULL);
      exit(EXIT_FAILURE);
    }
    length = strlen(s);
    width = get_east_asia_str_width(lc, s, 0);
    if (printf(fmt, i, s, length, width) < 0) {
      perror(NULL);
      exit(EXIT_FAILURE);
    }
    free(s);
  }
  return 0;
}

#endif
