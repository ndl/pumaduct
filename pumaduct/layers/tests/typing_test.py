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

"""Tests TypingLayer functionality."""

import copy

from pumaduct.layers.tests.common import LayerTestCommon

TYPING_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.typing",
        "content": {"user_ids": ["@test:localhost"]},
        "room_id": "room_id1"
    }]
}

NOT_TYPING_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.typing",
        "content": {"user_ids": []},
        "room_id": "room_id1"
    }]
}

class TypingLayerTest(LayerTestCommon):
  """Tests TypingLayer functionality."""

  def test_typing_to_matrix(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "contact-typing", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", True)
      self.mc.set_user_typing.assert_called_with(
          "@xmpp-test2:localhost", "room_id0", True)
      self.backend.base.dispatch_callbacks(
          "contact-typing", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", False)
      self.mc.set_user_typing.assert_called_with(
          "@xmpp-test2:localhost", "room_id0", False)

  def test_typing_to_purple(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id1"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, TYPING_EVENTS)
        # room_id is unknown, therefore no typing notification should be sent.
        self.pc.set_typing.assert_not_called()
        self.assertIn("cannot set typing state", log_cm.output[0])
      # Cheating here a bit - normally conv_id would never be 'None'
      # in this callback or in create_conversation() call, but we're setting
      # it 'None' so that we can test another code path in typing handling.
      self.pc.create_conversation.return_value = None
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", None,
          "test2@localhost", "recv", "Test message.", 12345)
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(2, TYPING_EVENTS)
        # conv_id is unknown, therefore no typing notification should be sent.
        self.pc.set_typing.assert_not_called()
        self.assertIn("cannot set typing state", log_cm.output[0])
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test message.", 12345)
      self.backend.process_transaction(3, TYPING_EVENTS)
      self.pc.set_typing.assert_called_with("prpl-jabber", "test@localhost", 123, True)
      self.backend.process_transaction(4, NOT_TYPING_EVENTS)
      self.pc.set_typing.assert_called_with("prpl-jabber", "test@localhost", 123, False)

  def test_typing_feedback_correct_state(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id1"
    typing_events = copy.deepcopy(TYPING_EVENTS)
    # Typing notification comes from external user - no need to send this
    # back to this external user.
    typing_events["events"][0]["content"]["user_ids"][0] = "@xmpp-test2:localhost"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test message.", 12345)
      self.backend.process_transaction(1, typing_events)
      # The user associated with the account is not present in typing user ids,
      # hence its typing update should be 'False'.
      self.pc.set_typing.assert_called_with("prpl-jabber", "test@localhost", 123, False)
