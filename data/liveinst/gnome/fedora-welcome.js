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

let anacondaApp = null;

function makeLabel(label, button) {
    let widget = new Gtk.Label();

    if (button) {
        widget.set_markup(`<b><span size="x-large">${label}</span></b>`);
    } else {
        widget.set_wrap(true);
        widget.set_justify(Gtk.Justification.CENTER);
        widget.set_margin_top(32);
        widget.set_margin_bottom(32);

        widget.set_markup(`<span size="large">${label}</span>`);
    }

    return widget;
}

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
        const title = _('Welcome to Fedora!');
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
            description: _('This live media can be used to install Fedora or as a temporary system. Installation can be started at any time using the install icon in Activities.'),
        });
        this.content.set_child(statusPage);

        const buttonBox = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 16,
            halign: Gtk.Align.CENTER,
        });
        statusPage.set_child(buttonBox);

        const tryContent = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 16,
        });
        tryContent.append(new Gtk.Image({
            icon_name: 'media-optical',
            pixel_size: 256,
        }));
        tryContent.append(makeLabel(_('Not Now'), true));

        const tryButton = new Gtk.Button({
            child: tryContent,
            actionName: 'window.close',
        });
        buttonBox.append(tryButton);

        const installContent = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 16,
        });

        // provided by the 'fedora-logos' package
        installContent.append(new Gtk.Image({
            icon_name: 'org.fedoraproject.AnacondaInstaller',
            pixel_size: 256,
        }));
        installContent.append(makeLabel(_('Install Fedora…'), true));

        const installButton = new Gtk.Button({
            child: installContent,
            actionName: 'window.install-fedora',
        });
        buttonBox.append(installButton);
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
        this.styleManager.colorScheme = Adw.ColorScheme.PREFER_DARK;
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
