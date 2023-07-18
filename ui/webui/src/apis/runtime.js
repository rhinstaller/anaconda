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

export class RuntimeClient {
    constructor (address) {
        if (RuntimeClient.instance && (!address || RuntimeClient.instance.address === address)) {
            return RuntimeClient.instance;
        }

        RuntimeClient.instance?.client.close();

        RuntimeClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Modules.Runtime",
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener(
            "close", () => console.error("Runtime client closed")
        );
    }
}

/**
 *
 * @returns {Promise}           Reports if the given OS release is considered final
 */
export const getIsFinal = () => {
    return (
        new RuntimeClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Runtime/UserInterface",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Runtime.UserInterface",
                "IsFinal",
            ]
        )
                .then(res => res[0].v)
    );
};
