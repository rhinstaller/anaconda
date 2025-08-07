from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.bootc.bootc_interface import BootcInterface
from pyanaconda.modules.payloads.payload.bootc.installation import DeployBootcTask
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase

log = get_module_logger(__name__)


class BootcModule(PayloadBase):
    """The Bootc payload module.

    Handles OCI image based systems via bootc.
    """

    def __init__(self):
        super().__init__()
        self._internal_mounts = []

        # Bootc handles the bootloader configuration itself
        self.set_kernel_version_list([])

    def for_publication(self):
        """Get the interface used to publish this source."""
        return BootcInterface(self)

    @property
    def type(self):
        return PayloadType.BOOTC

    @property
    def default_source_type(self):
        return SourceType.BOOTC

    @property
    def supported_source_types(self):
        return [SourceType.BOOTC]

    def process_kickstart(self, data):
        from pyanaconda.modules.payloads.source.factory import SourceFactory

        source_type = SourceType.BOOTC if getattr(data, "bootc", None) and data.bootc.seen else None
        if not source_type:
            return
        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def setup_kickstart(self, data):
        for source in self.sources:
            source.setup_kickstart(data)

    def _get_bootc_source(self):
        return self._get_source(SourceType.BOOTC)

    def install_with_tasks(self):
        """Install the payload using bootc.

        :return: list of tasks
        """
        source = self._get_bootc_source()
        if not source:
            return []
        data = source.configuration

        tasks = [
            DeployBootcTask(
                data=data,
                physroot=conf.target.physical_root,
                sysroot=conf.target.system_root,
            )
        ]

        return tasks
