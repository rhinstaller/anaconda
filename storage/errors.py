
# Device
class DeviceError(Exception):
    pass

class DeviceCreateError(DeviceError):
    pass

class DeviceDestroyError(DeviceError):
    pass

class DeviceResizeError(DeviceError):
    pass

class DeviceSetupError(DeviceError):
    pass

class DeviceTeardownError(DeviceError):
    pass

class DeviceResizeError(DeviceError):
    pass

class DeviceUserDeniedFormatError(DeviceError):
    pass

# DeviceFormat
class DeviceFormatError(Exception):
    pass

class FormatCreateError(DeviceFormatError):
    pass

class FormatDestroyError(DeviceFormatError):
    pass

class FormatSetupError(DeviceFormatError):
    pass

class FormatTeardownError(DeviceFormatError):
    pass

class DMRaidMemberError(DeviceFormatError):
    pass

class FSError(DeviceFormatError):
    pass

class FSResizeError(FSError):
    pass

class FSMigrateError(FSError):
    pass

class LUKSError(DeviceFormatError):
    pass

class MDMemberError(DeviceFormatError):
    pass

class PhysicalVolumeError(DeviceFormatError):
    pass

class SwapSpaceError(DeviceFormatError):
    pass

# devicelibs
class SwapError(Exception):
    pass

class SuspendError(SwapError):
    pass

class OldSwapError(SwapError):
    pass

class MDRaidError(Exception):
    pass

class DMError(Exception):
    pass

class LVMError(Exception):
    pass

class CryptoError(Exception):
    pass

# DeviceTree
class DeviceTreeError(Exception):
    pass

# DeviceAction
class DeviceActionError(Exception):
    pass

# partitioning
class PartitioningError(Exception):
    pass

class PartitioningWarning(Exception):
    pass

# udev
class UdevError(Exception):
    pass


