#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/kd.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <zlib.h>
#include <rpm/rpmio.h>

#include "isys/cpio.h"
#include "loader.h"
#include "lang.h"
#include "log.h"

struct aString {
    unsigned int hash;
    short length;
    char * str;
} ;

struct aString * strings = NULL;
int numStrings = 0, allocedStrings = 0;

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

struct langInfo {
    char * lang, * key, * font, * map, * lc_all;
} ;

/* FONT LIST STARTS */
static const struct langInfo languages[] = {
        { "Czech", 	"cs", 	"lat2-sun16", 	"iso02",	"cs_CZ" },
        { "English",	"en",	NULL,		NULL,		"en_US" },
	{ "French",	"fr",	"lat0-sun16",	"iso15",	"fr_FR" },
	{ "German",	"de",	"lat0-sun16",	"iso15",	"de_DE" },
	{ "Hungarian",  "hu",   "lat2-sun16",   "iso02",	"hu_HU" },
	{ "Icelandic",	"is",	"lat0-sun16",	"iso15",	"is_IS" },
	{ "Italian",	"it",	"lat0-sun16",	"iso15",	"it_IT" },
	{ "Norwegian",	"no",	"lat0-sun16",	"iso15",	"no_NO" },
	{ "Romanian",	"ro",	"lat2-sun16",	"iso02",	"ro_RO" },
	{ "Slovak",	"sk",	"lat2-sun16",	"iso02",	"sk_SK" },
	{ "Russian", 	"ru", 	"Cyr_a8x16", 	"koi2alt",	"ru_SU" },
	{ "Ukrainian", "uk_UA", "RUSCII_8x16",	"koi2alt",	"uk_UA" },
};
/* FONT LIST ENDS */
const int numLanguages = sizeof(languages) / sizeof(struct langInfo);

void loadLanguage (char * file, int flags) {
    char filename[200];
    FD_t stream;
    int fd, hash, rc;
    char * key = getenv("LANG");

    if (!key || !strcmp(key, "en")) {
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

    stream = fdOpen(file, O_RDONLY, 0644);

    if (fdFileno(stream) < 0) {
	newtWinMessage("Error", "Ok", "Cannot open %s: %s. Installation will "
			"proceed in English.", file, strerror(errno));
	return ;
    }
    
    sprintf(filename, "%s.tr", key);

    rc = installCpioFile(stream, filename, "/tmp/translation", 1);
    fdClose(stream);

    if (rc || access("/tmp/translation", R_OK)) {
	newtWinMessage("Error", "Ok", "Cannot get translation file %s.\n", 
			filename);
	return;
    }
    
    fd = open("/tmp/translation", O_RDONLY);
    if (fd < 0) {
	newtWinMessage("Error", "Ok", "Failed to open /tmp/translation: %s\n", 
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

static int loadFont(char * fontFile, int flags) {
    char font[8192];
    unsigned short map[E_TABSZ];
    struct unimapdesc d;
    struct unimapinit u;
    struct unipair desc[2048];
    int fd;
    FD_t stream;
    int rc;

    if (!FL_TESTING(flags)) {
	stream = fdOpen("/etc/fonts.cgz", O_RDONLY, 0644);
	if (fdFileno(stream) < 0) {
	    newtWinMessage("Error", "Ok", 
			"Cannot open fonts: %s", strerror(errno));
	    return LOADER_ERROR;
	}

	rc = installCpioFile(stream, fontFile, "/tmp/font", 1);
	fdClose(stream);
	if (rc || access("/tmp/font", R_OK)) {
	    return LOADER_ERROR;
	}

	fd = open("/tmp/font", O_RDONLY);
	read(fd, font, sizeof(font));
	read(fd, map, sizeof(map));
        read(fd, &d.entry_ct, sizeof(d.entry_ct));
        d.entries = desc;
        read(fd, desc, d.entry_ct * sizeof(desc[0]));
	close(fd);

	if (ioctl(1, PIO_FONT, font))
	    logMessage("PIO_FONT failed: %s", strerror(errno)); 

	if (ioctl(1, PIO_UNIMAPCLR, &u))
	    logMessage("PIO_UNIMAPCLR failed: %s", strerror(errno));
	
	if (ioctl(1, PIO_UNIMAP, &d))
	    logMessage("PIO_UNIMAP failed: %s", strerror(errno));
	
	if (ioctl(1, PIO_UNISCRNMAP, map))
	    logMessage("PIO_UNISCRNMAP failed: %s", strerror(errno)); 

	fprintf(stderr, "\033(K");
    }
    return 0;
}

int chooseLanguage(int flags) {
    int choice = 0;
    char ** langs;
    int i;
    int english = 0;

    if (strings) {
	free(strings), strings = NULL;
	numStrings = allocedStrings = 0;
    }

    langs = alloca(sizeof(*langs) * (numLanguages + 1)); 

    for (i = 0; i < numLanguages; i++) {
	if (!strncmp(languages[i].key, "en", 2))
	    english = i;
	langs[i] = languages[i].lang;
    }

    langs[i] = NULL;

    choice = english;
    
    if (getenv("LANG")) {
	for (choice = 0; choice < numLanguages; choice++)
	    if (!strcmp(languages[choice].key, getenv("LANG"))) break;
	if (choice == numLanguages) choice = 0;
    }

    newtWinMenu(_("Choose a Language"), _("What language should be used "
		"during the installation process?"), 40, 5, 5, 8,
		langs, &choice, _("Ok"), NULL);

    if (choice == english) {
	/* stick with the default (English) */
	unsetenv("LANG");
	unsetenv("LC_ALL");
	unsetenv("LINGUAS");
	return 0;
    }

    setenv("LANG", languages[choice].key, 1);
    setenv("LC_ALL", languages[choice].lc_all, 1);
    setenv("LINGUAS", languages[choice].key, 1);
    loadLanguage (NULL, flags);
    if (languages[choice].font)
	loadFont(languages[choice].font, flags);

    return 0;
}



