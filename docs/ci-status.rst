CI Status
=========

This page shows current status of CI jobs that:

* are scheduled to run repeatedly, instead of started by human actions,
* are expected to be stable and keep succeeding,
* do not display result status on PRs.

The status badges are organized by repository where the github workflow is stored.


Anaconda
--------

.. |container-autoupdate-fedora| image:: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate-fedora.yml/badge.svg
   :alt: Refresh Fedora container images
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate-fedora.yml

.. |container-autoupdate-eln| image:: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate-eln.yml/badge.svg
   :alt: Refresh ELN container images
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate-eln.yml

.. |try-release-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml/badge.svg
   :alt: Test releasing and translations daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml

.. |release-automatically| image:: https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml/badge.svg
   :alt: Make a Rawhide release automatically
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml

.. |webui-periodic| image:: https://github.com/rhinstaller/anaconda/actions/workflows/webui-periodic.yml/badge.svg
   :alt: Run WebUI intergration tests daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/webui-periodic.yml

.. |tests-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/tests-daily.yml/badge.svg
   :alt: Run unit and RPM tests daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/tests-daily.yml

.. |cockpit-lib-update| image:: https://github.com/rhinstaller/anaconda/actions/workflows/cockpit-lib-update.yml/badge.svg
   :alt: Updates Cockpit library
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/cockpit-lib-update.yml

.. _Dependabot: https://github.com/rhinstaller/anaconda/network/updates

|container-autoupdate-fedora|
  Fedora CI test container images, built daily. The containers are used in unit and rpm tests.

|container-autoupdate-eln|
  Same as above but for ELN. It is expected this can often fail.

|try-release-daily|
  Tests the release process daily, including checks for missing important translations.

|release-automatically|
  Makes a Rawhide release automatically with no human oversight for the upstream/non-Fedora part
  of the process.

|webui-periodic|
  Runs WebUI integration end-to-end tests every day.

|tests-daily|
  Runs unit and RPM tests every day, independent of any changes to code or containers.

|cockpit-lib-update|
  Updates the COCKPIT_REPO_COMMIT in ui/webui/Makefile.am and opens a pull request.

Dependabot_
  Checks Anaconda dependencies and opens pull requests for new versions.


Kickstart-tests
---------------

.. |ks-container-autoupdate| image:: https://github.com/rhinstaller/kickstart-tests/actions/workflows/container-autoupdate.yml/badge.svg
   :alt: Build and push containers
   :target: https://github.com/rhinstaller/kickstart-tests/actions/workflows/container-autoupdate.yml


.. |daily-boot-iso-rhel8| image:: https://github.com/rhinstaller/kickstart-tests/actions/workflows/daily-boot-iso-rhel8.yml/badge.svg
   :alt: Build and test daily RHEL boot.iso
   :target: https://github.com/rhinstaller/kickstart-tests/actions/workflows/daily-boot-iso-rhel8.yml


.. |daily-boot-iso-rawhide| image:: https://github.com/rhinstaller/kickstart-tests/actions/workflows/daily-boot-iso-rawhide.yml/badge.svg
   :alt: Build daily Rawhide+COPR boot.iso
   :target: https://github.com/rhinstaller/kickstart-tests/actions/workflows/daily-boot-iso-rawhide.yml


.. |scenarios-permian| image:: https://github.com/rhinstaller/kickstart-tests/actions/workflows/scenarios-permian.yml/badge.svg
   :alt: Daily run
   :target: https://github.com/rhinstaller/kickstart-tests/actions/workflows/scenarios-permian.yml

|ks-container-autoupdate|
  CI test container images, built daily. Reused by daily kickstart test runs as well as kickstart tests on PRs.

|daily-boot-iso-rhel8|
  Build RHEL 8 ``boot.iso`` every day.

|daily-boot-iso-rawhide|
  Build Rawhide ``boot.iso`` every day.

|scenarios-permian|
  Daily kickstart test runs. This tries to execute all tests in three scenarios: Rawhide, RHEL 8, and RHEL 9.
  
  Given the volume of kickstart test suite, failures are still numerous.


Anaconda-l10n
-------------

.. |pot-file-update| image:: https://github.com/rhinstaller/anaconda-l10n/actions/workflows/pot-file-update.yaml/badge.svg
   :alt: Automate pot file creation
   :target: https://github.com/rhinstaller/anaconda-l10n/actions/workflows/pot-file-update.yaml

|pot-file-update|
  Update translation definitions (``.pot``, ``msgid``) from the anaconda repository.
  Weblate automatically picks up the results from the repo.
