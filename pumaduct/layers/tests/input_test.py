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

"""Tests InputLayer functionality."""

from unittest.mock import Mock

from pumaduct.layers.tests.common import LayerTestCommon
from pumaduct.storage import Account

# pylint: disable=duplicate-code

REQUEST_INPUT_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id2",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"body": "test-token"},
        "room_id": "room_id0"
    }]
}

class InputLayerTest(LayerTestCommon):
  """Tests InputLayer functionality."""

  def test_input_with_existing_account(self):
    self.create_account()
    self.backend = self.create_backend()
    self.mc.create_room.return_value = "room_id0"
    self.pc.get_auth_token.return_value = "test-token"
    self.backend.base.networks["prpl-jabber"]["use_auth_token"] = True
    ok_cb = Mock()
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "request-input", "prpl-jabber", "test@localhost",
          "Auth Code", "https://accounts.google.com/o/oauth2/auth/something",
          "", "", ok_cb, "some_cancel_cb")
      self.backend.process_transaction(1, REQUEST_INPUT_EVENTS)
      ok_cb.assert_called_with("test-token")
      accounts = self.db_session.query(Account).all()
      self.assertEqual(accounts[0].auth_token, None)
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      self.assertEqual(accounts[0].auth_token, "test-token")

  def test_input_unknown_user(self):
    self.create_account()
    ok_cb = Mock()
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks(
            "request-input", "prpl-jabber", "unknown@localhost",
            "Auth Code", "https://accounts.google.com/o/oauth2/auth/something",
            "", "", ok_cb, "some_cancel_cb")
        self.assertIn("User not found", log_cm.output[0])
        self.mc.create_room.assert_not_called()
        self.mc.send_message.assert_not_called()
        ok_cb.assert_not_called()

  def test_input_unknown_network(self):
    self.create_account()
    ok_cb = Mock()
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks(
            "request-input", "prpl-unknown", "unknown@localhost",
            "Auth Code", "https://accounts.google.com/o/oauth2/auth/something",
            "", "", "some_ok_cb", "some_cancel_cb")
        self.assertIn("No configuration found", log_cm.output[0])
        self.mc.create_room.assert_not_called()
        self.mc.send_message.assert_not_called()
        ok_cb.assert_not_called()
