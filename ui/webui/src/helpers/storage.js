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

export const isDuplicateRequestField = (requests, fieldName, fieldValue) => {
    return requests.filter((request) => request[fieldName] === fieldValue).length > 1;
};
