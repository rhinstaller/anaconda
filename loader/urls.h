#ifndef H_LOADER_URLS
#define H_LOADER_URLS

enum urlprotocol_t { URL_METHOD_FTP, URL_METHOD_HTTP };
typedef enum urlprotocol_t urlprotocol;

struct iurlinfo {
    char * address;
    char * login;
    char * password;
    char * prefix;
    char * proxy;
    char * proxyPort;
    char * urlprefix;
};

int urlMainSetupPanel(struct iurlinfo * ui, urlprotocol protocol,
		      char * doSecondarySetup);
int urlSecondarySetupPanel(struct iurlinfo * ui, urlprotocol protocol);
FD_t urlinstStartTransfer(struct iurlinfo * ui, char * filename);
int urlinstFinishTransfer(FD_t fd);

#endif
