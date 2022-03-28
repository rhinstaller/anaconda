/*
 * Copyright (C) 2022 Red Hat, Inc.
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
import React, { useEffect, useState } from "react";

import {
    Checkbox, Title,
    DataList, DataListItem,
    DataListItemRow, DataListItemCells,
    DataListCell,
    DescriptionList, DescriptionListGroup,
    DescriptionListTerm, DescriptionListDescription,
    Flex, Popover,
} from "@patternfly/react-core";

import {
    getSelectedDisks, getDeviceData,
} from "../../apis/storage.js";

import {
    getLanguage, getLanguageData,
} from "../../apis/localization.js";

import { HelpIcon } from "@patternfly/react-icons";

const _ = cockpit.gettext;

export const ReviewConfiguration = () => {
    const [deviceData, setDeviceData] = useState({});
    const [selectedDisks, setSelectedDisks] = useState();
    const [systemLanguage, setSystemLanguage] = useState();

    useEffect(() => {
        getLanguage()
                .then(res => {
                    getLanguageData({ lang: res }).then(res => {
                        setSystemLanguage(res["native-name"].v);
                    }, console.error);
                }, console.error);
        getSelectedDisks()
                .then(res => {
                    setSelectedDisks(res);
                    // get detailed data for the selected disks
                    res.forEach(disk => {
                        getDeviceData({ disk })
                                .then(res => {
                                    setDeviceData(d => ({ ...d, [disk]: res[0] }));
                                }, console.error);
                    });
                }, console.error);
    }, []);

    // handle case of disks not (yet) loaded
    if (!selectedDisks || !systemLanguage) {
        return null;
    }

    return (
        <>
            <DescriptionList isHorizontal>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Language")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id="installation-review-target-system-language">
                        {systemLanguage}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </DescriptionList>
            <Title headingLevel="h3" size="xl">
                {_("Installation destination")}
            </Title>
            <DataList>
                {selectedDisks.map(selectedDisk => (
                    <DataListItem key={selectedDisk}>
                        <DataListItemRow>
                            <DataListItemCells
                              dataListCells={[
                                  <DataListCell key={selectedDisk} id={"installation-review-disk-label-" + selectedDisk}>
                                      {_("Local standard disk")}
                                  </DataListCell>,
                                  <DataListCell key={"description-" + selectedDisk} id={"installation-review-disk-description-" + selectedDisk}>
                                      {deviceData && deviceData[selectedDisk] && deviceData[selectedDisk].description.v + " (" + selectedDisks + ")"}
                                  </DataListCell>,
                                  <DataListCell key={"size-" + selectedDisk} id={"installation-review-disk-size-" + selectedDisk}>
                                      {cockpit.format_bytes(deviceData && deviceData[selectedDisk] && deviceData[selectedDisk].size.v) + " " + _("total")}
                                  </DataListCell>
                              ]}
                            />
                        </DataListItemRow>
                    </DataListItem>
                ))}
            </DataList>
        </>
    );
};

export const ReviewConfigurationFooter = ({ isEraseChecked, setIsEraseChecked }) => {
    return (
        <Flex alignItems={{ default: "alignItemsCenter" }}>
            <Checkbox
              label={_("Erase disks to install")}
              isChecked={isEraseChecked}
              onChange={setIsEraseChecked}
              id="installation-review-disk-erase-confirm"
            />
            <Popover
              headerContent={
                  _("All data on the listed disks will be erased")
              }
              bodyContent={
                  _("Therefore it is recommended to only proceed if all data on these disks is either backed up or not important.")
              }
            >
                <button
                  type="button"
                  className="pf-c-form__group-label-help"
                >
                    <HelpIcon />
                </button>
            </Popover>
        </Flex>
    );
};
