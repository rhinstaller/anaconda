#
# Query and download sources of Flatpak content
#
# Copyright (C) 2024 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import json
import os
from abc import ABC, abstractmethod
from configparser import ConfigParser, NoSectionError
from contextlib import contextmanager
from functools import cached_property
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.util import requests_session
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.payloads.base.utils import get_downloader_for_repo_configuration
from pyanaconda.modules.payloads.payload.flatpak.constants import (
    FLATPAK_IMAGE_LAYOUT_VERSION,
    FLATPAK_MEDIA_TYPE,
    FLATPAK_REGISTRY_URL_PATTERN,
    FLATPAK_SCHEMA_V2,
)
from pyanaconda.modules.payloads.payload.flatpak.utils import (
    canonicalize_flatpak_ref,
    get_container_arch,
)

log = get_module_logger(__name__)

__all__ = ["FlatpakRegistrySource", "FlatpakSource", "FlatpakStaticSource"]


class SourceImage(ABC):
    """Base class for representation of a single image of a FlatpakSource.

    The "image" terminology is only used in Flatpak when installing a Flatpak from an OCI image.
    Where OCI image is artifact used by podman/docker which may contain multiple artifacts inside.

    One image could be single ref or a different artifact.
    """

    @property
    @abstractmethod
    def labels(self) -> Dict[str, str]:
        """The labels of the image."""

    @property
    def ref(self) -> Optional[str]:
        """Flatpak reference for the image, or None if not a Flatpak

        The None value could be returned if ref is not a Flatpak image as OCI image can have
        multiple different artifacts.
        """
        return self.labels.get("org.flatpak.ref")

    @property
    def download_size(self) -> int:
        """Download size, in bytes"""
        return int(self.labels["org.flatpak.download-size"])

    @property
    def installed_size(self) -> int:
        """Installed size, in bytes"""
        return int(self.labels["org.flatpak.installed-size"])


class FlatpakSource(ABC):
    """Base class for places where Flatpak images can be downloaded from.

    This class represents a source for OCI image layout where multiple images can be present.
    """

    @abstractmethod
    def calculate_size(self, refs: List[str]) -> Tuple[int, int]:
        """Calculate the total download and installed size of the images in refs and
        their dependencies.

        :param refs: list of Flatpak references
        :returns: download size, installed size
        """

    @abstractmethod
    def download(self, refs: List[str], download_location: str,
                 progress: Optional[ProgressReporter] = None) -> Optional[str]:
        """Downloads the images referenced by refs and any dependencies.

        If they are already local, or they can be installed
        directly from the remote location, nothing will be downloaded.

        Whether or not anything as been downloaded, returns
        the specification of a sideload repository that can be used to install from
        this source, or None if none is needed.

        :param refs: list of Flatpak references
        :param download_location: path to location for temporary downloads
        :param progress: used to report progress of the download
        :returns sideload location, including the transport (e.g. oci:<path>), or None
        """

    @property
    @abstractmethod
    def _images(self) -> List[SourceImage]:
        """All images in the source, filtered for the current architecture."""

    def _expand_refs(self, refs: List[str]) -> List[str]:
        """Expand the list of refs to be in full form and include any dependencies."""
        result = []
        for ref in refs:
            # We don't do anything with the collection ID for now
            _, ref = canonicalize_flatpak_ref(ref)
            result.append(ref)

        for image in self._images:
            if image.ref not in result:
                log.debug("Skipping source image %s: not requested", image.ref)
                continue

            metadata = image.labels.get("org.flatpak.metadata")
            if metadata is None:
                log.warning("Skipping source image %s: missing metadata", image.ref)
                continue

            cp = ConfigParser(interpolation=None)
            cp.read_string(metadata)
            try:
                runtime = cp.get('Application', 'Runtime')
                if runtime:
                    runtime_ref = f"runtime/{runtime}"
                    if runtime_ref not in result:
                        result.append(runtime_ref)
            except (NoSectionError, KeyError):
                log.error("Skipping source image %s: broken metadata", image.ref)

        log.debug("Refs: %s are expanded to: %s", refs, result)
        return result


class StaticSourceImage(SourceImage):
    """One image of a FlatpakStaticSource.

    This class represents one Flatpak image from the OCI format. Could be local or
    remote (not a Flatpak register).

    One image could be single ref or a different artifact.
    """

    def __init__(self, digest, manifest_json, config_json):
        self.digest = digest
        self.manifest_json = manifest_json
        self.config_json = config_json

    @property
    def labels(self):
        return self.config_json["config"]["Labels"]

    @property
    def download_size(self):
        # This is more accurate than using the org.flatpak.download-size label,
        # because further processing of the image might have recompressed
        # the layer using different settings.

        # If these values are not in json it would mean a corrupted image which should be rare
        # and should result in an exception anyway, from that reason it is not tested here.
        return sum(int(layer["size"]) for layer in self.manifest_json["layers"])


class FlatpakStaticSource(FlatpakSource):
    """Flatpak images stored in a OCI image layout, either locally or remotely

    https://github.com/opencontainers/image-spec/blob/main/image-layout.md
    """

    def __init__(self, repository_config: RepoConfigurationData, relative_path: str = "Flatpaks"):
        """Create a new source.

        :param repository_config: URL of the repository, or a local path
        :param relative_path: path of an OCI layout, relative to the repository root
        """
        self.repository_config = repository_config
        self._url = urljoin(repository_config.url + "/", relative_path)
        self._is_local = self._url.startswith("file://")
        self._cached_blobs = {}

    @contextmanager
    def _downloader(self):
        """Prepare a requests.Session.get method appropriately for the repository.

        :returns: a function that acts like requests.Session.get()
        """
        with requests_session() as session:
            downloader = get_downloader_for_repo_configuration(session, self.repository_config)
            yield downloader

    def calculate_size(self, refs):
        """Calculate the total download and installed size of the images in refs and
        their dependencies.

        :param refs: list of Flatpak references
        :returns: download size, installed size
        """
        log.debug("Calculating size of: %s", refs)

        download_size = 0
        installed_size = 0
        expanded = self._expand_refs(refs)

        for image in self._images:
            if image.ref not in expanded:
                log.debug("Skipping Flatpak %s size calculation as it is not in expanded list: %s",
                          image.ref, expanded)
                continue

            log.debug("%s: download %d%s, installed %d",
                      image.ref,
                      image.download_size,
                      " (skipped)" if self._is_local else "",
                      image.installed_size)
            download_size += 0 if self._is_local else image.download_size
            installed_size += image.installed_size

        log.debug("Total: download %d, installed %d", download_size, installed_size)
        return download_size, installed_size

    # TODO: To cover this code with unit tests we need to refactor the downloader out of the code
    def download(self, refs, download_location, progress=None):
        if self._is_local:
            return "oci:" + self._url.removeprefix("file://")

        collection_location = os.path.join(download_location, "Flatpaks")
        expanded_refs = self._expand_refs(refs)

        index_json = {
            "schemaVersion": FLATPAK_SCHEMA_V2,
            "manifests": []
        }

        with self._downloader() as downloader:
            for image in self._images:
                if image.ref in expanded_refs:
                    # Expanded refs have all the refs we need for the installation (including runtimes)
                    log.debug("Downloading %s, %s bytes", image.ref, image.download_size)
                    if progress:
                        progress.report_progress(_("Downloading {}").format(image.ref))

                    manifest_len = self._download_blob(downloader, collection_location, image.digest)
                    self._download_blob(downloader,
                                        collection_location, image.manifest_json["config"]["digest"])
                    index_json["manifests"].append({
                        "mediaType": FLATPAK_MEDIA_TYPE,
                        "digest": image.digest,
                        "size": manifest_len
                    })

                    for layer in image.manifest_json["layers"]:
                        self._download_blob(downloader,
                                            collection_location, layer["digest"],
                                            stream=True)

        os.makedirs(collection_location, exist_ok=True)
        with open(os.path.join(collection_location, "index.json"), "w") as f:
            json.dump(index_json, f)

        with open(os.path.join(collection_location, "oci-layout"), "w") as f:
            json.dump({
                "imageLayoutVersion": FLATPAK_IMAGE_LAYOUT_VERSION
            }, f)

        return "oci:" + collection_location

    @cached_property
    def _images(self) -> List[StaticSourceImage]:
        result = []

        with self._downloader() as downloader:
            url = self._url + "/index.json"
            response = downloader(url)
            if response.status_code == 404:
                raise SourceSetupError("No Flatpak source found at {}".format(url))
            response.raise_for_status()
            index_json = response.json()

            for manifest in index_json.get("manifests", ()):
                if manifest.get("mediaType") == FLATPAK_MEDIA_TYPE:
                    digest = manifest["digest"]
                    manifest_json = self._get_json(downloader, manifest["digest"])
                    config_json = self._get_json(downloader, manifest_json["config"]["digest"])
                    result.append(StaticSourceImage(digest, manifest_json, config_json))

        return result

    def _blob_url(self, digest):
        if not digest.startswith("sha256:"):
            raise RuntimeError("Only SHA-256 digests are supported")
        return self._url + "/blobs/sha256/" + digest[7:]

    def _get_blob(self, downloader, digest) -> bytes:
        result = self._cached_blobs.get(digest)
        if result:
            return result

        response = downloader(self._blob_url(digest))
        response.raise_for_status()

        self._cached_blobs[digest] = result = response.content
        return result

    def _download_blob(self, downloader, download_location, digest, stream=False):
        if not digest.startswith("sha256:"):
            raise RuntimeError("Only SHA-256 digests are supported")

        blobs_dir = os.path.join(download_location, "blobs/sha256/")
        os.makedirs(blobs_dir, exist_ok=True)

        path = os.path.join(blobs_dir, digest[7:])
        with open(path, "wb") as f:
            if stream:
                response = downloader(self._blob_url(digest), stream=True)
                response.raise_for_status()
                size = 0
                while True:
                    chunk = response.raw.read(64*1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)
                return size
            else:
                blob = self._get_blob(downloader, digest)
                f.write(blob)
                return len(blob)

    def _get_json(self, session, digest):
        return json.loads(self._get_blob(session, digest))


class RegistrySourceImage(SourceImage):
    """One image of a FlatpakRegistrySource.

    This class represents one Flatpak image from the OCI registry.

    The one Flatpak image could be single ref or a different artifact.
    """
    def __init__(self, labels):
        self._labels = labels

    @property
    def labels(self):
        return self._labels


class FlatpakRegistrySource(FlatpakSource):
    """Flatpak images indexed by a remote JSON file (OCI image layout), and stored in a registry.

    https://github.com/flatpak/flatpak-oci-specs/blob/main/registry-index.md
    """

    def __init__(self, url):
        self._index = None
        self._url = url

    def calculate_size(self, refs):
        # For registry sources, we don't download the images in advance;
        # instead they are downloaded into the /var/tmp of the target
        # system and installed one-by-one. So the downloads don't count
        # towards the space in the temporary download location, but we
        # need space for the largest download in the target system.
        # (That space will also be needed for upgrades after installation.)

        log.debug("Calculating size of: %s", refs)

        max_download_size = 0
        installed_size = 0
        expanded = self._expand_refs(refs)

        for image in self._images:
            if image.ref not in expanded:
                # Exclude all the refs which are not marked for installation
                log.debug("Image %s is not in expanded refs: %s", image.ref, expanded)
                continue

            log.debug("%s: download %d, installed %d",
                      image.ref, image.download_size, image.installed_size)

            max_download_size = max(max_download_size, image.download_size)
            installed_size += image.installed_size

        log.debug("Total: max download %d, installed %d", max_download_size, installed_size)
        return 0, installed_size + max_download_size

    @cached_property
    def _images(self):
        arch = get_container_arch()

        base_url = self._url.removeprefix("oci+")
        parsed = urlparse(base_url)
        if parsed.fragment:
            tag = parsed.fragment
            base_url = parsed._replace(fragment=None, query=None).geturl()
        else:
            tag = "latest"

        full_url = FLATPAK_REGISTRY_URL_PATTERN.format(base_url, arch, tag)
        with requests_session() as session:
            response = session.get(full_url)
            response.raise_for_status()
            index = response.json()

        result = []

        arch = get_container_arch()
        for repository in index["Results"]:
            for image in repository["Images"]:
                if image['Architecture'] != arch:
                    continue

                result.append(RegistrySourceImage(image["Labels"]))

        return result

    def download(self, refs, download_location, progress=None):
        return None
