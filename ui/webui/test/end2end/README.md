# WebUI Integration tests


## Examples

### Minimal
Performs basically default installation

`minimal.py`
```
import os
import sys

# import Cockpit's machinery for test VMs and its browser test API
TEST_DIR = os.environ['WEBUI_TEST_DIR']
sys.path.append(TEST_DIR)
sys.path.append(os.path.join(TEST_DIR, "common"))
sys.path.append(os.path.join(TEST_DIR, "helpers"))
sys.path.append(os.path.join(os.path.dirname(TEST_DIR), "bots/machine"))

from integration import IntegrationTest
from testlib import test_main

class ExampleMinimal(IntegrationTest):
    def test_installation(self):
        self.run_integration_test()

if __name__ == '__main__':
    test_main()
```
`minimal.tc.yaml`
```
name: Minimal installation example
description: |
  Performs instalation with minimal interaction with the UI
author: tester@example.com
tags:
  - anaconda
priority: 9
execution:
  type: anaconda-webui
  automation_data:
    script_file: ./ui/webui/test/integration/minimal.py
    test_case: ExampleMinimal
instructions:
  setup:
    - Start installation in VM
  steps:
    - step: Go through the required steps and keep as much as possible on default setting.
    - step: Start installation
      result: Installation finished successfully
    - step: Reboot
      result: Installed system starts
  teardown:
    - step: Remove VM
```

### Small
Does stuff in one section of the installation wizard

`small.py`
```
import os
import sys

# import Cockpit's machinery for test VMs and its browser test API
TEST_DIR = os.environ['WEBUI_TEST_DIR']
sys.path.append(TEST_DIR)
sys.path.append(os.path.join(TEST_DIR, "common"))
sys.path.append(os.path.join(TEST_DIR, "helpers"))
sys.path.append(os.path.join(os.path.dirname(TEST_DIR), "bots/machine"))

from integration import IntegrationTest
from testlib import test_main

class ExampleSmall(IntegrationTest):
    def test_installation(self):
        self.run_integration_test()

    def storage(self):
        self._storage.select_disk('vda', False)  # Unselect disk
        self._installer.check_next_disabled()
        self._storage.wait_no_disks()  # Error message visible
        self._storage.select_disk('vda', True)  # Select disk

if __name__ == '__main__':
    test_main()
```
`small.tc.yaml`
```
name: Small installation example
description: |
  Performs instalation, try to continue without selected disk
author: tester@example.com
tags:
  - anaconda
priority: 7
execution:
  type: anaconda-webui
  automation_data:
    script_file: ./ui/webui/test/integration/small.py
    test_case: ExampleSmall
instructions:
  setup:
    - Start installation in VM with one disk
  steps:
    - step: Go through the required steps to get to storage step
    - step: Unselect disk (if selected) and try to continue to next step
      result: |
        Next button is disabled and and there is message on the screen
        instructing user to select disk.
    - step: Select disk and continue with rest of the required steps
      result: Next button is enabled, installation can be started
    - step: Start installation
      result: Installation finished successfully
    - step: Reboot
      result: Installed system starts
  teardown:
    - step: Remove VM
```

### Large
Changes the way how the test steps through the installation wizard

`large.py`
```
import os
import sys

# import Cockpit's machinery for test VMs and its browser test API
TEST_DIR = os.environ['WEBUI_TEST_DIR']
sys.path.append(TEST_DIR)
sys.path.append(os.path.join(TEST_DIR, "common"))
sys.path.append(os.path.join(TEST_DIR, "helpers"))
sys.path.append(os.path.join(os.path.dirname(TEST_DIR), "bots/machine"))

from integration import IntegrationTest
from testlib import test_main

class ExampleLarge(IntegrationTest):
    def test_installation(self):
        self._installer.open()
        self.configure_language()
        self._installer.next()
        self.configure_storage()
        self._installer.next()
        self._installer.back()  # Return to storage screen
        self._installer.next()  # Immediately continue to review
        self.check_review_screen()
        self._installer.begin_installation()
        self.monitor_progress()
        self.reboot_to_installed_system()
        self.check_installed_system()

if __name__ == '__main__':
    test_main()
```
`large.tc.yaml`
```
name: Large installation example
description: |
  Performs instalation with minimal interaction with the UI but try to return
  from review screen
author: tester@example.com
tags:
  - anaconda
priority: 5
execution:
  type: anaconda-webui
  automation_data:
    script_file: ./ui/webui/test/integration/large.py
    test_case: ExampleLarge
instructions:
  setup:
    - Start installation in VM with one disk
  steps:
    - step: Go through the required steps to get to review step
    - step: Press back button to get to the storage screen
      result: Nothing changed on the storage screen, disk is selected.
    - step: Start installation
      result: Installation finished successfully
    - step: Reboot
      result: Installed system starts
  teardown:
    - step: Remove VM
```
