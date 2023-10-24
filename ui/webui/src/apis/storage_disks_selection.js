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

import {
    StorageClient,
} from "./storage.js";

/**
 * @returns {Promise}           Resolves all properties of DiskSelection interface
 */
export const getAllDiskSelection = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.freedesktop.DBus.Properties",
        "GetAll",
        ["org.fedoraproject.Anaconda.Modules.Storage.DiskSelection"],
    );
};

/**
 * @returns {Promise}           Resolves a list with disk names
 */
export const getUsableDisks = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
        "GetUsableDisks", []
    );
};

/**
 * @returns {Promise}           The list of selected disks
 */
export const getSelectedDisks = () => {
    return (
        new StorageClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
                "SelectedDisks"
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {Array.<string>} drives A list of drives names
 */
export const setSelectedDisks = ({ drives }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
            "SelectedDisks",
            cockpit.variant("as", drives)
        ]
    );
};
