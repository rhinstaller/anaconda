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

import { PasswordFormFields } from "../Password.jsx";

const _ = cockpit.gettext;

const rules = [
    {
        id: "length",
        text: (policy) => cockpit.format(_("Must be at least $0 characters"), policy["min-length"].v),
        check: (policy, password) => password.length >= policy["min-length"].v,
        isWarning: false,
    },
];

const CreateAccount = ({
    idPrefix,
    passwordPolicy,
    setIsUserValid,
}) => {
    const [fullName, setFullName] = useState();
    const [userAccount, setUserAccount] = useState();
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [isPasswordValid, setIsPasswordValid] = useState(false);

    useEffect(() => {
        setIsUserValid(isPasswordValid);
    }, [setIsUserValid, isPasswordValid]);

    const passphraseForm = (
        <PasswordFormFields
          idPrefix={idPrefix + "-create-account-password-form"}
          policy={passwordPolicy}
          initialPassword={password}
          passwordLabel={_("Passphrase")}
          initialConfirmPassword={confirmPassword}
          confirmPasswordLabel={_("Confirm passphrase")}
          rules={rules}
          onChange={setPassword}
          onConfirmChange={setConfirmPassword}
          setIsValid={setIsPasswordValid}
        />
    );

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
            {passphraseForm}
        </Form>
    );
};

export const Accounts = ({
    idPrefix,
    setIsFormValid,
    passwordPolicies,
}) => {
    const [isUserValid, setIsUserValid] = useState();
    useEffect(() => {
        setIsFormValid(isUserValid);
    }, [setIsFormValid, isUserValid]);

    return (
        <>
            <CreateAccount
              idPrefix={idPrefix}
              passwordPolicy={passwordPolicies.user}
              setIsUserValid={setIsUserValid}
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
