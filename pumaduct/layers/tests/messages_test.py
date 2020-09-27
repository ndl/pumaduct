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

"""Tests MessagesLayer functionality."""

import copy
import logging
from datetime import datetime

from pumaduct.im_client_base import ClientError
from pumaduct.layers.base import InternalError
from pumaduct.layers.tests.common import LayerTestCommon
from pumaduct.storage import Message

# pylint: disable=duplicate-code

INVITE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.member",
        "content": {"membership": "invite"},
        "state_key": "@xmpp-test2:localhost",
        "room_id": "room_id1"
    }]
}

MESSAGE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"msgtype": "m.text", "body": "Test message."},
        "room_id": "room_id1"
    }]
}

FORMATTED_MESSAGE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {
            "msgtype": "m.text",
            "body": "Test **message**.",
            "format": "some-format",
            "formatted_body": "Test <strong>message</strong>."
        },
        "room_id": "room_id1"
    }]
}

INVITE_AND_MESSAGE_EVENTS = {
    "events": [
        INVITE_EVENTS["events"][0],
        MESSAGE_EVENTS["events"][0]
    ]
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

SENT_MESSAGE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id0",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {"msgtype": "m.text", "body": "Test message."},
        "room_id": "room_id1"
    }]
}

IMAGE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {
            "msgtype": "m.image",
            "body": "Test image",
            "url": "mcx://localhost/image-url"
        },
        "room_id": "room_id1"
    }]
}

FILE_EVENTS = {
    "events": [{
        "sender": "@test:localhost",
        "event_id": "event_id1",
        "origin_server_ts": 12345000,
        "type": "m.room.message",
        "content": {
            "msgtype": "m.file",
            "body": "Test file",
            "url": "mcx://localhost/file-url"
        },
        "room_id": "room_id1"
    }]
}

IMAGE_DATA = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x3b"
FILE_DATA = b"\x01\x02\x03\x04\x05"

class MessagesLayerTest(LayerTestCommon): # pylint: disable=too-many-public-methods
  """Tests MessagesLayer functionality."""

  def test_route_purple_message(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test message.", dt)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})

  def test_route_purple_message_postprocess(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    self.backend = self.create_backend()
    self.backend.base.networks["prpl-jabber"]["convert_to_text"] = "html2text"
    self.backend.base.networks["prpl-jabber"]["format"] = "some-format"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv",
          "<html><span><strong>Test</strong> message.</span></html>", dt)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "**Test** message.", "format": "some-format",
               "formatted_body": "<html><span><strong>Test</strong> message.</span></html>"})

  def test_route_purple_message_unknown_postprocessor(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    self.backend = self.create_backend()
    self.backend.base.networks["prpl-jabber"]["convert_to_text"] = "smth"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    with self.backend:
      self.send_signon_callbacks()
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks(
            "new-message", "prpl-jabber", "test@localhost", 123,
            "test2@localhost", "recv", "Test message.", dt)
        self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
        self.mc.send_message.assert_called_with(
            "room_id0", "@xmpp-test2:localhost",
            dt, {"msgtype": "m.text", "body": "Test message."})
        self.assertIn("is unknown", log_cm.output[0])

  def test_route_matrix_message(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.pc.send_message.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test message.")

  def test_route_matrix_message_postprocess(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    self.backend.base.networks["prpl-jabber"]["convert_from_text"] = "markdown"
    events = copy.deepcopy(INVITE_AND_MESSAGE_EVENTS)
    events["events"][1]["content"]["body"] = "**Test** message."
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, events)
      self.pc.send_message.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "<p><strong>Test</strong> message.</p>")

  def test_route_matrix_message_unknown_postprocessor(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    self.backend.base.networks["prpl-jabber"]["convert_from_text"] = "smth"
    with self.backend:
      self.send_signon_callbacks()
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
        self.assertIn("is unknown", log_cm.output[0])
        self.pc.send_message.assert_called_with(
            "prpl-jabber", "test@localhost", 123, "Test message.")

  def test_route_matrix_message_matching_format(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    self.backend.base.networks["prpl-jabber"]["format"] = "some-format"
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_EVENTS)
      self.backend.process_transaction(2, FORMATTED_MESSAGE_EVENTS)
      self.pc.send_message.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test <strong>message</strong>.")

  def test_conv_destroyed(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
      self.assertIn("room_id1", self.backend.base.rooms)
      self.assertEqual(self.backend.base.rooms["room_id1"].conv_id, 123)
      self.backend.base.dispatch_callbacks(
          "conversation-destroyed", "prpl-jabber", "test@localhost", 123)
      self.assertIsNone(self.backend.base.rooms["room_id1"].conv_id)

  def test_route_to_purple_message_offline(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.glib.timeout_add_seconds.return_value = 1
    self.backend = self.create_backend()
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "contact-updated", "prpl-jabber", "test@localhost", "test2@localhost", "Test2")
      self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
      # We won't check the content of the message here, as it's checked
      # below for the final message anyhow.
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_clients_cb, 1)
      self.assertEqual(len(self.backend.messages.pending_deliveries_to_clients), 1)
      # Attempt delivery, but account is still offline - nothing should change here.
      self.backend.messages.on_attempt_delivery_to_clients()
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_clients_cb, 1)
      self.assertEqual(len(self.backend.messages.pending_deliveries_to_clients), 1)
      # Bring account online - delivery should be performed automatically.
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.pc.send_message.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test message.")
      self.assertEqual(self.db_session.query(Message).count(), 0)
      self.assertEqual(self.backend.messages.offline_delivery_to_clients_cb, 1)
      # Should do nothing, just clear the callback.
      self.backend.messages.on_attempt_delivery_to_clients()
      self.assertEqual(self.backend.messages.offline_delivery_to_clients_cb, None)
      self.assertEqual(len(self.backend.messages.pending_deliveries_to_clients), 0)

  def test_route_to_purple_message_client_exception(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.pc.send_message.side_effect = ClientError("Something bad happened")
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
        # The message should be stored offline and we expect the relevant log output.
        self.assertEqual(self.db_session.query(Message).count(), 1)
        self.assertIn("Client failure", log_cm.output[0])

  def test_route_to_purple_message_delivery_scheduled_on_sign_on(self):
    self.create_account()
    self.pc.send_message.return_value = False
    self.glib.timeout_add_seconds.return_value = 1
    self.backend = self.create_backend()
    with self.backend:
      self.backend.base.dispatch_callbacks(
          "contact-updated", "prpl-jabber", "test@localhost", "test2@localhost", "Test2")
      self.backend.process_transaction(1, INVITE_AND_MESSAGE_EVENTS)
      # Bring account online - delivery should be attempted, but
      # send_message returns false - hence, the delivery should be scheduled.
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      args = self.glib.timeout_add_seconds.call_args[0]
      self.assertEqual(args[0], 1)
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_clients_cb, 1)

  def test_route_to_purple_message_without_account_no_room(self):
    self.backend = self.create_backend()
    self.create_account()
    self.pc.create_conversation.return_value = 123
    # Start backend with registered account but without the matching room -
    # the message should be pending.
    with self.backend:
      self.backend.process_transaction(1, MESSAGE_EVENTS)
      self.send_signon_callbacks()
      with self.assertLogs(level=logging.DEBUG) as log_cm:
        self.backend.messages.on_attempt_delivery_to_clients()
        self.assertIn("skipping delivery", log_cm.output[0])
        self.assertEqual(self.db_session.query(Message).count(), 1)
      # Join the room and attempt delivery, but send_message will return False -
      # the message should stay offline.
      self.pc.send_message.return_value = False
      self.backend.process_transaction(2, INVITE_EVENTS)
      with self.assertLogs(level=logging.DEBUG) as log_cm:
        self.backend.messages.on_attempt_delivery_to_clients()
        self.assertIn("Delivery failed", log_cm.output[1])
      self.assertEqual(self.db_session.query(Message).count(), 1)
      # Retry, but send_message will return True -
      # should be successful now.
      self.pc.send_message.return_value = True
      self.backend.messages.on_attempt_delivery_to_clients()
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.pc.send_message.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test message.")
      self.assertEqual(self.db_session.query(Message).count(), 0)

  def test_route_to_matrix_message_offline(self):
    self.create_account()
    self.mc.send_message.return_value = False
    self.mc.create_room.return_value = "room_id0"
    self.glib.timeout_add_seconds.return_value = 1
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test message.", dt)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_matrix_cb, 1)
      # Attempt delivery, but Matrix is still offline - nothing should change here.
      self.mc.reset_mock()
      self.backend.messages.on_attempt_delivery_to_matrix()
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_matrix_cb, 1)
    self.mc.reset_mock()
    with self.backend:
      # On backend restart it should attempt re-delivery, but Matrix is still offline,
      # so nothing should change.
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})
      self.assertEqual(self.db_session.query(Message).count(), 1)
      self.assertEqual(self.backend.messages.offline_delivery_to_matrix_cb, 1)
      # Brign Matrix online and re-attempt delivery.
      self.mc.send_message.return_value = True
      self.backend.messages.on_attempt_delivery_to_matrix()
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})
      self.assertEqual(self.db_session.query(Message).count(), 0)
      self.assertEqual(self.backend.messages.offline_delivery_to_matrix_cb, None)

  def test_route_purple_message_sent(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id1"
    self.mc.send_message.return_value = "event_id0"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-message", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "sent", "Test message.", dt)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id1", "@test:localhost",
          dt, {"msgtype": "m.text", "body": "Test message."})
      self.backend.process_transaction(1, SENT_MESSAGE_EVENTS)
      # Even though the message originates from our user, we should not attempt
      # sending it via libpurple as it was delivered from libpurple.
      self.pc.send_message.assert_not_called()

  def test_messages_errors(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.assertRaises(
          InternalError,
          lambda: self.backend.messages.send_message_to_client(
              "room_id0", "@unknown:localhost",
              "@unknown2:localhost", {"msgtype": "m.text", "body": "Test."}))

  def test_route_purple_image(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.mc.upload_content.return_value = "test-url"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-image", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test image", IMAGE_DATA, dt)
      self.mc.upload_content.assert_called_with("image/gif", IMAGE_DATA)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.image", "body": "Test image", "url": "test-url"})

  def test_route_purple_file(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.mc.upload_content.return_value = "test-url"
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-file", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test file", FILE_DATA, dt)
      self.mc.upload_content.assert_called_with("application/octet-stream", FILE_DATA)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.file", "body": "Test file", "url": "test-url"})

  def test_route_purple_image_offline(self):
    self.create_account()
    self.mc.create_room.return_value = "room_id0"
    dt = datetime(1970, 1, 1, 3, 25, 45)
    self.mc.upload_content.return_value = None
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.base.dispatch_callbacks(
          "new-image", "prpl-jabber", "test@localhost", 123,
          "test2@localhost", "recv", "Test image", IMAGE_DATA, dt)
      # upload_content failed, the image should be stored offline.
      self.mc.send_message.assert_not_called()
      self.assertEqual(self.db_session.query(Message).count(), 1)
      # Attempt redelivery - should still fail and the image should be kept offline.
      self.backend.messages.on_attempt_delivery_to_matrix()
      self.mc.send_message.assert_not_called()
      self.assertEqual(self.db_session.query(Message).count(), 1)
      # Allow upload_content to succeed and attempt re-delivery - should be fine now.
      self.mc.upload_content.return_value = "test-url"
      self.backend.messages.on_attempt_delivery_to_matrix()
      self.assertEqual(self.db_session.query(Message).count(), 0)
      self.mc.upload_content.assert_called_with("image/gif", IMAGE_DATA)
      self.mc.create_room.assert_called_with("@xmpp-test2:localhost", ["@test:localhost"])
      self.mc.send_message.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          dt, {"msgtype": "m.image", "body": "Test image", "url": "test-url"})

  def test_route_matrix_image(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.mc.download_content.return_value = IMAGE_DATA
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_EVENTS)
      self.backend.process_transaction(1, IMAGE_EVENTS)
      self.mc.download_content.assert_called_with("localhost", "/image-url")
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.pc.send_image.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test image", IMAGE_DATA)

  def test_route_matrix_file(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.mc.download_content.return_value = FILE_DATA
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_EVENTS)
      self.backend.process_transaction(1, FILE_EVENTS)
      self.mc.download_content.assert_called_with("localhost", "/file-url")
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.pc.send_file.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test file", FILE_DATA)

  def test_route_matrix_image_offline(self):
    self.create_account()
    self.pc.create_conversation.return_value = 123
    self.mc.download_content.return_value = None
    self.backend = self.create_backend()
    with self.backend:
      self.send_signon_callbacks()
      self.backend.process_transaction(1, INVITE_EVENTS)
      self.backend.process_transaction(1, IMAGE_EVENTS)
      # download_content failed - the image should be stored offline.
      self.mc.download_content.assert_called_with("localhost", "/image-url")
      self.pc.send_image.assert_not_called()
      self.assertEqual(self.db_session.query(Message).count(), 1)
      # download_content will succeed, but now send_image will fail - the image
      # should still be kept offline.
      self.mc.download_content.return_value = IMAGE_DATA
      self.pc.send_image.return_value = False
      self.backend.messages.on_attempt_delivery_to_clients()
      self.pc.create_conversation.assert_called_with(
          "prpl-jabber", "test@localhost", "test2@localhost")
      self.assertEqual(self.db_session.query(Message).count(), 1)
      # Finally, send_image will return True - everything should be OK now.
      self.pc.send_image.return_value = True
      self.backend.messages.on_attempt_delivery_to_clients()
      self.pc.send_image.assert_called_with(
          "prpl-jabber", "test@localhost", 123, "Test image", IMAGE_DATA)
      self.assertEqual(self.db_session.query(Message).count(), 0)
