#define	LOGTO_C
#include	<stdio.h>
#include	<limits.h>
#include	<sys/stat.h>
#include	<sys/socket.h>

#include	<interface.h>

void	main(argc, argv)
int	argc;
char	*argv[];
{
	int	s, len;
	char	name[_POSIX_PATH_MAX], path[_POSIX_PATH_MAX];

	if ((s = SocketClientOpen()) == -1) {
		fprintf(stderr, "%s> connect fail.\n", argv[0]);
		exit(EOF);
	}
	if (argc < 2) {
		len = 0;
	} else {
		getcwd(path, _POSIX_PATH_MAX);
		sprintf(name, "%s/%s", path, argv[1]);
		len = strlen(name) + 1;
	}
	SocketSendStr(s, STR_LOGTO);
	if (SocketRecCtrl(s) != CHR_ACK) {
		fprintf(stderr, "%s> no answer.\n", argv[0]);
		exit(EOF);
	}
	if (SocketSendData((void *)&len, sizeof(int), s) == EOF) {
		fprintf(stderr, "%s> data length send error.\n", argv[0]);
		exit(EOF);
	}
	if (SocketSendData(name, len, s) == EOF) {
		fprintf(stderr, "%s> data send error.\n", argv[0]);
		exit(EOF);
	}
}
