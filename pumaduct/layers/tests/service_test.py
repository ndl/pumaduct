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

"""Tests ServiceLayer functionality."""

import copy

from pumaduct.layers.tests.common import LayerTestCommon
from pumaduct.storage import Message

SERVICE_EVENTS = {
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
        "content": {"body": ""},
        "room_id": "room_id0"
    }]
}

class ServiceLayerTest(LayerTestCommon):
  """Tests ServiceLayer functionality."""

  def test_service_help(self):
    help_events = copy.deepcopy(SERVICE_EVENTS)
    help_events["events"][1]["content"]["body"] = "help"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, help_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Usage:", args[3]["body"])
      # Make sure the messages in service room are not intercepted by
      # the 'normal' messages handler.
      self.assertEqual(self.db_session.query(Message).count(), 0)

  def test_service_unknown_cmd(self):
    unknown_cmd_events = copy.deepcopy(SERVICE_EVENTS)
    unknown_cmd_events["events"][1]["content"]["body"] = "abcabcabc"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(1, unknown_cmd_events)
      args = self.mc.send_message.call_args[0]
      self.assertEqual(args[0], "room_id0")
      self.assertEqual(args[1], "@pumaduct:localhost")
      self.assertIn("Unknown command:", args[3]["body"])
      self.assertIn("Usage:", args[3]["body"])

  def test_service_logic_errors(self):
    self.backend = self.create_backend()
    with self.backend:
      self.assertRaises(
          ValueError,
          lambda: self.backend.service.remove_service_callback("unknown-cmd", None))
