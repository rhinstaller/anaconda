#include <arpa/inet.h>
#include <ctype.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <rpmio.h>
#include <rpmlib.h>
#include <rpmurl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "isys/dns.h"

#include "lang.h"
#include "loader.h"
#include "urls.h"
#include "log.h"
#include "rpmmacro.h"

static const char * urlfilter(const char * u)
{
    int i = 0;
    static char buf[256];

    memset(&buf, 0, sizeof(buf));
    
    if (u == NULL)
	return u;
    
    while (*u && *u != '/') {
	buf[i++] = *u;
	u++;
    }
    while (*u && *u != ':') {
	buf[i++] = *u;
	u++;
    }
    if (*u) {
	buf[i] = 0;
	strcat(buf, ":[PASSWORD]");
	i += 11;
	while (*u && *u != '@') {
	    u++;
	}
    }
    while (*u) {
	buf[i++] = *u;
	u++;
    }
    return buf;
}

FD_t urlinstStartTransfer(struct iurlinfo * ui, char * filename) {
    char * buf;
    newtComponent form;
    FD_t fd;
    
    logMessage("transferring %s/RedHat/%s to a fd", urlfilter(ui->urlprefix),
	       filename);
    
    newtCenteredWindow(70, 3, _("Retrieving"));

    buf = alloca(strlen(ui->urlprefix) + strlen(filename) + 30);
    sprintf(buf, "%s %s...", _("Retrieving"), filename);
    form = newtForm(NULL, NULL, 0);
    newtFormAddComponent(form, newtLabel(1, 1, buf));

    newtDrawForm(form);
    newtRefresh();

    strcpy(buf, ui->urlprefix);
    strcat(buf, "/RedHat/");
    strcat(buf, filename);
    fd = ufdOpen(buf, O_RDONLY, 600);

    return fd;
}

int urlinstFinishTransfer(FD_t fd) {
    newtPopWindow();

    return 0;
}

char * addrToIp(char * hostname) {
    struct in_addr ad;
    char * chptr;

    for (chptr = hostname; *chptr; chptr++)
	if (!(isdigit(*chptr) || *chptr == '.')) break;

    if (!*chptr)
	return hostname;

    if (mygethostbyname(hostname, &ad))
	return NULL;

    return inet_ntoa(ad);
}

int urlMainSetupPanel(struct iurlinfo * ui, urlprotocol protocol,
		      char * doSecondarySetup) {
    newtComponent form, okay, cancel, siteEntry, dirEntry;
    newtComponent answer, text, cb = NULL;
    char * site, * dir;
    char * reflowedText = NULL;
    int width, height;
    newtGrid entryGrid, buttons, grid;

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

    buttons = newtButtonBar(_("Ok"), &okay, _("Back"), &cancel, NULL);
    
    switch (protocol) {
    case URL_METHOD_FTP:
	reflowedText = newtReflowText(
            _("Please enter the following information:\n"
	      "\n"
	      "    o the name or IP number of your FTP server\n" 
	      "    o the directory on that server containing\n" 
	      "      Red Hat Linux for your architecure\n"),
	    47, 5, 5, &width, &height);
	break;
    case URL_METHOD_HTTP:
	reflowedText = newtReflowText(
            _("Please enter the following information:\n"
	      "\n"
	      "    o the name or IP number of your web server\n" 
	      "    o the directory on that server containing\n" 
	      "      Red Hat Linux for your architecure\n"), 
	    47, 5, 5, &width, &height);
	break;
    }
    text = newtTextbox(-1, -1, width, height, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(text, reflowedText);
    free(reflowedText);

    siteEntry = newtEntry(22, 8, site, 24, &site, NEWT_ENTRY_SCROLL);
    dirEntry = newtEntry(22, 9, dir, 24, &dir, NEWT_ENTRY_SCROLL);

    entryGrid = newtCreateGrid(2, 2);
    newtGridSetField(entryGrid, 0, 0, NEWT_GRID_COMPONENT,
		     newtLabel(-1, -1, (protocol == URL_METHOD_FTP) ?
			                _("FTP site name:") :
			                _("Web site name:")),
		     0, 0, 1, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(entryGrid, 0, 1, NEWT_GRID_COMPONENT,
		     newtLabel(-1, -1, _("Red Hat directory:")),
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

#ifdef NO_PROXY
    switch (protocol) {
    case URL_METHOD_FTP:
	cb = newtCheckbox(3, 11, _("Use non-anonymous ftp or a proxy server"),
			  *doSecondarySetup, NULL, doSecondarySetup);
	break;
    case URL_METHOD_HTTP:
	cb = newtCheckbox(3, 11, _("Use proxy server"),
			  *doSecondarySetup, NULL, doSecondarySetup);
    }

    newtGridSetField(grid, 0, 2, NEWT_GRID_COMPONENT, cb,
		     0, 0, 0, 1, NEWT_ANCHOR_LEFT, 0);
#endif
	
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
		newtWinMessage(_("Error"), _("Ok"),
			       _("You must enter a server name."));
		continue;
	    }
	    if (!strlen(dir)) {
		newtWinMessage(_("Error"), _("Ok"),
			       _("You must enter a directory."));
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
    ui->prefix = strdup(dir);

    if (ui->urlprefix) free(ui->urlprefix);
    ui->urlprefix = malloc(sizeof(char) * (strlen(ui->address) +
					  strlen(ui->prefix) + 10));

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
	delMacro(NULL, "_httpproxy");
	delMacro(NULL, "_ftpproxy");
	delMacro(NULL, "_httpproxyport");
	delMacro(NULL, "_ftpproxyport");
    }

    sprintf(ui->urlprefix, "%s://%s/%s",
	    protocol == URL_METHOD_FTP ? "ftp" : "http",
	    addrToIp(ui->address), ui->prefix);

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
	  "password you wish to use below. If you are using an FTP proxy "
	  "enter the name of the FTP proxy server to use."),
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
	accountEntry = newtEntry(-1, -1, NULL, 24, &account, 
				 NEWT_ENTRY_SCROLL);
	passwordEntry = newtEntry(-1, -1, NULL, 24, &password, 
				  NEWT_ENTRY_SCROLL | NEWT_ENTRY_HIDDEN);
    }
    proxyEntry = newtEntry(-1, -1, ui->proxy, 24, &proxy, NEWT_ENTRY_SCROLL);
    proxyPortEntry = newtEntry(-1, -1, ui->proxyPort, 6, &proxyPort,
			       NEWT_ENTRY_SCROLL);

    entryGrid = newtCreateGrid(2, 4);
    if (protocol == URL_METHOD_FTP) {
	newtGridSetField(entryGrid, 0, 0, NEWT_GRID_COMPONENT,
		     newtLabel(-1, -1, _("Account name:")),
		     0, 0, 2, 0, NEWT_ANCHOR_LEFT, 0);
	newtGridSetField(entryGrid, 0, 1, NEWT_GRID_COMPONENT,
		     newtLabel(-1, -1, _("Password:")),
		     0, 0, 2, 0, NEWT_ANCHOR_LEFT, 0);
    }
    newtGridSetField(entryGrid, 0, 2, NEWT_GRID_COMPONENT,
		     protocol == URL_METHOD_FTP ?
		                 newtLabel(-1, -1, _("FTP Proxy:")) :
		                 newtLabel(-1, -1, _("HTTP Proxy:")),
		     0, 1, 1, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(entryGrid, 0, 3, NEWT_GRID_COMPONENT,
		     protocol == URL_METHOD_FTP ?
		                 newtLabel(-1, -1, _("FTP Proxy Port:")) :
		                 newtLabel(-1, -1, _("HTTP Proxy Port:")),
		     0, 0, 1, 0, NEWT_ANCHOR_LEFT, 0);
    if (protocol == URL_METHOD_FTP) {
	newtGridSetField(entryGrid, 1, 0, NEWT_GRID_COMPONENT, accountEntry,
			 0, 0, 0, 0, 0, 0);
	newtGridSetField(entryGrid, 1, 1, NEWT_GRID_COMPONENT, passwordEntry,
			 0, 0, 0, 0, 0, 0);
    }
    newtGridSetField(entryGrid, 1, 2, NEWT_GRID_COMPONENT, proxyEntry,
		     0, 1, 0, 0, 0, 0);
    newtGridSetField(entryGrid, 1, 3, NEWT_GRID_COMPONENT, proxyPortEntry,
		     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);

    buttons = newtButtonBar(_("Ok"), &okay, _("Back"), &cancel, NULL);

    grid = newtCreateGrid(1, 3);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text, 0, 0, 0, 0, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_SUBGRID, entryGrid, 
		     0, 1, 0, 0, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons, 
		     0, 1, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    
    
    if (protocol == URL_METHOD_FTP) {
	newtGridWrappedWindow(grid, "Further FTP Setup");
    } else {
	if (protocol == URL_METHOD_HTTP)
	    newtGridWrappedWindow(grid, "Further HTTP Setup");
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
    
    if (ui->proxy) free(ui->proxy);
    if (strlen(proxy)) {
	ui->proxy = strdup(proxy);
	if (protocol == URL_METHOD_FTP)
	    addMacro(NULL, "_ftpproxy", NULL, ui->proxy, RMIL_RPMRC);
	else
	    addMacro(NULL, "_httproxy", NULL, ui->proxy, RMIL_RPMRC);
    } else
	ui->proxy = NULL;
    
    if (ui->proxyPort) free(ui->proxyPort);
    if (strlen(proxy)) {
	ui->proxyPort = strdup(proxyPort);
	if (protocol == URL_METHOD_FTP)
	    addMacro(NULL, "_ftpproxyport", NULL,
		     ui->proxyPort, RMIL_RPMRC);
	else
	    addMacro(NULL, "_httpproxyport", NULL,
		     ui->proxyPort, RMIL_RPMRC);
    } else
	ui->proxyPort = NULL;

    if (ui->urlprefix) free(ui->urlprefix);
    ui->urlprefix = malloc(sizeof(char) * (strlen(ui->address) +
		   strlen(ui->prefix) +
			   (ui->login ? strlen(ui->login) : 0) +
			   (ui->password ? strlen(ui->password) : 0) + 15));
					   
    sprintf(ui->urlprefix, "%s://%s%s%s%s%s/%s",
	    protocol == URL_METHOD_FTP ? "ftp" : "http",
	    ui->login ? ui->login : "",
	    ui->password ? ":" : "",
	    ui->password ? ui->password : "",
	    ui->login ? "@" : "",
	    ui->address, ui->prefix);

    newtFormDestroy(form);
    newtPopWindow();

    return 0;
}
