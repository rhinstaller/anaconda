/*
 * urls.c - url handling code
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

#include <arpa/inet.h>
#include <ctype.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netdb.h>

#include "../isys/dns.h"

#include "ftp.h"
#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "urls.h"
#include "log.h"
#include "windows.h"
#include "net.h"

/* boot flags */
extern uint64_t flags;

/* convert a url (ftp or http) to a ui */
int convertURLToUI(char *url, struct iurlinfo *ui) {
    char *chptr;

    memset(ui, 0, sizeof(*ui));
    
    if (!strncmp("ftp://", url, 6)) {
	ui->protocol = URL_METHOD_FTP;
	url += 6;
	
	/* There could be a username/password on here */
	if ((chptr = strchr(url, '@'))) {
	    if ((chptr = strchr(url, ':'))) {
		*chptr = '\0';
		ui->login = strdup(url);
		url = chptr + 1;
		
		chptr = strchr(url, '@');
		*chptr = '\0';
		ui->password = strdup(url);
		url = chptr + 1;
	    } else {
		*chptr = '\0';
		ui->login = strdup(url);
		url = chptr + 1;
	    }
	}
    } else if (!strncmp("http://", url, 7)) {
	ui->protocol = URL_METHOD_HTTP;
	url +=7;
    } else {
	logMessage(ERROR, "unknown url protocol '%s'", url);
	return -1;
    }
    
    /* url is left pointing at the hostname */
    chptr = strchr(url, '/');
    if (chptr != NULL) {
        *chptr = '\0';
        ui->address = strdup(url);
        url = chptr;
        *url = '/';
        ui->prefix = strdup(url);
    }
    else {
       ui->address = strdup(url);
       ui->prefix = strdup("/");
    }
    
    logMessage(DEBUGLVL, "url address %s", ui->address);
    logMessage(DEBUGLVL, "url prefix %s", ui->prefix);

    return 0;
}

static char * getLoginName(char * login, struct iurlinfo *ui) {
    int i;

    i = 0;
    /* password w/o login isn't useful */
    if (ui->login && strlen(ui->login)) {
	i += strlen(ui->login) + 5;
	if (strlen(ui->password))
	    i += 3*strlen(ui->password) + 5;

	if (ui->login || ui->password) {
	    login = malloc(i);
	    strcpy(login, ui->login);
	    if (ui->password) {
		char * chptr;
		char code[4];

		strcat(login, ":");
		for (chptr = ui->password; *chptr; chptr++) {
		    sprintf(code, "%%%2x", *chptr);
		    strcat(login, code);
		}
		strcat(login, "@");
	    }
	}
    }

    return login;
}

/* convert a UI to a URL, returns allocated string */
char *convertUIToURL(struct iurlinfo *ui) {
    char * login;
    char * finalPrefix;
    char * url;

    if (!strcmp(ui->prefix, "/"))
	finalPrefix = "/.";
    else
	finalPrefix = ui->prefix;

    login = "";
    login = getLoginName(login, ui);
    
    url = malloc(strlen(finalPrefix) + 25 + strlen(ui->address) + strlen(login));
    sprintf(url, "%s://%s%s/%s", 
	    ui->protocol == URL_METHOD_FTP ? "ftp" : "http",
	    login, ui->address, finalPrefix);

    return url;
}

/* extraHeaders only applicable for http and used for pulling ks from http */
/* see ftp.c:httpGetFileDesc() for details */
/* set to NULL if not needed */
int urlinstStartTransfer(struct iurlinfo * ui, char * filename, 
                         char *extraHeaders) {
    char * buf;
    int fd, port;
    int family = -1;
    char * finalPrefix;
    struct in_addr addr;
    struct in6_addr addr6;
    char *hostname, *portstr;

    if (!strcmp(ui->prefix, "/"))
        finalPrefix = "";
    else
        finalPrefix = ui->prefix;

    buf = alloca(strlen(finalPrefix) + strlen(filename) + 20);
    if (*filename == '/')
        sprintf(buf, "%s%s", finalPrefix, filename);
    else
        sprintf(buf, "%s/%s", finalPrefix, filename);
    
    logMessage(INFO, "transferring %s://%s/%s to a fd",
               ui->protocol == URL_METHOD_FTP ? "ftp" : "http",
               ui->address, buf);

    splitHostname(ui->address, &hostname, &portstr);
    if (portstr == NULL)
        port = -1;
    else
        port = atoi(portstr);

    if (inet_pton(AF_INET, hostname, &addr) >= 1)
        family = AF_INET;
    else if (inet_pton(AF_INET6, hostname, &addr6) >= 1)
        family = AF_INET6;
    else {
        if (mygethostbyname(hostname, &addr, AF_INET) == 0) {
            family = AF_INET;
        } else if (mygethostbyname(hostname, &addr6, AF_INET6) == 0) {
            family = AF_INET6;
        } else {
            logMessage(ERROR, "cannot determine address family of %s",
                       hostname);
        }
    }

    if (ui->protocol == URL_METHOD_FTP) {
        ui->ftpPort = ftpOpen(hostname, family,
                              ui->login ? ui->login : "anonymous", 
                              ui->password ? ui->password : "rhinstall@", 
                              NULL, port);
        if (ui->ftpPort < 0)
            return -2;

        fd = ftpGetFileDesc(ui->ftpPort, addr6, family, buf);
        if (fd < 0) {
            close(ui->ftpPort);
            return -1;
        }
    } else {
        fd = httpGetFileDesc(hostname, port, buf, extraHeaders);
        if (fd < 0)
            return -1;
    }

    if (!FL_CMDLINE(flags))
        winStatus(70, 3, _("Retrieving"), "%s %s...", _("Retrieving"), 
                  filename);

    return fd;
}

int urlinstFinishTransfer(struct iurlinfo * ui, int fd) {
    if (ui->protocol == URL_METHOD_FTP)
        close(ui->ftpPort);
    close(fd);

    if (!FL_CMDLINE(flags))
        newtPopWindow();

    return 0;
}

char * addrToIp(char * hostname) {
    struct in_addr ad;
    struct in6_addr ad6;
    char *ret;

    if ((ret = malloc(48)) == NULL)
        return hostname;

    if (inet_ntop(AF_INET, &ad, ret, INET_ADDRSTRLEN) != NULL)
        return ret;
    else if (inet_ntop(AF_INET6, &ad6, ret, INET6_ADDRSTRLEN) != NULL)
        return ret;
    else if (mygethostbyname(hostname, &ad, AF_INET) == 0)
        return hostname;
    else if (mygethostbyname(hostname, &ad6, AF_INET6) == 0)
        return hostname;
    else
        return NULL;
}

int urlMainSetupPanel(struct iurlinfo * ui, urlprotocol protocol,
                      char * doSecondarySetup) {
    newtComponent form, okay, cancel, siteEntry, dirEntry;
    newtComponent answer, text;
    newtComponent cb = NULL;
    char * site, * dir;
    char * reflowedText = NULL;
    int width, height;
    newtGrid entryGrid, buttons, grid;
    char * chptr;
    char * buf = NULL;

    if (ui->address) {
        site = ui->address;
        dir = ui->prefix;
    } else {
        site = "";
        dir = "";
    }

    if (ui->login || ui->password || ui->proxy || ui->proxyPort)
        *doSecondarySetup = '*';
    else
        *doSecondarySetup = ' ';

    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &cancel, NULL);
    
    switch (protocol) {
    case URL_METHOD_FTP:
        buf = sdupprintf(_(netServerPrompt), _("FTP"), getProductName());
        reflowedText = newtReflowText(buf, 47, 5, 5, &width, &height);
        free(buf);
        break;
    case URL_METHOD_HTTP:
        buf = sdupprintf(_(netServerPrompt), _("Web"), getProductName());
        reflowedText = newtReflowText(buf, 47, 5, 5, &width, &height);
        free(buf);
        break;
    }
    text = newtTextbox(-1, -1, width, height, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(text, reflowedText);
    free(reflowedText);

    siteEntry = newtEntry(22, 8, site, 24, (const char **) &site, 
                          NEWT_ENTRY_SCROLL);
    dirEntry = newtEntry(22, 9, dir, 24, (const char **) &dir, 
                         NEWT_ENTRY_SCROLL);

    entryGrid = newtCreateGrid(2, 2);
    newtGridSetField(entryGrid, 0, 0, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, (protocol == URL_METHOD_FTP) ?
                                        _("FTP site name:") :
                                        _("Web site name:")),
                     0, 0, 1, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(entryGrid, 0, 1, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, 
                               sdupprintf(_("%s directory:"), 
                                          getProductName())),
                     0, 0, 1, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(entryGrid, 1, 0, NEWT_GRID_COMPONENT, siteEntry,
                     0, 0, 0, 0, 0, 0);
    newtGridSetField(entryGrid, 1, 1, NEWT_GRID_COMPONENT, dirEntry,
                     0, 0, 0, 0, 0, 0);

    grid = newtCreateGrid(1, 4);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, entryGrid,
                     0, 0, 0, 1, 0, 0);

    if (protocol == URL_METHOD_FTP) {
        cb = newtCheckbox(3, 11, _("Use non-anonymous ftp"),
                          *doSecondarySetup, NULL, doSecondarySetup);
        newtGridSetField(grid, 0, 2, NEWT_GRID_COMPONENT, cb,
                         0, 0, 0, 1, NEWT_ANCHOR_LEFT, 0);
    }
        
    newtGridSetField(grid, 0, 3, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    newtGridWrappedWindow(grid, (protocol == URL_METHOD_FTP) ? _("FTP Setup") :
                          _("HTTP Setup"));

    form = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, form, 1);    

    do {
        answer = newtRunForm(form);
        if (answer != cancel) {
            if (!strlen(site)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("You must enter a server name."));
                continue;
            }
            if (!strlen(dir)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("You must enter a directory."));
                continue;
            }

            if (!addrToIp(site)) {
                newtWinMessage(_("Unknown Host"), _("OK"),
                        _("%s is not a valid hostname."), site);
                continue;
            }
        }

        break;
    } while (1);
    
    if (answer == cancel) {
        newtFormDestroy(form);
        newtPopWindow();
        
        return LOADER_BACK;
    }

    if (ui->address) free(ui->address);
    ui->address = strdup(site);

    if (ui->prefix) free(ui->prefix);

    /* add a slash at the start of the dir if it is missing */
    if (*dir != '/') {
        if (asprintf(&(ui->prefix), "/%s", dir) == -1)
            ui->prefix = strdup(dir);
    } else {
        ui->prefix = strdup(dir);
    }

    /* Get rid of trailing /'s */
    chptr = ui->prefix + strlen(ui->prefix) - 1;
    while (chptr > ui->prefix && *chptr == '/') chptr--;
    chptr++;
    *chptr = '\0';

    if (*doSecondarySetup != '*') {
        if (ui->login)
            free(ui->login);
        if (ui->password)
            free(ui->password);
        if (ui->proxy)
            free(ui->proxy);
        if (ui->proxyPort)
            free(ui->proxyPort);
        ui->login = ui->password = ui->proxy = ui->proxyPort = NULL;
    }

    ui->protocol = protocol;

    newtFormDestroy(form);
    newtPopWindow();

    return 0;
}

int urlSecondarySetupPanel(struct iurlinfo * ui, urlprotocol protocol) {
    newtComponent form, okay, cancel, answer, text, accountEntry = NULL;
    newtComponent passwordEntry = NULL, proxyEntry = NULL;
    newtComponent proxyPortEntry = NULL;
    char * account, * password, * proxy, * proxyPort;
    newtGrid buttons, entryGrid, grid;
    char * reflowedText = NULL;
    int width, height;

    if (protocol == URL_METHOD_FTP) {
        reflowedText = newtReflowText(
        _("If you are using non anonymous ftp, enter the account name and "
          "password you wish to use below."),
        47, 5, 5, &width, &height);
    } else {
        reflowedText = newtReflowText(
        _("If you are using a HTTP proxy server "
          "enter the name of the HTTP proxy server to use."),
        47, 5, 5, &width, &height);
    }
    text = newtTextbox(-1, -1, width, height, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(text, reflowedText);
    free(reflowedText);

    if (protocol == URL_METHOD_FTP) {
        accountEntry = newtEntry(-1, -1, NULL, 24, (const char **) &account, 
                                 NEWT_FLAG_SCROLL);
        passwordEntry = newtEntry(-1, -1, NULL, 24, (const char **) &password, 
                                  NEWT_FLAG_SCROLL | NEWT_FLAG_PASSWORD);
    }
    proxyEntry = newtEntry(-1, -1, ui->proxy, 24, (const char **) &proxy, 
                           NEWT_ENTRY_SCROLL);
    proxyPortEntry = newtEntry(-1, -1, ui->proxyPort, 6, 
                               (const char **) &proxyPort, NEWT_FLAG_SCROLL);

    entryGrid = newtCreateGrid(2, 4);
    if (protocol == URL_METHOD_FTP) {
        newtGridSetField(entryGrid, 0, 0, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Account name:")),
                     0, 0, 2, 0, NEWT_ANCHOR_LEFT, 0);
        newtGridSetField(entryGrid, 0, 1, NEWT_GRID_COMPONENT,
                     newtLabel(-1, -1, _("Password:")),
                     0, 0, 2, 0, NEWT_ANCHOR_LEFT, 0);
    }
    if (protocol == URL_METHOD_FTP) {
        newtGridSetField(entryGrid, 1, 0, NEWT_GRID_COMPONENT, accountEntry,
                         0, 0, 0, 0, 0, 0);
        newtGridSetField(entryGrid, 1, 1, NEWT_GRID_COMPONENT, passwordEntry,
                         0, 0, 0, 0, 0, 0);
    }

    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &cancel, NULL);

    grid = newtCreateGrid(1, 3);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text, 0, 0, 0, 0, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, entryGrid, 
                     0, 1, 0, 0, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons, 
                     0, 1, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    if (protocol == URL_METHOD_FTP) {
        newtGridWrappedWindow(grid, _("Further FTP Setup"));
    } else {
        if (protocol == URL_METHOD_HTTP)
            newtGridWrappedWindow(grid, _("Further HTTP Setup"));
    }

    form = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, form, 1);
    newtGridFree(grid, 1);

    answer = newtRunForm(form);
    if (answer == cancel) {
        newtFormDestroy(form);
        newtPopWindow();
        
        return LOADER_BACK;
    }
 
    if (protocol == URL_METHOD_FTP) {
        if (ui->login) free(ui->login);
        if (strlen(account))
            ui->login = strdup(account);
        else
            ui->login = NULL;
        
        if (ui->password) free(ui->password);
        if (strlen(password))
            ui->password = strdup(password);
        else
            ui->password = NULL;
    }
    
    newtFormDestroy(form);
    newtPopWindow();

    return 0;
}

/* vim:set shiftwidth=4 softtabstop=4: */
