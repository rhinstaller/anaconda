[H[J

                      [7mRed Hat Kickstart Mode[m

[7mRed Hat[m provides a method for unattended installation of a system
using a text configuration file.  To enter the kickstart mode, type
[7mlinux ks <ENTER>[m.   Kickstart mode works with both NFS and CD-ROM 
installations.

The installation program looks in the following places for the config file:
   o   the broadcast server from bootp. 
   o   the bootp server if no other server name is broadcast.
   o   on the boot floppy if [7mlinux ks=floppy <ENTER>[m is given.

The file it looks for is given by the bootp server as either a directory or
an explicit file name.  If a directory is given, then kickstart looks for a
file in that directory with the IP of the client as the file name followed
by "-kickstart" (ie. 192.168.0.1-kickstart).  If the floppy argument is
given, then it will look for a file named "ks" on that floppy.

[7m[1-Main] [2-General] [3-Expert] [4-Rescue] [5-Kickstart] [6-Kernel][m
