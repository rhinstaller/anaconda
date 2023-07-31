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

import {
    Button,
    Form,
    FormGroup,
    FormHelperText,
    HelperText,
    HelperTextItem,
    Modal,
    TextArea,
    TextContent,
    TextVariants,
    Text,
} from "@patternfly/react-core";
import { ExternalLinkAltIcon } from "@patternfly/react-icons";

import { exitGui } from "../helpers/exit.js";

const _ = cockpit.gettext;

export const bugzillaPrefiledReportURL = (productQueryData) => {
    const baseURL = "https://bugzilla.redhat.com";
    const queryData = {
        ...productQueryData,
        component: "anaconda",
    };

    const reportURL = new URL(baseURL);
    reportURL.pathname = "enter_bug.cgi";
    Object.keys(queryData).map(query => reportURL.searchParams.append(query, queryData[query]));
    return reportURL.href;
};

const addExceptionDataToReportURL = (url, exception) => {
    const newUrl = new URL(url);
    newUrl.searchParams.append(
        "short_desc",
        "WebUI: " + exception.message
    );
    newUrl.searchParams.append(
        "comment",
        "Installer WebUI Critical Error:\n" + exception.name + ": " + exception.message + "\n\n" + _("Please attach the file /tmp/webui.log to the issue.")
    );
    return newUrl.href;
};

export const CriticalError = ({ exception, isBootIso, reportLinkURL }) => {
    const reportURL = addExceptionDataToReportURL(reportLinkURL, exception);
    const [logContent, setLogContent] = useState("");

    useEffect(() => {
        const syslogFile = cockpit.file("/tmp/syslog");
        syslogFile.read().then(content => setLogContent(content));
    }, []);

    const openBZIssue = (reportURL) => {
        cockpit.file("/tmp/webui.log").replace(logContent)
                .then(window.open(reportURL, "_blank"));
    };

    return (
        <Modal
          description={_("The installer cannot continue due to a critical error.")}
          id="critical-error-modal"
          isOpen
          position="top"
          showClose={false}
          title={_("Critical error")}
          titleIconVariant="danger"
          variant="small"
          footer={
              <>
                  {reportLinkURL &&
                  <Button
                    variant="primary"
                    icon={<ExternalLinkAltIcon />}
                    onClick={() => openBZIssue(reportURL)}
                    component="a">
                      {_("Send issue to Bugzilla")}
                  </Button>}
                  <Button variant="secondary" onClick={exitGui}>
                      {isBootIso ? _("Reboot") : _("Quit")}
                  </Button>
              </>
          }>
            <Form>
                <FormGroup label={_("Details")}>
                    {exception.contextData?.context &&
                    <TextContent>
                        <Text component={TextVariants.p}>
                            {exception.contextData.context}
                        </Text>
                    </TextContent>}
                    {exception.contextData?.hint &&
                    <TextContent>
                        <Text component={TextVariants.p}>
                            {cockpit.format(_("Hint: $0"), exception.contextData.hint)}
                        </Text>
                    </TextContent>}
                </FormGroup>
                <FormGroup label={_("Error")}>
                    <TextContent>
                        <Text component={TextVariants.p}>
                            {exception.name + ": " + exception.message}
                        </Text>
                    </TextContent>
                </FormGroup>
                <FormGroup
                  label={_("Log attachment")}
                >
                    <FormHelperText isHidden={false}>
                        <HelperText>
                            <HelperTextItem>{_("Please review the content of the log to be attached optionally when opening the Bugzilla issue report and remove any sensitive information if you agree with attaching the log.")}</HelperTextItem>
                        </HelperText>
                    </FormHelperText>
                    <TextArea
                      value={logContent}
                      onChange={setLogContent}
                      aria-label="review-attached-log"
                    />
                </FormGroup>
            </Form>
        </Modal>
    );
};

export const errorHandlerWithContext = (contextData, handler) => {
    return (exception) => {
        exception.contextData = contextData;
        handler(exception);
    };
};
