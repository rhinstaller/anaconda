#ifndef H_LOADER_URLS
#define H_LOADER_URLS

enum urlprotocol_t { URL_METHOD_FTP, URL_METHOD_HTTP };
typedef enum urlprotocol_t urlprotocol;

struct iurlinfo {
    urlprotocol protocol;
    char * address;
    char * login;
    char * password;
    char * prefix;
    char * proxy;
    char * proxyPort;
    int ftpPort;
};

int convertURLToUI(char *url, struct iurlinfo *ui);
char *convertUIToURL(struct iurlinfo *ui);

int setupRemote(struct iurlinfo * ui);
int urlMainSetupPanel(struct iurlinfo * ui, urlprotocol protocol,
		      char * doSecondarySetup);
int urlSecondarySetupPanel(struct iurlinfo * ui, urlprotocol protocol);
int urlinstStartTransfer(struct iurlinfo * ui, char * filename, 
                         char *extraHeaders);
int urlinstFinishTransfer(struct iurlinfo * ui, int fd);

#endif
