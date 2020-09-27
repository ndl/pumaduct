# PuMaDuct - integrates libpurple-supported IM protocols
# into Matrix, see https://endl.ch/projects/pumaduct
# https://matrix.org and https://developer.pidgin.im/wiki/WhatIsLibpurple
#
# Copyright (C) 2019 - 2020 Alexander Tsvyashchenko <matrix@endl.ch>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests PresenceLayer functionality."""

from pumaduct.layers.tests.common import LayerTestCommon

# pylint: disable=duplicate-code

PRESENCE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.presence",
        "content": {"user_id": "@test:localhost", "presence": "offline"}
    }]
}

class PresenceLayerTest(LayerTestCommon):
  """Tests PresenceLayer functionality."""

  def test_presence_to_matrix(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "contact-status-changed", "prpl-jabber", "test@localhost",
          "test2@localhost", "online")
      self.mc.set_user_presence.assert_called_with("@xmpp-test2:localhost", "online")
      self.backend.base.dispatch_callbacks(
          "contact-status-changed", "prpl-jabber", "test@localhost",
          "test2@localhost", "unavailable")
      self.mc.set_user_presence.assert_called_with("@xmpp-test2:localhost", "unavailable")

  def test_presence_refresh(self):
    self.create_account()
    self.pc.get_contact_status.return_value = "online"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.assertIsNotNone(self.backend.presence.presence_refresh_cb)
      self.pc.reset_mock()
      self.mc.reset_mock()
      self.backend.presence.on_presence_refresh()
      self.pc.get_contact_status.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.mc.set_user_presence.assert_any_call("@xmpp-test2:localhost", "online")
      self.mc.set_user_presence.assert_any_call("@pumaduct:localhost", "online")

  def test_request_presence_list_on_enter(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.mc.add_to_presence_list.assert_called_with(
          "@test:localhost", "@pumaduct:localhost")

  def test_has_presence_list_on_sign_on(self):
    self.create_account()
    self.backend = self.create_backend()
    self.mc.get_presence_list.return_value = [{
        "content": {"user_id": "@test:localhost", "presence": "offline"}}]
    self.mc.get_non_managed_user_presence.return_value = "unavailable"
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      self.mc.add_to_presence_list.assert_not_called()
      self.mc.get_non_managed_user_presence.assert_called_with(
          "@test:localhost", "@pumaduct:localhost")
      self.pc.set_account_status.assert_called_with(
          "prpl-jabber", "test@localhost", "unavailable")

  def test_presence_to_purple(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, PRESENCE_EVENTS)
      self.pc.set_account_status.assert_called_with(
          "prpl-jabber", "test@localhost", "offline")

  def test_presence_on_connection_error(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "connection-error", "prpl-jabber", "test@localhost",
          "test reason", "test description")
      self.mc.set_user_presence.assert_called_with("@xmpp-test2:localhost", "offline")
