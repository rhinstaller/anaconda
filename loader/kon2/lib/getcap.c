/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992-1996 Takashi MANABE (manabe@papilio.tutics.tut.ac.jp)
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY TAKASHI MANABE ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE TERRENCE R. LAMBERT BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 * 
 */

#include	<stdio.h>
#include	<string.h>
#include	<unistd.h>
#include	<stdlib.h>

#include	<getcap.h>

#define BUF_SIZE	1024

#define MAX_CAPS	20

static struct capability {
	char *name;			 /* Name of capability label */
	initializer *func;		 /* Function to perform configuration */
	int initialized;		 /* 1 if initialized */
	char *arg;			 /* Command line argument for this capability. */
	char *def_value;		 /* Default value.  NULL means required entry. */
} cap[MAX_CAPS];

static struct capability	*FindCap(const char *name)
{
	int	i;
	struct capability	*cp;

	for (i = 0, cp = cap; i < MAX_CAPS; i++, cp++) {
		if ((cp->name != NULL) && (strcasecmp(name, cp->name) == 0)) {
			return cp;
		}
	}
	return NULL;
}

/* Define initializer function func for capability name.  If def_value is nil,
   then the entry of the name must exist in configuration file.  An error is
   flagged if no entry is found.  If def_value is non-nil and no entry is found
   in configuration file, then func is invoked with def_value. */

void	DefineCap(const char *name, initializer *func, const char *def_value)
{
	int	i;
	struct capability	*cp;

	/* Pass 1 -- try to replace same name entry if exists. */
	if ((cp = FindCap(name)) != NULL) {
#ifdef	DEBUG
		fprintf(stderr, "cap %s redefined (default %s)\r\n", name,
			def_value ? def_value : "None");
#endif
		cp->name = strdup(name);
		cp->func = func;
		if (def_value)
			cp->def_value = strdup(def_value);
		return;
	}
	/* Pass 2 -- fine empty slot and insert new entry. */
	for (i = 0, cp = cap; i < MAX_CAPS; i++, cp++) {
		if (cp->name == NULL) {
#ifdef	DEBUG
			fprintf(stderr, "cap %s defined (default %s)\r\n", name,
				def_value ? def_value : "None");
#endif
			cp->name = strdup(name);
			cp->func = func;
			if (def_value)
				cp->def_value = strdup(def_value);
			return;
		}
	}
	fprintf(stderr, "Fatal: internal error - can't find room for capability `%s'\r\r\n", name);
	abort();
}

/* Delete all initializer functions. */

void CapInit(void)
{
	struct capability	*cp;
	int	i;

	for (i = 0, cp = cap; i < MAX_CAPS; i++, cp++) {
#ifdef	DEBUG
		if (cp->name) 
			fprintf(stderr, "cap %s deleted\r\n", cp->name);
#endif
		cp->initialized = 0;
		if (cp->name)
			free(cp->name);
		if (cp->arg)
			free(cp->arg);
		if (cp->def_value)
			free(cp->def_value);
		cp->name = cp->arg = cp->def_value = NULL;
	}
}

static const char label_delim[] = ":,; \t\n";

/* Read configuration file named filename and invoke initializer function for each entry. */

int	ReadConfig(const char *filename)
{
	FILE	*capFp;
	char	line[MAX_COLS], *p;
	char	buf[BUF_SIZE];
	struct capability *c;
	int	i;
	int	errors = 0;		 /* number of errors during configuration */

	if ((capFp = fopen(filename, "r")) == NULL) {
		fprintf(stderr, "Error: can't open config file\r\r\n");
		perror(filename);
		return FAILURE;
	}

	while(fgets(line, MAX_COLS, capFp) != NULL) {
	nextLabel:
		if ((p = strchr(line, '#')) != NULL)
			*p = '\0';
		if (strchr(line, ':') == NULL) continue; /* not a lebel */
		for (p = strtok(line, label_delim); p != NULL; p = strtok(NULL, label_delim)) {
			/* Process one label line. */
			if ((c = FindCap(p)) != NULL) {
				/* Found matching capability.  Get body from file. */
				char *l = buf;
				while (fgets(line, MAX_COLS, capFp) != NULL
				       && line[0] == '\t') {
					char *l2 = line;
					while (*l2 != '\n' && *l2 != '#') {
						*l++ = *l2++;
					}
					*l++ = '\n';
				}
				*l = '\0';
				if (! c->initialized) {
					/* do initialize */
					if (c->arg) {
#ifdef	DEBUG
						fprintf(stderr, "Capability %s set to arg %s\r\n",
							c->name, c->arg);
#endif
						if (c->func(c->arg) < 0)
							errors++;
					} else {
#ifdef	DEBUG
						fprintf(stderr, "Capability %s set to %s",
							c->name, buf);
#endif
						if (c->func(buf) < 0)
							errors++;
					}
					c->initialized = 1;
				}
				goto nextLabel;	/* next line already read */
			}
		}
	}
	/* Default initialization for unspecified capability. */
	for (i = 0, c = cap; i < MAX_CAPS; i++, c++) {
		if ((c->name != NULL) && !c->initialized) {
			if (c->arg) {
#ifdef	DEBUG
				fprintf(stderr, "Capability %s defaults to arg %s\r\n", c->name, c->arg);
#endif
				if (c->func(c->arg) < 0)
					errors++;
			} else if (c->def_value) {
#ifdef	DEBUG
				fprintf(stderr, "Capability %s defaults to %s\r\n", c->name, c->def_value);
#endif
				if (c->func(c->def_value) < 0)
					errors++;
			} else {
				fprintf(stderr, "Error: entry for capability `%s' not found\r\r\n", c->name);
				errors++;
			}
		}
	}
	fclose(capFp);
#ifdef	DEBUG
	fprintf(stderr, "Finished reading config file\r\n");
#endif
	if (errors)
		return FAILURE;
	else
		return SUCCESS;
}

/* Set value for capability capName. */
int	SetCapArg(const char *capName, const char *value)
{
	struct capability *cp;
	if ((cp = FindCap(capName)) == NULL) {
		return FAILURE;
	}
	if (cp->def_value == NULL) {
		/* Protected capability. */
		return FAILURE;
	}
	cp->arg = strdup(value);
#ifdef	DEBUG
	fprintf(stderr, "Setting arg for %s to %s\r\n", capName, value);
#endif
	return SUCCESS;
}

/* Utility function that return 1 if confstr is "On" and 0 if "OFF". */

bool BoolConf(const char *confstr)
{
	char name[MAX_COLS];
	sscanf(confstr, "%s", name);
	if (strcasecmp(name, "On") == 0 ||
	    strcasecmp(name, "True") == 0) {
		return TRUE;
	} else if (strcasecmp(name, "Off") != 0 &&
		   strcasecmp(name, "False") != 0) {
		fprintf(stderr, "Warning: value `%s' unrecognized as boolean; assuming `Off'\r\r\n",
		     name);
	}
	return FALSE;
}
