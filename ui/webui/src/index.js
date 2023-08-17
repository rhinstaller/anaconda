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

import "../pkg/lib/patternfly/patternfly-5-cockpit.scss";

import React from "react";
import { createRoot } from "react-dom/client";
import { Application } from "./components/app.jsx";
import cockpit from "cockpit";
/*
 * PF4 overrides need to come after the JSX components imports because
 * these are importing CSS stylesheets that we are overriding
 * Having the overrides here will ensure that when mini-css-extract-plugin will extract the CSS
 * out of the dist/index.js and since it will maintain the order of the imported CSS,
 * the overrides will be correctly in the end of our stylesheet.
 */
import "../pkg/lib/patternfly/patternfly-5-overrides.scss";
import "./components/app.scss";

document.addEventListener("DOMContentLoaded", function () {
    const root = createRoot(document.getElementById("app"));
    root.render(<Application />);
    document.documentElement.setAttribute("dir", cockpit.language_direction);
});

// As we are changing the language from the same iframe the localstorage change (cockpit.lang) will not fire.
// See Note section here for details: https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event
// We need to listen to the virtual event that we generate when changing language and adjust the language direction accordingly.
// This needs to be exposed as a helper function from cockpit: https://github.com/cockpit-project/cockpit/issues/18874
window.addEventListener("cockpit-lang", event => {
    if (cockpit.language_direction) {
        document.documentElement.setAttribute("dir", cockpit.language_direction);
    }
});
