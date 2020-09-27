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

"""Performs relevant actions on start / exit and account connectivity change."""

import logging
import urllib.parse

from pumaduct.layers.layer_base import LayerBase
from pumaduct.layers.base import Account

logger = logging.getLogger(__name__)

class ConnectionLayer(LayerBase):
  """
  Performs relevant actions on start / exit and account connectivity change.

  * Logins / log-offs all accounts on start / exit.
  * Updates `Account.connected` accordingly.
  * Restores contacts list configuration based on the client state.
  """
  def __init__(self, conf, base_layer):
    self.base = base_layer
    self.sync_account_profile_changes = conf["sync_account_profile_changes"]
    self.sync_contacts_profiles_changes = conf["sync_contacts_profiles_changes"]

  def __enter__(self):
    for account in self.base.db_session.query(self.base.account_storage).all():
      net_conf = self.base.networks[account.network]
      client = self.base.clients[net_conf["client"]]
      if "enabled" not in net_conf or net_conf["enabled"]:
        self.base.accounts[account.user].append(
            Account(account.id, account.network, account.ext_user, account.password,
                    account.auth_token, net_conf, client))

    self.base.add_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.add_clients_callback("user-signed-off", self.on_user_signed_off)
    self.base.add_clients_callback("connection-error", self.on_connection_error)
    self.base.add_clients_callback("contact-updated", self.on_contact_updated)
    self.base.add_clients_callback("new-auth-token", self.on_new_auth_token)

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.remove_clients_callback("user-signed-off", self.on_user_signed_off)
    self.base.remove_clients_callback("connection-error", self.on_connection_error)
    self.base.remove_clients_callback("contact-updated", self.on_contact_updated)
    self.base.remove_clients_callback("new-auth-token", self.on_new_auth_token)

    self.base.accounts.clear()

  def start(self):
    for accounts in self.base.accounts.values():
      for account in accounts:
        account.client.login(
            account.network, account.ext_user,
            password=account.password, auth_token=account.auth_token)

  def stop(self):
    """Disconnects all accounts."""
    for _, accounts in self.base.accounts.items():
      for account in accounts:
        account.client.logout(account.network, account.ext_user)

  def stopped(self):
    """Returns true if all accounts are disconnected."""
    for _, accounts in self.base.accounts.items():
      for account in accounts:
        if account.connected:
          return False
    return True

  def on_user_signed_on(self, user, account):
    """Performs the necessary bookkeeping when user signs on.

    More specifically:
    * Stores auth token, if necessary.
    * Syncs account profile from Matrix to client.
    * Performs updates on all contacts of the user."""
    account.connected = True
    if ("use_auth_token" in account.config and
        account.config["use_auth_token"]):
      auth_token = account.client.get_auth_token(
          account.network, account.ext_user)
      self.on_new_auth_token(user, account, auth_token)
    # Sync matrix profile back to the client one.
    profile = self.base.matrix_client.get_user_profile(user)
    account_displayname = account.client.get_account_displayname(
        account.network, account.ext_user)
    if ("displayname" in profile and
        (not account_displayname or (
            self.sync_account_profile_changes and
            account_displayname != profile["displayname"]))):
      account.client.set_account_displayname(
          account.network, account.ext_user, profile["displayname"])
    if "avatar_url" in profile:
      (_, icon_data) = account.client.get_account_icon(
          account.network, account.ext_user)
      # Note that there's no API to check the version / checksum of the
      # existing avatar, and re-downloading it each time we get here is
      # wasteful - therefore, downloading avatar only if it's not yet present.
      # This means we'll miss the updates to the existing avatars.
      if not icon_data:
        parts = urllib.parse.urlparse(profile["avatar_url"])
        icon = self.base.matrix_client.download_content(parts.netloc, parts.path)
        if icon:
          account.client.set_account_icon(account.network, account.ext_user, icon)
    ext_contacts = account.client.get_contacts(account.network, account.ext_user)
    for (ext_contact, display_name) in ext_contacts:
      self.on_contact_updated(user, account, ext_contact, display_name)

  def on_user_signed_off(self, user, account): # pylint: disable=no-self-use
    """Marks account as disconnected."""
    del user # Unused.
    account.connected = False

  def on_new_auth_token(self, user, account, auth_token):
    """Stores new auth token for subsequent reuse."""
    del user # Unused.
    stored_account = self.base.db_session.query(
        self.base.account_storage).get(account.id)
    stored_account.auth_token = auth_token
    self.base.db_session.commit()
    account.auth_token = auth_token

  def on_connection_error( # pylint: disable=no-self-use
      self, user, account, reason, description):
    """Marks account as disconnected."""
    del user, reason, description # Unused.
    account.connected = False
    # Allow reconnect.
    return True

  def on_contact_updated(self, user, account, ext_contact, display_name):
    """Syncs contact profile from the client to Matrix."""
    del user # Unused.
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    # Add the contact to the list of account contacts.
    # Note: for now performing the update only once, on the first contact
    # update callback, to avoid excessive load on Matrix server, as some
    # plugins generate high volume of on_contact_updated calls.
    if contact not in account.contacts:
      account.contacts.add(contact)
      # Register the user on Matrix for this contact, if it's not yet available.
      if not self.base.matrix_client.has_user(contact):
        self.base.matrix_client.register_user(contact)
      # Update contact profile on Matrix.
      profile = self.base.matrix_client.get_user_profile(contact)
      if (display_name and ("displayname" not in profile or
                            (self.sync_contacts_profiles_changes and
                             profile["displayname"] != display_name))):
        self.base.matrix_client.set_user_display_name(contact, display_name)
      (icon_ext, icon_data) = account.client.get_contact_icon(
          account.network, account.ext_user, ext_contact)
      # Note that there's no API to check the version / checksum of the
      # existing avatar, and re-downloading it each time we get here is
      # wasteful - therefore, uploading avatar only if it's not yet present.
      # This means we'll miss the updates to the existing avatars.
      if icon_data and "avatar_url" not in profile:
        content_uri = self.base.matrix_client.upload_content(
            "image/" + (icon_ext if icon_ext else "icon"), icon_data)
        if content_uri:
          self.base.matrix_client.set_user_avatar_url(contact, content_uri)
