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

"""Handles providing accounts and contacts information to the user."""

import logging

from pumaduct.layers.layer_base import LayerBase

logger = logging.getLogger(__name__)

class InfoLayer(LayerBase):
  """Handles providing accounts and contacts information to the user."""

  def __init__( # pylint:disable=duplicate-code
      self, conf, base_layer, messages_layer, service_layer):
    del conf # Unused.
    self.base = base_layer
    self.messages = messages_layer
    self.service = service_layer

  def __enter__(self):
    self.service.add_service_callback(
        "accounts", self.on_service_accounts,
        "accounts - list all registered accounts and their status.")
    self.service.add_service_callback(
        "contacts", self.on_service_contacts,
        "contacts network user - list all contacts for given account.")

  def __exit__(self, type_, value, traceback):
    self.service.remove_service_callback("accounts", self.on_service_accounts)
    self.service.remove_service_callback("contacts", self.on_service_contacts)

  def on_service_accounts(self, transaction_id, event, args):
    """Handles accounts info request."""
    del transaction_id, args # Unused.
    room_id = event["room_id"]
    sender = event["sender"]
    if sender not in self.base.accounts:
      self.service.send_message(
          room_id, sender, "You don't have any registered accounts yet.")
      return
    result = ""
    for account in self.base.accounts[sender]:
      status = ("online" if account.connected else "offline")
      msgs_count = self.messages.get_messages_to_client(
          sender, account).count()
      result += (
          "* Network: '{0}', user: '{1}', status: '{2}', "
          "number of contacts: {3}, number of offline "
          "messages to client: {4}\n".format(
              account.network, account.ext_user,
              status, len(account.contacts), msgs_count))
    self.service.send_message(room_id, sender, result)

  # Consider extracting common functionality between this one and
  # on_service_unregister into some sort of on_service_network_cmd()?
  def on_service_contacts( # pylint:disable=duplicate-code
      self, transaction_id, event, args):
    """Handles contacts info request."""
    del transaction_id # Unused.
    room_id = event["room_id"]
    sender = event["sender"]
    if len(args) != 3:
      self.service.send_message(
          room_id, sender, "Wrong number of arguments for "
          "'contacts' command: {0}".format(args))
      return
    if args[1] not in self.base.networks:
      self.service.send_message(
          room_id, sender, "Network '{0}' is not configured "
          "in PuMaDuct config, don't know how to retrieve contacts.".format(args[1]))
      return
    user, account = self.base.find_user_and_account(args[1], args[2])
    if not user:
      self.service.send_message(
          room_id, sender, "Cannot find the account {0} on the network {1}"
          " to retrieve contacts.".format(args[2], args[1]))
      return
    result = ""
    for contact in account.contacts:
      ext_contact = self.base.mxid_to_ext_contact(account.network, contact)
      displayname = account.client.get_contact_displayname(
          account.network, account.ext_user, ext_contact)
      status = account.client.get_contact_status(
          account.network, account.ext_user, ext_contact)
      result += "* Contact: '{0}', displayname: '{1}', status: '{2}'\n".format(
          contact, displayname, status)
    self.service.send_message(room_id, sender, result)
