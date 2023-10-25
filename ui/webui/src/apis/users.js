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
import { _setProperty } from "./helpers.js";

const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Users";
const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Users";

const setProperty = (...args) => {
    return _setProperty(UsersClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class UsersClient {
    constructor (address) {
        if (UsersClient.instance && (!address || UsersClient.instance.address === address)) {
            return UsersClient.instance;
        }

        UsersClient.instance?.client.close();

        UsersClient.instance = this;

        this.client = cockpit.dbus(
            INTERFACE_NAME,
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener(
            "close", () => console.error("Users client closed")
        );
    }
}

/**
 * @param {Array.<Object>} users An array of user objects
 */
export const setUsers = (users) => {
    return setProperty("Users", cockpit.variant("aa{sv}", users));
};
