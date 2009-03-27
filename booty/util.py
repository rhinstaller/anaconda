import string

def getDiskPart(dev, storage):
    path = storage.devicetree.getDeviceByName(dev).path[5:]
    cut = len(dev)
    if (path.startswith('rd/') or path.startswith('ida/') or
            path.startswith('cciss/') or path.startswith('sx8/') or
            path.startswith('mapper/') or path.startswith('mmcblk')):
        if dev[-2] == 'p':
            cut = -1
        elif dev[-3] == 'p':
            cut = -2
    else:
        if dev[-2] in string.digits:
            cut = -2
        elif dev[-1] in string.digits:
            cut = -1

    name = dev[:cut]

    # hack off the trailing 'p' from /dev/cciss/*, for example
    if name[-1] == 'p':
        for letter in name:
            if letter not in string.letters and letter != "/":
                name = name[:-1]
                break

    if cut < 0:
        partNum = int(dev[cut:]) - 1
    else:
        partNum = None

    return (name, partNum)

