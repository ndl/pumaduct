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

"""Tests InfoLayer functionality."""

import copy

from pumaduct.layers.tests.common import LayerTestCommon

# pylint: disable=duplicate-code

COMMAND_EVENTS = {
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
        "content": {},
        "room_id": "room_id0"
    }]
}

class InfoLayerTest(LayerTestCommon):
  """Tests InfoLayer functionality."""

  def test_accounts_success(self):
    self.create_account()
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "accounts"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertEqual(
          args[3]["body"], "* Network: 'prpl-jabber', user: 'test@localhost', "
          "status: 'online', number of contacts: 1, "
          "number of offline messages to client: 0\n")

  def test_accounts_failure_unknown_user(self):
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "accounts"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("don't have any registered accounts", args[3]["body"])

  def test_contacts_success(self):
    self.create_account()
    self.backend = self.create_backend()
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "contacts prpl-jabber test@localhost"
    self.pc.get_contact_status.return_value = "online"
    self.pc.get_contact_displayname.return_value = "Test2"
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertEqual(
          args[3]["body"], "* Contact: '@xmpp-test2:localhost', "
          "displayname: 'Test2', status: 'online'\n")

  def test_contacts_failure_account_not_found(self):
    self.create_account()
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "contacts prpl-jabber abc"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Cannot find", args[3]["body"])

  def test_contacts_failure_wrong_format(self):
    self.create_account()
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "contacts abc"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Wrong number", args[3]["body"])

  def test_contacts_failure_unknown_network(self):
    self.create_account()
    cmd_events = copy.deepcopy(COMMAND_EVENTS)
    cmd_events["events"][1]["content"]["body"] = "contacts abc def"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("not configured", args[3]["body"])
