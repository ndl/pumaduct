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

"""Tests ConnnectionLayer functionality."""

from pumaduct.layers.tests.common import LayerTestCommon

class ConnectionTest(LayerTestCommon):
  """Tests ConnnectionLayer functionality."""

  def test_subscription_requested(self):
    self.mc.get_non_managed_user_presence.return_value = None
    self.create_account()
    self.backend = self.create_backend()
    with self.backend:
      with self.assertLogs() as log_cm:
        self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
        self.mc.add_to_presence_list.assert_called_with("@test:localhost", "@pumaduct:localhost")
        self.assertIn("doesn't have the presence", log_cm.output[0])

  def test_account_profile_sync(self):
    self.create_account()
    self.pc.get_account_displayname.return_value = None
    self.mc.get_user_profile.return_value = {
        "displayname": "Test",
        "avatar_url": "mcx://localhost/media123"}
    self.pc.get_account_icon.return_value = (None, None)
    self.mc.download_content.return_value = "PNG"
    self.backend = self.create_backend()
    with self.backend:
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      self.pc.set_account_displayname.assert_called_with("prpl-jabber", "test@localhost", "Test")
      self.mc.download_content.assert_called_with("localhost", "/media123")
      self.pc.set_account_icon.assert_called_with("prpl-jabber", "test@localhost", "PNG")

  def test_contacts_updated_at_sign_on(self):
    self.create_account()
    self.mc.has_user.return_value = False
    self.pc.get_contacts.return_value = [("test2@localhost", "Test2")]
    self.backend = self.create_backend()
    with self.backend:
      self.backend.base.dispatch_callbacks("user-signed-on", "prpl-jabber", "test@localhost")
      self.assertIn(
          "@xmpp-test2:localhost",
          self.backend.base.accounts["@test:localhost"][0].contacts)
      self.mc.register_user.assert_called_with("@xmpp-test2:localhost")
