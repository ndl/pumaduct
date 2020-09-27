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

"""Abstract interface for IM clients implementations."""

from abc import ABCMeta, abstractmethod

class ClientError(Exception):
  pass

class ImClientBase(metaclass=ABCMeta):
  """Abstract interface for IM clients implementations.

  The following callbacks need to be provided:
  * "user-signed-on": network, user
  * "user-signed-off": network, user
  * "new-auth-token": network, user, token
  * "connection-error": network, user, reason, description
  * "contact-status-changed": network, user, contact, status
  * "contact-typing": network, user, conversation_id, contact, is_typing
  * "new-message": network, user, conversation_id, contact,
      direction, body, time
  * "new-image": network, user, conversation_id, contact,
      direction, description, image, time
  * "new-file": network, user, conversation_id, contact,
      direction, description, file, time
  * "conversation-destroyed": network, user, conversation_id
  * "contact-updated": network, user, contact, displayname
  * "request-input": network, user, title, primary, secondary,
      default_value, ok_callback, cancel_callback.
  """

  @abstractmethod
  def __enter__(self):
    raise NotImplementedError()

  @abstractmethod
  def __exit__(self, type_, value, traceback):
    raise NotImplementedError()

  @abstractmethod
  def add_callback(self, callback_id, callback):
    raise NotImplementedError()

  @abstractmethod
  def remove_callback(self, callback_id, callback):
    raise NotImplementedError()

  @abstractmethod
  def login(self, network, user, password=None, auth_token=None):
    raise NotImplementedError()

  @abstractmethod
  def logout(self, network, user):
    raise NotImplementedError()

  @abstractmethod
  def get_auth_token(self, network, user):
    raise NotImplementedError()

  @abstractmethod
  def create_conversation(self, network, user, contact):
    raise NotImplementedError()

  @abstractmethod
  def send_message(self, network, user, conversation, message):
    raise NotImplementedError()

  @abstractmethod
  def send_image(self, network, user, conversation, description, content):
    raise NotImplementedError()

  @abstractmethod
  def send_file(self, network, user, conversation, description, content):
    raise NotImplementedError()

  @abstractmethod
  def set_typing(self, network, user, conversation, is_typing):
    raise NotImplementedError()

  @abstractmethod
  def get_contacts(self, network, user):
    raise NotImplementedError()

  @abstractmethod
  def get_contact_status(self, network, user, contact):
    raise NotImplementedError()

  @abstractmethod
  def get_contact_displayname(self, network, user, contact):
    raise NotImplementedError()

  @abstractmethod
  def get_contact_icon(self, network, user, contact):
    raise NotImplementedError()

  @abstractmethod
  def set_account_status(self, network, user, status):
    raise NotImplementedError()

  @abstractmethod
  def get_account_displayname(self, network, user):
    raise NotImplementedError()

  @abstractmethod
  def set_account_displayname(self, network, user, displayname):
    raise NotImplementedError()

  @abstractmethod
  def get_account_icon(self, network, user):
    raise NotImplementedError()

  @abstractmethod
  def set_account_icon(self, network, user, icon):
    raise NotImplementedError()
