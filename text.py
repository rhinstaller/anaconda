import _balkan
from snack import *

screen = SnackScreen()

device = 'hda';
table = _balkan.readTable('/dev/' + device)
partList = []
for i in range(0, len(table) - 1):
    (type, start, size) = table[i]
    if (type == 0x83 and size):
	fullName = '/dev/%s%d' % (device, i + 1)
	partList.append((fullName, fullName))
    
rc = ListboxChoiceWindow(screen, 'Root Partition', 'What partition would you '
		    'like to use for your root partition?', partList,
		    buttons = ['Ok'])

screen.finish()

print rc
