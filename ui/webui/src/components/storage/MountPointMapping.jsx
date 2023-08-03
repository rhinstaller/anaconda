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
    Checkbox,
    Flex,
    FlexItem,
    HelperText,
    HelperTextItem,
    Label,
    Popover,
    Select,
    SelectOption,
    SelectVariant,
    TextInput,
} from "@patternfly/react-core";
import { HelpIcon, TrashIcon } from "@patternfly/react-icons";

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

const MountPointColumn = ({ handleRequestChange, idPrefix, isRequiredMountPoint, request, requests }) => {
    const mountpoint = request["mount-point"] || "";

    const [mountPointText, setMountPointText] = useState(mountpoint);

    const duplicatedMountPoint = isDuplicateRequestField(requests, "mount-point", mountpoint);

    return (
        <Flex direction={{ default: "column" }} spaceItems={{ default: "spaceItemsNone" }}>
            <Flex spaceItems={{ default: "spaceItemsMd" }}>
                {isRequiredMountPoint
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
                        onChange={setMountPointText}
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
          onToggle={setIsOpen}
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

const FormatColumn = ({ deviceData, handleRequestChange, idPrefix, request }) => {
    const mountpoint = request["mount-point"];
    const isRootMountPoint = mountpoint === "/";

    return (
        <Flex>
            <Checkbox
              id={idPrefix + "-checkbox"}
              isChecked={request.reformat}
              isDisabled={isRootMountPoint}
              label={_("Reformat")}
              onChange={checked => handleRequestChange(request["mount-point"], request["device-spec"], request["request-id"], checked)}
            />
            {isRootMountPoint &&
                <Popover
                  bodyContent={_("The root partition is always re-formatted by the installer.")}
                  showClose={false}>
                    <HelpIcon />
                </Popover>}
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
                        />
                    ),
                    props: { className: columnClassName }
                },
                {
                    title: (
                        isRequiredMountPoint ? null : <MountPointRowRemove request={request} setRequests={setRequests} />
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
            const mountPoints = requests.map(r => r["mount-point"]);
            const devices = requests.map(r => r["device-spec"]);

            const isFormValid = (
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
    }, [requests, setIsFormValid]);

    const handleRequestChange = (mountpoint, device, newRequestId, reformat) => {
        const data = deviceData[device];
        const _requests = requests.map(row => {
            const newRow = { ...row };
            if (row["request-id"] === newRequestId) {
                // Reset reformat option when changing from /
                if (row["mount-point"] === "/" && mountpoint !== row["mount-point"] && row.reformat) {
                    newRow.reformat = false;
                }

                // TODO: Anaconda does not support formatting btrfs yet
                if (row["device-spec"] !== device && data?.["format-type"] === "btrfs") {
                    newRow.reformat = false;
                }

                // Always reformat the root partition
                if (mountpoint === "/") {
                    newRow.reformat = true;
                }

                if (reformat !== undefined) {
                    newRow.reformat = reformat;
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

export const MountPointMapping = ({ deviceData, diskSelection, partitioningData, dispatch, idPrefix, setIsFormValid, onAddErrorNotification, stepNotification }) => {
    const [creatingPartitioning, setCreatingPartitioning] = useState(true);

    // If device selection changed since the last partitioning request redo the partitioning
    const selectedDevices = diskSelection.selectedDisks;
    const partitioningDevices = partitioningData?.requests?.map(r => r["device-spec"]) || [];
    const canReusePartitioning = selectedDevices.length === partitioningDevices.length && selectedDevices.every(d => partitioningDevices.includes(d));

    useEffect(() => {
        if (canReusePartitioning) {
            setCreatingPartitioning(false);
        } else {
            /* Reset the bootloader drive before we schedule partitions
             * The bootloader drive is automatically set during the partitioning, so
             * make sure we always reset the previous value before we run another one,
             * so it can be automatically set again based on the current disk selection.
             * Otherwise, the partitioning can fail with an error.
             */
            setBootloaderDrive({ drive: "" })
                    .then(() => createPartitioning({ method: "MANUAL" }))
                    .then(() => setCreatingPartitioning(false));
        }
    }, [canReusePartitioning]);

    if (creatingPartitioning || !partitioningData?.path || (partitioningData?.requests?.length || 0) < 1) {
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
