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

"""Creates and manages all backend processing layers."""

import contextlib
import functools
import logging

from pumaduct.layers.base import BaseLayer
from pumaduct.layers.connection import ConnectionLayer
from pumaduct.layers.input import InputLayer
from pumaduct.layers.messages import MessagesLayer
from pumaduct.layers.presence import PresenceLayer
from pumaduct.layers.registration import RegistrationLayer
from pumaduct.layers.room_state import RoomStateLayer
from pumaduct.layers.service import ServiceLayer
from pumaduct.layers.typing import TypingLayer
from pumaduct.layers.info import InfoLayer

logger = logging.getLogger(__name__)

class Backend(object): # pylint:disable=too-many-instance-attributes
  """Creates and manages all backend processing layers."""

  def __init__(self, conf, glib, matrix_client, clients, db_session,
               account_storage, message_storage):
    self.base = BaseLayer(conf, glib, matrix_client, clients, db_session,
                          account_storage, message_storage)
    self.connection = ConnectionLayer(conf, self.base)
    self.messages = MessagesLayer(conf, self.base)
    self.typing = TypingLayer(conf, self.base)
    self.service = ServiceLayer(conf, self.base, self.messages)
    self.room_state = RoomStateLayer(conf, self.base, self.service)
    self.presence = PresenceLayer(conf, self.base, self.service)
    self.registration = RegistrationLayer(
        conf, self.base, self.messages, self.service)
    self.input = InputLayer(
        conf, self.base, self.messages, self.service, self.registration)
    self.info = InfoLayer(conf, self.base, self.messages, self.service)
    self.layers = [
        self.base, self.connection, self.messages, self.typing, self.service,
        self.room_state, self.presence, self.registration, self.input, self.info]
    self.context_manager = contextlib.ExitStack()

  def __enter__(self):
    # First stage initialization: prepare callbacks and other stuff.
    for layer in self.layers:
      self.context_manager.enter_context(layer)
    # Second stage initialization: perform the actual work.
    for layer in self.layers:
      layer.start()

  def __exit__(self, type_, value, traceback):
    self.context_manager.close()

  def process_transaction(self, transaction_id, transaction):
    """Processes single transaction sent by Matrix server.

    Always returns success because the actual processing is delayed until
    the main loop picks it up and Matrix protocol for AS doesn't make provisions
    for reporting errors in transactions anyhow.

    Doing invocation in the main loop is necessary because HTTP thread runs in a
    separate thread and libpurple (hence, the rest of the processing) is not thread-safe."""
    self.base.glib.main_context_invoke(
        functools.partial(self.base.process_transaction, transaction_id, transaction))
    return True

  def has_contact(self, contact):
    """Checks whether given contact is the contact for any of the accounts we know about."""
    return self.base.has_contact(contact)

  def stop(self):
    """Initiates layers shutdown in the reverse sequence they were entered."""
    for layer in reversed(self.layers):
      layer.stop()

  def stopped(self):
    """Returns true if all layers have stopped."""
    for layer in self.layers:
      if not layer.stopped():
        return False
    return True
