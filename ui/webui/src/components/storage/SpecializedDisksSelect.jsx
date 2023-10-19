/*
 * Copyright (C) 2023 Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with This program; If not, see <http://www.gnu.org/licenses/>.
 */
import cockpit from "cockpit";
import React, { useState } from "react";

import { Dropdown, DropdownList, MenuToggle } from "@patternfly/react-core";

import { AddISCSITarget } from "./ISCSITarget.jsx";

const _ = cockpit.gettext;

export const SpecializedDisksSelect = ({ deviceData, dispatch }) => {
    const [isOpen, setIsOpen] = useState(false);
    const iscsiDevices = Object.keys(deviceData)
            .filter((device) => deviceData[device].type.v === "iscsi")
            .reduce((acc, device) => {
                acc[device] = deviceData[device];
                return acc;
            }, {});

    return (
        <Dropdown
          isOpen={isOpen}
          onSelect={() => setIsOpen(false)}
          onOpenChange={setIsOpen}
          toggle={(toggleRef) => (
              <MenuToggle id="configure-specialized-disks-button" ref={toggleRef} onClick={() => setIsOpen(_isOpen => setIsOpen(!_isOpen))} isExpanded={isOpen}>
                  {_("Configure specialized & network disks")}
              </MenuToggle>
          )}
          shouldFocusToggleOnSelect
        >
            <DropdownList>
                <AddISCSITarget devices={iscsiDevices} key="iscsi" dispatch={dispatch} />
            </DropdownList>
        </Dropdown>
    );
};
