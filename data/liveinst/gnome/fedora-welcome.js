#!/usr/bin/gjs -m

/*
 * Copyright (C) 2012 Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

import Adw from 'gi://Adw?version=1';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';

import {gettext as _} from 'gettext';
import Gettext from 'gettext';

import {programArgs, programInvocationName} from 'system';

const LOCALE_DIR = '/usr/share/locale';
const OS_RELEASE = '/etc/os-release';

let anacondaApp = null;

class WelcomeWindow extends Adw.ApplicationWindow {
    static {
        GObject.registerClass(this);

        this.add_shortcut(new Gtk.Shortcut({
            trigger: Gtk.ShortcutTrigger.parse_string('Escape'),
            action: Gtk.NamedAction.new('window.close'),
        }));

        this.install_action('window.install-fedora', null,
            self => self._installFedora());
    }

    constructor(application) {
        const osRelease = Gio.File.new_for_path(OS_RELEASE);
        const osReleaseContents = osRelease.load_contents(null)[1];
        const osReleaseLines = osReleaseContents.toString().split('\n');
        const osReleaseLineName = osReleaseLines.find(line => line.startsWith('NAME=')).split('=')[1].replace(/"/g, '');

        const title = _('Welcome to %s').replace('%s', osReleaseLineName);
        super({
            application,
            title,
            content: new Gtk.WindowHandle(),
            default_width: 600,
            default_height: 550,
        });

        const statusPage = new Adw.StatusPage({
            title,
            iconName: 'fedora-logo-icon',
            description: _('This live media can be used to install %s or as a temporary system. Installation can be started at any time using the install icon in Activities.').replace('%s', osReleaseLineName),
        });
        this.content.set_child(statusPage);

        const buttonBox = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            homogeneous: true,
            spacing: 24,
            halign: Gtk.Align.CENTER,
        });
        statusPage.set_child(buttonBox);

        const installButton = new Gtk.Button({
            label: _('Install %s…').replace('%s', osReleaseLineName),
            actionName: 'window.install-fedora',
        });
        installButton.add_css_class('pill');
        installButton.add_css_class('suggested-action');
        buttonBox.append(installButton);

        const tryButton = new Gtk.Button({
            label: _('Not Now'),
            actionName: 'window.close',
        });
        tryButton.add_css_class('pill');
        buttonBox.append(tryButton);
    }

    _installFedora() {
        anacondaApp.launch([], this.display.get_app_launch_context());
        this.close();
    }
}

class WelcomeApp extends Adw.Application {
    static {
        GObject.registerClass(this);
    }

    constructor() {
        super({application_id: 'org.fedoraproject.welcome-screen'});
    }

    vfunc_activate() {
        let {activeWindow} = this;
        if (!activeWindow)
            activeWindow = new WelcomeWindow(this);
        activeWindow.present();
    }
}

Gettext.bindtextdomain('anaconda', LOCALE_DIR);
Gettext.textdomain('anaconda');

// provided by the 'anaconda' package
anacondaApp = Gio.DesktopAppInfo.new('anaconda.desktop');
if (!anacondaApp)
    anacondaApp = Gio.DesktopAppInfo.new('liveinst.desktop');

if (anacondaApp)
    new WelcomeApp().run([programInvocationName, ...programArgs]);
