#!/usr/bin/env gjs-console

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

imports.gi.versions.Gdk = '3.0';
imports.gi.versions.Gtk = '3.0';

const Gdk = imports.gi.Gdk;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const GObject = imports.gi.GObject;
const Gtk = imports.gi.Gtk;

const Gettext = imports.gettext;
const _ = imports.gettext.gettext;

const LOCALE_DIR = '/usr/share/locale';

let anacondaApp = null;

function makeLabel(label, button) {
    let widget = new Gtk.Label();

    if (button) {
        widget.set_markup(`<b><span size="x-large">${label}</span></b>`);
    } else {
        widget.set_line_wrap(true);
        widget.set_justify(Gtk.Justification.CENTER);
        widget.set_margin_top(32);
        widget.set_margin_bottom(32);

        widget.set_markup(`<span size="large">${label}</span>`);
    }

    return widget;
}

class WelcomeWindow extends Gtk.ApplicationWindow {
    static {
        GObject.registerClass(this);
    }

    constructor(application) {
        super({
            application,
            type: Gtk.WindowType.TOPLEVEL,
            default_width: 600,
            default_height: 550,
            skip_taskbar_hint: true,
            title: _('Welcome to Fedora'),
            window_position: Gtk.WindowPosition.CENTER,
        });

        this.connect('key-press-event', (w, event) => {
            const key = event.get_keyval()[1];

            if (key === Gdk.KEY_Escape)
                this.destroy();

            return Gdk.EVENT_CONTINUE;
        });

        const mainGrid = new Gtk.Grid({
            orientation: Gtk.Orientation.VERTICAL,
            row_spacing: 16,
            vexpand: true,
            hexpand: true,
            halign: Gtk.Align.CENTER,
            valign: Gtk.Align.CENTER,
        });
        this.add(mainGrid);

        const buttonBox = new Gtk.Grid({
            orientation: Gtk.Orientation.HORIZONTAL,
            column_spacing: 16,
            halign: Gtk.Align.CENTER,
        });
        mainGrid.add(buttonBox);

        const tryContent = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 16,
        });
        tryContent.add(new Gtk.Image({
            icon_name: 'media-optical',
            pixel_size: 256,
        }));
        tryContent.add(makeLabel(_('Try Fedora'), true));

        const tryButton = new Gtk.Button({child: tryContent});
        buttonBox.add(tryButton);

        const installContent = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 16,
        });

        // provided by the 'fedora-logos' package
        installContent.add(new Gtk.Image({
            icon_name: 'org.fedoraproject.AnacondaInstaller',
            pixel_size: 256,
        }));
        installContent.add(makeLabel(anacondaApp.get_name(), true));

        const installButton = new Gtk.Button({child: installContent});
        buttonBox.add(installButton);

        this._label = makeLabel(
            _('You are currently running Fedora from live media.\nYou can install Fedora now, or choose "Install to Hard Drive" in the Activities Overview at any later time.'),
            false);
        mainGrid.add(this._label);

        installButton.connect('clicked', () => {
            GLib.spawn_command_line_async('liveinst');
            this.destroy();
        });

        tryButton.connect('clicked', () => {
            buttonBox.destroy();
            this._label.destroy();

            // provided by the 'fedora-logos' package
            let image = new Gtk.Image({
                icon_name: 'org.fedoraproject.AnacondaInstaller',
                pixel_size: 256,
                halign: Gtk.Align.CENTER,
            });
            mainGrid.add(image);

            this._label = makeLabel(
                _('You can choose "Install to Hard Drive"\nin the Activities Overview at any later time.'),
                false);
            mainGrid.add(this._label);

            const closeLabel = makeLabel(_('Close'), true);
            closeLabel.margin = 10;
            const button = new Gtk.Button({
                child: closeLabel,
                halign: Gtk.Align.CENTER,
            });
            button.connect('clicked', () => this.destroy());
            mainGrid.add(button);

            mainGrid.show_all();
        });

        mainGrid.show_all();
    }
}

Gettext.bindtextdomain('anaconda', LOCALE_DIR);
Gettext.textdomain('anaconda');

GLib.set_prgname('fedora-welcome');
Gtk.init(null, null);
Gtk.Settings.get_default().gtk_application_prefer_dark_theme = true;

// provided by the 'anaconda' package
anacondaApp = Gio.DesktopAppInfo.new('anaconda.desktop');
if (!anacondaApp)
    anacondaApp = Gio.DesktopAppInfo.new('liveinst.desktop');

if (anacondaApp) {
    let application = new Gtk.Application({ application_id: 'org.fedoraproject.welcome-screen',
                                            flags: Gio.ApplicationFlags.FLAGS_NONE });
    let welcomeWindow = null;

    application.connect('startup', () => {
        welcomeWindow = new WelcomeWindow(application);
    });
    application.connect('activate', () => {
        welcomeWindow.present();
    });

    application.run(ARGV);
}
