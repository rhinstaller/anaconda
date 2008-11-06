#!/usr/bin/python
#
# release_notes.py - "I can't believe it's not a web browser."
#
# David Cantrell <dcantrell@redhat.com>
#
# Copyright 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys
import os
import signal
import gtk
import gtkhtml2
import urllib
import urlparse

import gui

from rhpl.translate import _, N_

class ReleaseNotesViewer:
	def __init__(self, anaconda):
		self.currentURI = None
		self.htmlheader = "<html><head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\"></head><body bgcolor=\"white\"><pre>"
		self.htmlfooter = "</pre></body></html>"
		self.doc = gtkhtml2.Document()
		self.vue = gtkhtml2.View()
		self.opener = urllib.FancyURLopener()

		# FIXME: these do not work, disabling for FC6   --dcantrell
		#self.doc.connect('request_url', self.requestURLCallBack)
		#self.doc.connect('link_clicked', self.linkClickedCallBack)
		#self.vue.connect('request_object', self.requestObjectCallBack)
		self.topDir = None

		self.width = None
		self.height = None

		self.is_showing = False

		self.anaconda = anaconda
		self.load()
		self.resize()
		self.setupWindow()

	def getReleaseNotes(self):
		langs = self.anaconda.id.instLanguage.getCurrentLangSearchList() + [ "" ]
		suffixList = []
		for lang in langs:
			if lang:
				suffixList.append("-%s.html" % (lang,))
				suffixList.append(".%s" % (lang,))

		for suffix in suffixList:
			fn = "RELEASE-NOTES%s" % (suffix,)
			try:
				tmpfile = os.path.abspath(self.anaconda.dispatch.method.getFilename(fn, destdir="/tmp", retry=0))
				if tmpfile is None:
					continue

				# Just because we got a filename back doesn't
				# mean it's a valid file.  Check that it's not
				# zero length too.
				st = os.stat(tmpfile)
				if st.st_size == 0L:
					os.remove(tmpfile)
					continue

				self.topDir = os.path.dirname(tmpfile)
				return tmpfile
			except:
				continue

		return None

	def resize(self, w=None, h=None):
		sw = gtk.gdk.screen_width()
		(step, args) = self.anaconda.dispatch.currentStep()

		if w is None:
			if sw >= 800:
				self.width = 800
			else:
				self.width = 640
		else:
			self.width = int(w)

		# if we are at the installation progress bar step, make the
		# release notes window smaller so the progress bar is still
		# visible...otherwise, consume the entire screen
		if h is None:
			if sw >= 800:
				if step == "installpackages":
					self.height = 445
				else:
					self.height = 600
			else:
				if step == "installpackages":
					self.height = 300
				else:
					self.height = 480
		else:
			self.height = int(h)

	# FIXME: replace with logger from anaconda_log (fix exec first)
	def log(self, string):
		print string

	def load(self, uri=None):
		def loadWrapper(baloney):
			self.doc.open_stream('text/html')
			self.doc.write_stream(self.htmlheader)
			self.doc.write_stream(baloney)
			self.doc.write_stream(self.htmlfooter)

		if uri is None:
			uri = self.getReleaseNotes()

		if uri is not None:
			if os.access(uri, os.R_OK):
				try:
					f = self.openURI(uri)
				except OSError:
					self.log("Failed to open %s" % (uri,))
					return

				if f is not None:
					self.doc.clear()
					headers = f.info()

					mime = headers.getheader('Content-type')
					if mime:
						self.doc.open_stream(mime)
						self.doc.write_stream(f.read())
					else:
						loadWrapper(f.read())

					self.doc.close_stream()
					f.close()

					self.currentURI = self.resolveURI(uri)
			else:
				loadWrapper(_("Release notes are missing.\n"))

				self.currentURI = None
		else:
			loadWrapper(_("Release notes are missing.\n"))

			self.currentURI = None

	def isShowing(self):
		return self.is_showing

	def hide(self):
		if self.textWin is not None:
			self.textWin.hide_all()
			self.is_showing = False

	def setupWindow(self):
		self.vue.set_document(self.doc)
		self.textWin = gtk.Window()
		self.textWin.connect("delete-event", self.closedCallBack)
		mainbox = gtk.VBox(False, 6)
		self.textWin.add(mainbox)

		table = gtk.Table(3, 3, False)
		mainbox.pack_start(table)

		mainbox.pack_start(gtk.HSeparator(), False, False)
		bb = gtk.HButtonBox()
		bb.set_property("layout-style", gtk.BUTTONBOX_END)

		b = gtk.Button(stock="gtk-close")
		b.connect("clicked", self.closedCallBack)
		bb.pack_start(b)
		mainbox.pack_start(bb, False, False)

		vbox1 = gtk.VBox()
		vbox1.set_border_width(10)
		frame = gtk.Frame("")
		frame.add(vbox1)
		frame.set_label_align(0.5, 0.5)
		frame.set_shadow_type(gtk.SHADOW_NONE)

		self.textWin.set_position(gtk.WIN_POS_NONE)
		self.textWin.set_gravity(gtk.gdk.GRAVITY_NORTH_WEST)

		if self.vue is not None:
			sw = gtk.ScrolledWindow()
			sw.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
			sw.set_shadow_type(gtk.SHADOW_IN)
			sw.add(self.vue)
			vbox1.pack_start(sw)

			a = gtk.Alignment(0, 0, 1.0, 1.0)
			a.add(frame)

			self.textWin.set_default_size(self.width, self.height)
			self.textWin.set_size_request(self.width, self.height)

			# we want the release notes dialog to be the same
			# size as the main installer window so it covers it
			# up completely.  this isn't always the same size
			# as the root window, so figure out our northwest
			# origin point and then move the window
			if gtk.gdk.screen_width() == self.width:
				self.textWin.move(0, 0)
			else:
				# the width will always be fixed, but our
				# height changes depending on the installation
				# stage, so do the origin point calculations
				# using what would be the full height
				if self.width == 800:
					fullh = 600
				elif self.width == 640:
					fullh = 480

				left = (gtk.gdk.screen_width() - self.width) / 2
				top = (gtk.gdk.screen_height() - fullh) / 2
				self.textWin.move(left, top)

			table.attach(a, 1, 2, 1, 2, gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 5, 5)

			self.textWin.set_border_width(0)
			gui.addFrame(self.textWin, _("Release Notes"))
		else:
			self.textWin.set_position(gtk.WIN_POS_CENTER)
			label = gtk.Label(_("Unable to load file!"))

			table.attach(label, 1, 2, 1, 2, gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 5, 5)

			self.textWin.set_border_width(0)
			gui.addFrame(self.textWin)

	def view(self):
		self.textWin.show_all()

		# set cursor to normal (assuming that anaconda set it to busy
		# when it exec'd this viewer app to give progress indicator
		# to user).
		root = gtk.gdk.get_default_root_window()
		cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
		root.set_cursor(cursor)

		self.is_showing = True

	def resolveURI(self, link):
		parts = urlparse.urlparse(link)
		if parts[0] or parts[1]:
			return link
		else:
			# FIXME: does not work right now
			#return urlparse.urljoin(self.currentURI, link)
			return link

	def openURI(self, link):
		try:
			ret = self.opener.open(self.resolveURI(link))
		except IOError:
			ret = None

		return ret

	def closedCallBack(self, *args):
		self.textWin.hide_all()
		self.is_showing = False

	def linkClickedCallBack(self, document, link):
		if link[0] == '#':
			self.log("jump to anchor: %s" % (link,))
			self.vue.jump_to_anchor(link)
		else:
			self.load(link)

	def requestURLCallBack(self, document, url, stream):
		try:
			f = self.openURI(url)
			stream.write(f.read())
		except:
			# we'll try local from self.topDir
			url = os.path.abspath(self.topDir + '/' + url)
			try:
				f = self.openURI(url)
				stream.write(f.read())
			except:
				self.log("requested url not found: %s" % (url,))

	def requestObjectCallBack(self, *args):
		self.log("request objects call back: %s" % (args))
