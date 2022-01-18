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
import React, { useState, useContext, useEffect } from "react";

import {
    Checkbox,
    Form, FormGroup,
    PageSection,
} from "@patternfly/react-core";

import { useEvent, useObject } from "hooks";

import { password_quality as passwordQuality, PasswordFormFields } from "cockpit-components-password.jsx";
import { AddressContext, Header } from "../Common.jsx";

const _ = cockpit.gettext;

export const RootAccount = () => {
    const [errors, setErrors] = useState({});
    const [isLocked, setIsLocked] = useState();
    const [pwd, setPwd] = useState("");
    const [pwdConfirm, setPwdConfirm] = useState("");
    const [pwdMessage, setPwdMessage] = useState("");
    const [pwdStrength, setPwdStrength] = useState("");
    const address = useContext(AddressContext);

    const usersProxy = useObject(() => {
        const client = cockpit.dbus("org.fedoraproject.Anaconda.Modules.Users", { superuser: "try", bus: "none", address });
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Users",
            "/org/fedoraproject/Anaconda/Modules/Users",
        );
        setIsLocked(proxy.IsRootAccountLocked);

        return proxy;
    }, null, [address]);

    useEvent(usersProxy, "changed", (event, data) => {
        setIsLocked(data.IsRootAccountLocked);
    });

    useEffect(() => {
        if (pwd) {
            passwordQuality(pwd)
                    .then(strength => {
                        setErrors({});
                        setPwdStrength(strength.value);
                        setPwdMessage(strength.message || "");
                    })
                    .catch(ex => {
                        const errors = {};
                        errors.pwd = (ex.message || ex.toString()).replace("\n", " ");
                        setErrors(errors);
                        setPwdStrength(0);
                        setPwdMessage("");
                    });
        } else {
            setPwdStrength("");
        }
    }, [pwd]);

    const onPwdChange = (type, value) => {
        if (type === "password") {
            setPwd(value);
        }
        if (type === "password_confirm") {
            setPwdConfirm(value);
        }
    };

    const onDoneClicked = () => {
        usersProxy.SetRootAccountLocked(isLocked);
        // TODO Set crypted root password
        cockpit.location.go(["summary"]);
    };

    return (
        <>
            <Header
              done={onDoneClicked}
              title={_("Root password")}
            />
            <PageSection>
                <Form isHorizontal>
                    <PasswordFormFields
                      change={onPwdChange}
                      error_password={errors && errors.pwd}
                      idPrefix="root-account-set-pwd"
                      password={pwd}
                      password_confirm={pwdConfirm}
                      password_confirm_label={_("Confirm root password")}
                      password_label={_("Root password")}
                      password_message={pwdMessage}
                      password_strength={pwdStrength}
                    />
                    <FormGroup fieldId="root-account-lock">
                        <Checkbox
                          id="root-account-lock"
                          isChecked={isLocked}
                          isDisabled={isLocked === undefined}
                          label={_("Lock root account")}
                          onChange={setIsLocked}
                        />
                    </FormGroup>
                </Form>
            </PageSection>
        </>
    );
};
