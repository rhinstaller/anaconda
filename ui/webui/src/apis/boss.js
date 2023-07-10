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

/**
 * @param {string} address      Anaconda bus address
 *
 * @returns {Object}            A DBus client for the Boss bus
 */
export class BossClient {
    constructor (address) {
        if (BossClient.instance && (!address || BossClient.instance.address === address)) {
            return BossClient.instance;
        }

        BossClient.instance?.client.close();

        BossClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Boss",
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener("close", () => console.error("Boss client closed"));
    }
}

/**
 * @param {string} task         DBus path to a task
 *
 * @returns {Promise}           Resolves the total number of tasks
 */
export const getSteps = ({ task }) => {
    return new BossClient().client.call(
        task,
        "org.freedesktop.DBus.Properties",
        "Get",
        ["org.fedoraproject.Anaconda.Task", "Steps"]
    )
            .then(ret => ret[0]);
};

/**
 * @returns {Promise}           Resolves a list of tasks
 */
export const installWithTasks = () => {
    return new BossClient().client.call(
        "/org/fedoraproject/Anaconda/Boss",
        "org.fedoraproject.Anaconda.Boss",
        "InstallWithTasks", []
    )
            .then(ret => ret[0]);
};

/**
 * @param {string} locale       Locale id
 */
export const setLocale = ({ locale }) => {
    return new BossClient().client.call(
        "/org/fedoraproject/Anaconda/Boss",
        "org.fedoraproject.Anaconda.Boss",
        "SetLocale", [locale]
    );
};
