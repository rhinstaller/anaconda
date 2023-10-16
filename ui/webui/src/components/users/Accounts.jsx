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
import React, { useState, useEffect } from "react";

import {
    Form,
    FormGroup,
    TextInput,
    Title,
} from "@patternfly/react-core";

import "./Accounts.scss";

const _ = cockpit.gettext;

const CreateAccount = ({
    idPrefix,
}) => {
    const [fullName, setFullName] = useState();
    const [userAccount, setUserAccount] = useState();
    const [password, setPassword] = useState();
    const [confirmPassword, setConfirmPassword] = useState();

    return (
        <Form
          isHorizontal
          id={idPrefix + "-create-account"}
        >
            <Title
              headingLevel="h2"
              id={idPrefix + "-create-account-title"}
            >
                {_("Create account")}
            </Title>
            {_("This account will have administration priviledge with sudo.")}
            <FormGroup
              label={_("Full name")}
              fieldId={idPrefix + "-create-account-full-name"}
            >
                <TextInput
                  id={idPrefix + "-create-account-full-name"}
                  value={fullName}
                  onChange={(_event, val) => setFullName(val)}
                />
            </FormGroup>
            <FormGroup
              label={_("User account")}
              fieldId={idPrefix + "-create-account-user-account"}
            >
                <TextInput
                  id={idPrefix + "-create-account-user-account"}
                  value={userAccount}
                  onChange={(_event, val) => setUserAccount(val)}
                />
            </FormGroup>
            <FormGroup
              label={_("Password")}
              fieldId={idPrefix + "-create-account-password"}
            >
                <TextInput
                  id={idPrefix + "-create-account-password"}
                  value={password}
                  onChange={(_event, val) => setPassword}
                />
            </FormGroup>
            <FormGroup
              label={_("Confirm password")}
              fieldId={idPrefix + "-create-account-confirm-password"}
            >
                <TextInput
                  id={idPrefix + "-create-account-confirm-password"}
                  value={confirmPassword}
                  onChange={(_event, val) => setConfirmPassword}
                />
            </FormGroup>
        </Form>
    );
};

export const Accounts = ({
    idPrefix,
    setIsFormValid,
}) => {
    useEffect(() => {
        setIsFormValid(true);
    }, [setIsFormValid]);

    return (
        <>
            <CreateAccount
              idPrefix={idPrefix}
            />
        </>
    );
};

export const getPageProps = () => {
    return ({
        id: "accounts",
        label: _("Create Account"),
        title: null,
    });
};
