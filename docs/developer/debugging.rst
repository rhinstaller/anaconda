Remote Debugging with debugpy
==============================

This guide explains how to use debugpy for remote debugging of Anaconda during installation.

Setup
-----

.. note::
   The debugpy package is not included in Anaconda installation images by default.
   You must download it from COPR and include it in an updates.img to enable remote debugging.

1. Download debugpy from COPR
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, fetch the debugpy package from the rhinstaller/devutils COPR repository:

.. code-block:: bash

   ./scripts/fetch_rpm_from_copr @rhinstaller/devutils python3-debugpy

This downloads the package into ``cache/rpms/`` for inclusion in updates.img.

2. Create boot.iso with debugpy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   ./scripts/testing/update_iso -a cache/rpms/python3-debugpy-1.8.20-*.rpm

This creates a new boot.iso with debugpy included, ready for installation.

.. note::
   Alternatively, you can create an ``updates.img`` with the package included,
   or use the ``rebuild_iso`` script instead of ``update_iso``.

3. Launch VM with debugpy enabled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the boot.iso created in step 2 to launch the VM.

.. note::
   The examples below use rootless VMs with passt networking for port forwarding.
   The ``portForward`` parameter maps host ports directly to the same ports in the VM,
   allowing connection via ``localhost`` in your IDE's launch.json.

   If you run the VM differently (e.g., with standard bridged networking), you'll need
   to connect to the VM's IP address instead of ``localhost`` in your launch.json
   configuration.

**Option A: Debug all modules (auto-discover)**

.. code-block:: bash

   virt-install \
     --noautoconsole \
     --graphics=vnc \
     --memory 4000 \
     --network passt,portForward=50000-50100 \
     --extra-arg inst.remote-debugger=all:50000-50100 \
     --extra-arg inst.lang=en_US \
     --location path/to/anaconda/result/iso/boot-updated.iso,kernel=images/pxeboot/vmlinuz,initrd=images/pxeboot/initrd.img \
     --name debugpy

With ``all:50000-50100``, anaconda gets port 50000 and modules are assigned sequentially in alphabetical order (Boss: 50001, Localization: 50002, Network: 50003, etc.).

**Option B: Debug specific modules only**

.. code-block:: bash

   virt-install \
     --noautoconsole \
     --graphics=vnc \
     --memory 4000 \
     --network passt,portForward0=50000:50000,portForward1=50002:50002,portForward2=50010:50010 \
     --extra-arg inst.remote-debugger=anaconda:50000 \
     --extra-arg inst.remote-debugger=pyanaconda.modules.boss:50002 \
     --extra-arg inst.remote-debugger=pyanaconda.modules.subscription:50010 \
     --extra-arg inst.lang=en_US \
     --location path/to/anaconda/result/iso/boot-updated.iso,kernel=images/pxeboot/vmlinuz,initrd=images/pxeboot/initrd.img \
     --name debugpy

.. note::
   Cannot mix ``all:`` with specific module configurations. Use one or the other.

4. Connect from your IDE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While these instructions focus on VS Code, debugpy can be used with other IDEs that implement the Debug Adapter Protocol (DAP), such as Vim, Neovim, and others. The connection parameters (host and port) remain the same regardless of the client. A list of known supported IDEs and extensions is maintained at https://microsoft.github.io/debug-adapter-protocol/implementors/tools/.

In VS Code, Press **F5** to attach. Each process starts with ``wait_for_client=True``, so you'll need to reconnect as new modules initialize (main entrypoint first, then Boss, Localization, Network, Storage, etc.).

Example launch.json
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "main entrypoint",
         "type": "debugpy",
         "request": "attach",
         "connect": {"host": "localhost", "port": 50000},
         "justMyCode": false,
         "pathMappings": [
           {"localRoot": "${workspaceFolder}/anaconda.py", "remoteRoot": "/usr/bin/anaconda"},
           {"localRoot": "${workspaceFolder}/pyanaconda", "remoteRoot": "${env:PYTHON_SITE_PACKAGES}/pyanaconda"}
         ]
       },
       {
         "name": "Boss Module",
         "type": "debugpy",
         "request": "attach",
         "connect": {"host": "localhost", "port": 50002},
         "justMyCode": false,
         "pathMappings": [
           {"localRoot": "${workspaceFolder}/anaconda.py", "remoteRoot": "/usr/bin/anaconda"},
           {"localRoot": "${workspaceFolder}/pyanaconda", "remoteRoot": "${env:PYTHON_SITE_PACKAGES}/pyanaconda"}
         ]
       }
     ],
     "compounds": [
       {
         "name": "Debug Anaconda VM",
         "configurations": ["main entrypoint", "Boss Module"],
         "stopAll": true
       }
     ]
   }

.. note::
   Repeat the configuration pattern for other modules: Localization (50002), Network (50003), Payloads (50004), etc.

.. note::
   Set ``PYTHON_SITE_PACKAGES`` in your devcontainer Dockerfile or environment for ``${env:PYTHON_SITE_PACKAGES}`` to resolve correctly.

   To find the correct path, run:

   .. code-block:: bash

      rpm --eval %{python3_sitearch}
