Installation mount points
=========================

Below you can find mount points that the installer uses during the installation.

Target system
-------------

The root of the target system is mounted under the directories ``/mnt/sysimage`` and
``/mnt/sysroot``.

/mnt/sysimage
^^^^^^^^^^^^^

This is a mount point of the physical root of the target system. It is used to mount a device that
contains ``/`` of the target system.

/mnt/sysroot
^^^^^^^^^^^^

This is a mount point of the system root of the target system. It is used to mount ``/`` of the
target system.

Usually, the physical root and the system root are the same, so ``/mnt/sysroot`` is attached to
the same file system as ``/mnt/sysimage``. The only exceptions are rpm-ostree systems, where the
system root is changing based on the deployment. Then ``/mnt/sysroot`` is attached to a
subdirectory of ``/mnt/sysimage``.

It is recommended to use ``/mnt/sysroot`` for ``chroot``.
