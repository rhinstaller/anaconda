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
 *
 * Authors: Cosimo Cecchi <cosimoc@redhat.com>
 *
 */

const Gdk = imports.gi.Gdk;
const GdkPixbuf = imports.gi.GdkPixbuf;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Gtk = imports.gi.Gtk;
const Lang = imports.lang;
const Pango = imports.gi.Pango;

const Gettext = imports.gettext;
const _ = imports.gettext.gettext;

const LOCALE_DIR = '/usr/share/locale';

let anacondaApp = null;

function makeLabel(label, button) {
    let widget = new Gtk.Label();

    if (button)
        widget.set_markup('<b><span size="x-large">' + label + '</span></b>');
    else {
        widget.set_line_wrap(true);
        widget.set_justify(Gtk.Justification.CENTER);
        widget.set_margin_top(32);
        widget.set_margin_bottom(32);

        widget.set_markup('<span size="large">' + label + '</span>');
    }

    return widget;
}

const WelcomeWindow = new Lang.Class({
  Name: 'WelcomeWindow',

  _init: function(application) {
      this.window = new Gtk.ApplicationWindow({ application: application,
                                                type: Gtk.WindowType.TOPLEVEL,
                                                default_width: 600,
                                                default_height: 550,
                                                skip_taskbar_hint: true,
                                                title: _("Welcome to Fedora"),
                                                window_position: Gtk.WindowPosition.CENTER });
      this.window.connect('key-press-event', Lang.bind(this,
          function(w, event) {
              let key = event.get_keyval()[1];

              if (key == Gdk.KEY_Escape)
                  this.window.destroy();

              return false;
          }));

      let mainGrid = new Gtk.Grid({ orientation: Gtk.Orientation.VERTICAL,
                                    row_spacing: 16,
                                    vexpand: true,
                                    hexpand: true,
                                    halign: Gtk.Align.CENTER,
                                    valign: Gtk.Align.CENTER });
      this.window.add(mainGrid);

      let buttonBox = new Gtk.Grid({ orientation: Gtk.Orientation.HORIZONTAL,
                                     column_spacing: 16,
                                     halign: Gtk.Align.CENTER });
      mainGrid.add(buttonBox);

      let tryContent = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL,
                                     spacing: 16 });
      tryContent.add(new Gtk.Image({ icon_name: 'media-optical',
                                     pixel_size: 256 }));
      tryContent.add(makeLabel(_("Try Fedora"), true));

      let tryButton = new Gtk.Button({ child: tryContent });
      buttonBox.add(tryButton);

      let installContent = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL,
                                         spacing: 16 });

      // provided by the 'fedora-logos' package
      installContent.add(new Gtk.Image({ icon_name: 'anaconda',
                                         pixel_size: 256 }));
      installContent.add(makeLabel(anacondaApp.get_name(), true));

      let installButton = new Gtk.Button({ child: installContent });
      buttonBox.add(installButton);

      this._label = makeLabel(_("You are currently running Fedora from live media.\nYou can install Fedora now, or choose \"Install to Hard Drive\" in the Activities Overview at any later time."), false);
      mainGrid.add(this._label);

      installButton.connect('clicked', Lang.bind(this,
          function() {
              GLib.spawn_command_line_async('liveinst');
              this.window.destroy();
          }));

      tryButton.connect('clicked', Lang.bind(this,
          function() {
              buttonBox.destroy();
              this._label.destroy();

              let image = new Gtk.Image({ file: '/usr/share/anaconda/gnome/install-button.png',
                                          halign: Gtk.Align.CENTER });
              mainGrid.add(image);

              this._label = makeLabel(_("You can choose \"Install to Hard Drive\"\nin the Activities Overview at any later time."), false);
              mainGrid.add(this._label);

              let closeLabel = makeLabel(_("Close"), true);
              closeLabel.margin = 10;
              let button = new Gtk.Button({ child: closeLabel,
                                            halign: Gtk.Align.CENTER });
              button.connect('clicked', Lang.bind(this,
                  function() {
                      this.window.destroy();
                  }));
              mainGrid.add(button);

              mainGrid.show_all();
          }));
  }
});

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

    application.connect('startup', Lang.bind(this,
        function() {
            welcomeWindow = new WelcomeWindow(application);
        }));
    application.connect('activate', Lang.bind(this,
        function() {
            welcomeWindow.window.show_all();
        }));

    application.run(ARGV);
}
