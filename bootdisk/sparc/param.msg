[H[J

                        [7mKernel Parameter Help[m

Some kernel parameters can be specified on the command line and will be
passed to the running kernel.  This does not include options to modules
such as ethernet cards or devices such as CD-ROM drives.

To pass an option to the kernel, use the following format:
     [7mlinux <options>[m
If a different installation mode is desired, enter it after the option(s).

For example, to install on a system with 128MB of RAM using expert mode, 
type the following:
     [7mlinux mem=128M expert[m

To pass options to modules, you will need to use the expert mode to disable
PCI and SBUS autoprobing.  When the installation asks for your device type
that needs an option or parameter passed to it, there will be a place to
type those in at that time. 



[7m[1-Main] [2-General] [3-Expert] [4-Rescue] [5-Kickstart] [6-Kernel][m
