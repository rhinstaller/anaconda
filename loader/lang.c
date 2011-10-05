/*
 * lang.c - determines language, handles translations
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wchar.h>
#include <glib.h>

#include "loader.h"
#include "lang.h"
#include "loadermisc.h"
#include "windows.h"
#include "unpack.h"

#include "../pyanaconda/isys/lang.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/log.h"

const char *LANG_DEFAULT = "en_US.UTF-8";

/* boot flags */
extern uint64_t flags;

struct aString {
    unsigned int hash;
    short length;
    char * str;
} ;

struct aString * strings = NULL;
int numStrings = 0, allocedStrings = 0;

static int english = 0;

static char * topLineWelcome = N_("Welcome to %s for %s");
static char * topLineWelcomeRescue = N_("Welcome to %s for %s - Rescue Mode");
static char * bottomHelpLine = N_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen ");

static int aStringCmp(const void * a, const void * b) {
    const struct aString * first = a;
    const struct aString * second = b;

    if (first->hash < second->hash)
        return -1;
    else if (first->hash == second->hash)
        return 0;

    return 1;
}

char * translateString(char * str) {
    unsigned int sum = 0, xor = 0;
    int len = 0;
    char * chptr;
    struct aString * match;
    struct aString key;

    for (chptr = str; *chptr; chptr++) {
        sum += *chptr;
        xor ^= *chptr;
        len++;
    }

    key.hash = (sum << 16) | ((xor & 0xFF) << 8) | (len & 0xFF);
    match = bsearch(&key, strings, numStrings, sizeof(*strings), aStringCmp);
    if (!match)
        return str;

    return match->str;
}

static struct langInfo * languages = NULL;
static int numLanguages = 0;

static int defaultLanguageIndex(void) {
    int i;
    for (i = 0; i < numLanguages; ++i)
        if (!strcmp(languages[i].lc_all, LANG_DEFAULT))
            return i;
    return -1;
}

static void loadLanguageList(void) {
    char * file = "/etc/lang-table";
    FILE * f;
    char line[256];
    char name[256], key[256], font[256], code[256],
        keyboard[256], timezone[256];
    int lineNum = 0;

    wcwidth(0);
    f = fopen(file, "r");
    if (!f) {
        newtWinMessage(_("Error"), _("OK"), "cannot open %s: %m", file);
        return;
    }

    while (fgets(line, sizeof(line), f)) {
        lineNum++;
        languages = realloc(languages, sizeof(*languages) * (numLanguages + 1));
        if (sscanf(line, "%[^\t]\t%[^\t]\t%[^\t]\t%[^\t]\t%[^\t]\t%[^\t]\n",
                   name, key, font, code, keyboard, timezone) != 6) {
            printf("bad line %d in lang-table", lineNum);
            logMessage(WARNING, "bad line %d in lang-table", lineNum);
        } else {
            languages[numLanguages].lang = strdup(name);
            languages[numLanguages].key = strdup(key);
            languages[numLanguages].font = strdup(font);
            languages[numLanguages].lc_all = strdup(code);
            languages[numLanguages++].keyboard = strdup(keyboard);
        }
    }
    fclose(f);
}

int getLangInfo(struct langInfo ** langs) {
    if (!languages)
        loadLanguageList();

    *langs = languages;
    return numLanguages;
}

/**
 * Normalize the value of lang= boot argument.
 *
 * Currently only replaces the trailing .utf8 with .UTF-8.
 *
 * Returns a heap-allocated string.
 */
gchar *normalizeLang(const gchar *s)
{
    if (g_str_has_suffix(s, ".utf8")) {
        gchar *lang = g_strndup(s, strlen(s) - strlen(".utf8"));
        gchar *result = g_strconcat(lang, ".UTF-8", NULL);
        g_free(lang);
        return result;
    }

    return g_strdup(s);
}

void loadLanguage(void)
{
    char *filename;
    int fd, hash, rc;
    char * key = getenv("LANGKEY");

    if (strings) {
	free(strings), strings = NULL;
	numStrings = allocedStrings = 0;
    }

    /* english requires no files */
    if (!strcmp(key, "en"))
        return;

    checked_asprintf(&filename, "/tmp/translation/%s.tr", key);

    rc = unpack_archive_file("/etc/loader.tr", "/tmp/translation");
    if (rc != ARCHIVE_OK || access("/tmp/translation", R_OK) == -1) {
        newtWinMessage("Error", "OK", "Cannot get translation file %s.\n", 
                        filename);
        return;
    }

    fd = open(filename, O_RDONLY);
    if (fd < 0) {
        newtWinMessage("Error", "OK", "Failed to open /tmp/translation: %m\n");
        free(filename);
        return;
    }

    while (read(fd, &hash, 4) == 4) {
        if (allocedStrings == numStrings) {
            allocedStrings += 10;
            strings = realloc(strings, sizeof(*strings) * allocedStrings);
        }

        strings[numStrings].hash = ntohl(hash);
        rc = read(fd, &strings[numStrings].length, 2);
        strings[numStrings].length = ntohs(strings[numStrings].length);
        strings[numStrings].str = malloc(strings[numStrings].length + 1);
        rc = read(fd, strings[numStrings].str, strings[numStrings].length);
        strings[numStrings].str[strings[numStrings].length] = '\0';
        numStrings++;
    }

    close(fd);
    free(filename);
    int translation_dir_fd = open("/tmp/translation", O_RDONLY);
    recursiveRemove(translation_dir_fd);
    close(translation_dir_fd);
    rmdir("/tmp/translation");

    qsort(strings, numStrings, sizeof(*strings), aStringCmp);
}


/* give the index of the language to set to -- sets the appropriate
 * lang variables if we have a font.
 *
 * ASSUMPTION: languages exists
 */
static void setLangEnv (int i) {
    if (i > numLanguages)
        return;

    if (strcmp(languages[i].font, "latarcyrheb-sun16"))
        return;
    logMessage(INFO, "setting language to %s", languages[i].lc_all);

    setenv("LANG", languages[i].lc_all, 1);
    setenv("LANGKEY", languages[i].key, 1);
    setenv("LINGUAS", languages[i].lang, 1);
    loadLanguage();
}

/* choice is the index of the chosen language in languages */
static int setupLanguage(int choice, int forced) {
    char * buf;
    char *locale_def = NULL;    /* locale lang name */
    char *locale_charset = NULL;/* locale charset */
    char *locale_mod = NULL;    /* locale variant */
    char *locale_p = NULL;      /* last known locale separator */
    char *locale_i = NULL;      /* string iterator */
    int i;
    pid_t localedef_pid;

    logMessage(DEBUGLVL, "going to set language to %s", languages[choice].lc_all);

    /* Parse locale parts out of locale name.

      Locale examples:
      en
      en_US
      cz_CS.UTF-8
      cz_CS.UTF-8@latin
    */

    locale_p = locale_i = languages[choice].lc_all;
    while (1) {
        // we found new separator
        if (*locale_i == '.' || *locale_i == '@' || *locale_i == '\0') {
            // last separator was annotating charset
            if (*locale_p == '.') locale_charset = strndup(locale_p + 1, locale_i - locale_p - 1);
            // last separator was annotating modifier
            else if (*locale_p == '@') locale_mod = strndup(locale_p + 1, locale_i - locale_p - 1);
            // there was no known separator last time
            else locale_def = strndup(locale_p, locale_i - locale_p);

            // save last known separator
            locale_p = locale_i;

            if(*locale_i == '\0') break; // end of the string
        }

        // test next character
        locale_i++;
    }

    logMessage(DEBUGLVL, "locale %s: base: %s, mod: %s, charset: %s", languages[choice].lc_all, locale_def, locale_mod, locale_charset);

    /* prepare locale name without charset */
    i = strlen(locale_def);
    if (locale_mod) i+= strlen(locale_mod) + 1; /* +1 for the @ char */ 
    locale_p = (char*)calloc(i+1, sizeof(char));
    locale_p = strcpy(locale_p, locale_def);
    if (locale_mod){
        locale_p[strlen(locale_p)] = '@';
        locale_p = strcat(locale_p, locale_mod);
    }

    /* generate locale record */
    logMessage(INFO, "going to prepare locales for %s (locale: %s, charset: %s)", languages[choice].lc_all, locale_p, locale_charset);
    if ((localedef_pid = fork()) == 0) {
        execl("/usr/bin/localedef", "localedef",
              "-i", locale_p,
              "-f", (locale_charset) ? locale_charset : "UTF-8",
              languages[choice].lc_all, NULL);
        _exit(254);
    }

    if (localedef_pid < 0) logMessage(ERROR, "failed forking localedef for %s", languages[choice].lc_all);
    else{
        waitpid(localedef_pid, &i, 0);
        if (WEXITSTATUS(i) != 0) logMessage(ERROR, "failed preparing locales %s [%d]", languages[choice].lc_all, WEXITSTATUS(i));
    }

    /* cleanup */
    if (locale_charset) free(locale_charset);
    if (locale_def) free(locale_def);
    if (locale_mod) free(locale_mod);
    if (locale_p) free(locale_p);

    /* load the language only if it is displayable.  if they're using
     * a serial console or iSeries vioconsole, we hope it's smart enough */
    if ((strcmp(languages[choice].font, "latarcyrheb-sun16") && !FL_SERIAL(flags) && 
         !FL_VIRTPCONSOLE(flags) && !isVioConsole())) {
        if (forced == 1) return 0;

	newtWinMessage("Language Unavailable", "OK", 
		       "%s display is unavailable in text mode.  The "
		       "installation will continue in English until the "
		       "display of %s is possible.", languages[choice].lang,
		       languages[choice].lang);
        setLangEnv(english);
	return 0;
    }

    setLangEnv (choice);
    isysLoadFont();

    /* clear out top line */
    buf = alloca(81); /* reserve one byte for \0 */
    for (i=0; i < 80; i++)
	buf[i] = ' ';
    buf[80] = 0; /* and set the \0 */
    newtDrawRootText(0, 0, buf);

    char *fmt = FL_RESCUE(flags) ? _(topLineWelcomeRescue) : _(topLineWelcome);
    checked_asprintf(&buf, fmt, getProductName(), getProductArch());

    newtDrawRootText(0, 0, buf);
    free(buf);
    newtPopHelpLine();
    newtPushHelpLine(_(bottomHelpLine));

    return 0;
}

/* this is pretty simple.  we want to break down the language specifier
 * into its short form (eg, en_US)
 */
static char * getLangShortForm(char * oldLang) {
    char * lang;
    char * c;
    
    lang = strdup(oldLang);

    c = strchr(lang, '@');
    if (c) {
        *c = '\0';
    }

    c = strchr(lang, '.');
    if (c) {
        *c = '\0';
    }

    return lang;
}

/* return the nick of a language -- eg en_US -> en */
static char * getLangNick(char * oldLang) {
    char * lang;
    char * c;
    
    lang = strdup(oldLang);

    c = strchr(lang, '_');
    if (c) {
        *c = '\0';
    }

    return lang;
}

int setLanguage (const char * key, int forced) {
    int i;

    if (!languages) loadLanguageList();

    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(languages[i].lc_all, key)) {
            return setupLanguage(i, forced | !FL_KICKSTART(flags));
        }
    }

    /* we didn't specify anything that's exactly in the lang-table.  check
     * against short forms and nicks */
    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(getLangShortForm(languages[i].lc_all), key)) {
            return setupLanguage(i, forced | !FL_KICKSTART(flags));
        }
    }

    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(getLangNick(languages[i].lc_all), key)) {
            return setupLanguage(i, forced | !FL_KICKSTART(flags));
        }
    }

    logMessage(ERROR, "unable to set the requested language '%s', "
               "setting the default '%s'", key, LANG_DEFAULT);
    return setupLanguage(defaultLanguageIndex(), forced | !FL_KICKSTART(flags));
}

int chooseLanguage(char ** lang) {
    int choice = 0;
    char ** langs;
    int i;
    int current = -1;
    char * currentLangName = getenv("LANG");
    int numLangs = 0;
    char * langPicked;

    if (!languages) loadLanguageList();

    langs = alloca(sizeof(*langs) * (numLanguages + 1)); 

    for (i = 0; i < numLanguages; i++) {
        if (!strncmp(languages[i].key, "en", 2))
            english = numLangs;
        if (currentLangName &&
            !strcmp(languages[i].lang, currentLangName))
            current = numLangs;

        langs[numLangs++] = languages[i].lang;
    }

    langs[numLangs] = NULL;

    if (current >= 0)
        choice = current;
    else
        choice = english;

    if (!FL_CMDLINE(flags))
        newtWinMenu(_("Choose a Language"),
                    _("What language would you like to use during the "
                      "installation process?"), 40, 5, 5, 8,
                    langs, &choice, _("OK"), NULL);

    langPicked = langs[choice];
    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(langPicked, languages[i].lang)) {
            *lang = languages[i].lc_all;
            choice = i;
            break;
        }
    }

    /* this can't happen */
    if (i == numLanguages) abort();

    return setupLanguage(choice, 0);
}
