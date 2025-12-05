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
   :alt: Refresh Fedora and CentOS Stream container images
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/container-autoupdate.yml

.. |try-release-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml/badge.svg
   :alt: Test releasing and translations daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/try-release-daily.yml

.. |release-automatically| image:: https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml/badge.svg
   :alt: Make a Rawhide release automatically
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml

.. |tests-daily| image:: https://github.com/rhinstaller/anaconda/actions/workflows/tests-daily.yml/badge.svg
   :alt: Run unit and RPM tests daily
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/tests-daily.yml

.. |l10n-po-update| image:: https://github.com/rhinstaller/anaconda/actions/workflows/l10n-po-update.yml/badge.svg
   :alt: Update translations
   :target: https://github.com/rhinstaller/anaconda/actions/workflows/l10n-po-update.yml

.. _Dependabot: https://github.com/rhinstaller/anaconda/network/updates

|container-autoupdate|
  Fedora and CentOS Stream CI test container images, built daily. The containers are used in unit and rpm tests.

|try-release-daily|
  Tests the release process daily, including checks for missing important translations.

|release-automatically|
  Makes a Rawhide release automatically with no human oversight for the upstream/non-Fedora part
  of the process.

|tests-daily|
  Runs unit and RPM tests every day, independent of any changes to code or containers.

|l10n-po-update|
  Updates translations weekly, by opening a PR that bumps the pinned hash used to download when building RPMs.

  The PR runs the usual tests, where potential failures caused by translation changes are caught.

Dependabot_
  Checks Anaconda dependencies and opens pull requests for new versions.

Anaconda Web UI
---------------

.. |cockpit-lib-update| image:: https://github.com/rhinstaller/anaconda-webui/actions/workflows/cockpit-lib-update.yml/badge.svg
   :alt: Updates Cockpit library
   :target: https://github.com/rhinstaller/anaconda-webui/actions/workflows/cockpit-lib-update.yml

.. |weblate-sync-po| image:: https://github.com/rhinstaller/anaconda-webui/actions/workflows/weblate-sync-po.yml/badge.svg
   :alt: Sync translations from Weblate repository
   :target: https://github.com/rhinstaller/anaconda-webui/actions/workflows/weblate-sync-po.yml

.. |weblate-sync-pot| image:: https://github.com/rhinstaller/anaconda-webui/actions/workflows/weblate-sync-pot.yml/badge.svg
   :alt: Sync pot (source) files to Weblate repository
   :target: https://github.com/rhinstaller/anaconda-webui/actions/workflows/weblate-sync-pot.yml

.. |test-compose| image:: https://github.com/rhinstaller/anaconda-webui/actions/workflows/test-compose.yml/badge.svg
   :alt: Test Results Integration with Fedora QA Wiki
   :target: https://github.com/rhinstaller/anaconda-webui/actions/workflows/test-compose.yml

|cockpit-lib-update|
  Updates the Cockpit library used by Anaconda Web UI to the latest commit in Cockpit's main branch.

|weblate-sync-po|
  Syncs translation files (``.po``) from Weblate to the repository.

|weblate-sync-pot|
  Syncs source translation definition files (``.pot``) from the repository to Weblate.

|test-compose|
  Runs WebUI tests against latest compose and reports results to Fedora QA Wiki.

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
