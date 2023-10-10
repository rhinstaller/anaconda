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
import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";

import {
    Alert,
    Button,
    Switch,
    Flex,
    FlexItem,
    HelperText,
    HelperTextItem,
    Label,
    TextInput,
    Tooltip
} from "@patternfly/react-core";
import {
    Select,
    SelectOption,
    SelectVariant
} from "@patternfly/react-core/deprecated";
import { TrashIcon } from "@patternfly/react-icons";

import { ListingTable } from "cockpit-components-table.jsx";
import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";

import { AnacondaPage } from "../AnacondaPage.jsx";
import { EncryptedDevices } from "./EncryptedDevices.jsx";

import {
    createPartitioning,
    setBootloaderDrive,
    setManualPartitioningRequests,
} from "../../apis/storage.js";
import {
    getDeviceChildren,
    getLockedLUKSDevices,
    hasDuplicateFields,
    isDuplicateRequestField,
} from "../../helpers/storage.js";

import "./MountPointMapping.scss";

const _ = cockpit.gettext;

/* Filter out the partitioning requests array to contain only:
 * - rows with required mount points
 * - rows with mount points already selected by the user
 * @param {Array} requests - partitioning requests
 * @param {Array} requiredMountPoints - required mount points
 * @returns {Array} filtered requests
 */
const getInitialRequests = (requests, requiredMountPoints) => {
    const requiredRequests = requiredMountPoints.map((mountPoint, idx) => {
        const originalRequest = requests.find(request => request["mount-point"] === mountPoint["mount-point"].v);
        const request = ({ "mount-point": mountPoint["mount-point"].v, reformat: mountPoint["mount-point"].v === "/" });

        if (originalRequest) {
            return { ...originalRequest, ...request };
        }

        return request;
    });

    const extraRequests = requests.filter(r => (
        r["mount-point"] &&
        !requiredMountPoints.find(m => m["mount-point"].v === r["mount-point"])
    )) || [];

    return [...requiredRequests, ...extraRequests];
};

/* Check validity of the requests array
 * @param {Array} requests - partitioning requests
 * @deviceData {Object} deviceData - device data
 * @returns {boolean}
 */
const getRequestsValid = (requests, deviceData) => {
    const checkValidRequest = r => {
        return (
            r["mount-point"] &&
            r["device-spec"] &&
            !isReformatInvalid(deviceData, r, requests)[0]
        );
    };

    /* When requests change check for duplicate mount point or device assignments and update form validity */
    const isFormValid = (
        !hasDuplicateFields(requests, "mount-point") &&
        !hasDuplicateFields(requests, "device-spec") &&
        requests.every(checkValidRequest)
    );

    return isFormValid;
};

const isReformatInvalid = (deviceData, request, requests) => {
    const device = request["device-spec"];

    if (!device || !request.reformat) {
        return [false, ""];
    }

    if (!deviceData[device].formatData.formattable.v) {
        return [true, cockpit.format(_("Selected device's format '$0' cannot be reformatted."),
                                     deviceData[device].formatData.type.v)];
    }

    const children = getDeviceChildren({ deviceData, device });

    /* When parent device is re-formatted all children must:
     * - either exist in the mount points mapper table and  be re-formatted
     * - or not exist in the mountpoints mapper table
     */
    const isChildReformatValid = children.every(child => {
        const childRequest = requests.find(r => r["device-spec"] === child);

        return !childRequest || childRequest.reformat === true;
    });

    if (!isChildReformatValid) {
        return [true, _("Mismatch between parent device and child device reformat selection.")];
    } else {
        return [false, ""];
    }
};

const requestsToDbus = (requests) => {
    return requests.map(row => {
        return {
            "device-spec": cockpit.variant("s", row["device-spec"] || ""),
            "format-type": cockpit.variant("s", row["format-type"] || ""),
            "mount-point": cockpit.variant("s", row["mount-point"] || ""),
            reformat: cockpit.variant("b", !!row.reformat),
        };
    });
};

/* Build the backend-requests object from the unapplied requests.
 * @param {Array.<Object>} requests An array of request objects from back-end
 * @param {Array.<Object>} newRequests An array of request objects from front-end
 * @param string partitioning DBus path to a partitioning
 * @returns {Promise}
 */
const updatePartitioningRequests = ({ requests, newRequests, partitioning }) => {
    const backendRequests = [...requests];

    backendRequests.forEach((backendRequest, backendRequestIndex) => {
        const newRequestIndex = newRequests.findIndex(r => r["device-spec"] === backendRequest["device-spec"]);

        if (newRequestIndex === -1) {
            // When a 'device' is not selected in the front-end set the mount-point to empty string
            backendRequests[backendRequestIndex]["mount-point"] = "";
        } else if (newRequests[newRequestIndex]?.["device-spec"]) {
            //  Otherwise sync the object from the front-end to back-end
            backendRequests[backendRequestIndex] = newRequests[newRequestIndex];
        }
    });

    return setManualPartitioningRequests({
        partitioning,
        requests: requestsToDbus(backendRequests),
    });
};

const isDeviceMountPointInvalid = (deviceData, requiredMountPoints, request) => {
    const device = request["device-spec"];
    const requiredMountPointData = requiredMountPoints.find(val => val["mount-point"].v === request["mount-point"]);

    if (!device || !request["mount-point"] || !requiredMountPointData) {
        return [false, ""];
    }

    // we have constraints for filesystem type for required mount points from the backend) {
    if (requiredMountPointData && requiredMountPointData["required-filesystem-type"].v !== "" &&
        deviceData[device].formatData.type.v !== requiredMountPointData["required-filesystem-type"].v) {
        return [true,
            cockpit.format(_("'$0' must be on a device formatted to '$1'"),
                           request["mount-point"], requiredMountPointData["required-filesystem-type"].v)];
    }

    return [false, ""];
};

const MountPointColumn = ({ handleRequestChange, idPrefix, isRequiredMountPoint, request, requests, requestIndex }) => {
    const mountpoint = request["mount-point"] || "";

    const [mountPointText, setMountPointText] = useState(mountpoint);

    const duplicatedMountPoint = isDuplicateRequestField(requests, "mount-point", mountpoint);

    const swapMountpoint = mountpoint === "swap";

    useEffect(() => {
        setMountPointText(request["mount-point"] || "");
    }, [request]);

    return (
        <Flex direction={{ default: "column" }} spaceItems={{ default: "spaceItemsNone" }}>
            <Flex spaceItems={{ default: "spaceItemsMd" }}>
                {(isRequiredMountPoint && !duplicatedMountPoint) || swapMountpoint
                    ? (
                        <FlexItem
                          className="mount-point-mapping__mountpoint-text"
                          id={idPrefix}
                        >
                            {mountpoint || request["format-type"]}
                        </FlexItem>
                    )
                    : <TextInput
                        className="mount-point-mapping__mountpoint-text"
                        id={idPrefix}
                        onBlur={() => handleRequestChange({ mountPoint: mountPointText, deviceSpec: request["device-spec"], requestIndex })}
                        onChange={(_event, val) => setMountPointText(val)}
                        value={mountPointText}
                    />}
                {isRequiredMountPoint && <Label color="gold">{_("Required")}</Label>}
                {!isRequiredMountPoint && <Label color="purple">{_("Custom")}</Label>}

            </Flex>
            {mountpoint && duplicatedMountPoint &&
                <HelperText>
                    <HelperTextItem variant="error" hasIcon>
                        {_("Duplicate mount point.")}
                    </HelperTextItem>
                </HelperText>}
        </Flex>
    );
};

const DeviceColumnSelect = ({ deviceData, devices, idPrefix, isRequiredMountPoint, lockedLUKSDevices, handleRequestChange, request, requestIndex }) => {
    const [isOpen, setIsOpen] = useState(false);

    const device = request["device-spec"];
    const options = devices.map(device => {
        const formatType = deviceData[device]?.formatData.type.v;
        const format = deviceData[device]?.formatData.description.v;
        const size = cockpit.format_bytes(deviceData[device]?.total.v);
        const description = cockpit.format("$0, $1", format, size);
        const isLockedLUKS = lockedLUKSDevices.some(p => device.includes(p));
        /* Disable the following devices:
         * - Locked LUKS devices
         * - Swap devices when the mount point is preset (required) as these reset it
         */
        const isDisabled = isLockedLUKS || (formatType === "swap" && isRequiredMountPoint);

        return (
            <SelectOption
              data-value={device}
              isDisabled={isDisabled}
              description={description}
              key={device}
              value={device}
            />
        );
    });

    return (
        <Select
          hasPlaceholderStyle
          isOpen={isOpen}
          placeholderText={_("Select a device")}
          selections={device ? [device] : []}
          variant={SelectVariant.single}
          onToggle={(_event, val) => setIsOpen(val)}
          onSelect={(_, selection, isAPlaceHolder) => {
              handleRequestChange({ mountPoint: request["mount-point"], deviceSpec: selection, requestIndex });
              setIsOpen(false);
          }}
          onClear={() => {
              handleRequestChange({ mountPoint: request["mount-point"], deviceSpec: "", requestIndex });
              setIsOpen();
          }}
          toggleId={idPrefix + "-select-toggle"}
        >
            {options}
        </Select>
    );
};

const DeviceColumn = ({ deviceData, devices, requiredMountPoints, idPrefix, isRequiredMountPoint, handleRequestChange, lockedLUKSDevices, request, requests, requestIndex }) => {
    const device = request["device-spec"];
    const duplicatedDevice = isDuplicateRequestField(requests, "device-spec", device);
    const [deviceInvalid, errorMessage] = isDeviceMountPointInvalid(deviceData, requiredMountPoints, request);

    return (
        <Flex direction={{ default: "column" }} spaceItems={{ default: "spaceItemsNone" }}>
            <DeviceColumnSelect
              deviceData={deviceData}
              devices={devices}
              idPrefix={idPrefix}
              isRequiredMountPoint={isRequiredMountPoint}
              handleRequestChange={handleRequestChange}
              lockedLUKSDevices={lockedLUKSDevices}
              request={request}
              requestIndex={requestIndex}
            />
            {device && duplicatedDevice &&
                <HelperText>
                    <HelperTextItem variant="error" hasIcon>
                        {_("Duplicate device.")}
                    </HelperTextItem>
                </HelperText>}
            {deviceInvalid &&
                <HelperText>
                    <HelperTextItem variant="error" hasIcon>
                        {errorMessage}
                    </HelperTextItem>
                </HelperText>}
        </Flex>
    );
};

const FormatColumn = ({ deviceData, handleRequestChange, idPrefix, request, requests, requestIndex }) => {
    const mountpoint = request["mount-point"];
    const isRootMountPoint = mountpoint === "/";
    const [reformatInvalid, reformatErrorMsg] = isReformatInvalid(deviceData, request, requests);
    const FormatSwitch = () => {
        return (
            <Switch
              id={idPrefix + "-switch"}
              isChecked={!!request.reformat}
              isDisabled={isRootMountPoint}
              aria-label={_("Reformat")}
              onChange={(_event, checked) => handleRequestChange({ mountPoint: request["mount-point"], deviceSpec: request["device-spec"], requestIndex, reformat: checked })}
            />
        );
    };

    return (
        <Flex id={idPrefix}>
            {!isRootMountPoint &&
                <FormatSwitch />}
            {isRootMountPoint &&
                <Tooltip
                  content={_("The root partition is always re-formatted by the installer.")}>
                    <FormatSwitch />
                </Tooltip>}
            {reformatInvalid &&
                <HelperText>
                    <HelperTextItem variant="error" hasIcon>
                        {reformatErrorMsg}
                    </HelperTextItem>
                </HelperText>}
        </Flex>
    );
};

const MountPointRowRemove = ({ requestIndex, handleRequestChange }) => {
    const handleRemove = () => {
        // remove row from requests and update requests with higher ID
        handleRequestChange({ requestIndex, remove: true });
    };

    return (
        <Button
          aria-label={_("Remove")}
          onClick={handleRemove}
          variant="plain"
        >
            <TrashIcon />
        </Button>
    );
};

const getRequestRow = ({
    allDevices,
    deviceData,
    handleRequestChange,
    idPrefix,
    lockedLUKSDevices,
    request,
    requestIndex,
    requests,
    requiredMountPoints,
}) => {
    const columnClassName = idPrefix + "__column";
    const isRequiredMountPoint = !!requiredMountPoints.find(val => val["mount-point"].v === request["mount-point"]);
    const duplicatedMountPoint = isDuplicateRequestField(requests, "mount-point", request["mount-point"]);
    const rowId = idPrefix + "-row-" + (requestIndex + 1);

    return ({
        props: { key: requestIndex, id: rowId },
        columns: [
            {
                title: (
                    <MountPointColumn
                      handleRequestChange={handleRequestChange}
                      idPrefix={rowId + "-mountpoint"}
                      isRequiredMountPoint={isRequiredMountPoint}
                      request={request}
                      requestIndex={requestIndex}
                      requests={requests}
                    />
                ),
                props: { className: columnClassName }
            },
            {
                title: (
                    <DeviceColumn
                      deviceData={deviceData}
                      devices={allDevices}
                      handleRequestChange={handleRequestChange}
                      idPrefix={rowId + "-device"}
                      isRequiredMountPoint={isRequiredMountPoint}
                      lockedLUKSDevices={lockedLUKSDevices}
                      request={request}
                      requestIndex={requestIndex}
                      requests={requests}
                      requiredMountPoints={requiredMountPoints}
                    />
                ),
                props: { className: columnClassName }
            },
            {
                title: (
                    <FormatColumn
                      deviceData={deviceData}
                      handleRequestChange={handleRequestChange}
                      idPrefix={rowId + "-format"}
                      isRequiredMountPoint={isRequiredMountPoint}
                      request={request}
                      requestIndex={requestIndex}
                      requests={requests}
                    />
                ),
                props: { className: columnClassName }
            },
            {
                title: (
                    (isRequiredMountPoint && !duplicatedMountPoint) ? null : <MountPointRowRemove requestIndex={requestIndex} handleRequestChange={handleRequestChange} />
                ),
                props: { className: columnClassName }
            }
        ],
    });
};

const getNewRequestProps = ({ mountPoint, deviceSpec, reformat, requests }) => {
    const formatType = requests.find(device => device["device-spec"] === deviceSpec)?.["format-type"];
    const newProps = {};

    if (mountPoint !== undefined) {
        newProps["mount-point"] = mountPoint;
    }
    if (deviceSpec !== undefined) {
        newProps["device-spec"] = deviceSpec;
        if (formatType === "swap") {
            newProps["mount-point"] = "swap";
        }
    }
    if (reformat !== undefined) {
        newProps.reformat = !!reformat;
    }
    if (formatType !== undefined) {
        newProps["format-type"] = formatType;
    }

    return newProps;
};

const RequestsTable = ({
    deviceData,
    idPrefix,
    lockedLUKSDevices,
    onAddErrorNotification,
    partitioningDataPath,
    requests,
    requiredMountPoints,
    setIsFormValid,
}) => {
    const currentPartitioning = useRef();
    const [unappliedRequests, setUnappliedRequests] = useState([]);
    const allDevices = useMemo(() => {
        return requests?.filter(r => isUsableDevice(r["device-spec"], deviceData)).map(r => r["device-spec"]) || [];
    }, [requests, deviceData]);

    // Add the required mount points to the initial requests
    useEffect(() => {
        if (partitioningDataPath === currentPartitioning.current) {
            return;
        }

        currentPartitioning.current = partitioningDataPath;

        const initialRequests = getInitialRequests(requests, requiredMountPoints);
        setUnappliedRequests(initialRequests);

        setIsFormValid(getRequestsValid(initialRequests, deviceData));
    }, [deviceData, setIsFormValid, partitioningDataPath, requests, requiredMountPoints]);

    const handleRequestChange = useCallback(({ mountPoint, deviceSpec, requestIndex, reformat, remove }) => {
        const newRequests = [...unappliedRequests];
        if (remove) {
            // Remove a request from the specified index
            newRequests.splice(requestIndex, 1);
        } else {
            const newRequest = {
                ...(newRequests[requestIndex] || {}),
                ...getNewRequestProps({ mountPoint, deviceSpec, reformat, requests })
            };

            if (requestIndex === unappliedRequests.length) {
                // Add new request in the end of the array
                newRequests.push(newRequest);
            } else {
                // Update existing request
                newRequests[requestIndex] = newRequest;
            }
        }

        setIsFormValid(getRequestsValid(newRequests, deviceData));

        /* Sync newRequests to the backend */
        updatePartitioningRequests({
            requests,
            newRequests,
            partitioning: partitioningDataPath
        }).catch(ex => {
            onAddErrorNotification(ex);
            setIsFormValid(false);
        });

        setUnappliedRequests(newRequests);
    }, [setIsFormValid, deviceData, unappliedRequests, requests, partitioningDataPath, onAddErrorNotification]);

    return (
        <>
            <ListingTable
              aria-label={_("Mount point assignment")}
              columns={[
                  { title: _("Mount point"), props: { width: 30 } },
                  { title: _("Device"), props: { width: 40 } },
                  { title: _("Reformat"), props: { width: 20 } },
                  { title: "", props: { width: 10 } },
              ]}
              emptyCaption={_("No devices")}
              id={idPrefix}
              rows={unappliedRequests
                      .map((request, idx) => (
                          getRequestRow({
                              allDevices,
                              deviceData,
                              handleRequestChange,
                              idPrefix,
                              lockedLUKSDevices,
                              request,
                              requestIndex: idx,
                              requests: unappliedRequests,
                              requiredMountPoints,
                          })
                      ))} />
            <div>
                <Button
                  variant="secondary"
                  onClick={() => handleRequestChange({ requestIndex: unappliedRequests.length })}>
                    {_("Add mount")}
                </Button>
            </div>
        </>
    );
};

const isUsableDevice = (devSpec, deviceData) => {
    const device = deviceData[devSpec];
    if (device === undefined || device.formatData === undefined) {
        return false;
    }

    // luks is allowed -- we need to be able to unlock it
    if (device.formatData.type.v === "luks") {
        return true;
    }

    // only swap and mountable filesystems should be shown in the mount point assignment
    if (device.formatData.type.v === "swap" || device.formatData.mountable.v === true) {
        return true;
    }

    return false;
};

export const MountPointMapping = ({
    deviceData,
    diskSelection,
    dispatch,
    idPrefix,
    onAddErrorNotification,
    partitioningData,
    requiredMountPoints,
    reusePartitioning,
    setIsFormValid,
    setReusePartitioning,
    stepNotification,
}) => {
    const [usedPartitioning, setUsedPartitioning] = useState(partitioningData?.path);
    const [skipUnlock, setSkipUnlock] = useState(false);
    const lockedLUKSDevices = useMemo(
        () => getLockedLUKSDevices(partitioningData?.requests, deviceData),
        [deviceData, partitioningData?.requests]
    );

    useEffect(() => {
        if (!reusePartitioning || partitioningData?.method !== "MANUAL") {
            /* Reset the bootloader drive before we schedule partitions
             * The bootloader drive is automatically set during the partitioning, so
             * make sure we always reset the previous value before we run another one,
             * so it can be automatically set again based on the current disk selection.
             * Otherwise, the partitioning can fail with an error.
             */
            setBootloaderDrive({ drive: "" })
                    .then(() => createPartitioning({ method: "MANUAL" }))
                    .then(path => {
                        setUsedPartitioning(path[0]);
                        setReusePartitioning(true);
                    });
        }
    }, [reusePartitioning, setReusePartitioning, partitioningData?.method, partitioningData?.path]);

    const isLoadingNewPartitioning = !reusePartitioning || usedPartitioning !== partitioningData.path;
    const showLuksUnlock = lockedLUKSDevices?.length > 0 && !skipUnlock;

    return (
        <AnacondaPage title={_("Manual disk configuration: Mount point mapping")}>
            {stepNotification && stepNotification.step === "mount-point-mapping" &&
                <Alert
                  isInline
                  title={stepNotification.message}
                  variant="danger"
                />}

            {showLuksUnlock &&
            (
                <EncryptedDevices
                  dispatch={dispatch}
                  idPrefix={idPrefix}
                  isLoadingNewPartitioning={isLoadingNewPartitioning}
                  lockedLUKSDevices={lockedLUKSDevices}
                  setSkipUnlock={setSkipUnlock}
                />
            )}
            {!showLuksUnlock && (
                (isLoadingNewPartitioning || !requiredMountPoints || !partitioningData?.requests)
                    ? (
                        <EmptyStatePanel loading />
                    )
                    : (
                        <RequestsTable
                          deviceData={deviceData}
                          idPrefix={idPrefix + "-table"}
                          lockedLUKSDevices={lockedLUKSDevices}
                          onAddErrorNotification={onAddErrorNotification}
                          partitioningDataPath={partitioningData?.path}
                          requests={partitioningData?.requests}
                          requiredMountPoints={requiredMountPoints}
                          setIsFormValid={setIsFormValid}
                        />
                    ))}
        </AnacondaPage>
    );
};
