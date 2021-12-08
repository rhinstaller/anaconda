/*
 * This file is part of Cockpit.
 *
 * Copyright (C) 2021 Red Hat, Inc.
 *
 * Cockpit is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * Cockpit is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with Cockpit; If not, see <http://www.gnu.org/licenses/>.
 */

import cockpit from 'cockpit';
import React, { useEffect, useState } from 'react';
import {
    Card, CardBody, CardTitle,
    DescriptionList, DescriptionListGroup, DescriptionListTerm, DescriptionListDescription,
    Switch,
} from '@patternfly/react-core';

import { useEvent, useObject } from 'hooks';

export const Application = () => {
    const [timezoneProps, setTimezoneProps] = useState();
    const [address, setAddress] = useState();

    const timezoneProxy = useObject(() => {
        const client = cockpit.dbus("org.fedoraproject.Anaconda.Modules.Timezone", { superuser: "try", bus: "none", address });
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Timezone",
            "/org/fedoraproject/Anaconda/Modules/Timezone",
        );
        setTimezoneProps(proxy.data);

        return proxy;
    }, null, [address]);

    useEvent(timezoneProxy, "changed", (event, data) => setTimezoneProps(data));
    useEffect(() => cockpit.file("/run/anaconda/bus.address").watch(setAddress), []);

    return (
        <Card>
            <CardTitle>Anaconda Web UI</CardTitle>
            <CardBody>
                {timezoneProps &&
                <DescriptionList isHorizontal>
                    {Object.keys(timezoneProps).map(prop => {
                        return (
                            <DescriptionListGroup key={prop}>
                                <DescriptionListTerm>{prop}</DescriptionListTerm>
                                <DescriptionListDescription>
                                    {prop === "NTPEnabled"
                                        ? <Switch
                                            isChecked={timezoneProps[prop]}
                                            label="On"
                                            labelOff="Off"
                                            onChange={enabled => timezoneProxy.SetNTPEnabled(enabled)} />
                                        : timezoneProps[prop].toString()}
                                </DescriptionListDescription>
                            </DescriptionListGroup>
                        );
                    })}
                </DescriptionList>}
            </CardBody>
        </Card>
    );
};
