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
import React, { useEffect, useState } from "react";

import { useDialogs } from "dialogs.jsx";
import { ModalError } from "cockpit-components-inline-notification.jsx";

import {
    Button,
    DropdownItem,
    Flex,
    FlexItem,
    Form,
    FormFieldGroup,
    FormFieldGroupHeader,
    FormGroup,
    Label,
    List,
    ListItem,
    Modal,
    TextInput,
} from "@patternfly/react-core";

import {
    getCanSetInitiator,
    getInitiator,
    getIsSupported,
    runDiscover,
    runLogin,
    setInitiator
} from "../../apis/storage_iscsi.js";
import {
    objectFromDBus
} from "../../helpers/utils.js";
import {
    rescanDevices
} from "../../helpers/storage.js";

const _ = cockpit.gettext;
const idPrefix = "add-iscsi-target-dialog";

export const AddISCSITarget = ({ devices, dispatch }) => {
    const [isSupported, setIsSupported] = useState(false);
    const Dialogs = useDialogs();

    useEffect(() => {
        const updateFields = async () => {
            const _isSupported = await getIsSupported();
            setIsSupported(_isSupported);
        };
        updateFields();
    }, []);

    const open = () => Dialogs.show(<DiscoverISCSITargetModal devices={devices} dispatch={dispatch} />);

    return (
        <DropdownItem
          id={idPrefix + "-button"}
          value="iscsi"
          isDisabled={!isSupported}
          onClick={open}
        >
            {_("Add iSCSI target")}
        </DropdownItem>
    );
};

const DiscoverISCSITargetModal = ({ devices, dispatch }) => {
    const [canSetInitiator, setCanSetInitiator] = useState(false);
    const [discoveryUsername, setDiscoveryUsername] = useState("");
    const [discoveryPassword, setDiscoveryPassword] = useState("");
    const [discoveredTargets, setDiscoveredTargets] = useState();
    const [isInProgress, setIsInProgress] = useState(false);
    const [error, setError] = useState(null);
    const [initiatorName, setInitiatorName] = useState("");
    const [targetIPAddress, setTargetIPAddress] = useState("");
    const portal = { "ip-address": targetIPAddress };

    const Dialogs = useDialogs();

    useEffect(() => {
        const updateFields = async () => {
            try {
                const _initiatorName = await getInitiator();
                setInitiatorName(_initiatorName);

                const _canSetInitiator = await getCanSetInitiator();
                setCanSetInitiator(_canSetInitiator);
            } catch (e) {
                setError(e);
            }
        };
        updateFields();
    }, []);

    const onSubmit = async () => {
        setError(null);
        setIsInProgress(true);
        await setInitiator({ initiator: initiatorName });
        await runDiscover({
            portal,
            credentials: { username: discoveryUsername, password: discoveryPassword },
            onSuccess: async res => {
                setDiscoveredTargets(res.map(objectFromDBus));
                setIsInProgress(false);
            },
            onFail: async (exc) => {
                setIsInProgress(false);
                setError(exc);
            },
        });
    };

    return (
        <Modal
          position="top" variant="large" id={`${idPrefix}-discover-modal`}
          isOpen
          onClose={() => Dialogs.close()}
          title={_("Discover iSCSI targets")}
          footer={
              <>
                  <Button
                    id={`${idPrefix}-discover`}
                    isDisabled={isInProgress}
                    isLoading={isInProgress}
                    onClick={onSubmit}
                  >
                      {_("Start discovery")}
                  </Button>
                  <Button
                    id={`${idPrefix}-cancel`}
                    isDisabled={isInProgress}
                    onClick={() => Dialogs.close()}
                    variant="link"
                  >
                      {_("Cancel")}
                  </Button>
              </>
          }
        >
            <Form isHorizontal>
                {error && <ModalError dialogError={error.message} id={`${idPrefix}-error`} />}
                <FormGroup
                  label={_("Initiator name")}
                  fieldId={`${idPrefix}-initiator-name`}
                >
                    <TextInput
                      id={`${idPrefix}-initiator-name`}
                      isDisabled={isInProgress || !canSetInitiator}
                      value={initiatorName}
                      onChange={(_, value) => setInitiatorName(value)}
                    />
                </FormGroup>
                <FormGroup
                  label={_("Target IP address")}
                  fieldId={`${idPrefix}-target-ip-address`}
                >
                    <TextInput
                      id={`${idPrefix}-target-ip-address`}
                      isDisabled={isInProgress}
                      onChange={(_, value) => setTargetIPAddress(value)}
                      value={targetIPAddress}
                    />
                </FormGroup>
                <FormFieldGroup
                  header={
                      <FormFieldGroupHeader
                        titleText={{ text: _("CHAP discovery authentication") }}
                      />
                  }
                >
                    <FormGroup
                      label={_("User name")}
                      fieldId={`${idPrefix}-discovery-username`}
                    >
                        <TextInput
                          id={`${idPrefix}-discovery-username`}
                          isDisabled={isInProgress}
                          value={discoveryUsername}
                          onChange={(_, value) => setDiscoveryUsername(value)}
                        />
                    </FormGroup>
                    <FormGroup
                      label={_("Password")}
                      fieldId={`${idPrefix}-discovery-password`}
                    >
                        <TextInput
                          id={`${idPrefix}-discovery-password`}
                          isDisabled={isInProgress}
                          type="password"
                          value={discoveryPassword}
                          onChange={(_, value) => setDiscoveryPassword(value)}
                        />
                    </FormGroup>
                </FormFieldGroup>
                <FormFieldGroup
                  header={
                      <FormFieldGroupHeader
                        titleText={{ text: _("Available targets") }}
                      />
                  }
                >
                    <List isPlain id={`${idPrefix}-available-targets`}>
                        {Object.keys(devices)
                                ?.map(target => devices[target])
                                .map(target => (
                                    <ListItem key={target.name?.v}>
                                        <Flex>
                                            <FlexItem>{target.attrs?.v.target}</FlexItem>
                                            <Label color="green" variant="fill">
                                                {_("Connected")}
                                            </Label>
                                        </Flex>
                                    </ListItem>
                                )) || []}
                        {discoveredTargets
                                ?.map(target => (
                                    <ListItem key={target.name}>
                                        <Flex>
                                            <FlexItem>{target.name}</FlexItem>
                                            <Button variant="link" onClick={() => Dialogs.show(<LoginISCSITargetModal target={target} portal={portal} dispatch={dispatch} />)}>
                                                {_("Login")}
                                            </Button>
                                        </Flex>
                                    </ListItem>
                                )) || []}
                    </List>
                </FormFieldGroup>
            </Form>
        </Modal>
    );
};

const LoginISCSITargetModal = ({ target, portal, dispatch }) => {
    const [chapPassword, setChapPassword] = useState("");
    const [chapUsername, setChapUsername] = useState("");
    const [error, setError] = useState(null);
    const [loginInProgress, setLoginInProgress] = useState(false);

    const Dialogs = useDialogs();

    const onSubmit = () => {
        setError(null);
        setLoginInProgress(true);

        return (
            runLogin({
                portal,
                credentials: { username: chapUsername, password: chapPassword },
                node: target,
                onSuccess: () => {
                    setLoginInProgress(true);
                    return rescanDevices({
                        onSuccess: () => Dialogs.close(),
                        onFail: setError,
                        dispatch,
                    });
                },
                onFail: exc => {
                    setLoginInProgress(false);
                    setError(exc);
                },
            })
        );
    };

    return (
        <Modal
          position="top" variant="large" id={`${idPrefix}-login-modal`}
          isOpen
          onClose={() => Dialogs.close()}
          title={cockpit.format(_("Login to iSCSI target $0"), target.name)}
          footer={
              <>
                  <Button
                    id={`${idPrefix}-login`}
                    isDisabled={loginInProgress}
                    isLoading={loginInProgress}
                    onClick={onSubmit}
                  >
                      {_("Login")}
                  </Button>
                  <Button
                    id={`${idPrefix}-cancel`}
                    isDisabled={loginInProgress}
                    onClick={() => Dialogs.close()}
                    variant="link"
                  >
                      {_("Cancel")}
                  </Button>
              </>
          }
        >
            <Form isHorizontal>
                {error && <ModalError dialogError={error.message} id={`${idPrefix}-error`} />}
                <FormFieldGroup
                  header={
                      <FormFieldGroupHeader
                        titleText={{ text: _("CHAP credentials for initiator authentication by target") }}
                      />
                  }
                >
                    <FormGroup
                      label={_("User name")}
                      fieldId={`${idPrefix}-chap-username`}
                    >
                        <TextInput
                          id={`${idPrefix}-chap-username`}
                          isDisabled={loginInProgress}
                          value={chapUsername}
                          onChange={(_, value) => setChapUsername(value)}
                        />
                    </FormGroup>
                    <FormGroup
                      label={_("Password")}
                      fieldId={`${idPrefix}-chap-password`}
                    >
                        <TextInput
                          id={`${idPrefix}-chap-password`}
                          isDisabled={loginInProgress}
                          type="password"
                          value={chapPassword}
                          onChange={(_, value) => setChapPassword(value)}
                        />
                    </FormGroup>
                </FormFieldGroup>
            </Form>
        </Modal>
    );
};
