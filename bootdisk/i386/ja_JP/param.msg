

                        09Kernel Parameter Help07

Some kernel parameters can be specified on the command line and will be
passed to the running kernel.  This does not include options to modules
such as ethernet cards or devices such as CD-ROM drives.

To pass an option to the kernel, use the following format:
     0flinux <options>07
If a different installation mode is desired, enter it after the option(s).

For example, to install on a system with 128MB of RAM using expert mode, 
type the following:
     0flinux mem=128M expert07

To pass options to modules, you will need to use the expert mode to disable
PCI autoprobing.  When the installation asks for your device type that needs
an option or parameter passed to it, there will be a place to type those
in at that time. 



05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07
