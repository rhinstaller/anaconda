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

import { getDevicesAction, getDiskSelectionAction } from "../actions/storage-actions.js";
import { scanDevicesWithTask, runStorageTask } from "../apis/storage.js";
import { resetPartitioning } from "../apis/storage_partitioning.js";

/* Get the list of names of all the ancestors of the given device
 * (including the device itself)
 * @param {Object} deviceData - The device data object
 * @param {string} device - The name of the device
 * @returns {Array}
 */
const getDeviceAncestors = (deviceData, device) => {
    // device ancestors including the device itself
    const ancestors = [];
    const deviceParents = deviceData[device]?.parents?.v || [];

    ancestors.push(device);
    deviceParents.forEach(parent => {
        ancestors.push(...getDeviceAncestors(deviceData, parent));
    });

    return ancestors;
};

/* Check if the given device is a descendant of the given ancestor
 * @param {string} device - The name of the device
 * @param {string} rootDevice - The name of the ancestor
 * @param {Object} deviceData - The device data object
 * @returns {boolean}
 */
export const checkDeviceInSubTree = ({ device, rootDevice, deviceData }) => {
    return getDeviceChildren({ deviceData, device: rootDevice }).includes(device);
};

/* Get the list of names of all the descendants of the given device
 * (including the device itself)
 * @param {string} device - The name of the device
 * @param {Object} deviceData - The device data object
 * @returns {Array}
 */
export const getDeviceChildren = ({ deviceData, device }) => {
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

/* Get the list of names of all LUKS devices
 * @param {Object} deviceData - The device data object
 * @param {Array} requests - The list of requests from a partitioning
 * @returns {Array}
 */
export const getLockedLUKSDevices = (requests, deviceData) => {
    const devs = requests?.map(r => r["device-spec"]) || [];

    // check for requests and all their ancestors for locked LUKS devices
    const requestsAncestors = [];
    devs.forEach(d => {
        const ancestors = getDeviceAncestors(deviceData, d);
        requestsAncestors.push(...ancestors);
    });

    return Object.keys(deviceData).filter(d => {
        return (
            requestsAncestors.includes(d) &&
            deviceData[d].formatData.type.v === "luks" &&
            deviceData[d].formatData.attrs.v.has_key !== "True"
        );
    });
};

/* Check if the requests array contains duplicate entries
 * @param {Array} requests - The list of requests from a partitioning
 * @param {string} fieldName - The name of the field to check for duplicates, ex: "mount-point"
 * @returns {boolean}
 */
export const hasDuplicateFields = (requests, fieldName) => {
    let _requests = requests;
    if (fieldName === "mount-point") {
        /* Swap devices have empty mount points and multiple swap devices are allowed
         * so we need to remove these before checking for duplicates
         */
        _requests = requests.filter(r => r["format-type"] !== "swap");
    }
    const items = _requests.map(r => r[fieldName]);

    return new Set(items).size !== items.length;
};

/* Check if the requests array contains duplicate entries for a given field value
 * @param {Array} requests - The list of requests from a partitioning
 * @param {string} fieldName - The name of the field to check for duplicates, ex: "mount-point"
 * @param {string} fieldValue - The value of the field to check for duplicates, ex: "/boot"
 * @returns {boolean}
 */
export const isDuplicateRequestField = (requests, fieldName, fieldValue) => {
    return requests.filter((request) => request[fieldName] === fieldValue).length > 1;
};

export const rescanDevices = ({ onSuccess, onFail, dispatch }) => {
    return scanDevicesWithTask()
            .then(task => {
                return runStorageTask({
                    task,
                    onSuccess: () => resetPartitioning()
                            .then(() => Promise.all([
                                dispatch(getDevicesAction()),
                                dispatch(getDiskSelectionAction())
                            ]))
                            .finally(onSuccess)
                            .catch(onFail),
                    onFail
                });
            });
};
