Anaconda Rescue Mode
====================

The rescue mode allows to use Anaconda installation environment for
troubleshooting an installed system. It is able to find and mount existing
installed system so it can be examined and repaired (perhaps in chroot) using
the tools available in the installer environment.


Invoking
--------

- *Troubleshooting* submenu in installation DVD boot menu
- adding ``inst.rescue`` boot option
- using ``rescue`` kickstart command


Configuration of the rescue environment
---------------------------------------

Most of the installer boot options (eg. `ip=`, `inst.updates`)
should be applied to the rescue mode. As for kickstart commands, these commands
should have effect on rescue mode:

- ``network``
- ``iscsi``
- ``driverdisk``
- ``logging``
- ``reboot``, ``shutdown``
- ``updates``


(Semi) automatic system repairs
-------------------------------

Kickstart ``%pre`` and ``%post`` scripts are applied (the latter only if a
system root was successfuly found and mounted) alowing for automatic scripted
modification of the system. If the mode is invoked by ``rescue`` kickstart
command, it won't go interactive but use the command options (``--nomount``,
``--romount``) to decide how to proceed. Only if encrypted devices or multiple
OS installations are found it will ask to choose the OS to be mounted, or for a
passphrase to unlock the device. After running the scripts the system will
reboot or not based on ``reboot`` kickstart command.


Examples of use
---------------

- adding driver using ``inst.dd`` boot option (or ``driverdisk`` kickstart
  command)
- blacklisting a driver with ``modprobe.blacklist`` boot option
- examining and repairing storage using partitioning or lvm tools present in
  the installer image
- repairing or reinstalling the bootloader
- adding or removing software (drivers) via rpm package



