CI Status
=========

This page shows current status of CI jobs that are expected to be stable.


Anaconda
--------

.. |container-autoupdate| image:: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate.yml/badge.svg
   :alt: Refresh container images
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate.yml

.. |container-daily-rhel-copr| image:: https://github.com/rhinstaller/anaconda/actions/workflows/daily-rhel-copr.yml/badge.svg
   :alt: Build current anaconda rhel-8 branch in RHEL COPR
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/daily-rhel-copr.yml

.. |tag-release| image:: https://github.com/rhinstaller/anaconda/actions/workflows/tag-release.yml/badge.svg
   :alt: Release from tags
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/tag-release.yml

.. |try-release-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml/badge.svg
   :alt: Test releasing and translations daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml

.. _releases: https://github.com/rhinstaller/anaconda/releases

|container-autoupdate|
  CI test container images, built daily. The containers are used in unit and rpm tests.

  ELN can often fail to build, this is sort of expected.

|container-daily-rhel-copr|
  Daily builds of Anaconda in RHEL 8 COPR (internal).

|tag-release|
  Creates releases_ built automatically from tagged Anaconda versions for Fedora.

|try-release-daily|
  Tests the release process daily, including checks for missing important translations

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


.. |scenarios| image:: https://github.com/rhinstaller/kickstart-tests/actions/workflows/scenarios.yml/badge.svg
   :alt: Daily run
   :target: https://github.com/rhinstaller/kickstart-tests/actions/workflows/scenarios.yml

|ks-container-autoupdate|
  CI test container images, built daily. Reused by daily kickstart test runs as well as kickstart tests on PRs.

|daily-boot-iso-rhel8|
  Build RHEL 8 ``boot.iso`` every day.

|daily-boot-iso-rawhide|
  Build Rawhide ``boot.iso`` every day.

|scenarios|
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
