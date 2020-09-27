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

"""Common functionality for all layers tests."""

import unittest

from unittest.mock import create_autospec

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pumaduct import backend
from pumaduct import glib
from pumaduct import logger_format
from pumaduct import matrix_client
from pumaduct import purple_client

from pumaduct.storage import Base, Account, Message

class BackendWithStopOnExit(backend.Backend):
  """Wrapper for PuMaDuct backend that calls stop() on exit."""

  def __exit__(self, type_, value, traceback):
    super(BackendWithStopOnExit, self).__exit__(type_, value, traceback)
    self.stop()

class LayerTestCommon(unittest.TestCase):
  """Common functionality for all layers tests."""

  def setUp(self):
    logger_format.setup()
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    self.glib = create_autospec(glib)
    self.glib.main_context_invoke.side_effect = lambda callback: callback()
    self.pc = create_autospec(purple_client.Client) # pylint: disable=invalid-name,no-member
    self.mc = create_autospec(matrix_client.Client) # pylint: disable=invalid-name
    self.conf = {
        "service_localpart": "pumaduct",
        "service_display_name": "PuMaDuct",
        "presence_refresh_interval": 600,
        "max_cache_items": 1,
        "sync_account_profile_changes": True,
        "sync_contacts_profiles_changes": True,
        "networks": {
            "prpl-jabber": {
                "prefix": "xmpp",
                "client": "purple",
                "ext_pattern": "^((?P<user>[^@]+)@)?(?P<host>[^/@]+)(/(?P<resource>.*))?$",
                "ext_format": "{user}@{host}",
                "inputs": [{
                    "pattern": "^https://accounts.google.com/o/oauth2/auth",
                    "message": "Please authorize Matrix bridge at url {primary} and reply "
                               "to this message with the code that was shown to you."
                }]}},
        "users_blacklist": ["^@spammer:{hs_host}$"],
        "users_whitelist": ["^@[^:]+:{hs_host}$"],
        "hs_server": "https://localhost:8448",
        "offline_messages_delivery_interval": 1
    }
    self.db_session = sessionmaker(bind=engine)()
    self.pc.get_contact_icon.return_value = ("png", "PNG")
    self.backend = None

  def create_account(self):
    """Creates new account for testing."""
    account = Account(
        user="@test:localhost", network="prpl-jabber",
        ext_user="test@localhost", password="password")
    self.db_session.add(account)
    self.db_session.commit()

  def send_signon_callbacks(self, also_contact=True):
    """Sends 'sign-on' and 'contact-updated' for the standard user and contact."""
    self.backend.base.dispatch_callbacks(
        "user-signed-on", "prpl-jabber", "test@localhost")
    if also_contact:
      self.backend.base.dispatch_callbacks(
          "contact-updated", "prpl-jabber", "test@localhost", "test2@localhost", "Test2")

  def create_backend(self):
    """Creates and initializes backend."""
    clients = {"purple": self.pc}
    return BackendWithStopOnExit(
        self.conf, self.glib, self.mc, clients,
        self.db_session, Account, Message)

  def tearDown(self):
    self.db_session = None
    Base.metadata.bind = None
    logger_format.clean()
