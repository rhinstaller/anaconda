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
import { StorageClient } from "./storage.js";
import { _setProperty } from "./helpers.js";

const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Storage.Bootloader";
const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage/Bootloader";

const setProperty = (...args) => {
    return _setProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

/**
 * @param {string} drive     A drive name
 */
export const setBootloaderDrive = ({ drive }) => {
    return setProperty("Drive", cockpit.variant("s", drive));
};
