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
import { debounce } from "throttle-debounce";

import {
    Form,
    FormGroup,
    FormHelperText,
    HelperText,
    TextInput,
    Title,
} from "@patternfly/react-core";

import "./Accounts.scss";

import { PasswordFormFields, ruleLength } from "../Password.jsx";

const _ = cockpit.gettext;

export function getAccountsState (
    fullName = "",
    userAccount = "",
    password = "",
    confirmPassword = "",
) {
    return {
        fullName,
        userAccount,
        password,
        confirmPassword,
    };
}

export const accountsToDbusUsers = (accounts) => {
    return [{
        name: cockpit.variant("s", accounts.userAccount || ""),
        gecos: cockpit.variant("s", accounts.fullName || ""),
        password: cockpit.variant("s", accounts.password || ""),
        "is-crypted": cockpit.variant("b", false),
        groups: cockpit.variant("as", ["wheel"]),
    }];
};

const reservedNames = [
    "root",
    "bin",
    "daemon",
    "adm",
    "lp",
    "sync",
    "shutdown",
    "halt",
    "mail",
    "operator",
    "games",
    "ftp",
    "nobody",
    "home",
    "system",
];

const isUserAccountWithInvalidCharacters = (userAccount) => {
    return (
        userAccount === "." ||
        userAccount === ".." ||
        userAccount.match(/^[0-9]+$/) ||
        !userAccount.match(/^[A-Za-z0-9._][A-Za-z0-9._-]{0,30}([A-Za-z0-9._-]|\$)?$/)
    );
};

const CreateAccount = ({
    idPrefix,
    passwordPolicy,
    setIsUserValid,
    accounts,
    setAccounts,
}) => {
    const [fullName, setFullName] = useState(accounts.fullName);
    const [_userAccount, _setUserAccount] = useState(accounts.userAccount);
    const [userAccount, setUserAccount] = useState(accounts.userAccount);
    const [userAccountInvalidHint, setUserAccountInvalidHint] = useState("");
    const [isUserAccountValid, setIsUserAccountValid] = useState(null);
    const [password, setPassword] = useState(accounts.password);
    const [confirmPassword, setConfirmPassword] = useState(accounts.confirmPassword);
    const [isPasswordValid, setIsPasswordValid] = useState(false);

    useEffect(() => {
        debounce(300, () => setUserAccount(_userAccount))();
    }, [_userAccount, setUserAccount]);

    useEffect(() => {
        setIsUserValid(isPasswordValid && isUserAccountValid);
    }, [setIsUserValid, isPasswordValid, isUserAccountValid]);

    useEffect(() => {
        let valid = true;
        setUserAccountInvalidHint("");
        if (userAccount.length === 0) {
            valid = null;
        } else if (userAccount.length > 32) {
            valid = false;
            setUserAccountInvalidHint(_("The user name is too long"));
        } else if (reservedNames.includes(userAccount)) {
            valid = false;
            setUserAccountInvalidHint(_("Sorry, that user name is not available. Please try another."));
        } else if (isUserAccountWithInvalidCharacters(userAccount)) {
            valid = false;
            setUserAccountInvalidHint(cockpit.format(_("The user name should usually only consist of lower case letters from a-z, digits and the following characters: $0"), "-_"));
        }
        setIsUserAccountValid(valid);
    }, [userAccount]);

    const passphraseForm = (
        <PasswordFormFields
          idPrefix={idPrefix}
          policy={passwordPolicy}
          initialPassword={password}
          passwordLabel={_("Passphrase")}
          initialConfirmPassword={confirmPassword}
          confirmPasswordLabel={_("Confirm passphrase")}
          rules={[ruleLength]}
          onChange={setPassword}
          onConfirmChange={setConfirmPassword}
          setIsValid={setIsPasswordValid}
        />
    );

    useEffect(() => {
        setAccounts(ac => ({ ...ac, fullName, userAccount, password, confirmPassword }));
    }, [setAccounts, fullName, userAccount, password, confirmPassword]);

    return (
        <Form
          isHorizontal
          id={idPrefix}
        >
            <Title
              headingLevel="h2"
              id={idPrefix + "-title"}
            >
                {_("Create account")}
            </Title>
            {_("This account will have administration priviledge with sudo.")}
            <FormGroup
              label={_("Full name")}
              fieldId={idPrefix + "-full-name"}
            >
                <TextInput
                  id={idPrefix + "-full-name"}
                  value={fullName}
                  onChange={(_event, val) => setFullName(val)}
                />
            </FormGroup>
            <FormGroup
              label={_("User account")}
              fieldId={idPrefix + "-user-account"}
            >
                <TextInput
                  id={idPrefix + "-user-account"}
                  value={_userAccount}
                  onChange={(_event, val) => _setUserAccount(val)}
                  validated={isUserAccountValid === null ? "default" : isUserAccountValid ? "success" : "error"}
                />
                <FormHelperText>
                    <HelperText component="ul" aria-live="polite" id={idPrefix + "-full-name-helper"}>
                        {userAccountInvalidHint}
                    </HelperText>
                </FormHelperText>
            </FormGroup>
            {passphraseForm}
        </Form>
    );
};

export const Accounts = ({
    idPrefix,
    setIsFormValid,
    passwordPolicies,
    accounts,
    setAccounts,
}) => {
    const [isUserValid, setIsUserValid] = useState();
    useEffect(() => {
        setIsFormValid(isUserValid);
    }, [setIsFormValid, isUserValid]);

    return (
        <>
            <CreateAccount
              idPrefix={idPrefix + "-create-account"}
              passwordPolicy={passwordPolicies.user}
              setIsUserValid={setIsUserValid}
              accounts={accounts}
              setAccounts={setAccounts}
            />
        </>
    );
};

export const getPageProps = ({ isBootIso }) => {
    return ({
        id: "accounts",
        label: _("Create Account"),
        isHidden: !isBootIso,
        title: null,
    });
};
