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

"""Tests RoomStateLayer functionality."""

from pumaduct.layers.tests.common import LayerTestCommon

# pylint: disable=duplicate-code

MESSAGE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "invite"},
        "state_key": "@xmpp-test2:localhost",
        "room_id": "room_id1"
    }, {
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"msgtype": "m.text", "body": "Test message."},
        "room_id": "room_id1"
    }]
}

LEAVE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "leave"},
        "state_key": "@xmpp-test2:localhost",
        "room_id": "room_id1"
    }]
}

SERVICE_LEAVE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "leave"},
        "state_key": "@pumaduct:localhost",
        "room_id": "room_id0"
    }]
}

INITIAL_SYNC_CONTACT_STATE = {
    "next_batch": "abc123",
    "rooms": {
        "join": {
            "room_id1": {
                "state": {
                    "events": [{
                        "state_key": "@xmpp-test2:localhost",
                        "content": {"membership": "join"}
                    }, {
                        "state_key": "@test:localhost",
                        "content": {"membership": "join"}
                    }]
                }
            }
        }
    }
}

INITIAL_SYNC_SERVICE_USER_STATE = {
    "next_batch": "abc123",
    "rooms": {
        "join": {
            "room_id0": {
                "state": {
                    "events": [{
                        "state_key": "@pumaduct:localhost",
                        "content": {"membership": "join"}
                    }, {
                        "state_key": "@test:localhost",
                        "content": {"membership": "join"}
                    }]
                }
            }
        }
    }
}

UNEXPECTED_JOIN_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "join"},
        "state_key": "@pumaduct:localhost",
        "room_id": "room_id0"
    }, {
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "join"},
        "state_key": "@xmpp-test2:localhost",
        "room_id": "room_id1"
    }]
}

UNEXPECTED_MEMBERSHIP_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "unknown"},
        "state_key": "@xmpp-test2:localhost",
        "room_id": "room_id1"
    }]
}

class RoomStateLayerTest(LayerTestCommon):
  """Tests RoomStateLayer functionality."""

  def test_membership_leave(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, MESSAGE_EVENTS)
      self.assertIn("room_id1", self.backend.base.rooms)
      self.assertEqual(
          self.backend.base.rooms["room_id1"].members,
          set(["@xmpp-test2:localhost"]))
      self.backend.process_transaction(2, LEAVE_EVENTS)
      self.assertIn("room_id1", self.backend.base.rooms)
      self.assertEqual(self.backend.base.rooms["room_id1"].members, set())

  def test_membership_service_leave(self):
    self.create_account()
    self.backend = self.create_backend()
    self.mc.get_user_state.return_value = INITIAL_SYNC_SERVICE_USER_STATE
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      self.assertEqual(len(self.backend.service.rooms), 1)
      self.backend.process_transaction(1, SERVICE_LEAVE_EVENTS)
      self.assertEqual(len(self.backend.service.rooms), 0)
      with self.assertLogs() as log_cm:
        # The room should not be found, so no change is expected.
        self.backend.process_transaction(2, SERVICE_LEAVE_EVENTS)
        self.assertIn("no service room", log_cm.output[0])
        self.assertEqual(len(self.backend.service.rooms), 0)

  def test_unexpected_joins(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.pc.login.assert_called_with(
          "prpl-jabber", "test@localhost", password="password", auth_token=None)
      self.send_signon_callbacks()
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, UNEXPECTED_JOIN_EVENTS)
        self.assertIn("not recorded in our state", log_cm.output[0])
        self.assertIn("not recorded in our state", log_cm.output[1])
        self.assertEqual(len(self.backend.base.rooms), 0)
        self.assertEqual(len(self.backend.service.rooms), 0)

  def test_membership_errors(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, UNEXPECTED_MEMBERSHIP_EVENTS)
        self.assertIn("Unknown membership", log_cm.output[0])

  def test_initial_sync(self):
    self.create_account()
    self.backend = self.create_backend()
    self.mc.get_user_state.return_value = INITIAL_SYNC_SERVICE_USER_STATE
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "user-signed-on", "prpl-jabber", "test@localhost")
      self.assertEqual(len(self.backend.base.rooms), 0)
      self.assertEqual(len(self.backend.service.rooms), 1)
      self.assertIn("room_id0", self.backend.service.rooms)
      self.assertEqual(self.backend.service.rooms["room_id0"].user, "@test:localhost")
      self.mc.get_user_state.return_value = INITIAL_SYNC_CONTACT_STATE
      self.backend.base.dispatch_callbacks(
          "contact-updated", "prpl-jabber", "test@localhost", "test2@localhost", "Test2")
      self.assertEqual(len(self.backend.base.rooms), 1)
      self.assertEqual(len(self.backend.service.rooms), 1)
      self.assertIn("room_id1", self.backend.base.rooms)
      self.assertEqual(self.backend.base.rooms["room_id1"].user, "@test:localhost")
      self.assertEqual(
          self.backend.base.rooms["room_id1"].members,
          set(["@xmpp-test2:localhost"]))
