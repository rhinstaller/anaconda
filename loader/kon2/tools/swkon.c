#include	<stdio.h>
#include	<stdlib.h>
#include	<unistd.h>
#include	<errno.h>
#include	<string.h>
#include	<ctype.h>
#include	<sys/stat.h>
#include	<sys/socket.h>
#include	<signal.h>

#include	<interface.h>

const char	*progName;

int	OpenSocket(void)
{
	int	s;

	if ((s = SocketClientOpen()) == -1) {
		fprintf(stderr, "%s> connect fail.\n", progName);
		exit(EXIT_FAILURE);
	}
	return s;
}

int	WaitAck(int s)
{
	struct messageHeader mh;
	bzero(&mh, sizeof(mh));
	SocketRecCommand(s, &mh);
	if (mh.cmd != CHR_ACK) {
		fprintf(stderr, "%s> no answer.\n", progName);
		return EXIT_FAILURE;
	}
	return EXIT_SUCCESS;
}

int	ChangeMode(char	cmd)
{
	int	s = OpenSocket();
	SocketSendCommand(s, cmd);
	return WaitAck(s);
}

int	ResetKon(int argc, const char *argv[])
{
	int	s = OpenSocket();
	int	i, len;

	SocketSendCommand(s, CHR_RESTART);
	if (WaitAck(s) != EXIT_SUCCESS)
		return EXIT_FAILURE;
	write(s, &argc, sizeof(argc));
	for (i = 0; i < argc; i++) {
		len = strlen(argv[i]);
		write(s, &len, sizeof(len));
		write(s, argv[i], len);
	}
	return EXIT_SUCCESS;
}

void	usage(void)
{
	fprintf(stderr, "usage:\n"
		"	%s -h|-help	(print this help)\n"
		"	%s -t		(switch to text mode)\n"
		"	%s -g		(switch to graphics mode)\n"
		"	%s [video] [-capability value ...]	(reset KON)\n",
		progName, progName, progName, progName);
}

int	main(int argc, const char *argv[])
{
	progName = argv[0];

	if (argc == 2) {
		if (strcasecmp(argv[1], "-h") == 0 || strcasecmp(argv[1], "-help") == 0) {
			usage();
			return EXIT_SUCCESS;
		} else if (strcasecmp(argv[1], "-t") == 0)
			return ChangeMode(CHR_TEXTMODE);
		else if (strcasecmp(argv[1], "-g") == 0)
			return ChangeMode(CHR_GRAPHMODE);
		else if (strcasecmp(argv[1], "-s") == 0)
			return ChangeMode(CHR_STAT);
	}
	return ResetKon(argc - 1, argv + 1);
}
