/*
 * unicode-lite.c - simple library to LD_PRELOAD for emulation of
 * wide character functionality when glibc gconv data isn't available
 *
 * Matt Wilson <msw@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#define WLITE_REDEF_STDC 0
#include <wlite_wchar.h>
#include <wlite_wctype.h>
#include <pthread.h>

int wcwidth (wchar_t c) {
    return wlite_wcwidth(c);
}

size_t mbrtowc (wchar_t *pwc, const char *s, size_t n, void *ps) {
    return wlite_mbrtowc (pwc, s, n, ps);
}

int iswspace (wchar_t c) {
    return wlite_iswctype((c), wlite_space_);
}

size_t wcrtomb(char *s, wchar_t wc, void *ps) {
    return wlite_wcrtomb (s, wc, ps);
}

const char * __dgettext(const char * domainname, const char * msgid) {
    return msgid;
}

const char * __dcgettext(const char * domainname, const char * msgid,
		       int category) {
    return msgid;
}

/* Define ALIASNAME as a strong alias for NAME.  */
# define strong_alias(name, aliasname) _strong_alias(name, aliasname)
# define _strong_alias(name, aliasname) \
  extern __typeof (name) aliasname __attribute__ ((alias (#name)));

strong_alias (__dgettext, dgettext);
strong_alias (__dcgettext, dcgettext);

#ifdef DIET
/* lie to slang to trick it into using unicode chars for linedrawing */
char * setlocale (int category, const char *locale) {
    if (locale == NULL || *locale == '\0')
	return "en_US.UTF-8";
    return 0;
}

/* avoid bringing in glibc's setlocale.o - we want to use our
   fake setlocale() */
typedef pthread_mutex_t __libc_lock_t;
__libc_lock_t __libc_setlocale_lock;

#endif
