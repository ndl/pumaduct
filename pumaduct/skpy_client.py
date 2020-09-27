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

"""Implements ImClientBase interface for Skype network using SkPy library."""

from collections import defaultdict
from collections import namedtuple
import io
import logging
import threading

import requests

from skpy import Skype
from skpy import SkypeAuthException
from skpy import SkypeEndpointEvent
from skpy import SkypeMessageEvent
from skpy import SkypePresenceEvent
from skpy import SkypeImageMsg
from skpy import SkypeFileMsg
from skpy import SkypeTextMsg
from skpy import SkypeTypingEvent
from skpy import SkypeUtils

from pumaduct import glib
from pumaduct.im_client_base import ClientError
from pumaduct.im_client_base import ImClientBase

logger = logging.getLogger(__name__)

NetworkUser = namedtuple("NetworkUser", ["network", "user"])

class SkPyError(ClientError):
  """Error thrown for all SkPy client-specific errors."""
  pass

class SkypeLoop(Skype):
  """Wraps SkPy Skype class to provide threaded looping and events delivery."""

  def __init__(self, network, user, events_callback, loop_stopped_callback):
    super(SkypeLoop, self).__init__(connect=False)
    self.account = NetworkUser(network, user)
    self.events_callback = events_callback
    self.loop_stopped_callback = loop_stopped_callback
    self.statuses = {}
    self.sent_msgs = set()
    self.canceled = False

  def loop(self):
    """Execute skpy polling until cancel() is called."""
    self.canceled = False
    while not self.canceled:
      try:
        events = self.getEvents()
      except requests.ConnectionError:
        logger.exception("Connection error while polling")
      glib.main_context_invoke(
          lambda: self.events_callback(self, events))
      for event in events:
        event.ack()
    glib.main_context_invoke(
        lambda: self.loop_stopped_callback(self))

  def cancel(self):
    """Cancel skpy polling."""
    self.canceled = True

class Client(ImClientBase): # pylint: disable=too-many-public-methods
  """Implements ImClientBase interface for Skype network using SkPy library."""

  STATUS_MAP = {
      # pylint: disable=no-member
      SkypeUtils.Status.Online: "online",
      SkypeUtils.Status.Idle: "unavailable",
      SkypeUtils.Status.Away: "unavailable",
      SkypeUtils.Status.Busy: "unavailable",
      SkypeUtils.Status.Hidden: "unavailable",
      SkypeUtils.Status.Offline: "offline"
  }

  def __init__(self, conf):
    del conf # Unused.
    self.instances = {}
    self.threads = {}
    self.callbacks = defaultdict(list)

  def __enter__(self):
    pass

  def __exit__(self, type_, value, traceback):
    pass

  def add_callback(self, callback_id, callback):
    """Adds client callback."""
    self.callbacks[callback_id].append(callback)

  def remove_callback(self, callback_id, callback):
    """Removes previously added client callback."""
    self.callbacks[callback_id].remove(callback)

  def on_skpy_events(self, inst, events):
    """Handles all skpy-generated events."""
    logger.debug("on_skpy_events: {0}", events)
    for event in events:
      if isinstance(event, SkypePresenceEvent):
        self.on_contact_status_changed(inst, event)
      elif isinstance(event, SkypeTypingEvent):
        self.on_contact_typing(inst, event)
      elif isinstance(event, SkypeMessageEvent):
        return self.on_message(inst, event)
      elif isinstance(event, SkypeEndpointEvent):
        # Ignore, not actionable.
        pass
      else:
        logger.warning("Unknown SkPy event: {0}", event)

  def on_new_token(self, network, user, token):
    """Routes new auth token info from skpy to backend."""
    if "new-auth-token" in self.callbacks:
      for callback in self.callbacks["new-auth-token"]:
        callback(network, user, token)

  def on_contact_status_changed(self, inst, event):
    """Routes contact status change to backend."""
    user_id = event.user.id
    if ("contact-status-changed" in self.callbacks and
        user_id != inst.user.id):
      if event.status in Client.STATUS_MAP:
        network, user = inst.account
        status = Client.STATUS_MAP[event.status]
        inst.statuses[user_id] = status
        for callback in self.callbacks["contact-status-changed"]:
          callback(network, user, user_id, status)
      else:
        raise ValueError(
            "Unknown contact presence status: '{0}'".format(event.status))

  def on_contact_typing(self, inst, event):
    """Routes contact typing event to backend."""
    if "contact-typing" in self.callbacks:
      network, user = inst.account
      for callback in self.callbacks["contact-typing"]:
        callback(network, user, event.chat, event.user.id, event.active)

  def on_message(self, inst, event):
    """Routes message event (including image or file) to backend."""
    if event.msg.clientId in inst.sent_msgs:
      # This is our own message - skip.
      inst.sent_msgs.remove(event.msg.clientId)
      return
    network, user = inst.account
    if inst.user.id == event.msg.userId:
      direction = "sent"
      contact = event.msg.chat.user.id
    else:
      direction = "recv"
      contact = event.msg.userId
    if isinstance(event.msg, SkypeTextMsg):
      if "new-message" in self.callbacks:
        for callback in self.callbacks["new-message"]:
          callback(
              network, user, event.msg.chat, contact,
              direction, event.msg.html, event.msg.time)
    elif isinstance(event.msg, SkypeFileMsg):
      if isinstance(event.msg, SkypeImageMsg):
        callback_id = "new-image"
      else:
        callback_id = "new-file"
      if callback_id in self.callbacks:
        for callback in self.callbacks[callback_id]:
          callback(
              network, user, event.msg.chat, event.msg.userId,
              direction, event.msg.file.name,
              event.msg.fileContent, event.msg.time)
    else:
      logger.debug("Unknown message type, skipping: {0}", event.msg)

  def on_loop_stopped(self, inst):
    """Called when the polling loop finished after being canceled."""
    network, user = inst.account
    if (network, user) in self.threads:
      thread = self.threads[(network, user)]
      thread.join()
      del self.threads[(network, user)]
    del self.instances[(network, user)]
    if "user-signed-off" in self.callbacks:
      for callback in self.callbacks["user-signed-off"]:
        callback(network, user)

  def login(self, network, user, password=None, auth_token=None):
    """Attempts to login to skype network."""
    if (network, user) not in self.instances:
      inst = SkypeLoop(network, user, self.on_skpy_events, self.on_loop_stopped)
      inst.conn.setNewTokenCallback(
          lambda token: self.on_new_token(network, user, token))
      self.instances[(network, user)] = inst
    inst = self.instances[(network, user)]
    inst.conn.setUserPwd(user, password)
    if self._login(inst, auth_token) and inst.conn.connected:
      if "user-signed-on" in self.callbacks:
        for callback in self.callbacks["user-signed-on"]:
          callback(network, user)
      if (network, user) not in self.threads:
        thread = threading.Thread(target=inst.loop)
        self.threads[(network, user)] = thread
        thread.start()
    else:
      raise SkPyError("Unknown login flow state: not connected, "
                      "but also no exception")

  def logout(self, network, user):
    """Initiate logout from skype network."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      inst.cancel()
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def get_auth_token(self, network, user):
    """Retrieves current auth token."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      stream = io.StringIO()
      inst.conn.writeToken(stream)
      return stream.getvalue()
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def create_conversation(self, network, user, contact):
    """Creates (or returns existing) conversation."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      return inst.contacts[contact].chat
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def send_message(self, network, user, conversation, message):
    """Sends new message."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      # Skype doesn't seem to understand <strong> tag?
      message = message.replace("<strong>", "<b>")
      message = message.replace("</strong>", "</b>")
      msg = conversation.sendMsg(message)
      inst.sent_msgs.add(msg.clientId)
      return True
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def send_image(self, network, user, conversation, description, content):
    """Sends new image."""
    return self._send_file(network, user, conversation, description, content, True)

  def send_file(self, network, user, conversation, description, content):
    """Sends new file."""
    return self._send_file(network, user, conversation, description, content, False)

  def set_typing(self, network, user, conversation, is_typing):
    """Sets typing state for the conversation."""
    del network, user # Unused.
    conversation.setTyping(is_typing)

  def get_contacts(self, network, user):
    """Returns all user contacts."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      result = []
      for contact in inst.contacts:
        if contact.id != inst.user.id:
          displayname = self.get_contact_displayname(network, user, contact.id)
          result.append((contact.id, displayname))
      return result
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def get_contact_status(self, network, user, contact):
    """Returns status for the given contact."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      if contact in inst.statuses:
        return inst.statuses[contact]
      else:
        return "offline"
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def get_contact_displayname(self, network, user, contact):
    """Returns display name for the given contact."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      displayname = None
      contact_info = inst.contacts[contact]
      if contact_info and contact_info.name:
        displayname = str(contact_info.name)
      return displayname
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def get_contact_icon(self, network, user, contact):
    """Returns avatar / icon for the given contact."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      icon = None
      if contact in inst.contacts:
        contact_info = inst.contacts[contact]
        resp = requests.get(contact_info.avatar)
        if resp.status_code == requests.codes.ok: # pylint: disable=no-member
          icon = resp.content
      return (None, icon)
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def set_account_status(self, network, user, status):
    """Sets the status of the account."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      # pylint: disable=no-member
      if status == "online":
        inst.setPresence(SkypeUtils.Status.Online)
      elif status == "unavailable":
        inst.setPresence(SkypeUtils.Status.Busy)
      elif status == "offline":
        inst.setPresence(SkypeUtils.Status.Hidden)
      else:
        raise ValueError("Unknown status '{0}' requested for '{1}', '{2}'".format(
            status, network, user))
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def get_account_displayname(self, network, user):
    """Returns display name of the account."""
    return self.get_contact_displayname(network, user, user)

  def set_account_displayname(self, network, user, displayname):
    """Sets display name of the account."""
    logger.warning(
        "set_account_displayname is not implemented in SkPy: {0}, {1}, {2}",
        network, user, displayname)

  def get_account_icon(self, network, user):
    """Returns account icon / avatar."""
    return self.get_contact_icon(network, user, user)

  def set_account_icon(self, network, user, icon):
    """Sets account icon / avatar."""
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      inst.setAvatar(io.BytesIO(icon))
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")

  def _login(self, inst, auth_token):
    network, user = inst.account
    try:
      if auth_token:
        try:
          inst.conn.readToken(auth_token)
        except SkypeAuthException:
          logger.exception("Failed to reuse existing auth token")
          inst.conn.getSkypeToken()
      else:
        inst.conn.getSkypeToken()
    except SkypeAuthException as auth_ex:
      if "account doesn't exist" in auth_ex.args[0]:
        reason = "invalid username"
      else:
        reason = "authentication failed"
      if "connection-error" in self.callbacks:
        for callback in self.callbacks["connection-error"]:
          callback(network, user, reason, auth_ex.args[0])
      return False
    return True

  def _send_file(self, network, user, conversation, description, content, is_image):
    if (network, user) in self.instances:
      inst = self.instances[(network, user)]
      msg = conversation.sendFile(io.BytesIO(content), description, image=is_image)
      inst.sent_msgs.add(msg.clientId)
      return True
    else:
      raise SkPyError("Skype instance for '{0}', '{1}' was not found")
