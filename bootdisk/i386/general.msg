
                        09General Boot Help07

You are now ready to begin the installation process.  In most cases, 
the best way to get started is to simply press the 0f<ENTER>07 key.

The graphical installer uses the framebuffer in 16-bit color and 800x600 
resolution. If you are having problems with the graphical installer, try 
one of the following options:
    -  Start the installer in 640x480 resolution by typing 0flowres <ENTER>07.
    -  Avoid using framebuffer mode by typing 0fnofb <ENTER>07.
    -  Specify another framebuffer resolution at the boot prompt by appending 
       'vga=xxx' according to one of the following modes:
          1024x768x16bpp -> vga=791   1280x1024x16bpp -> vga=794
          1024x768x24bpp -> vga=792   1280x1024x24bpp -> vga=795

Certain hardware configurations may have trouble with the automatic hardware
detection done during the installation.  If you experience problems during the 
installation, restart the installation using expert mode.  Press 05<F3>07 for more
information on expert mode.

There are a number of parameters that can be passed to the Linux kernel
at boot time.  Press 05<F4>07 for more information. 

05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07
