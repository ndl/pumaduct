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

"""Handles users registeration / unregistration."""

import logging

from collections import defaultdict

from pumaduct.layers.layer_base import LayerBase
from pumaduct.layers.base import Account, InternalError

logger = logging.getLogger(__name__)

FATAL_REGISTRATION_ERRORS = set([
    "invalid username",
    "authentication failed",
    "authentication impossible",
    "name in use",
    "invalid settings"])

class Registration(object):
  """Represents one registration request on the external network by Matrix user."""

  def __init__(self, room_id=None, password=None):
    """
    :param room_id: ID of the service room the registration is taking place in.
    :param password: User password on the external network.
    """
    self.room_id = room_id
    self.password = password

class RegistrationLayer(LayerBase):
  """Handles users registeration / unregistration.

  This doesn't handle _actual_ registration on the external network -
  it's assumed the user has the account there already, it just lets PuMaDuct
  know about this account so that it can be used on behalf of the user."""

  def __init__(self, conf, base_layer, messages_layer, service_layer):
    del conf # Unused.
    self.base = base_layer
    self.messages = messages_layer
    self.service = service_layer
    self.pending = defaultdict(Registration)

  def __enter__(self):
    self.base.add_clients_callback(
        "user-signed-on", self.on_user_signed_on_without_account, map_account=False)
    self.base.add_clients_callback(
        "connection-error", self.on_connection_error_without_account, map_account=False)

    self.service.add_service_callback(
        "register", self.on_service_register,
        "register network user password - registers new account, "
        "the message will be redacted afterwards so that password doesn't stay in the history.")
    self.service.add_service_callback(
        "unregister", self.on_service_unregister,
        "unregister network user - unregisters exisitng account.")

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("user-signed-on", self.on_user_signed_on_without_account)
    self.base.remove_clients_callback("connection-error", self.on_connection_error_without_account)

    self.service.remove_service_callback("register", self.on_service_register)
    self.service.remove_service_callback("unregister", self.on_service_unregister)

  def on_user_signed_on_without_account(self, network, ext_user): # pylint: disable=invalid-name
    """If this sign on is for pending registration - create the corresponding account."""
    if (network, ext_user) in self.pending:
      reg = self.pending[(network, ext_user)]
      del self.pending[(network, ext_user)]
      if reg.room_id in self.service.rooms:
        user = self.service.rooms[reg.room_id].user
        stored_account = self.base.account_storage(
            user=user, network=network, ext_user=ext_user,
            password=reg.password)
        self.base.db_session.add(stored_account)
        self.base.db_session.commit()
        net_conf = self.base.networks[network]
        client = self.base.clients[net_conf["client"]]
        account = Account(
            stored_account.id, stored_account.network,
            stored_account.ext_user, stored_account.password,
            stored_account.auth_token, net_conf, client)
        self.base.accounts[user].append(account)
        self.service.send_message(
            reg.room_id, user, "Successfully registered "
            "{0} on the network {1}".format(user, network))
        self.base.dispatch_callbacks("user-signed-on", network, ext_user)
      else:
        raise InternalError("Room id '{0}' not found in service rooms!".format(reg.room_id))

  def on_connection_error_without_account( # pylint: disable=invalid-name
      self, network, ext_user, reason, description):
    """Discard the pending registration if this connection error is permanent."""
    reg_key = (network, ext_user)
    if reg_key in self.pending:
      if reason in FATAL_REGISTRATION_ERRORS:
        reg = self.pending[reg_key]
        if reg.room_id in self.service.rooms:
          user = self.service.rooms[reg.room_id].user
          self.service.send_message(
              reg.room_id, user, "Failed to register {0} on network {1}: "
              "error reason is '{2}', error description is: '{3}'".format(
                  user, network, reason, description))
          del self.pending[reg_key]
          return False
        else:
          raise InternalError("Room id '{0}' not found in service rooms!".format(reg.room_id))
    # Allow reconnect.
    return True

  def on_service_register(self, transaction_id, event, args):
    """Handles user registration request."""
    del transaction_id # Unused.
    room_id = event["room_id"]
    sender = event["sender"]
    if len(args) != 4:
      self.service.send_message(
          room_id, sender, "Wrong number of arguments "
          "for 'register' command: {0}".format(args))
      return
    if args[1] not in self.base.networks:
      self.service.send_message(
          room_id, sender,
          "Network '{0}' is not configured in PuMaDuct config,"
          " don't know how to register.".format(args[1]))
      return
    user, _ = self.base.find_user_and_account(args[1], args[2])
    if user:
      self.service.send_message(
          room_id, sender, "Account {0} on the network {1}"
          " is already registered.".format(args[2], args[1]))
      return
    net_conf = self.base.networks[args[1]]
    if "enabled" in net_conf and not net_conf["enabled"]:
      self.service.send_message(
          room_id, sender, "Network '{0}' is configured but currently "
          "disabled, cannot register.".format(args[1]))
      return
    event_id = event["event_id"]
    self.base.matrix_client.redact_event(
        room_id, self.service.user, event_id, "Stripped sensitive data")
    self.service.send_message(
        room_id, sender, "Registering account {0} "
        "on the network {1}...".format(args[2], args[1]))
    reg_key = (args[1], args[2])
    if reg_key not in self.pending:
      self.pending[reg_key] = Registration(room_id, args[3])
      self.base.clients[net_conf["client"]].login(
          args[1], args[2], password=args[3])

  def on_service_unregister(self, transaction_id, event, args):
    """Handles user unregistration request."""
    del transaction_id # Unused.
    room_id = event["room_id"]
    sender = event["sender"]
    if len(args) != 3:
      self.service.send_message(
          room_id, sender, "Wrong number of arguments "
          "for 'unregister' command: {0}".format(args))
      return
    if args[1] not in self.base.networks:
      self.service.send_message(
          room_id, sender, "Network '{0}' is not configured in "
          "PuMaDuct config, don't know how to unregister.".format(args[1]))
      return
    user, account = self.base.find_user_and_account(args[1], args[2])
    if not user:
      self.service.send_message(
          room_id, sender, "Cannot find the account {0} on "
          "the network {1} to unregister.".format(args[2], args[1]))
      return
    # Note: we're not cleaning up the rooms from the contacts
    # associated with this account as it's possible (although
    # unlikely) that some contacts might be the same between
    # multiple accounts.
    # Therefore, just clean up the accounts table and remove
    # its cached version. Offline messages stay intact and will
    # be garbage-collected once they expire.
    self.base.db_session.query(self.base.account_storage).filter(
        self.base.account_storage.id == account.id).delete()
    self.base.db_session.commit()
    self.base.accounts[user].remove(account)
    if not self.base.accounts[user]:
      del self.base.accounts[user]
    if (user, account) in self.messages.pending_deliveries_to_clients:
      self.messages.pending_deliveries_to_clients.remove((user, account))
    self.service.send_message(
        room_id, sender, "Unregistered account {0} for the user {1} "
        "on the network {2}.".format(args[2], user, args[1]))
