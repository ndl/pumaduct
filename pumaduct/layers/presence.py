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

"""Handles presences changes and their routing between clients and Matrix."""

import logging

from pumaduct.layers.layer_base import LayerBase
from pumaduct.utils import query_json_path

logger = logging.getLogger(__name__)

class PresenceLayer(LayerBase):
  """
  Handles presences changes and their routing between clients and Matrix.
  """
  def __init__(self, conf, base_layer, service_layer):
    self.base = base_layer
    self.service = service_layer
    self.presence_refresh_interval = conf["presence_refresh_interval"]
    self.presence_refresh_cb = None
    self.presence_list = set()

  def __enter__(self):
    self.base.add_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.add_clients_callback("connection-error", self.on_connection_error)
    self.base.add_clients_callback("user-signed-off", self.on_user_signed_off)
    self.base.add_clients_callback("contact-status-changed", self.on_contact_status_changed)

    self.base.add_transaction_callback("m.presence", self.on_transaction_presence)

  def __exit__(self, type_, value, traceback):
    self.base.matrix_client.set_user_presence(self.service.user, "offline")

    self.base.remove_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.remove_clients_callback("connection-error", self.on_connection_error)
    self.base.remove_clients_callback("user-signed-off", self.on_user_signed_off)
    self.base.remove_clients_callback("contact-status-changed", self.on_contact_status_changed)

    self.base.remove_transaction_callback("m.presence", self.on_transaction_presence)

  def start(self):
    self.presence_refresh_cb = self.base.glib.timeout_add_seconds(
        self.presence_refresh_interval, self.on_presence_refresh)

    # Determine which users are on our presence list.
    presence_list = self.base.matrix_client.get_presence_list(self.service.user)
    for presence in presence_list:
      user = query_json_path(presence, "content", "user_id")
      if user is not None:
        self.presence_list.add(user)

    # Add to presence list everybody who's not yet on it.
    for user in self.base.accounts:
      if user not in self.presence_list:
        logger.info(
            "Service {0} doesn't have the presence for user {1}, requesting",
            self.service.user, user)
        self.base.matrix_client.add_to_presence_list(user, self.service.user)

    self.base.matrix_client.set_user_presence(self.service.user, "online")

  def stop(self):
    if self.presence_refresh_cb:
      self.base.glib.source_remove(self.presence_refresh_cb)
      self.presence_refresh_cb = None

  def on_user_signed_on(self, user, account):
    """Syncs the presence between client and Matrix for user and contacts."""
    # Check that the user is on our presence list.
    # Might not be the case if the account was just registered.
    if user not in self.presence_list:
      logger.info(
          "Service {0} doesn't have the presence for user {1}, requesting",
          self.service.user, user)
      if self.base.matrix_client.add_to_presence_list(user, self.service.user):
        self.presence_list.add(user)

    # Mirror back to the client the presence of this user.
    presence = self.base.matrix_client.get_non_managed_user_presence(
        user, self.service.user)
    if presence is not None:
      account.client.set_account_status(
          account.network, account.ext_user, presence)

    # Fetch and update all contacts statuses for this account.
    self._set_contacts_statuses(user, account, None)

  def on_user_signed_off(self, user, account):
    """Sets contacts statuses for the user to 'offline'."""
    self._set_contacts_statuses(user, account, "offline")

  def on_connection_error(self, user, account, reason, description):
    """Sets contacts statuses for the user to 'offline'."""
    del reason, description # Unused.
    self._set_contacts_statuses(user, account, "offline")
    # Allow reconnect.
    return True

  def on_contact_status_changed(self, user, account, ext_contact, status):
    """Routes contact status change to Matrix."""
    del user # Unused.
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    self.base.matrix_client.set_user_presence(contact, status)

  def on_presence_refresh(self):
    """Refresh the presence for all contacts of all accounts on Matrix server."""
    for user, accounts in self.base.accounts.items():
      for account in accounts:
        # Set Matrix presence for all contacts of this user.
        for contact in account.contacts:
          ext_contact = self.base.mxid_to_ext_contact(account.network, contact)
          status = account.client.get_contact_status(
              account.network, account.ext_user, ext_contact)
          self.on_contact_status_changed(user, account, ext_contact, status)
    self.base.matrix_client.set_user_presence(self.service.user, "online")
    # Continue calling this callback.
    return True

  def on_transaction_presence(self, transaction_id, event):
    """Routes user presence changes from Matrix to the client."""
    del transaction_id # Unused.
    user = query_json_path(event, "content", "user_id")
    presence = query_json_path(event, "content", "presence")
    if user in self.base.accounts:
      for account in self.base.accounts[user]:
        account.client.set_account_status(account.network, account.ext_user, presence)

  def _set_contacts_statuses(self, user, account, status):
    # Set Matrix presence for all contacts of this user.
    for contact in account.contacts:
      ext_contact = self.base.mxid_to_ext_contact(account.network, contact)
      if not status:
        new_status = account.client.get_contact_status(
            account.network, account.ext_user, ext_contact)
      else:
        new_status = status
      self.on_contact_status_changed(user, account, ext_contact, new_status)
