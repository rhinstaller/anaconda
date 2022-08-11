CI Status
=========

This page shows current status of CI jobs that:

* are scheduled to run repeatedly, instead of started by human actions,
* are expected to be stable and keep succeeding,
* do not display result status on PRs.

The status badges are organized by repository where the github workflow is stored.


Anaconda
--------

.. |container-autoupdate| image:: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate.yml/badge.svg
   :alt: Refresh container images
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate.yml

.. |container-daily-rhel-copr| image:: https://github.com/rhinstaller/anaconda/actions/workflows/daily-rhel-copr.yml/badge.svg
   :alt: Build current anaconda rhel-8 branch in RHEL COPR
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/daily-rhel-copr.yml

.. |try-release-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml/badge.svg
   :alt: Test releasing and translations daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml

.. _Dependabot: https://github.com/rhinstaller/anaconda/network/updates

|container-autoupdate|
  CI test container images, built daily. The containers are used in unit and rpm tests.

  ELN can often fail to build, this is sort of expected.

|container-daily-rhel-copr|
  Daily builds of Anaconda in RHEL 8 COPR (internal).

|try-release-daily|
  Tests the release process daily, including checks for missing important translations

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
