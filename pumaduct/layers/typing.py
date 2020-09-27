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

"""Routes typing notifications between clients and Matrix."""

import logging

from pumaduct.layers.layer_base import LayerBase
from pumaduct.utils import query_json_path

logger = logging.getLogger(__name__)

class TypingLayer(LayerBase):
  """Routes typing notifications between clients and Matrix."""

  def __init__(self, conf, base_layer):
    del conf # Unused.
    self.base = base_layer

  def __enter__(self):
    self.base.add_clients_callback("contact-typing", self.on_contact_typing)
    self.base.add_transaction_callback("m.typing", self.on_transaction_typing)

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("contact-typing", self.on_contact_typing)
    self.base.remove_transaction_callback("m.typing", self.on_transaction_typing)

  def on_contact_typing(self, user, account, conv_id, ext_contact, is_typing):
    """Routes typing notifications from the client to Matrix server."""
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    room_id = self.base.ensure_room(user, contact, conv_id)
    self.base.matrix_client.set_user_typing(contact, room_id, is_typing)

  def on_transaction_typing(self, transaction_id, event):
    """Routes typing notifications from Matrix server to the client."""
    del transaction_id # Unused.
    room_id = query_json_path(event, "room_id")
    if room_id in self.base.rooms and self.base.rooms[room_id].members:
      user = self.base.rooms[room_id].user
      typing_user_ids = set(query_json_path(event, "content", "user_ids"))
      # Note: the implementation assumes 1:1 chat.
      contact = next(iter(self.base.rooms[room_id].members))
      account = self.base.find_account_for_contact(user, contact)
      if account:
        conv_id = self.base.rooms[room_id].conv_id
        # We cannot operate without conv_id as it's required by
        # the client for sending the typing state.
        if not conv_id:
          ext_contact = self.base.mxid_to_ext_contact(account.network, contact)
          conv_id = account.client.create_conversation(
              account.network, account.ext_user, ext_contact)
          self.base.rooms[room_id].conv_id = conv_id
        if conv_id:
          # Note: we can get here via feedback loop, that is - when Matrix server
          # receives our typing notification from the external client, it will send
          # us the transaction and we'll end up here. We cannot distinguish it from
          # the "genuine" update for the user and discard, though, so the best we
          # can do is to send the correct current typing state for the user.
          account.client.set_typing(
              account.network, account.ext_user, conv_id, user in typing_user_ids)
          return
      logger.info(
          "Cannot figure out conversation id or account "
          "for room '{0}', cannot set typing state", room_id)
    else:
      logger.info("Room '{0}' is unknown, cannot set typing state", room_id)
