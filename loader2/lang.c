/*
 * lang.c - determines language, handles translations
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
#include <unistd.h>

#include "loader.h"
#include "lang.h"
#include "log.h"
#include "loadermisc.h"
#include "windows.h"

#include "../isys/stubs.h"
#include "../isys/cpio.h"
#include "../isys/lang.h"

struct aString {
    unsigned int hash;
    short length;
    char * str;
} ;

struct aString * strings = NULL;
int numStrings = 0, allocedStrings = 0;

static char * topLineWelcome = N_("Welcome to %s");
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

static void loadLanguageList(int flags) {
    char * file = FL_TESTING(flags) ? "../lang-table" :
                    "/etc/lang-table";
    FILE * f;
    char line[256];
    char name[256], key[256], font[256], map[256], code[256],
         keyboard[256], timezone[256];
    int lineNum = 0;

    f = fopen(file, "r");
    if (!f) {
        newtWinMessage(_("Error"), _("OK"), "cannot open %s: %s",
                       file, strerror (errno));
        return;
    }

    while (fgets(line, sizeof(line), f)) {
        lineNum++;
        languages = realloc(languages, sizeof(*languages) * (numLanguages + 1));
        if (sscanf(line, "%s %s %s %s %s %s %s\n", name, key, font, map,
                                             code, keyboard, timezone) != 7) {
            logMessage("bad line %d in lang-table", lineNum);
        } else {
            languages[numLanguages].lang = strdup(name);
            languages[numLanguages].key = strdup(key);
            languages[numLanguages].font = strdup(font);
            languages[numLanguages].map = strdup(map);
            languages[numLanguages].lc_all = strdup(code);
            languages[numLanguages].keyboard = strdup(keyboard);
            numLanguages++;
        }
    }
}

int getLangInfo(struct langInfo ** langs, int flags) {
    if (!languages)
	loadLanguageList(flags);

    *langs = languages;
    return numLanguages;
}

void loadLanguage (char * file, int flags) {
    char filename[200];
    gzFile stream;
    int fd, hash, rc;
    char * key = getenv("LANGKEY");

    if (!key || !strcmp(key, "en_US")) {
        if (strings) {
            free(strings), strings = NULL;
            numStrings = allocedStrings = 0;
        }
        return;
    }

    if (!file) {
        file = filename;
        if (FL_TESTING(flags))
            sprintf(filename, "loader.tr");
        else
            sprintf(filename, "/etc/loader.tr");
    }

    stream = gunzip_open(file);

    if (!stream) {
        newtWinMessage("Error", "OK", "Translation for %s is not available.  "
                       "The Installation will proceed in English.", key);
        return ;
    }
    
    sprintf(filename, "%s.tr", key);

    rc = installCpioFile(stream, filename, "/tmp/translation", 1);
    gunzip_close(stream);

    if (rc || access("/tmp/translation", R_OK)) {
        newtWinMessage("Error", "OK", "Cannot get translation file %s.\n", 
                        filename);
        return;
    }
    
    fd = open("/tmp/translation", O_RDONLY);
    if (fd < 0) {
        newtWinMessage("Error", "OK", "Failed to open /tmp/translation: %s\n", 
                        strerror(errno));
        return;
    }

    while (read(fd, &hash, 4) == 4) {
        if (allocedStrings == numStrings) {
            allocedStrings += 10;
            strings = realloc(strings, sizeof(*strings) * allocedStrings);
        }

        strings[numStrings].hash = ntohl(hash);
        read(fd, &strings[numStrings].length, 2);
        strings[numStrings].length = ntohs(strings[numStrings].length);
        strings[numStrings].str = malloc(strings[numStrings].length + 1);
        read(fd, strings[numStrings].str, strings[numStrings].length);
        strings[numStrings].str[strings[numStrings].length] = '\0';
        numStrings++;
    }

    close(fd);
    unlink("/tmp/translation");

    qsort(strings, numStrings, sizeof(*strings), aStringCmp);
}


void setLanguage (char * key, int flags) {
    int i;

    if (!languages) loadLanguageList(flags);

    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(languages[i].key, key)) {
            if (!strcmp(languages[i].font, "None"))
                break;
            setenv("LANG", languages[i].lc_all, 1);
            setenv("LANGKEY", languages[i].key, 1);
            setenv("LC_ALL", languages[i].lc_all, 1);
            setenv("LINGUAS", languages[i].lc_all, 1);
            loadLanguage (NULL, flags);
            if (languages[i].map)
                isysLoadFont(languages[i].map);
            break;
        }
    }
}

int chooseLanguage(char ** lang, int flags) {
    int choice = 0;
    char ** langs;
    int i;
    int english = 0;
    int current = -1;
    char * currentLangName = getenv("LANG");
    int numLangs = 0;
    char * langPicked;
    char * buf;

    /* JKFIXME: I ripped out some of the wacky Kon stuff.  it might need
     * to come back for bterm */
    if (!languages) loadLanguageList(flags);

    langs = alloca(sizeof(*langs) * (numLanguages + 1)); 

    for (i = 0; i < numLanguages; i++) {
        if (!strncmp(languages[i].key, "en", 2))
            english = numLangs;
        if (currentLangName &&
            !strcmp(languages[i].lc_all, currentLangName))
            current = numLangs;

        langs[numLangs++] = languages[i].lang;
    }

    langs[numLangs] = NULL;

    if (current >= 0)
        choice = current;
    else
        choice = english;

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

    if (!strncmp(languages[choice].key, "en", 2)) {
        char *buf;
        /* stick with the default (English) */
        unsetenv("LANG");
        unsetenv("LANGKEY");
        unsetenv("LC_ALL");
        unsetenv("LINGUAS");
        if (strings) {
            free(strings), strings = NULL;
            numStrings = allocedStrings = 0;
        }
        buf = sdupprintf(_(topLineWelcome), PRODUCTNAME);
        newtDrawRootText(0, 0, buf);
        free(buf);
        newtPushHelpLine(_(bottomHelpLine));

        return 0;
    }

    /* only set the environment variables when we actually have a way
       to display the language */
    if (strcmp(languages[choice].font, "None")) {
        setenv("LANG", languages[choice].lc_all, 1);
        setenv("LANGKEY", languages[choice].key, 1);
        setenv("LC_ALL", languages[choice].lc_all, 1);
        setenv("LINGUAS", languages[choice].lc_all, 1);
    }
    
    if (strings) {
        free(strings), strings = NULL;
        numStrings = allocedStrings = 0;
    }

    /* load the language only if it is displayable */
    if (!strcmp(languages[choice].font, "None")) {
        newtWinMessage("Language Unavailable", "OK", 
                       "%s display is unavailable in text mode.  The "
                       "installation will continue in English until the "
                       "display of %s is possible.", languages[choice].lang,
                       languages[choice].lang);
    } else {
        loadLanguage (NULL, flags);
    }

    if (languages[choice].map)
        isysLoadFont(languages[choice].map);

    
    buf = sdupprintf(_(topLineWelcome), PRODUCTNAME);
    newtDrawRootText(0, 0, buf);
    free(buf);
    newtPushHelpLine(_(bottomHelpLine));

    return 0;
}

void setKickstartLanguage(struct loaderData_s * loaderData, int argc, 
                          char ** argv, int * flagsPtr) {
    if (argc < 2) {
        logMessage("no argument passed to lang kickstart command");
        return;
    }

    loaderData->lang = argv[1];
    loaderData->lang_set = 1;

}
