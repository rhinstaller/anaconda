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

#include <glob.h>   /* XXX rpmlib.h */
#include <dirent.h> /* XXX rpmlib.h */

#include <linux/keyboard.h>
#include <linux/kd.h>

#include "isys/cpio.h"
#include "loader.h"
#include "lang.h"
#include "log.h"
#include "misc.h"
#include "windows.h"
#include "stubs.h"
#include "kickstart.h"

#define errorWindow(String) \
	newtWinMessage(_("Error"), _("OK"), String, strerror (errno));

extern int haveKon;

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

struct langInfo {
    char * lang, * key, * font, * map, * lc_all, * keyboard;
} ;

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
	    languages[numLanguages].key	= strdup(key);
	    languages[numLanguages].font = strdup(font);
	    languages[numLanguages].map	= strdup(map);
	    languages[numLanguages].lc_all = strdup(code);
	    languages[numLanguages].keyboard = strdup(keyboard);
	    numLanguages++;
	}
    }
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

static int loadFont(char * fontFile, int flags) {
    char font[8192];
    unsigned short map[E_TABSZ];
    struct unimapdesc d;
    struct unimapinit u;
    struct unipair desc[2048];
    int fd;
    gzFile stream;
    int rc;

    if (!strcmp(fontFile, "None") || !strcmp(fontFile, "Kon")) return 0;
#if 0
    if (!FL_TESTING(flags)) {
#endif
	stream = gunzip_open("/etc/fonts.cgz");
	if (!stream) {
	    newtWinMessage("Error", "OK", 
			"Cannot open fonts: %s", strerror(errno));
	    return LOADER_ERROR;
	}

	rc = installCpioFile(stream, fontFile, "/tmp/font", 1);
        gunzip_close(stream);
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

void setLanguage (char * key, int flags) {
    int i;

    if (!languages) loadLanguageList(flags);

    for (i = 0; i < numLanguages; i++) {
        if (!strcmp(languages[i].key, key)) {
#if !defined (__s390__) && !defined (__s390x__)
            if (!strcmp(languages[i].font, "Kon") && !haveKon)
                break;
#endif
            if (!strcmp(languages[i].font, "None"))
                break;
            setenv("LANG", languages[i].lc_all, 1);
            setenv("LANGKEY", languages[i].key, 1);
            setenv("LC_ALL", languages[i].lc_all, 1);
            setenv("LINGUAS", languages[i].lc_all, 1);
            loadLanguage (NULL, flags);
            if (languages[i].map)
                loadFont(languages[i].map, 0);
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
    extern int continuing;
    char * currentLangName = getenv("LANG");
    int numLangs = 0;
    char * langPicked;
    char * buf;

    if (!languages) loadLanguageList(flags);

    langs = alloca(sizeof(*langs) * (numLanguages + 1)); 

    for (i = 0; i < numLanguages; i++) {
	/* If we're running in kon, only offer languages which use the
	   Kon or default8x16 fonts. Don't display languages which require
	   Kon font if we have no way of providing it. */
	if (continuing && strcmp(languages[i].font, "Kon") &&
	    continuing && strcmp(languages[i].font, "default8x16"))
	    continue;

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
#if !defined (__s390__) && !defined (__s390x__)
    if ((!strcmp(languages[choice].font, "Kon") && haveKon) ||
	(strcmp(languages[choice].font, "None") &&
	 strcmp(languages[choice].font, "Kon")))
#endif
	{
	    setenv("LANG", languages[choice].lc_all, 1);
		 setenv("LANGKEY", languages[choice].key, 1);
	    setenv("LC_ALL", languages[choice].lc_all, 1);
		 setenv("LINGUAS", languages[choice].lc_all, 1);
    }
    
    if (strings) {
	free(strings), strings = NULL;
	numStrings = allocedStrings = 0;
    }

    if (haveKon) {
	extern void stopNewt(void);
	
	if (!strcmp (languages[choice].font, "Kon") && !continuing) {
	    char * args[4];

	    stopNewt();

	    args[0] = "kon";
	    args[1] = "-e";
	    args[2] = FL_TESTING(flags) ? "./loader" : "/sbin/continue";
	    args[3] = NULL;
	    
	    execv(FL_TESTING(flags) ? "./loader" : "/sbin/loader", args);
	}
    }

    /* load the language only if it is displayable */
    /* If we need kon and have it, or if it's not kon or none, load the lang */
    /* S/390 is different because everything depends on the capabilities */
    /* of the xterm/kterm... from which anaconda will be started */
#if defined (__s390__) || defined (__s390x__)
   loadLanguage (NULL, flags);
#else
    if ((!strcmp(languages[choice].font, "None")) ||
	((!strcmp(languages[choice].font, "Kon")) && (!haveKon))) {
	newtWinMessage("Language Unavailable", "OK", 
		       "%s display is unavailable in text mode.  The "
		       "installation will continue in English until the "
		       "display of %s is possible.", languages[choice].lang,
		       languages[choice].lang);
    } else {
	loadLanguage (NULL, flags);
    }
#endif	

    if (languages[choice].map)
	loadFont(languages[choice].map, flags);

    
    buf = sdupprintf(_(topLineWelcome), PRODUCTNAME);
    newtDrawRootText(0, 0, buf);
    free(buf);
    newtPushHelpLine(_(bottomHelpLine));

    return 0;
}

#ifdef __sparc__
struct defaultKeyboardByLang {
    char * lang, * keyboard;
} defaultSunKeyboards[] = {
    { "fi_FI", "sunt5-fi-latin1" },   
    { "cs_CZ", "sunt5-cz-us" },
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

    if (gunzip_read(stream, &magic, sizeof(magic)) != sizeof(magic)) {
	logMessage("failed to read kmap magic: %s", strerror(errno));
	return LOADER_ERROR;
    }

    if (magic != KMAP_MAGIC) {
	logMessage("bad magic for keymap!");
	return LOADER_ERROR;
    }

    if (gunzip_read(stream, keymaps, sizeof(keymaps)) != sizeof(keymaps)) {
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

	if (gunzip_read(stream, keymap, sizeof(keymap)) != sizeof(keymap)) {
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
    char *lang;
    int argc;
    char **argv;

#ifdef __sparc__
#define KBDTYPE_SUN            0
#define KBDTYPE_PC             1
    struct defaultKeyboardByLang * kbdEntry;
    int kbdtype = -1;
    int j;
#endif

    if (FL_SERIAL (flags)) return LOADER_NOOP;

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
#endif /* kickstart sparc crap */
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
#endif /* sparc */

    if (!languages) loadLanguageList(flags);

    lang = getenv("LANG");
    if (!defkbd && lang) {
	for (i = 0; i < numLanguages; i++) {
	    if (!strncmp(languages[i].lc_all, lang, 2)) {
		defkbd = languages[i].keyboard;
		break;
	    }
	}

#ifdef __sparc__
	if (kbdtype == KBDTYPE_SUN)
	    kbdEntry = defaultSunKeyboards;
	while (kbdEntry->lang && 
	       strcmp(kbdEntry->lang, getenv("LANG")))
	     kbdEntry++;
	if (kbdEntry->keyboard) defkbd = kbdEntry->keyboard;
#endif /* more sparc drain bamage */
    }
    if (!defkbd)
#ifdef __sparc__
	if (kbdtype == KBDTYPE_SUN)
	    defkbd = "sunkeymap";
	else
#endif /* sparc drain bamage */
	    defkbd = "us";

    f = gunzip_open("/etc/keymaps.gz");
    if (!f) {
	errorWindow("cannot open /etc/keymaps.gz: %s");
	return LOADER_ERROR;
    }

    if (gunzip_read(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	errorWindow("failed to read keymaps header: %s");
	gunzip_close(f);
	return LOADER_ERROR;
    }

    logMessage("%d keymaps are available", hdr.numEntries);

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gunzip_read(f, infoTable, i) != i) {
	errorWindow("failed to read keymap information: %s");
	gunzip_close(f);
	return LOADER_ERROR;
    }

    if (FL_KICKSTART(flags)) {
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
    
    if (num == -1 ) {
#ifdef __sparc__
	kbds = alloca(sizeof(*kbds) * (hdr.numEntries + 1));
	for (j = 0, i = 0; j < hdr.numEntries; j++) {
	    if (kbdtype == KBDTYPE_SUN && strncmp (infoTable[j].name, "sun", 3))
		continue;
	    else if (kbdtype == KBDTYPE_PC && !strncmp (infoTable[j].name, "sun", 3))
	        continue;
	    kbds[i] = infoTable[j].name;
	    i++;
	}
#else	
	kbds = alloca(sizeof(*kbds) * (hdr.numEntries + 1));
	for (i = 0; i < hdr.numEntries; i++)  {
	    kbds[i] = infoTable[i].name;
	}
#endif

	kbds[i] = NULL;
	qsort(kbds, i, sizeof(*kbds), simpleStringCmp);

	for (i = 0; i < hdr.numEntries; i++) 
	    if (!strcmp(kbds[i], defkbd)) 
		num = i;

	rc = newtWinMenu(_("Keyboard Type"), 
			_("What type of keyboard do you have?"),
		        40, 5, 5, 8, kbds, &num, _("OK"), _("Back"), NULL);
	if (rc == 2) return LOADER_BACK;

	/* num needs to index the right keyboard infoTable */
	for (i = 0; i < hdr.numEntries; i++)
	    if (!strcmp(kbds[num], infoTable[i].name)) break;
	num = i;
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
	if (gunzip_read(f, buf, infoTable[i].size) != infoTable[i].size) {
	    logMessage("error reading %d bytes from file: %s", 
			    infoTable[i].size, strerror(errno));
	    gunzip_close(f);
	    rc = LOADER_ERROR;
	}
    }

    if (!rc) rc = loadKeymap(f);

    gunzip_close(f);

    if (keymap) *keymap = strdup(infoTable[num].name);

#ifdef __sparc__
    if (kbdtypep) *kbdtypep = (kbdtype == KBDTYPE_SUN) ? "sun" : "pc";
#endif

    return rc;
}
