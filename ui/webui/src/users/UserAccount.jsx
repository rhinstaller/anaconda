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
import React, { useState, useContext, /* useEffect */ } from "react";

import {
    Form,
    FormGroup,
    TextInput,
    PageSection
} from "@patternfly/react-core";

import { AddressContext, Header } from "../Common.jsx";

const _ = cockpit.gettext;

import { useEvent, useObject } from "hooks";

export const UserAccount = () => {
    const [name, setName] = useState();
    const [gecos, setGecos] = useState();
    const address = useContext(AddressContext);

    const usersProxy = useObject(() => {
        const client = cockpit.dbus("org.fedoraproject.Anaconda.Modules.Users", { superuser: "try", bus: "none", address });
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Users",
            "/org/fedoraproject/Anaconda/Modules/Users",
        );

        return proxy;
    }, null, [address]);

    const onUsernameChange = (value) => {
        // console.log("onUsernameChange: " + value);
        setName(value);
    };

    const onGecosChange = (value) => {
        // console.log("onGecosChange: " + value);
        setGecos(value);
    };

    useEvent(usersProxy, "changed", (event, data) => {
        // setUiSomething(data.DBusProxySomething);
    });

    const onDoneClicked = () => {
        const user = {
            gecos: cockpit.variant("s", gecos),
            name: cockpit.variant("s", name),
            uid: cockpit.variant("u", 0),
            groups: cockpit.variant("as", ["wheel"]),
            "uid-mode": cockpit.variant("s", "ID_MODE_USE_DEFAULT"),
            gid: cockpit.variant("u", 0),
            "gid-mode": cockpit.variant("s", "ID_MODE_USE_DEFAULT"),
            homedir: cockpit.variant("s", ""),
            password: cockpit.variant("s", ""),
            "is-crypted": cockpit.variant("b", true),
            lock: cockpit.variant("b", false),
            shell: cockpit.variant("s", ""),
        };
        console.log("onDoneClicked, user: " + user);
        usersProxy.SetUsers([user]);
        cockpit.location.go(["summary"]);
    };

    return (
        <>
            <Header
              done={onDoneClicked}
              title={_("Create user")}
            />
            <PageSection>
                <Form isHorizontal>
                    <FormGroup label={_("Real name")}>
                        <TextInput id="gecos" onChange={onGecosChange} placeholder="John Doe" />
                    </FormGroup>
                    <FormGroup label={_("User name")}>
                        <TextInput id="name" onChange={onUsernameChange} placeholder="jdoe" />
                    </FormGroup>
                </Form>
            </PageSection>
        </>
    );
};
