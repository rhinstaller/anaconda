#include <newt.h>

#include "urls.h"

int haveKon = 0;
int continuing = 0;

void stopNewt(void) {
}

int main(void) {
    struct iurlinfo iu;
    char doSecondary;
    int fd;
    int size;
    int total = 0;
    char buf[16384];


    newtInit();
    newtCls();

    memset(&iu, 0, sizeof(iu));

    iu.protocol = URL_METHOD_HTTP;
    iu.address = "localhost";
    iu.prefix = "/";

    iu.protocol = URL_METHOD_FTP;
    iu.address = "localhost";
    iu.prefix = "/pub/oot/i386";

    fd = urlinstStartTransfer(&iu, "RedHat/base/netstg1.img", 1);
    if (fd >= 0) {
	while ((size = read(fd, buf, sizeof(buf))) > 0)
	    total += size;
	urlinstFinishTransfer(&iu, fd);

	newtWinMessage("Got it", "OK", "Got: %d bytes\n", total);
    } else {
	newtWinMessage("Failed", "OK", ":-(");
    }

    newtFinished();
}
