[H[J

                       [7mRed Hat Rescue Mode[m

The [7mRed Hat[m installation program has undergone changes that will allow 
you to create a custom boot disk for your specific system.  This new boot
disk is customized according to your system's hardware configuration.  This 
will ensure that you will always be able to boot your system, even if LILO
has been overwritten by another operating system.

Your boot disk is the first disk in a two-part rescue disk set.  The second
disk required for rescue mode must be created from the rescue.img image file,
located in the images directory of the [7mRed Hat[m Linux CD.  To create the
second disk, insert a blank floppy in your system's floppy drive, and type
[7mdd if=rescue.img of=/dev/fd0 bs=72k[m.  You may then boot into rescue mode by
booting from your boot disk, and typing [7mrescue[m at the boot prompt.  Insert
the disk created from rescue.img when prompted to do so.


[7m[1-Main] [2-General] [3-Expert] [4-Rescue] [5-Kickstart] [6-Kernel][m
