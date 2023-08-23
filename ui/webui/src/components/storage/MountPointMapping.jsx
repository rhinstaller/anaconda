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

import "./MountPointMapping.scss";

const _ = cockpit.gettext;

const requiredMountPointOptions = [
    { value: "/boot", name: "boot" },
    { value: "/", name: "root" },
];

const getDeviceChildren = ({ deviceData, device }) => {
    const children = [];
    const deviceChildren = deviceData[device]?.children?.v || [];

    if (deviceChildren.length === 0) {
        children.push(device);
    } else {
        deviceChildren.forEach(child => {
            children.push(...getDeviceChildren({ deviceData, device: child }));
        });
    }

    return children;
};

const getInitialRequests = (partitioningData) => {
    const bootOriginalRequest = partitioningData.requests.find(r => r["mount-point"] === "/boot");
    const rootOriginalRequest = partitioningData.requests.find(r => r["mount-point"] === "/");

    const requests = requiredMountPointOptions.map((mountPoint, idx) => {
        const request = ({ "mount-point": mountPoint.value, reformat: mountPoint.name === "root" });

        if (mountPoint.name === "boot" && bootOriginalRequest) {
            return { ...bootOriginalRequest, ...request };
        }

        if (mountPoint.name === "root" && rootOriginalRequest) {
            return { ...rootOriginalRequest, ...request };
        }

        return request;
    });

    const extraRequests = partitioningData.requests.filter(r => r["mount-point"] && r["mount-point"] !== "/" && r["mount-point"] !== "/boot" && r["format-type"] !== "biosboot") || [];
    return [...requests, ...extraRequests].map((request, idx) => ({ ...request, "request-id": idx + 1 }));
};

const isDuplicateRequestField = (requests, fieldName, fieldValue) => {
    return requests.filter((request) => request[fieldName] === fieldValue).length > 1;
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

const getLockedLUKSDevices = (requests, deviceData) => {
    const devs = requests?.map(r => r["device-spec"]) || [];

    return Object.keys(deviceData).filter(d => {
        return (
            devs.includes(d) &&
            deviceData[d].formatData.type.v === "luks" &&
            deviceData[d].formatData.attrs.v.has_key !== "True"
        );
    });
};

const isDuplicateMountPoint = (requests, mountpoint) => {
    // we can have multiple swap devices "mounted"
    if (mountpoint === "swap") {
        return false;
    }

    return isDuplicateRequestField(requests, "mount-point", mountpoint);
};

const MountPointColumn = ({ handleRequestChange, idPrefix, isRequiredMountPoint, request, requests }) => {
    const mountpoint = request["mount-point"] || "";

    const [mountPointText, setMountPointText] = useState(mountpoint);

    const duplicatedMountPoint = isDuplicateMountPoint(requests, mountpoint);

    const swapMountpoint = mountpoint === "swap";

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
                        onBlur={() => handleRequestChange(mountPointText, request["device-spec"], request["request-id"])}
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

const DeviceColumnSelect = ({ deviceData, devices, idPrefix, lockedLUKSDevices, handleRequestChange, request }) => {
    const [isOpen, setIsOpen] = useState(false);

    const device = request["device-spec"];
    const options = devices.map(device => {
        const format = deviceData[device]?.formatData.description.v;
        const size = cockpit.format_bytes(deviceData[device]?.total.v);
        const description = cockpit.format("$0, $1", format, size);
        const isLockedLUKS = lockedLUKSDevices.some(p => device.includes(p));

        return (
            <SelectOption
              data-value={device}
              isDisabled={isLockedLUKS}
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
              handleRequestChange(request["mount-point"], selection, request["request-id"]);
              setIsOpen(false);
          }}
          onClear={() => {
              handleRequestChange(request["mount-point"], "", request["request-id"]);
              setIsOpen();
          }}
          toggleId={idPrefix + "-select-toggle"}
        >
            {options}
        </Select>
    );
};

const DeviceColumn = ({ deviceData, devices, idPrefix, handleRequestChange, lockedLUKSDevices, request, requests }) => {
    const device = request["device-spec"];
    const duplicatedDevice = isDuplicateRequestField(requests, "device-spec", device);

    return (
        <Flex direction={{ default: "column" }} spaceItems={{ default: "spaceItemsNone" }}>
            <DeviceColumnSelect
              deviceData={deviceData}
              devices={devices}
              idPrefix={idPrefix}
              handleRequestChange={handleRequestChange}
              lockedLUKSDevices={lockedLUKSDevices}
              request={request}
            />
            {device && duplicatedDevice &&
                <HelperText>
                    <HelperTextItem variant="error" hasIcon>
                        {_("Duplicate device.")}
                    </HelperTextItem>
                </HelperText>}
        </Flex>
    );
};

const FormatColumn = ({ deviceData, handleRequestChange, idPrefix, request, requests }) => {
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
              onChange={(_event, checked) => handleRequestChange(request["mount-point"], request["device-spec"], request["request-id"], checked)}
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

const MountPointRowRemove = ({ request, setRequests }) => {
    const handleRemove = () => {
        setRequests(requests => requests.filter(r => r["request-id"] !== request["request-id"]));
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

const RequestsTable = ({
    allDevices,
    deviceData,
    handleRequestChange,
    idPrefix,
    lockedLUKSDevices,
    requests,
    setRequests,
}) => {
    const columnClassName = idPrefix + "__column";
    const getRequestRow = (request) => {
        const isRequiredMountPoint = !!requiredMountPointOptions.find(val => val.value === request["mount-point"]);
        const duplicatedMountPoint = isDuplicateRequestField(requests, "mount-point", request["mount-point"]);
        const rowId = idPrefix + "-row-" + request["request-id"];

        return {
            props: { key: request["request-id"], id: rowId },
            columns: [
                {
                    title: (
                        <MountPointColumn
                          handleRequestChange={handleRequestChange}
                          idPrefix={rowId + "-mountpoint"}
                          isRequiredMountPoint={isRequiredMountPoint}
                          request={request}
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
                          lockedLUKSDevices={lockedLUKSDevices}
                          request={request}
                          requests={requests}
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
                          request={request}
                          requests={requests}
                        />
                    ),
                    props: { className: columnClassName }
                },
                {
                    title: (
                        (isRequiredMountPoint && !duplicatedMountPoint) ? null : <MountPointRowRemove request={request} setRequests={setRequests} />
                    ),
                    props: { className: columnClassName }
                }
            ],
        };
    };

    return (
        <ListingTable
          aria-label={_("Mount point assignment")}
          columns={[
              { title: _("Mount point"), props: { width: 30 } },
              { title: _("Device"), props: { width: 40 } },
              { title: _("Reformat"), props: { width: 20 } },
              { title: "", props: { width: 10 } },
          ]}
          emptyCaption={_("No devices")}
          id="mount-point-mapping-table"
          rows={requests.map(getRequestRow)} />
    );
};

const MountPointMappingContent = ({ deviceData, partitioningData, dispatch, idPrefix, setIsFormValid, onAddErrorNotification }) => {
    const [skipUnlock, setSkipUnlock] = useState(false);
    const [requests, setRequests] = useState(getInitialRequests(partitioningData));
    const [updateRequestCnt, setUpdateRequestCnt] = useState(0);
    const currentUpdateRequestCnt = useRef(0);

    const allDevices = useMemo(() => {
        return partitioningData.requests?.map(r => r["device-spec"]) || [];
    }, [partitioningData.requests]);

    const lockedLUKSDevices = useMemo(
        () => getLockedLUKSDevices(partitioningData.requests, deviceData),
        [deviceData, partitioningData.requests]
    );

    const handlePartitioningRequestsChange = useCallback(_requests => {
        if (!_requests) {
            return;
        }
        const requestsToDbus = partitioningDataRequests => {
            return partitioningDataRequests.map(row => {
                const newRequest = _requests.find(r => r["device-spec"] === row["device-spec"]);

                return {
                    "device-spec": cockpit.variant("s", row["device-spec"]),
                    "format-type": cockpit.variant("s", row["format-type"]),
                    "mount-point": cockpit.variant("s", newRequest !== undefined ? newRequest["mount-point"] : ""),
                    reformat: cockpit.variant("b", newRequest !== undefined ? !!newRequest.reformat : false),
                };
            });
        };

        setManualPartitioningRequests({
            partitioning: partitioningData.path,
            requests: requestsToDbus(partitioningData.requests)
        }).catch(ex => {
            onAddErrorNotification(ex);
            setIsFormValid(false);
        });
    }, [partitioningData.path, onAddErrorNotification, partitioningData.requests, setIsFormValid]);

    /* When requests change apply directly to the backend */
    useEffect(() => {
        if (currentUpdateRequestCnt.current !== updateRequestCnt) {
            currentUpdateRequestCnt.current = updateRequestCnt;
            handlePartitioningRequestsChange(requests);
        }
    }, [updateRequestCnt, requests, handlePartitioningRequestsChange]);

    /* When requests change check for duplicate mount point or device assignments and update form validity */
    useEffect(() => {
        if (requests) {
            const mountPoints = requests.filter(r => r["mount-point"] !== "swap").map(r => r["mount-point"]);
            const devices = requests.map(r => r["device-spec"]);
            const reformatInvalid = requests.some(request => isReformatInvalid(deviceData, request, requests)[0]);

            const isFormValid = (
                !reformatInvalid &&
                new Set(mountPoints).size === mountPoints.length &&
                new Set(devices).size === devices.length &&
                mountPoints.every(m => m) &&
                devices.every(d => d)
            );

            setIsFormValid(isFormValid);
            if (isFormValid) {
                setUpdateRequestCnt(updateRequestCnt => updateRequestCnt + 1);
            }
        }
    }, [deviceData, requests, setIsFormValid]);

    const handleRequestChange = (mountpoint, device, newRequestId, reformat) => {
        const data = deviceData[device];
        const _requests = requests.map(row => {
            const newRow = { ...row };
            if (row["request-id"] === newRequestId) {
                // Reset reformat option when changing from /
                if (row["mount-point"] === "/" && mountpoint !== row["mount-point"] && row.reformat) {
                    newRow.reformat = false;
                }

                // Always reformat the root partition
                if (mountpoint === "/") {
                    newRow.reformat = true;
                }

                if (reformat !== undefined) {
                    newRow.reformat = reformat;
                }

                // set "swap" as the default mountpoint for swap devices
                if (device !== undefined && data !== undefined && data.formatData.type.v === "swap") {
                    mountpoint = "swap";
                }

                // device changed to a non-swap device, reset mountpoint
                if (row["device-spec"] !== device && mountpoint === "swap" && data !== undefined && data.formatData.type.v !== "swap") {
                    mountpoint = undefined;
                }

                newRow["mount-point"] = mountpoint;
                newRow["device-spec"] = device;
            }
            return newRow;
        });
        setRequests(_requests);
    };

    if (lockedLUKSDevices?.length > 0 && !skipUnlock) {
        return (
            <EncryptedDevices
              dispatch={dispatch}
              idPrefix={idPrefix}
              lockedLUKSDevices={lockedLUKSDevices}
              setSkipUnlock={setSkipUnlock}
            />
        );
    } else {
        return (
            <>
                <RequestsTable
                  allDevices={allDevices}
                  deviceData={deviceData}
                  handleRequestChange={handleRequestChange}
                  idPrefix={idPrefix + "-table"}
                  lockedLUKSDevices={lockedLUKSDevices}
                  requests={requests}
                  setRequests={setRequests}
                />
                <div>
                    <Button
                      variant="secondary"
                      onClick={() => setRequests([...requests, { "request-id": requests.length + 1 }])}>
                        {_("Add mount")}
                    </Button>
                </div>
            </>
        );
    }
};

export const MountPointMapping = ({ deviceData, diskSelection, partitioningData, dispatch, idPrefix, setIsFormValid, onAddErrorNotification, reusePartitioning, setReusePartitioning, stepNotification }) => {
    const [usedPartitioning, setUsedPartitioning] = useState(partitioningData?.path);

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

    if (!reusePartitioning || usedPartitioning !== partitioningData.path) {
        return <EmptyStatePanel loading />;
    }

    return (
        <AnacondaPage title={_("Manual disk configuration: Mount point mapping")}>
            {stepNotification && stepNotification.step === "mount-point-mapping" &&
                <Alert
                  isInline
                  title={stepNotification.message}
                  variant="danger"
                />}
            <MountPointMappingContent
              deviceData={deviceData}
              dispatch={dispatch}
              idPrefix={idPrefix}
              onAddErrorNotification={onAddErrorNotification}
              partitioningData={partitioningData}
              setIsFormValid={setIsFormValid}
            />
        </AnacondaPage>
    );
};
