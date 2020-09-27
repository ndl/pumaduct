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

"""Tests BaseLayer functionality."""

from pumaduct.layers.base import _parse_hs_host
from pumaduct.layers.tests.common import LayerTestCommon

class BaseLayerTest(LayerTestCommon):

  """Tests BaseLayer functionality."""

  def test_contacts_translation(self):
    self.backend = self.create_backend()
    with self.backend:
      # Mapping from external contact to MXID.
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "test@example.com"),
          "@xmpp-test%example.com:localhost")
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "test@example.com/resource"),
          "@xmpp-test%example.com:localhost")
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "example.com"),
          "@xmpp%example.com:localhost")
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "test@localhost"),
          "@xmpp-test:localhost")
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "localhost"),
          "@xmpp:localhost")
      self.assertEqual(
          self.backend.base.ext_contact_to_mxid("prpl-jabber", "user:with:col@localhost"),
          "@xmpp-user#with#col:localhost")
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.ext_contact_to_mxid("prpl-jabber", "user@"))
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.ext_contact_to_mxid("prpl-unknown", "user@domain"))
      # Mapping from MXID to external contact.
      self.assertEqual(
          self.backend.base.mxid_to_ext_contact("prpl-jabber", "@xmpp-test%example.com:localhost"),
          "test@example.com")
      self.assertEqual(
          self.backend.base.mxid_to_ext_contact("prpl-jabber", "@xmpp%example.com:localhost"),
          "@example.com")
      self.assertEqual(
          self.backend.base.mxid_to_ext_contact("prpl-jabber", "@xmpp-test:localhost"),
          "test@localhost")
      self.assertEqual(
          self.backend.base.mxid_to_ext_contact("prpl-jabber", "@xmpp:localhost"),
          "@localhost")
      self.assertEqual(
          self.backend.base.mxid_to_ext_contact("prpl-jabber", "@xmpp-user#with#col:localhost"),
          "user:with:col@localhost")
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.mxid_to_ext_contact("prpl-jabber", "@"))
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.mxid_to_ext_contact("prpl-jabber", "@hangouts-test:localhost"))
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.mxid_to_ext_contact("prpl-unknown", "user@domain"))

  def test_hs_host_parsing(self):
    self.backend = self.create_backend()
    # Hm, importing and calling internal module function - not nice ...
    self.assertEqual(_parse_hs_host("http://localhost:8448"), "localhost")
    self.assertEqual(_parse_hs_host("http://localhost"), "localhost")
    self.assertEqual(_parse_hs_host("http://some.domain"), "some.domain")

  def test_base_logic_errors(self):
    self.backend = self.create_backend()
    with self.backend:
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.remove_clients_callback("unknown-cmd", None))
      self.assertRaises(
          ValueError,
          lambda: self.backend.base.remove_transaction_callback("unknown-cmd", None))
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks("user-signed-on")
        self.assertIn("InternalError", log_cm.output[0])

  def test_transaction_unknown_event_type(self):
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(
            1, {"events": [{"sender": "@test:localhost", "type": "unknown"}]})
        self.assertIn("Unknown event", log_cm.output[0])

  def test_transaction_ignored_event_type(self):
    self.backend = self.create_backend()
    with self.backend:
      self.backend.process_transaction(
          1, {"events": [{"sender": "@test:localhost", "type": "m.room.create"}]})

  def test_transaction_missing_required_attributes(self):
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(1, {"events": [{}]})
        self.assertIn("missing required attributes", log_cm.output[0])

  def test_backend_start_stop(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.pc.login.assert_called_with(
          "prpl-jabber", "test@localhost", password="password", auth_token=None)
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      self.backend.stop()
      self.pc.logout.assert_called_with("prpl-jabber", "test@localhost")
      self.assertFalse(self.backend.stopped())
      self.backend.base.dispatch_callbacks("user-signed-off", "prpl-jabber", "test@localhost")
      self.assertTrue(self.backend.stopped())

  def test_transaction_denied_sender(self):
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(
            1, {"events": [{"sender": "@spammer:localhost", "type": "m.message"}]})
        self.assertIn("not allowed", log_cm.output[0])

  def test_transaction_unknown_sender(self):
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.process_transaction(
            1, {"events": [{"sender": "@test:remotehost", "type": "m.message"}]})
        self.assertIn("not allowed", log_cm.output[0])

  def test_has_contact(self):
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      self.assertFalse(self.backend.has_contact("@xmpp-test2:localhost"))
      self.backend.base.dispatch_callbacks(
          "contact-updated", "prpl-jabber", "test@localhost", "test2@localhost", "Test2")
      self.assertTrue(self.backend.has_contact("@xmpp-test2:localhost"))

  def test_ensure_room_and_user_power_level(self):
    self.conf["user_power_level"] = 75
    self.create_account()
    self.backend = self.create_backend()
    self.mc.create_room.return_value = "room_id0"
    with self.backend:
      self.backend.base.ensure_room("@test:localhost", "@xmpp-test2:localhost", 123)
      self.assertEqual(self.backend.base.rooms["room_id0"].user, "@test:localhost")
      self.assertEqual(self.backend.base.rooms["room_id0"].conv_id, 123)
      self.assertIn("@xmpp-test2:localhost", self.backend.base.rooms["room_id0"].members)
      self.mc.set_users_power_levels.assert_called_with(
          "room_id0", "@xmpp-test2:localhost",
          {"@test:localhost": 75, "@xmpp-test2:localhost": 100})
