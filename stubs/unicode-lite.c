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

#include <stdlib.h>
#include <string.h>
#include <locale.h>

#define WLITE_REDEF_STDC 0
#include <wlite_wchar.h>
#include <wlite_wctype.h>


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

/* lie to slang to trick it into using unicode chars for linedrawing */
char *setlocale (int category, const char *locale) {
    if (locale == NULL || *locale == '\0') {
        if (!strcmp("vt100-nav", getenv("TERM")))
            return "en_US";
        else
            return "en_US.UTF-8";
    }
    return NULL;
}

/* lie to slang some more */
char *nl_langinfo(int item) {
    return NULL;
}

#  define __libc_freeres_fn_section \
  __attribute__ ((section ("__libc_freeres_fn")))

void __libc_freeres_fn_section ___nl_locale_subfreeres (void) {}
strong_alias (___nl_locale_subfreeres, _nl_locale_subfreeres);

const char *const _nl_category_names[] = {
    [LC_COLLATE] = "LC_COLLATE",
    [LC_CTYPE] = "LC_CTYPE",
    [LC_MONETARY] = "LC_MONETARY",
    [LC_NUMERIC] = "LC_NUMERIC",
    [LC_TIME] = "LC_TIME",
    [LC_MESSAGES] = "LC_MESSAGES",
    [LC_PAPER] = "LC_PAPER",
    [LC_NAME] = "LC_NAME",
    [LC_ADDRESS] = "LC_ADDRESS",
    [LC_TELEPHONE] = "LC_TELEPHONE",
    [LC_MEASUREMENT] = "LC_MEASUREMENT",
    [LC_IDENTIFICATION] = "LC_IDENTIFCATION",
    [LC_ALL] = "LC_ALL"
};

u_int8_t my_nl_category_name_idxs[1] = {0};
strong_alias (my_nl_category_name_idxs, _nl_category_name_idxs);

const size_t _nl_category_name_sizes[] = {
    [LC_COLLATE] = sizeof("LC_COLLATE") - 1,
    [LC_CTYPE] = sizeof("LC_CTYPE") -1,
    [LC_MONETARY] = sizeof("LC_MONETARY") -1,
    [LC_NUMERIC] = sizeof("LC_NUMERIC") -1,
    [LC_TIME] = sizeof("LC_TIME") -1,
    [LC_MESSAGES] = sizeof("LC_MESSAGES") -1,
    [LC_PAPER] = sizeof("LC_PAPER") -1,
    [LC_NAME] = sizeof("LC_NAME") -1,
    [LC_ADDRESS] = sizeof("LC_ADDRESS") -1,
    [LC_TELEPHONE] = sizeof("LC_TELEPHONE") -1,
    [LC_MEASUREMENT] = sizeof("LC_MEASUREMENT") -1,
    [LC_IDENTIFICATION] = sizeof("LC_IDENTIFCATION") -1,
    [LC_ALL] = sizeof("LC_ALL")
};

/* avoid bringing in glibc's setlocale.o - we want to use our
   fake setlocale() */
union
{
  pthread_mutex_t mtx;
  pthread_rwlock_t rwlck;
} __libc_setlocale_lock __attribute__((nocommon));
