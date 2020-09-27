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

"""Tests RegistrationLayer functionality."""

import copy
from unittest.mock import Mock

from pumaduct.layers.tests.common import LayerTestCommon
from pumaduct.storage import Account

# pylint: disable=duplicate-code

REGISTRATION_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "invite"},
        "state_key": "@pumaduct:localhost",
        "room_id": "room_id0"
    }, {
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"body": "register prpl-jabber test@localhost 'password with spaces'"},
        "room_id": "room_id0"
    }]
}

UNREGISTRATION_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "invite"},
        "state_key": "@pumaduct:localhost",
        "room_id": "room_id0"
    }, {
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"body": "unregister prpl-jabber test@localhost"},
        "room_id": "room_id0"
    }]
}

REQUEST_INPUT_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id2",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"body": "auth-code"},
        "room_id": "room_id0"
    }]
}

class RegistrationLayerTest(LayerTestCommon):
  """Tests RegistrationLayer functionality."""

  def test_registration_success(self):
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, REGISTRATION_EVENTS)
      self.assertEqual(len(self.backend.registration.pending.keys()), 1)
      self.assertIn("room_id0", self.backend.service.rooms)
      self.assertNotIn("room_id0", self.backend.base.rooms)
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      accounts = self.db_session.query(Account).all()
      self.assertEqual(len(accounts), 1)
      self.assertEqual(accounts[0].user, "@test:localhost")
      self.assertEqual(accounts[0].network, "prpl-jabber")
      self.assertEqual(accounts[0].ext_user, "test@localhost")
      self.assertEqual(accounts[0].password, "password with spaces")
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Successfully registered @test:localhost", args[3]["body"])

  def test_registration_failure_invalid_username(self):
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, REGISTRATION_EVENTS)
      self.backend.base.dispatch_callbacks(
          "connection-error", "prpl-jabber", "test@localhost",
          "invalid username", "test description")
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      accounts = self.db_session.query(Account).all()
      self.assertEqual(len(accounts), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Failed to register @test:localhost", args[3]["body"])

  def test_registration_failure_wrong_format(self):
    self.backend = self.create_backend()
    reg_events = copy.deepcopy(REGISTRATION_EVENTS)
    reg_events["events"][1]["content"]["body"] = "register smth"
    with self.backend:
      self.backend.process_transaction(1, reg_events)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Wrong number", args[3]["body"])

  def test_registration_failure_unknown_network(self):
    self.create_account()
    self.backend = self.create_backend()
    reg_events = copy.deepcopy(REGISTRATION_EVENTS)
    reg_events["events"][1]["content"]["body"] = "register smth user password"
    with self.backend:
      self.backend.process_transaction(1, reg_events)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("not configured", args[3]["body"])

  def test_registration_failure_disabled_network(self):
    self.create_account()
    self.backend = self.create_backend()
    self.conf["networks"]["prpl-jabber"]["enabled"] = False
    with self.backend:
      self.backend.process_transaction(1, REGISTRATION_EVENTS)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("disabled", args[3]["body"])

  def test_registration_failure_already_registered(self):
    self.create_account()
    self.backend = self.create_backend()
    reg_events = copy.deepcopy(REGISTRATION_EVENTS)
    with self.backend:
      self.backend.process_transaction(1, reg_events)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("already registered", args[3]["body"])

  def test_registration_failure_no_room(self):
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, REGISTRATION_EVENTS)
      self.assertEqual(len(self.backend.registration.pending.keys()), 1)
      self.backend.service.rooms.clear()
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks(
            "connection-error", "prpl-jabber", "test@localhost",
            "invalid username", "test description")
        self.assertIn("InternalError", log_cm.output[0])
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks(
            "user-signed-on", "prpl-jabber", "test@localhost")
        self.assertIn("InternalError", log_cm.output[0])
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      self.assertEqual(self.db_session.query(Account).count(), 0)

  def test_registration_with_input(self):
    self.backend = self.create_backend()
    # Not strictly required for the test, but is likely to be on for the
    # registration with input anyway, plus allows us to test this code path.
    self.backend.base.networks["prpl-jabber"]["use_auth_token"] = True
    self.pc.get_auth_token.return_value = "test-token"
    ok_cb = Mock()
    with self.backend:
      self.backend.process_transaction(1, REGISTRATION_EVENTS)
      self.backend.base.dispatch_callbacks(
          "request-input", "prpl-jabber", "test@localhost",
          "Auth Code", "https://accounts.google.com/o/oauth2/auth/something",
          "", "", ok_cb, "some_cancel_cb")
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn(
          "https://accounts.google.com/o/oauth2/auth/something", args[3]["body"])
      self.backend.process_transaction(2, REQUEST_INPUT_EVENTS)
      ok_cb.assert_called_with("auth-code")
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      accounts = self.db_session.query(Account).all()
      self.assertEqual(len(accounts), 1)
      self.assertEqual(accounts[0].auth_token, "test-token")

  def test_unregistration_success(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.backend.messages.pending_deliveries_to_clients = set(
          [("@test:localhost", self.backend.base.accounts["@test:localhost"][0])])
      self.backend.process_transaction(1, UNREGISTRATION_EVENTS)
      accounts = self.db_session.query(Account).all()
      self.assertEqual(len(accounts), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Unregistered", args[3]["body"])

  def test_unregistration_failure_account_not_found(self):
    self.create_account()
    events = copy.deepcopy(UNREGISTRATION_EVENTS)
    events["events"][1]["content"]["body"] = "unregister prpl-jabber abc"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, events)
      accounts = self.db_session.query(Account).all()
      self.assertEqual(len(accounts), 1)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Cannot find", args[3]["body"])

  def test_unregistration_failure_wrong_format(self):
    self.create_account()
    self.backend = self.create_backend()
    reg_events = copy.deepcopy(UNREGISTRATION_EVENTS)
    reg_events["events"][1]["content"]["body"] = "unregister smth"
    with self.backend:
      self.backend.process_transaction(1, reg_events)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Wrong number", args[3]["body"])

  def test_unregistration_failure_unknown_network(self):
    self.create_account()
    self.backend = self.create_backend()
    reg_events = copy.deepcopy(UNREGISTRATION_EVENTS)
    reg_events["events"][1]["content"]["body"] = "unregister smth user"
    with self.backend:
      self.backend.process_transaction(1, reg_events)
      self.assertEqual(len(self.backend.registration.pending.keys()), 0)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("not configured", args[3]["body"])

  def test_registration_transaction_error(self):
    self.backend = self.create_backend()
    self.pc.login.side_effect = ValueError("test exception")
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, REGISTRATION_EVENTS)
        self.assertIn("ValueError", log_cm.output[0])
