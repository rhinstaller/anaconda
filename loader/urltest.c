#include <newt.h>

#include "urls.h"

int main(void) {
    struct iurlinfo iu;
    char doSecondary;
    char buf[1024];
    int fd;
    int size;

    newtInit();
    newtCls();

    memset(&iu, 0, sizeof(iu));

    iu.protocol = URL_METHOD_FTP;
    iu.address = "mercury.devel.redhat.com";
    iu.prefix = "/mnt/redhat/test/oot/i386";

    iu.protocol = URL_METHOD_HTTP;
    iu.address = "mercury.devel.redhat.com";
    iu.prefix = "/";

    fd = urlinstStartTransfer(&iu, "test.html");
    if (fd >= 0) {
	size = read(fd, buf, sizeof(buf));
	buf[size] = '\0';
	urlinstFinishTransfer(&iu, fd);

	newtWinMessage("Got it", "Ok", "Got: '%s'", buf);
    }

    newtFinished();
}
