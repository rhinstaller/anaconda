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
import React from "react";

import {
    Button,
    Modal,
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
        "Instructions about what to fill here and which logs tarball to attach"
    );
    return newUrl.href;
};

export const CriticalError = ({ exception, isBootIso, reportLinkURL }) => {
    const reportURL = addExceptionDataToReportURL(reportLinkURL, exception);

    const openBZIssue = (reportURL) => {
        window.open(reportURL, "_blank");
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
            {exception.contextData?.context &&
            <TextContent>
                <Text component={TextVariants.p}>
                    {cockpit.format(_("Action: $0"), exception.contextData.context)}
                </Text>
            </TextContent>}
            <TextContent>
                <Text component={TextVariants.p}>
                    {cockpit.format(_("Error: $0"), exception.message)}
                </Text>
            </TextContent>
            {exception.contextData?.hint &&
            <TextContent>
                <Text component={TextVariants.p}>
                    {cockpit.format(_("Hint: $0"), exception.contextData.hint)}
                </Text>
            </TextContent>}
        </Modal>
    );
};

export const errorHandlerWithContext = (contextData, handler) => {
    return (exception) => {
        exception.contextData = contextData;
        handler(exception);
    };
};
