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
#include <linux/keyboard.h>
#include <linux/kd.h>

#include "isys/cpio.h"
#include "loader.h"
#include "lang.h"
#include "log.h"
#include "windows.h"

#define errorWindow(String) \
	newtWinMessage(_("Error"), _("OK"), String, strerror (errno));

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

#ifdef INCLUDE_KON
static const struct langInfo languages[] = {
        { "English",	"en",	NULL,		NULL,		"en_US" },
	{ "Japanese",	"ja",	NULL,		NULL,		"ja_JP" },
};
#else
/* FONT LIST STARTS */
static const struct langInfo languages[] = {
        { "Czech", 	"cs", 	"lat2-sun16", 	"iso02",	"cs_CZ" },
        { "English",	"en",	NULL,		NULL,		"en_US" },
	{ "French",	"fr",	NULL,		NULL,		"fr_FR" },
	{ "German",	"de",	NULL,		NULL,		"de_DE" },
	{ "Hungarian",  "hu",   "lat2-sun16",   "iso02",	"hu_HU" },
	{ "Icelandic",	"is",	"lat0-sun16",	"iso15",	"is_IS" },
	{ "Indonesian",	"id",	"lat0-sun16",	"iso15",	"id_ID" },
	{ "Italian",	"it",	"lat0-sun16",	"iso15",	"it_IT" },
	{ "Norwegian",	"no",	"lat0-sun16",	"iso15",	"no_NO" },
	{ "Romanian",	"ro",	"lat2-sun16",	"iso02",	"ro_RO" },
	{ "Russian", 	"ru", 	"Cyr_a8x16", 	"koi2alt",	"ru_RU.KOI8-R" },
	{ "Serbian",	"sr",	"lat2-sun16",	"iso02",	"sr_YU" },
	{ "Slovak",	"sk",	"lat2-sun16",	"iso02",	"sk_SK" },
	{ "Slovenian",	"sl",	"lat2-sun16",	"iso02",	"sl_SI" },
	{ "Turkish",	"tr",	"iso05.f16",	"iso05",	"tr_TR" },
	{ "Ukrainian",  "uk",   "Cyr_a8x16",	"koi2alt",	"ru_RU.KOI8-R" },
};
/* FONT LIST ENDS */
#endif
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
	newtWinMessage("Error", "OK", "Cannot open %s: %s. Installation will "
			"proceed in English.", file, strerror(errno));
	return ;
    }
    
    sprintf(filename, "%s.tr", key);

    rc = installCpioFile(stream, filename, "/tmp/translation", 1);
    fdClose(stream);

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

static int loadFont(char * fontFile, int flags) {
    char font[8192];
    unsigned short map[E_TABSZ];
    struct unimapdesc d;
    struct unimapinit u;
    struct unipair desc[2048];
    int fd;
    FD_t stream;
    int rc;

#if 0
    if (!FL_TESTING(flags)) {
#endif
	stream = fdOpen("/etc/fonts.cgz", O_RDONLY, 0644);
	if (fdFileno(stream) < 0) {
	    newtWinMessage("Error", "OK", 
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
#if 0
    }
#endif
    return 0;
}

void setLanguage (char * key) {
    int i;
    
    for (i = 0; i < numLanguages; i++) {
	if (!strcmp(languages[i].key, key)) {
	    setenv("LANG", languages[i].key, 1);
	    setenv("LC_ALL", languages[i].lc_all, 1);
	    setenv("LINGUAS", languages[i].key, 1);
	    loadLanguage (NULL, 0);
	    if (languages[i].font)
		loadFont(languages[i].font, 0);
	    break;
	}
    }
}

int chooseLanguage(char ** lang, int flags) {
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
		langs, &choice, _("OK"), NULL);

    *lang = languages[choice].lc_all;

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

struct defaultKeyboardByLang {
    char * lang, * keyboard;
} defaultKeyboards[] = {
    { "de", "de-latin1" }, 
    { "cs", "cz-lat2" },
    { "fi", "fi-latin1" },
    { "hu", "hu" },
    { "is", "is-latin1" },
    { "it", "it" },
    { "no", "no-latin1" },   
    { "ru", "ru" },
    { "se", "se-latin1" },
    { "tr", "trq" },
    { NULL, NULL } };

#ifdef __sparc__
struct defaultKeyboardByLang
defaultSunKeyboards[] = {
    { "fi", "sunt5-fi-latin1" },   
    { "cs", "sunt5-cz-us" },
    { NULL, NULL } };
#endif

/* the file pointer must be at the beginning of the section already! */
static int loadKeymap(gzFile stream) {
    int console;
    int kmap, key;
    struct kbentry entry;
    int keymaps[MAX_NR_KEYMAPS];
    int count = 0;
    int magic;
    short keymap[NR_KEYS];

    if (gzread(stream, &magic, sizeof(magic)) != sizeof(magic)) {
	logMessage("failed to read kmap magic: %s", strerror(errno));
	return LOADER_ERROR;
    }

    if (magic != KMAP_MAGIC) {
	logMessage("bad magic for keymap!");
	return LOADER_ERROR;
    }

    if (gzread(stream, keymaps, sizeof(keymaps)) != sizeof(keymaps)) {
	logMessage("failed to read keymap header: %s", strerror(errno));
	return LOADER_ERROR;
    }


    console = open("/dev/console", O_RDWR);
    if (console < 0) {
	logMessage("failed to open /dev/console: %s", strerror(errno));
	return LOADER_ERROR;
    }

    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	if (!keymaps[kmap]) continue;

	if (gzread(stream, keymap, sizeof(keymap)) != sizeof(keymap)) {
	    logMessage("failed to read keymap data: %s", strerror(errno));
	    close(console);
	    return LOADER_ERROR;
	}

	count++;
	for (key = 0; key < NR_KEYS; key++) {
	    entry.kb_index = key;
	    entry.kb_table = kmap;
	    entry.kb_value = keymap[key];
	    if (KTYP(entry.kb_value) != KT_SPEC) {
		if (ioctl(console, KDSKBENT, &entry)) {
		    close(console);
		    logMessage("keymap ioctl failed: %s", strerror(errno));
		}
	    }
	}
    }

    logMessage("loaded %d keymap tables", count);

    close(console);

    return 0;
}

int chooseKeyboard(char ** keymap, char ** kbdtypep, int flags) {
    int num = -1;
    int rc;
    gzFile f;
    struct kmapHeader hdr;
    struct kmapInfo * infoTable;
    char ** kbds;
    char buf[16384]; 			/* I hope this is big enough */
    int i;
    char * defkbd = keymap ? *keymap : NULL;
    struct defaultKeyboardByLang * kbdEntry;

#ifdef __sparc__
#define KBDTYPE_SUN            0
#define KBDTYPE_PC             1
    int kbdtype = -1;
    int j;
#endif

    if (FL_SERIAL (flags)) return 0;

    /*if (testing) return 0;*/

#ifdef __sparc__
#if 0
    if (kickstart) {
    	kbdtype = KBDTYPE_SUN;
	if (!ksGetCommand(KS_CMD_KBDTYPE, NULL, &argc, &argv)) {
	    if (argc < 2) {
		logMessage("no argument passed to keyboard "
				"kickstart command");
	    } else {
	        if (!strcasecmp (argv[1], "sun"))
	            kbdtype = KBDTYPE_SUN;
	        else if (!strcasecmp (argv[1], "pc"))
	            kbdtype = KBDTYPE_PC;
	    }
	}
    } else
#endif
    {
        char twelve = 12;
        int fd;
        
        if (ioctl (0, TIOCLINUX, &twelve) < 0)
            kbdtype = KBDTYPE_SUN; /* probably serial console, but one should not call us in such a case */
        else {
            fd = open("/dev/kbd", O_RDWR);
            if (fd < 0)
            	kbdtype = KBDTYPE_PC; /* if PC keyboard, then there is no driver for /dev/kbd */
            else {
            	close(fd);
                kbdtype = KBDTYPE_SUN;
            }
        }
    }
#endif
    
    if (!defkbd && getenv("LANG")) {
	kbdEntry = defaultKeyboards;
#ifdef __sparc__
	if (kbdtype == KBDTYPE_SUN)
	    kbdEntry = defaultSunKeyboards;
#endif	
	while (kbdEntry->lang && 
	       strcmp(kbdEntry->lang, getenv("LANG")))
	     kbdEntry++;
	if (kbdEntry->keyboard) defkbd = kbdEntry->keyboard;
    }
    if (!defkbd)
#ifdef __sparc__
	if (kbdtype == KBDTYPE_SUN)
	    defkbd = "sunkeymap";
	else
#endif
	    defkbd = "us";

    f = gzopen("/etc/keymaps.gz", "r");
    if (!f) {
	errorWindow("cannot open /etc/keymaps.gz: %s");
	return LOADER_ERROR;
    }

    if (gzread(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	errorWindow("failed to read keymaps header: %s");
	gzclose(f);
	return LOADER_ERROR;
    }

    logMessage("%d keymaps are available", hdr.numEntries);

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gzread(f, infoTable, i) != i) {
	errorWindow("failed to read keymap information: %s");
	gzclose(f);
	return LOADER_ERROR;
    }

#if 0
    if (kickstart) {
	if (!ksGetCommand(KS_CMD_KEYBOARD, NULL, &argc, &argv)) {
	    if (argc < 2) {
		logMessage("no argument passed to keyboard "
				"kickstart command");
	    } else {
		for (i = 0; i < hdr.numEntries; i++) 
		    if (!strcmp(infoTable[i].name, argv[1])) break;
#ifdef __sparc__
		if (i < hdr.numEntries) {
		    if (kbdtype == KBDTYPE_SUN && strncmp (argv[1], "sun", 3))
		    	i = hdr.numEntries;
		    else if (kbdtype == KBDTYPE_PC && !strncmp (argv[1], "sun", 3))
		    	i = hdr.numEntries;
		}
#endif
		if (i < hdr.numEntries)
		    num = i;
		else 
		    newtWinMessage("Kickstart Error", "OK", "Bad keymap "
				   "name %s passed to kickstart command.",
				   argv[1]);
	    }
	}
    }
#endif
    
    if (num == -1 ) {
#ifdef __sparc__
	kbds = alloca(sizeof(*kbds) * (hdr.numEntries + 1));
	for (j = 0, i = 0; j < hdr.numEntries; j++) {
	    if (kbdtype == KBDTYPE_SUN && strncmp (infoTable[j].name, "sun", 3))
		continue;
	    else if (kbdtype == KBDTYPE_PC && !strncmp (infoTable[j].name, "sun", 3))
	        continue;
	    kbds[i] = infoTable[j].name;
	    if (!strcmp(infoTable[j].name, defkbd))
		num = i;
	    i++;
	}
#else	
	kbds = alloca(sizeof(*kbds) * (hdr.numEntries + 1));
	for (i = 0; i < hdr.numEntries; i++)  {
	    kbds[i] = infoTable[i].name;
	    if (!strcmp(infoTable[i].name, defkbd)) 
		num = i;
	}
#endif

	kbds[i] = NULL;

	rc = newtWinMenu(_("Keyboard Type"), 
			_("What type of keyboard do you have?"),
		        40, 5, 5, 8, kbds, &num, _("OK"), _("Back"), NULL);
	if (rc == 2) return LOADER_BACK;
    }

    rc = 0;

#ifdef __sparc__
    for (j = 0, i = 0; i < hdr.numEntries; i++) {
	if (kbdtype == KBDTYPE_SUN && strncmp (infoTable[i].name, "sun", 3))
		continue;
	if (kbdtype == KBDTYPE_PC && !strncmp (infoTable[i].name, "sun", 3))
		continue;
	if (j == num) {
		num = i;
		break;
	}
	j++;
    }
#endif	

    for (i = 0; i < num; i++) {
	if (gzread(f, buf, infoTable[i].size) != infoTable[i].size) {
	    logMessage("error reading %d bytes from file: %s", 
			    infoTable[i].size, strerror(errno));
	    gzclose(f);
	    rc = LOADER_ERROR;
	}
    }

    if (!rc) rc = loadKeymap(f);

    gzclose(f);

    if (keymap) *keymap = strdup(infoTable[num].name);

#ifdef __sparc__
    if (kbdtypep) *kbdtypep = (kbdtype == KBDTYPE_SUN) ? "sun" : "pc";
#endif

    return rc;
}
