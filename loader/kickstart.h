#ifndef H_KICKSTART

#define KS_CMD_NONE	0
#define KS_CMD_NFS	1
#define KS_CMD_CDROM	2
#define KS_CMD_HD	3
#define KS_CMD_URL	4
#define KS_CMD_NETWORK	5
#define KS_CMD_DEVICE	6
#define KS_CMD_XDISPLAY	7

int ksReadCommands(char * cmdFile);
int ksGetCommand(int cmd, char ** last, int * argc, char *** argv);
int ksHasCommand(int cmd);

#endif
