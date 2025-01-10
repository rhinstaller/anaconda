#
# Copyright (C) 2023  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import Mock, patch

from pyanaconda.core.glib import Variant
from pyanaconda.core.signal import Signal
from pyanaconda.modules.localization.localed import CompositorLocaledWrapper, LocaledWrapper


class LocaledWrapperTestCase(unittest.TestCase):
    """Test LocaledWrapper."""

    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_no_systembus_conf(self, mocked_conf):
        """Test LocaledWrapper on environments with nonavailability of systembus configured."""
        mocked_conf.system.provides_system_bus = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)

    def _guarded_localed_wrapper_calls_check(self, localed_wrapper):
        """Test that calls to LocaledWrapper are guarded not to fail."""
        assert localed_wrapper.keymap == ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.set_layouts(["us-altgr-intl"])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_properties(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test conversion of return values from Localed service to LocaledWraper."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        localed_wrapper = LocaledWrapper()
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        assert localed_wrapper.keymap == \
            "cz"
        assert localed_wrapper.layouts_variants == \
            ["cz (qwerty)", "fi", "us (euro)", "fr"]
        assert localed_wrapper.options == \
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"]

        mocked_localed_proxy.VConsoleKeymap = ""
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        assert localed_wrapper.keymap == ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_safe_calls(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test calling LocaledWrapper with invalid values does not raise exception."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        localed_wrapper = LocaledWrapper()
        # valid values
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        # invalid values
        localed_wrapper.set_keymap("iinvalid")
        localed_wrapper.set_keymap("iinvalid", convert=True)
        localed_wrapper.convert_keymap("iinvalid")
        localed_wrapper.set_and_convert_keymap("iinvalid")
        # valid values
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        # invalid values
        # rhbz#1843379
        localed_wrapper.set_layouts(["us-altgr-intl"])
        localed_wrapper.set_and_convert_layouts(["us-altgr-intl"])
        localed_wrapper.convert_layouts(["us-altgr-intl"])

        # test set_layout on proxy with options
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["cz (qwerty)", "us"])
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,us",
            "pc105",  # hardcoded
            "qwerty,",
            "",
            False,
            False
        )

        # test set_layout on proxy with options not set explicitly (None)
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["cz (qwerty)", "us"], options=None)
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,us",
            "pc105",  # hardcoded
            "qwerty,",
            "",
            False,
            False
        )

        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["us"], "", True)
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us",
            "pc105",  # hardcoded
            "",
            "",  # empty options will remove existing options
            True,
            False
        )

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    def test_localed_wrapper_no_systembus(self, mocked_system_bus):
        """Test LocaledWrapper in environment without system bus.

        Which is also the environment of our tests.
        """
        # Emulates mock environment
        mocked_system_bus.check_connection.return_value = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)


class CompositorLocaledWrapperTestCase(LocaledWrapperTestCase):

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_compositor_localed_wrapper_properties(
        self, mocked_conf, mocked_localed_service, mocked_system_bus
    ):
        """Test conversion of return values from Localed service to CompositorLocaledWraper."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        localed_wrapper = CompositorLocaledWrapper()
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        assert localed_wrapper.layouts_variants == \
            ["cz (qwerty)", "fi", "us (euro)", "fr"]
        assert localed_wrapper.current_layout_variant == "cz (qwerty)"
        assert localed_wrapper.options == \
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"]

        mocked_localed_proxy.VConsoleKeymap = ""
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []
        assert localed_wrapper.current_layout_variant == ""

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_compositor_localed_wrapper_safe_calls(
        self, mocked_conf, mocked_localed_service, mocked_system_bus
    ):
        """Test calling CopmositorLocaledWrapper with invalid values does not raise exception."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        localed_wrapper = CompositorLocaledWrapper()
        # valid values
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        # invalid values
        # rhbz#1843379
        localed_wrapper.set_layouts(["us-altgr-intl"])

        # set_layouts should change user defined layouts
        localed_wrapper.set_layouts(["cz", "us (euro)"])
        assert localed_wrapper._user_layouts_variants == ["cz", "us (euro)"]

        # test set_layout on proxy with options
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["cz (qwerty)", "us"])
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,us",
            "pc105",  # hardcoded
            "qwerty,",
            "grp:alt_shift_toggle,grp:ctrl_alt_toggle",  # options will be reused what is set
            False,
            False
        )

        # test set_layout on proxy with options not set explicitly (None)
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["cz (qwerty)", "us"], options=None)
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,us",
            "pc105",  # hardcoded
            "qwerty,",
            "grp:alt_shift_toggle,grp:ctrl_alt_toggle",  # options will be reused what is set
            False,
            False
        )

        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper.set_layouts(["us"], "", True)
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us",
            "pc105",  # hardcoded
            "",
            "",  # empty options will remove existing options
            True,
            False
        )

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_compositor_localed_wrapper_set_next_layout(
        self, mocked_conf, mocked_localed_service, mocked_system_bus
    ):
        """Test CompositorLocaledWrapper method to set current layout to compositor.

        Verify that we are selecting next layout to what is currently set in compositor.
        Because setting current layout changing the ordering we have to decide next layout based
        on the user selection.
        """
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        #  currently selected is first in this list 'cz (qwerty)'
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = ""
        localed_wrapper = CompositorLocaledWrapper()

        # test switch to next layout
        user_defined = ["cz (qwerty)", "fi", "us (euro)", "fr"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fi,us,fr,cz",
            "pc105",  # hardcoded
            ",euro,,qwerty",
            "",
            False,
            False
        )

        # test switch to next layout in the middle of user defined list
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        user_defined = ["es", "cz (qwerty)", "us (euro)", "fr"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us,fr,es,cz",
            "pc105",  # hardcoded
            "euro,,,qwerty",
            "",
            False,
            False
        )

        # test switch to next layout with different user defined list
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        user_defined = ["cz (qwerty)", "es"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "es,cz",
            "pc105",  # hardcoded
            ",qwerty",
            "",
            False,
            False
        )

        # the compositor list is empty test
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        user_defined = ["cz (qwerty)", "es"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,es",
            "pc105",  # hardcoded
            "qwerty,",
            "",
            False,
            False
        )

        # the user defined list is empty test
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

        # the user defined list has only one value
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz,fi,us,es"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        user_defined = ["es (euro)"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "es",
            "pc105",  # hardcoded
            "euro",
            "",
            False,
            False
        )

        # everything is empty
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_compositor_localed_wrapper_set_current_layout(
        self, mocked_conf, mocked_localed_service, mocked_system_bus
    ):
        """Test CompositorLocaledWrapper method to set current layout to compositor.

        Verify that the layout to be set is moved to the first place.
        """
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = ""
        localed_wrapper = CompositorLocaledWrapper()
        user_defined = ["cz (qwerty)", "fi", "us (euro)", "fr"]

        # check if layout is correctly set
        localed_wrapper._user_layouts_variants = user_defined
        localed_wrapper.select_layout("fi")
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fi,us,fr,cz",
            "pc105",  # hardcoded
            ",euro,,qwerty",
            "",
            False,
            False
        )

        # check if layout is correctly set including variant
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_layout("us (euro)") is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us,fr,cz,fi",
            "pc105",  # hardcoded
            "euro,,qwerty,",
            "",
            False,
            False
        )

        # check when we are selecting non-existing layout
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "fi"
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_layout("cz") is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

        # check when the layout set is empty
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_layout("fr") is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fr,cz,fi,us",
            "pc105",  # hardcoded
            ",qwerty,,euro",
            "",
            False,
            False
        )

        # can't set layout when we don't have user defined set
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz, us"
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_layout("cz (qwerty)") is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_compositor_localed_wrapper_signals(self, mocked_conf,
                                     mocked_localed_service,
                                     mocked_system_bus):
        """Test signals from the compositor localed wrapper

        This one could be tricky. The issue is that this class has to store last known values to
        be able to recognize changes.

        We need:
        last_known_from_compositor - we need to store what was in compositor before it changed
                                     compositor configuration, so we can correct sent a message
                                     that current selection is different

        None of the information above could be found directly from localed service.
        """
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_proxy.PropertiesChanged = Signal()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_layouts_changed = Mock()
        mocked_selected_layout_changed = Mock()
        localed_wrapper = CompositorLocaledWrapper()
        localed_wrapper.compositor_layouts_changed = mocked_layouts_changed
        localed_wrapper.compositor_selected_layout_changed = mocked_selected_layout_changed

        def _check_localed_wrapper_signals(last_known_state, compositor_state,
                                           expected_selected_signal, expected_layouts_signal):
            """Test the compositor localed wrapper signals are correctly emitted.

            :param last_known_state: State of the localed before the change. Used to resolve if
                                     selected layout has changed.
            :type last_known_state: [(str,str)] e.g.:[('cz', 'qwerty'), ('us','')...]
            :param compositor_state: New state the compositor will get into.
            :type compositor_state: {str: str} e.g.: {"X11Layout": "cz", "X11Variant": "qwerty"}
            :param expected_selected_signal: Currently selected layout we expect CompositorLocaledWrapper
                                             will signal out. If signal shouldn't set None.
            :type expected_selected_signal: str
            :param expected_layouts_signal: Current configuration of the compositor signaled from
                                            CompositorLocaledWrapper.
            :type expected_layouts_signal: [str] e.g.: ["cz", "us (euro)"]
            """
            mocked_layouts_changed.reset_mock()
            mocked_selected_layout_changed.reset_mock()
            # set user defined layouts by setting current ones (mock will take this)
            mocked_localed_proxy.X11Layout = ",".join(map(lambda x: x[0], last_known_state))
            mocked_localed_proxy.X11Variant = ",".join(map(lambda x: x[1], last_known_state))
            # loading the above values to local last known list
            # pylint: disable=pointless-statement
            localed_wrapper.layouts_variants

            for k in compositor_state:
                compositor_state[k] = Variant('s', compositor_state[k])

            mocked_localed_proxy.PropertiesChanged.emit(None, compositor_state, None)
            # these signals should be called by localed wrapper
            if expected_selected_signal is None:
                mocked_selected_layout_changed.emit.assert_not_called()
            else:
                mocked_selected_layout_changed.emit.assert_called_once_with(
                    expected_selected_signal
                    )
            if expected_layouts_signal is None:
                mocked_layouts_changed.emit.assert_not_called()
            else:
                mocked_layouts_changed.emit.assert_called_once_with(expected_layouts_signal)
            # we shouldn't set values back to localed service
            mocked_localed_proxy.SetX11Keyboard.assert_not_called()

        # basic test compositor changing different values
        _check_localed_wrapper_signals(
            last_known_state=[],
            compositor_state={"X11Options": "grp:something"},
            expected_selected_signal=None,
            expected_layouts_signal=None
        )

        # basic test with no knowledge of previous state
        _check_localed_wrapper_signals(
            last_known_state=[],
            compositor_state={"X11Layout": "cz",
                              "X11Variant": "qwerty"},
            expected_selected_signal="cz (qwerty)",
            expected_layouts_signal=["cz (qwerty)"]
        )

        # basic test with no knowledge of previous state and multiple values
        _check_localed_wrapper_signals(
            last_known_state=[],
            compositor_state={"X11Layout": "cz,es",
                              "X11Variant": "qwerty,"},
            expected_selected_signal="cz (qwerty)",
            expected_layouts_signal=["cz (qwerty)", "es"]
        )

        # test no values from compositor
        _check_localed_wrapper_signals(
            last_known_state=[("cz", "")],
            compositor_state={"X11Layout": "",
                              "X11Variant": ""},
            expected_selected_signal="",
            expected_layouts_signal=[]
        )

        # test with knowledge of previous state everything changed
        _check_localed_wrapper_signals(
            last_known_state=[("es", "euro"), ("us", "")],
            compositor_state={"X11Layout": "cz",
                              "X11Variant": "qwerty"},
            expected_selected_signal="cz (qwerty)",
            expected_layouts_signal=["cz (qwerty)"]
        )

        # test with knowledge of previous state no change
        _check_localed_wrapper_signals(
            last_known_state=[("cz", "qwerty"), ("es", "")],
            compositor_state={"X11Layout": "cz,es",
                              "X11Variant": "qwerty,"},
            expected_selected_signal=None,
            expected_layouts_signal=["cz (qwerty)", "es"]
        )

        # test with knowledge of previous state selected has changed
        _check_localed_wrapper_signals(
            last_known_state=[("cz", "qwerty"), ("es", "")],
            compositor_state={"X11Layout": "es,cz",
                              "X11Variant": ",qwerty"},
            expected_selected_signal="es",
            expected_layouts_signal=["es", "cz (qwerty)"]
        )

        # test with knowledge of previous state layouts has changed
        _check_localed_wrapper_signals(
            last_known_state=[("cz", "qwerty"), ("es", "")],
            compositor_state={"X11Layout": "cz,es,us",
                              "X11Variant": "qwerty,,"},
            expected_selected_signal=None,
            expected_layouts_signal=["cz (qwerty)", "es", "us"]
        )

        # test with knowledge of previous state just variant change
        _check_localed_wrapper_signals(
            last_known_state=[("cz", "qwerty"), ("es", "")],
            compositor_state={"X11Layout": "cz,es,us",
                              "X11Variant": ",,"},
            expected_selected_signal="cz",
            expected_layouts_signal=["cz", "es", "us"]
        )
