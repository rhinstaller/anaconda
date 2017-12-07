from pyanaconda.installclasses.fedora import FedoraBaseInstallClass
from pyanaconda.product import productName

class FedoraWorkstationInstallClass(FedoraBaseInstallClass):
    name = "Fedora Workstation"
    stylesheet = "/usr/share/anaconda/pixmaps/workstation/fedora-workstation.css"
    sortPriority = FedoraBaseInstallClass.sortPriority + 1
    if not productName.startswith("Fedora Workstation"):  # pylint: disable=no-member
        hidden = True
    defaultPackageEnvironment = "workstation-product-environment"
