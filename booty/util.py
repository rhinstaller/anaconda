def getDiskPart(dev, storage):
    dev = storage.devicetree.getDeviceByName(dev)

    if dev.type == "partition":
        partNum = dev.partedPartition.number
        disk = dev.disk
    else:
        partNum = None
        disk = dev
    
    return (disk.name, partNum)
