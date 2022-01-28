/*
 * Copyright (C) 2021 Red Hat, Inc.
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
import React, { useEffect, useState } from "react";

import {
    Page,
} from "@patternfly/react-core";

import { InstallationLanguage } from "./InstallationLanguage.jsx";
import { Summary } from "./Summary.jsx";
import { AddressContext } from "./Common.jsx";

import { usePageLocation } from "hooks";

export const Application = () => {
    const [address, setAddress] = useState();
    const { path } = usePageLocation();

    useEffect(() => cockpit.file("/run/anaconda/bus.address").watch(setAddress), []);

    return (
        <Page>
            <AddressContext.Provider value={address}>
                {!path.length > 0 && <InstallationLanguage />}
            </AddressContext.Provider>
            {path.length > 0 &&
            <AddressContext.Provider value={address}>
                <Summary />
            </AddressContext.Provider>}
        </Page>
    );
};
