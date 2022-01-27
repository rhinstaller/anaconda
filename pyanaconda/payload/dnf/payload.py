# DNF/rpm software payload management.
#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import dnf.exceptions
import dnf.repo

from glob import glob

from pyanaconda.modules.common.errors.installation import NonCriticalInstallationError, \
    InstallationError
from pyanaconda.modules.common.errors.payload import UnknownRepositoryError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.payloads.kickstart import convert_ks_repo_to_repo_data
from pyanaconda.modules.payloads.payload.dnf.initialization import configure_dnf_logging
from pyanaconda.modules.payloads.payload.dnf.installation import ImportRPMKeysTask, \
    SetRPMMacrosTask, DownloadPackagesTask, InstallPackagesTask, PrepareDownloadLocationTask, \
    CleanUpDownloadLocationTask, ResolvePackagesTask, UpdateDNFConfigurationTask
from pyanaconda.modules.payloads.payload.dnf.utils import get_kernel_version_list, \
    calculate_required_space
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager, DNFManagerError
from pyanaconda.payload.source import SourceFactory, PayloadSourceTypeUnrecognized

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import constants, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE, ISO_DIR, PAYLOAD_TYPE_DNF, \
    SOURCE_TYPE_URL, SOURCE_TYPE_CDROM, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK, SOURCE_REPO_FILE_TYPES, SOURCE_TYPE_CDN, MULTILIB_POLICY_ALL
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.flags import flags
from pyanaconda.kickstart import RepoData
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.payloads.source.utils import has_network_protocol
from pyanaconda.modules.common.errors.storage import DeviceSetupError, MountFilesystemError
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.errors import PayloadError, PayloadSetupError
from pyanaconda.payload.image import find_first_iso_image, find_optical_install_media
from pyanaconda.modules.payloads.payload.dnf.tree_info import TreeInfoMetadata, NoTreeInfoError, \
    TreeInfoMetadataError
from pyanaconda.ui.lib.payload import get_payload, get_source, create_source, set_source, \
    set_up_sources, tear_down_sources

__all__ = ["DNFPayload"]

YUM_REPOS_DIR = "/etc/yum.repos.d/"

log = get_packaging_logger()


class DNFPayload(Payload):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A list of verbose error strings
        self.verbose_errors = []

        # Get a DBus payload to use.
        self._payload_proxy = get_payload(self.type)

        self.tx_id = None

        self._dnf_manager = DNFManager()
        self._updates_enabled = True

        # Configure the DNF logging.
        configure_dnf_logging()

        # FIXME: Don't call this method before set_from_opts.
        # This will create a default source if there is none.
        self._configure()

    @property
    def dnf_manager(self):
        """The DNF manager."""
        return self._dnf_manager

    @property
    def _base(self):
        """Return a DNF base.

        FIXME: This is a temporary property.
        """
        return self._dnf_manager._base

    @property
    def _repos_lock(self):
        """A lock for a dictionary of DNF repositories.

        FIXME: This is a temporary property.
        """
        return self._dnf_manager._lock

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        # Set the source based on opts.method if it isn't already set
        # - opts.method is currently set by command line/boot options
        if opts.method and (not self.proxy.Sources or self._is_source_default()):
            try:
                source = SourceFactory.parse_repo_cmdline_string(opts.method)
            except PayloadSourceTypeUnrecognized:
                log.error("Unknown method: %s", opts.method)
            else:
                source_proxy = source.create_proxy()
                set_source(self.proxy, source_proxy)

        # Set up the current source.
        source_proxy = self.get_source_proxy()

        if source_proxy.Type == SOURCE_TYPE_URL:
            # Get the repo configuration.
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.RepoConfiguration
            )

            if opts.proxy:
                repo_configuration.proxy = opts.proxy

            if not conf.payload.verify_ssl:
                repo_configuration.ssl_verification_enabled = conf.payload.verify_ssl

            # Update the repo configuration.
            source_proxy.SetRepoConfiguration(
                RepoConfigurationData.to_structure(repo_configuration)
            )

        # Set up packages.
        if opts.multiLib:
            configuration = self.get_packages_configuration()
            configuration.multilib_policy = MULTILIB_POLICY_ALL
            self.set_packages_configuration(configuration)

        # Reset all the other things now that we have new configuration.
        self._configure()

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_DNF

    def get_source_proxy(self):
        """Get the DBus proxy of the RPM source.

        The default source for the DNF payload is set via
        the default_source option in the payload section
        of the Anaconda config file.

        :return: a DBus proxy
        """
        return get_source(self.proxy, conf.payload.default_source)

    @property
    def source_type(self):
        """The DBus type of the source."""
        source_proxy = self.get_source_proxy()
        return source_proxy.Type

    def get_packages_configuration(self) -> PackagesConfigurationData:
        """Get the DBus data with the packages configuration."""
        return PackagesConfigurationData.from_structure(
            self.proxy.PackagesConfiguration
        )

    def set_packages_configuration(self, data: PackagesConfigurationData):
        """Set the DBus data with the packages configuration."""
        return self.proxy.SetPackagesConfiguration(
            PackagesConfigurationData.to_structure(data)
        )

    def get_packages_selection(self) -> PackagesSelectionData:
        """Get the DBus data with the packages selection."""
        return PackagesSelectionData.from_structure(
            self.proxy.PackagesSelection
        )

    def set_packages_selection(self, data: PackagesSelectionData):
        """Set the DBus data with the packages selection."""
        return self.proxy.SetPackagesSelection(
            PackagesSelectionData.to_structure(data)
        )

    def is_ready(self):
        """Is the payload ready?"""
        enabled_repos = self._dnf_manager.enabled_repositories

        # If CDN is used as the installation source and we have
        # a subscription attached then any of the enabled repos
        # should be fine as the base repo.
        # If CDN is used but subscription has not been attached
        # there will be no redhat.repo file to parse and we
        # don't need to do anything.
        if self.source_type == SOURCE_TYPE_CDN:
            return self._is_cdn_set_up() and enabled_repos

        # Otherwise, a base repository has to be enabled.
        return any(map(self._is_base_repo, enabled_repos))

    def _is_cdn_set_up(self):
        """Is the CDN source set up?"""
        if not self.source_type == SOURCE_TYPE_CDN:
            return False

        if not is_module_available(SUBSCRIPTION):
            return False

        subscription_proxy = SUBSCRIPTION.get_proxy()
        return subscription_proxy.IsSubscriptionAttached

    def _is_base_repo(self, repo_id):
        """Is it a base repository?"""
        return repo_id == constants.BASE_REPO_NAME \
            or repo_id in constants.DEFAULT_REPOS

    def is_complete(self):
        """Is the payload complete?"""
        return self.source_type not in SOURCE_REPO_FILE_TYPES or self.is_ready()

    def setup(self):
        self.verbose_errors = []

    def unsetup(self):
        self._configure()
        tear_down_sources(self.proxy)

    @property
    def needs_network(self):
        """Test base and additional repositories if they require network."""
        return (self.service_proxy.IsNetworkRequired() or
                any(self._repo_needs_network(repo) for repo in self.data.repo.dataList()))

    def _repo_needs_network(self, repo):
        """Returns True if the ksdata repo requires networking."""
        urls = [repo.baseurl]
        if repo.mirrorlist:
            urls.extend(repo.mirrorlist)
        elif repo.metalink:
            urls.extend(repo.metalink)
        return self._source_needs_network(urls)

    def _source_needs_network(self, sources):
        """Return True if the source requires network.

        :param sources: Source paths for testing
        :type sources: list
        :returns: True if any source requires network
        """
        for s in sources:
            if has_network_protocol(s):
                log.debug("Source %s needs network for installation", s)
                return True

        log.debug("Source doesn't require network for installation")
        return False

    def bump_tx_id(self):
        if self.tx_id is None:
            self.tx_id = 1
        else:
            self.tx_id += 1
        return self.tx_id

    def _get_proxy_url(self):
        """Get a proxy of the current source.

        :return: a proxy or None
        """
        source_proxy = self.get_source_proxy()
        source_type = source_proxy.Type

        if source_type != SOURCE_TYPE_URL:
            return None

        data = RepoConfigurationData.from_structure(
            source_proxy.RepoConfiguration
        )

        return data.proxy

    def _configure(self):
        self._dnf_manager.reset_base()
        self._dnf_manager.configure_base(self.get_packages_configuration())
        self._dnf_manager.configure_proxy(self._get_proxy_url())
        self._dnf_manager.dump_configuration()

    def _sync_metadata(self, dnf_repo):
        try:
            dnf_repo.load()
        except dnf.exceptions.RepoError as e:
            id_ = dnf_repo.id
            log.info('_sync_metadata: addon repo error: %s', e)
            self._set_repo_enabled(id_, False)
            self.verbose_errors.append(str(e))
        log.debug('repo %s: _sync_metadata success from %s', dnf_repo.id,
                  dnf_repo.baseurl or dnf_repo.mirrorlist or dnf_repo.metalink)

    ###
    # METHODS FOR WORKING WITH REPOSITORIES
    ###

    def get_addon_repo(self, repo_id):
        """Return a ksdata Repo instance matching the specified repo id."""
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def _add_repo_to_dnf_and_ks(self, ksrepo):
        """Add an enabled repo to dnf and kickstart repo lists.

        Add the repo given by the pykickstart Repo object ksrepo to the
        system.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        if ksrepo.enabled:
            self._add_repo_to_dnf(ksrepo)
            self._dnf_manager.load_repository(ksrepo.name)

        # Add the repo to the ksdata so it'll appear in the output ks file.
        self.data.repo.dataList().append(ksrepo)

    def _add_repo_to_dnf(self, ksrepo):
        """Add a repo to the dnf repo object.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        data = convert_ks_repo_to_repo_data(ksrepo)
        enabled = ksrepo.enabled

        # An existing repository can be only enabled or disabled.
        if self._is_existing_repo_configuration(data):
            self._dnf_manager.set_repository_enabled(data.name, enabled)
            return

        # Set up the NFS source with a substituted URL.
        if data.url.startswith("nfs://"):
            url = self._dnf_manager.substitute(data.url)
            (server, path) = url[6:].split(":", 1)
            mountpoint = "%s/%s.nfs" % (constants.MOUNT_DIR, data.name)
            self._setup_NFS(mountpoint, server, path, None)
            data.url = "file://" + mountpoint

        # Add a new repository.
        self._dnf_manager.add_repository(data)

    def _is_existing_repo_configuration(self, data):
        """Is it a configuration of an existing repository?

        The user is trying to do "repo --name=updates" in a kickstart file.
        We can only enable or disable the already existing on-disk repo config.
        """
        return not data.url and data.name in self._dnf_manager.repositories

    def _remove_repo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found", repo_id)
        else:
            repos.pop(idx)

    def add_driver_repos(self):
        """Add driver repositories and packages.

        FIXME: Don't run this code on every payload restart.
        """
        # Drivers are loaded by anaconda-dracut, their repos are copied
        # into /run/install/DD-X where X is a number starting at 1. The list of
        # packages that were selected is in /run/install/dd_packages

        # Add repositories
        dir_num = 0
        while True:
            dir_num += 1
            repo = "/run/install/DD-%d/" % dir_num
            if not os.path.isdir(repo):
                break

            # Run createrepo if there are rpms and no repodata
            if not os.path.isdir(repo + "/repodata"):
                rpms = glob(repo + "/*rpm")
                if not rpms:
                    continue
                log.info("Running createrepo on %s", repo)
                util.execWithRedirect("createrepo_c", [repo])

            # Generate the repo name.
            repo_name = "DD-%d" % dir_num

            # The repo has been already created (#1268357).
            for ks_repo in self.data.repo.dataList():
                if repo_name == ks_repo.name:
                    continue

            # Or create a new one.
            ks_repo = self.data.RepoData(
                name=repo_name,
                baseurl="file://" + repo,
                enabled=True
            )

            self._add_repo_to_dnf_and_ks(ks_repo)

    @property
    def space_required(self):
        return calculate_required_space(self._dnf_manager)

    def set_updates_enabled(self, state):
        """Enable or Disable the repos used to update closest mirror.

        :param bool state: True to enable updates, False to disable.
        """
        self._updates_enabled = state

        # Enable or disable updates.
        for repo_id in conf.payload.updates_repositories:
            self._set_repo_enabled(repo_id, state)

        # Disable updates-testing.
        self._set_repo_enabled("updates-testing", False)
        self._set_repo_enabled("updates-testing-modular", False)

    def _set_repo_enabled(self, repo_id, enabled):
        """Enable or disable the repo in DNF and its data representation."""
        try:
            self._dnf_manager.set_repository_enabled(repo_id, enabled)
        except UnknownRepositoryError:
            pass

        repo = self.get_addon_repo(repo_id)
        if repo:
            repo.enabled = enabled

    def gather_repo_metadata(self):
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                self._sync_metadata(repo)
        self._base.fill_sack(load_system_repo=False)
        self._base.read_comps(arch_filter=True)

    def install(self):
        self._progress_cb(0, _('Starting package installation process'))

        # Get the packages configuration and selection data.
        configuration = self.get_packages_configuration()
        selection = self.get_packages_selection()

        # Add the rpm macros to the global transaction environment
        task = SetRPMMacrosTask(configuration)
        task.run()

        try:
            # Resolve packages.
            task = ResolvePackagesTask(self._dnf_manager, selection)
            task.run()
        except NonCriticalInstallationError as e:
            # FIXME: This is a temporary workaround.
            # Allow users to handle the error. If they don't want
            # to continue with the installation, raise a different
            # exception to make sure that we will not run the error
            # handler again.
            if error_handler.cb(e) == ERROR_RAISE:
                raise InstallationError(str(e)) from e

        # Set up the download location.
        task = PrepareDownloadLocationTask(self._dnf_manager)
        task.run()

        # Download the packages.
        task = DownloadPackagesTask(self._dnf_manager)
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

        # Install the packages.
        task = InstallPackagesTask(self._dnf_manager)
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

        # Clean up the download location.
        task = CleanUpDownloadLocationTask(self._dnf_manager)
        task.run()

        # Don't close the mother base here, because we still need it.

    def _get_repo(self, repo_id):
        """Return the yum repo object."""
        return self._base.repos[repo_id]

    def is_repo_enabled(self, repo_id):
        """Return True if repo is enabled."""
        try:
            return self._base.repos[repo_id].enabled
        except (dnf.exceptions.RepoError, KeyError):
            repo = self.get_addon_repo(repo_id)
            if repo:
                return repo.enabled
            else:
                return False

    def _reset_configuration(self):
        tear_down_sources(self.proxy)
        self._reset_additional_repos()
        self.tx_id = None
        self._dnf_manager.clear_cache()
        self._dnf_manager.reset_substitution()
        self._dnf_manager.configure_proxy(self._get_proxy_url())

    def _reset_additional_repos(self):
        for name in self._find_mounted_additional_repos():
            installation_dir = INSTALL_TREE + "-" + name
            self._unmount_source_directory(installation_dir)

            iso_dir = ISO_DIR + "-" + name
            self._unmount_source_directory(iso_dir)

    def _find_mounted_additional_repos(self):
        prefix = ISO_DIR + "-"
        prefix_len = len(prefix)
        result = []

        for dir_path in glob(prefix + "*"):
            result.append(dir_path[prefix_len:])

        return result

    def _unmount_source_directory(self, mount_point):
        if os.path.ismount(mount_point):
            device_path = payload_utils.get_mount_device_path(mount_point)
            device = payload_utils.resolve_device(device_path)
            if device:
                payload_utils.teardown_device(device)
            else:
                payload_utils.unmount(mount_point, raise_exc=True)

    def _is_source_default(self):
        """Report if the current source type is the default source type.

        NOTE: If no source was set previously a new default one
              will be created.
        """
        return self.source_type == conf.payload.default_source

    def update_base_repo(self, fallback=True, checkmount=True):
        """Update the base repository from the DBus source."""
        log.info("Configuring the base repo")
        self._reset_configuration()

        disabled_treeinfo_repo_names = self._cleanup_old_treeinfo_repositories()

        # Find the source and its type.
        source_proxy = self.get_source_proxy()
        source_type = source_proxy.Type

        # Change the default source to CDROM if there is a valid install media.
        # FIXME: Set up the default source earlier.
        if checkmount and self._is_source_default() and find_optical_install_media():
            source_type = SOURCE_TYPE_CDROM
            source_proxy = create_source(source_type)
            set_source(self.proxy, source_proxy)

        # Set up the source.
        set_up_sources(self.proxy)

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        # Enable or disable updates.
        self.set_updates_enabled(self._updates_enabled)

        # Repo files are always loaded from the system.
        # When reloaded their state needs to be synchronized with the user configuration.
        # So we disable them now and enable them later if required.
        enabled = []
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                enabled.append(repo.id)
                self._dnf_manager.set_repository_enabled(repo.id, False)

        # Add a new repo.
        if source_type not in SOURCE_REPO_FILE_TYPES:
            # Get the repo configuration of the first source.
            data = RepoConfigurationData.from_structure(
                self.proxy.GetRepoConfigurations()[0]
            )

            log.debug("Using the repo configuration: %s", data)

            # Get the URL.
            install_tree_url = data.url if data.type == URL_TYPE_BASEURL else ""
            mirrorlist = data.url if data.type == URL_TYPE_MIRRORLIST else ""
            metalink = data.url if data.type == URL_TYPE_METALINK else ""

            # Fallback to the installation root.
            base_repo_url = install_tree_url

            try:
                tree_info_metadata = TreeInfoMetadata()
                tree_info_metadata.load_data(data)

                self._dnf_manager.configure_substitution(
                    tree_info_metadata.release_version
                )

                base_repo_url = tree_info_metadata.get_base_repo_url()

                self._load_treeinfo_repositories(
                    tree_info_metadata,
                    base_repo_url,
                    disabled_treeinfo_repo_names,
                    data
                )
            except NoTreeInfoError as e:
                log.debug("No treeinfo metadata to use: %s", str(e))
            except TreeInfoMetadataError as e:
                log.warning("Couldn't use treeinfo metadata: %s", str(e))

            try:
                base_ksrepo = self.data.RepoData(
                    name=constants.BASE_REPO_NAME,
                    baseurl=base_repo_url,
                    mirrorlist=mirrorlist,
                    metalink=metalink,
                    noverifyssl=not data.ssl_verification_enabled,
                    proxy=data.proxy,
                    sslcacert=data.ssl_configuration.ca_cert_path,
                    sslclientcert=data.ssl_configuration.client_cert_path,
                    sslclientkey=data.ssl_configuration.client_key_path
                )
                self._add_repo_to_dnf(base_ksrepo)
                self._dnf_manager.load_repository(base_ksrepo.name)
            except (DNFManagerError, PayloadError) as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          source_type, base_repo_url)
                log.error("reason for repo removal: %s", e)
                with self._repos_lock:
                    self._base.repos.pop(constants.BASE_REPO_NAME, None)
                if not fallback:
                    with self._repos_lock:
                        for repo in self._base.repos.iter_enabled():
                            self._set_repo_enabled(repo.id, False)
                    return

                # Fallback to the default source
                #
                # This is at the moment CDN on RHEL
                # and closest mirror everywhere else.
                tear_down_sources(self.proxy)

                source_type = conf.payload.default_source
                source_proxy = create_source(source_type)
                set_source(self.proxy, source_proxy)

                set_up_sources(self.proxy)

        # We need to check this again separately in case REPO_FILES were set above.
        if source_type in SOURCE_REPO_FILE_TYPES:
            # If this is a kickstart install, just return now as we normally do not
            # want to read the on media repo files in such a case. On the other hand,
            # the local repo files are a valid use case if the system is subscribed
            # and the CDN is selected as the installation source.
            if flags.automatedInstall and not self._is_cdn_set_up():
                return

            # Otherwise, fall back to the default repos that we disabled above
            for repo_id in enabled:
                log.debug("repo %s: fall back enabled from default repos", repo_id)
                try:
                    self._dnf_manager.set_repository_enabled(repo_id, True)
                except UnknownRepositoryError:
                    pass

        for ksrepo in self.data.repo.dataList():
            if ksrepo.is_harddrive_based():
                ksrepo.baseurl = self._setup_harddrive_addon_repo(ksrepo)

            log.debug("repo %s: mirrorlist %s, baseurl %s, metalink %s",
                      ksrepo.name, ksrepo.mirrorlist, ksrepo.baseurl, ksrepo.metalink)
            # one of these must be set to create new repo
            if not (ksrepo.mirrorlist or ksrepo.baseurl or ksrepo.metalink or
                    ksrepo.name in self._base.repos):
                raise PayloadSetupError("Repository %s has no mirror, baseurl or "
                                        "metalink set and is not one of "
                                        "the pre-defined repositories" %
                                        ksrepo.name)

            self._add_repo_to_dnf(ksrepo)

        with self._repos_lock:

            # disable unnecessary repos
            for repo in self._base.repos.iter_enabled():
                id_ = repo.id
                if 'source' in id_ or 'debuginfo' in id_:
                    self._dnf_manager.set_repository_enabled(id_, False)
                elif constants.isFinal and 'rawhide' in id_:
                    self._dnf_manager.set_repository_enabled(id_, False)

            # fetch md for enabled repos
            for ks_repo in self.data.repo.dataList():
                if self.is_repo_enabled(ks_repo.name):
                    self._dnf_manager.load_repository(ks_repo.name)

    def _find_and_mount_iso(self, device, device_mount_dir, iso_path, iso_mount_dir):
        """Find and mount installation source from ISO on device.

        Return changed path to the iso to save looking for iso in the future call.
        """
        self._setup_device(device, mountpoint=device_mount_dir)

        # check for ISO images in the newly mounted dir
        path = device_mount_dir
        if iso_path:
            path = os.path.normpath("%s/%s" % (path, iso_path))

        # XXX it would be nice to streamline this when we're just setting
        #     things back up after storage activation instead of having to
        #     pretend we don't already know which ISO image we're going to
        #     use
        image = find_first_iso_image(path)
        if not image:
            payload_utils.teardown_device(device)
            raise PayloadSetupError("failed to find valid iso image")

        if path.endswith(".iso"):
            path = os.path.dirname(path)

        # this could already be set up the first time through
        if not os.path.ismount(iso_mount_dir):
            # mount the ISO on a loop
            image = os.path.normpath("%s/%s" % (path, image))
            payload_utils.mount(image, iso_mount_dir, fstype='iso9660', options="ro")

        if not iso_path.endswith(".iso"):
            result_path = os.path.normpath("%s/%s" % (iso_path,
                                                      os.path.basename(image)))
            while result_path.startswith("/"):
                # ridiculous
                result_path = result_path[1:]

            return result_path

        return iso_path

    @staticmethod
    def _setup_device(device, mountpoint):
        """Prepare an install CD/DVD for use as a package source."""
        log.info("setting up device %s and mounting on %s", device, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        real_mountpoint = os.path.realpath(mountpoint)
        mount_device_path = payload_utils.get_mount_device_path(real_mountpoint)

        if mount_device_path:
            log.warning("%s is already mounted on %s", mount_device_path, mountpoint)

            if mount_device_path == payload_utils.get_device_path(device):
                return
            else:
                payload_utils.unmount(real_mountpoint)

        try:
            payload_utils.setup_device(device)
            payload_utils.mount_device(device, mountpoint)
        except (DeviceSetupError, MountFilesystemError) as e:
            log.error("mount failed: %s", e)
            payload_utils.teardown_device(device)
            raise PayloadSetupError(str(e)) from e

    @staticmethod
    def _setup_NFS(mountpoint, server, path, options):
        """Prepare an NFS directory for use as an install source."""
        log.info("mounting %s:%s:%s on %s", server, path, options, mountpoint)
        device_path = payload_utils.get_mount_device_path(mountpoint)

        # test if the mountpoint is occupied already
        if device_path:
            _server, colon, _path = device_path.partition(":")
            if colon == ":" and server == _server and path == _path:
                log.debug("%s:%s already mounted on %s", server, path, mountpoint)
                return
            else:
                log.debug("%s already has something mounted on it", mountpoint)
                payload_utils.unmount(mountpoint)

        # mount the specified directory
        url = "%s:%s" % (server, path)

        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        payload_utils.mount(url, mountpoint, fstype="nfs", options=options)

    def _setup_harddrive_addon_repo(self, ksrepo):
        iso_device = payload_utils.resolve_device(ksrepo.partition)
        if not iso_device:
            raise PayloadSetupError("device for HDISO addon repo install %s does not exist" %
                                    ksrepo.partition)

        ksrepo.generate_mount_dir()

        device_mount_dir = ISO_DIR + "-" + ksrepo.mount_dir_suffix
        install_root_dir = INSTALL_TREE + "-" + ksrepo.mount_dir_suffix

        self._find_and_mount_iso(iso_device, device_mount_dir, ksrepo.iso_path, install_root_dir)
        url = "file://" + install_root_dir

        return url

    def _load_treeinfo_repositories(self, tree_info_metadata, base_repo_url,
                                    repo_names_to_disable, data):
        """Load new repositories from treeinfo file.

        :param base_repo_url: base repository url. This is not saved anywhere when the function
                              is called. It will be add to the existing urls if not None.
        :param repo_names_to_disable: list of repository names which should be disabled after load
        :type repo_names_to_disable: [str]
        :param data: repo configuration data
        """
        existing_urls = []

        if base_repo_url is not None:
            existing_urls.append(base_repo_url)

        for ks_repo in self.data.repo.dataList():
            baseurl = ks_repo.baseurl
            existing_urls.append(baseurl)

        for repo_md in tree_info_metadata.repositories:
            if repo_md.path in existing_urls:
                continue

            # disable repositories disabled by user manually before
            repo_enabled = repo_md.enabled \
                and repo_md.name not in repo_names_to_disable

            repo = RepoData(
                name=repo_md.name,
                baseurl=repo_md.path,
                noverifyssl=not data.ssl_verification_enabled,
                proxy=data.proxy,
                sslcacert=data.ssl_configuration.ca_cert_path,
                sslclientcert=data.ssl_configuration.client_cert_path,
                sslclientkey=data.ssl_configuration.client_key_path,
                install=False,
                enabled=repo_enabled
            )

            repo.treeinfo_origin = True
            log.debug("Adding new treeinfo repository: %s enabled: %s",
                      repo_md.name, repo_enabled)

            self._add_repo_to_dnf_and_ks(repo)

    def _cleanup_old_treeinfo_repositories(self):
        """Remove all old treeinfo repositories before loading new ones.

        Find all repositories added from treeinfo file and remove them. After this step new
        repositories will be loaded from the new link.

        :return: list of repository names which were disabled before removal
        :rtype: [str]
        """
        disabled_repo_names = []

        for ks_repo in list(self.data.repo.dataList()):
            if ks_repo.treeinfo_origin:
                log.debug("Removing old treeinfo repository %s", ks_repo.name)

                if not ks_repo.enabled:
                    disabled_repo_names.append(ks_repo.name)

                self._remove_repo(ks_repo.name)

        return disabled_repo_names

    def _write_dnf_repo(self, repo, repo_path):
        """Write a repo object to a DNF repo.conf file.

        :param repo: DNF repository object
        :param string repo_path: Path to write the repo to
        :raises: PayloadSetupError if the repo doesn't have a url
        """
        with open(repo_path, "w") as f:
            f.write("[%s]\n" % repo.id)
            f.write("name=%s\n" % repo.id)
            if self.is_repo_enabled(repo.id):
                f.write("enabled=1\n")
            else:
                f.write("enabled=0\n")

            if repo.mirrorlist:
                f.write("mirrorlist=%s\n" % repo.mirrorlist)
            elif repo.metalink:
                f.write("metalink=%s\n" % repo.metalink)
            elif repo.baseurl:
                f.write("baseurl=%s\n" % repo.baseurl[0])
            else:
                f.close()
                os.unlink(repo_path)
                raise PayloadSetupError("The repo {} has no baseurl, mirrorlist or "
                                        "metalink".format(repo.id))

            # kickstart repo modifiers
            ks_repo = self.get_addon_repo(repo.id)
            if not ks_repo:
                return

            if ks_repo.noverifyssl:
                f.write("sslverify=0\n")

            if ks_repo.proxy:
                try:
                    proxy = ProxyString(ks_repo.proxy)
                    f.write("proxy=%s\n" % proxy.url)
                except ProxyStringError as e:
                    log.error("Failed to parse proxy for _writeInstallConfig %s: %s",
                              ks_repo.proxy, e)

            if ks_repo.cost:
                f.write("cost=%d\n" % ks_repo.cost)

            if ks_repo.includepkgs:
                f.write("include=%s\n" % ",".join(ks_repo.includepkgs))

            if ks_repo.excludepkgs:
                f.write("exclude=%s\n" % ",".join(ks_repo.excludepkgs))

    def post_install(self):
        """Perform post-installation tasks."""
        # Write selected kickstart repos to target system
        for ks_repo in self.data.repo.dataList():
            if not ks_repo.install:
                continue

            if ks_repo.baseurl.startswith("nfs://"):
                log.info("Skip writing nfs repo %s to target system.", ks_repo.name)
                continue

            try:
                repo = self._get_repo(ks_repo.name)
                if not repo:
                    continue
            except (dnf.exceptions.RepoError, KeyError):
                continue
            repo_path = conf.target.system_root + YUM_REPOS_DIR + "%s.repo" % repo.id
            try:
                log.info("Writing %s.repo to target system.", repo.id)
                self._write_dnf_repo(repo, repo_path)
            except PayloadSetupError as e:
                log.error(e)

        # We don't need the mother base anymore. Close it.
        self._base.close()
        super().post_install()

        # rpm needs importing installed certificates manually, see rhbz#748320 and rhbz#185800
        task = ImportRPMKeysTask(
            sysroot=conf.target.system_root,
            gpg_keys=conf.payload.default_rpm_gpg_keys
        )
        task.run()

        # Update the DNF configuration.
        task = UpdateDNFConfigurationTask(
            sysroot=conf.target.system_root,
            data=self.get_packages_configuration()
        )
        task.run()

    @property
    def kernel_version_list(self):
        return get_kernel_version_list()
