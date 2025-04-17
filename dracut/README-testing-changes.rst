How to test your changes in dracut code
=======================================

You need to know the locations of files and how the filenames change - see explanations in README
as well as module-setup.sh. Understanding update images helps too, this process is very similar.


Creating an overlay image
-------------------------

- Create some directory ``<image-dir>`` and put the files inside with complete paths.
  Add also some "flag" file to tell that the overlay was successfully applied.

- ``chown -R root:root <image-dir>``

- ``cd <image-dir>``

- Create the image file:
  ``find . | cpio -o --format=newc | gzip -9cv > ../<your-overlay-image-file>``
  Note that the format might be a tripping point.

  It's important to put the image outside the directory, otherwise it will be added when you run
  this again.

- You can verify the image contents with `lsinitrd`.

- Copy the image file somewhere the testing system can access it. Next or near to the actual
  `initrd` file is a good idea, so that you don't have to think about the paths. (PXE makes this
  very easy.)


Using your overlay image
------------------------

- Start the testing system, and edit boot options.

- After ``initrd=<something>`` add a space and a path to your
  overlay: ``initrd=<something> <your-overlay-image-file>``.

- Make `dracut` stop so that you can check your changes were applied. Add to the end of boot
  options also: ``rd.break=pre-pivot rd.shell``.

- Confirm the boot command line and wait. During boot, the system will ask you to enter
  emergency shell with ENTER; do so. You should get a shell in `/root`.

- Check that your "flag file" exists and the overlay was applied successfully. If so, you can
  also examine the other files you changed. You also have `journalctl`, `find`, `grep` and some
  other basic tools to examine the system.

- Exit the shell with ``exit`` to let the system continue the whole boot ordeal.

- In the normal installation environment, you can further check that your changes had the desired
  effect.

| **Note**:
| If you need to change just a few files, a new-style ``newc:`` syntax allows you don't bother creating an initrd image yourself:
| https://www.gnu.org/software/grub/manual/grub/html_node/initrd.html
