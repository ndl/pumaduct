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

"""Provides service user-related functionality to the other layers."""

import logging
import shlex

from collections import defaultdict, namedtuple
from datetime import datetime

from pumaduct.layers.layer_base import LayerBase

logger = logging.getLogger(__name__)

class ServiceRoom(object):
  """
  Represents the room with the service user on the Matrix server.

  We track only Matrix user and service user, no other members in this room are expected.
  """
  def __init__(self, user=None):
    """
    :param user: MXID of the user this service room is for.

    These fields are set later, once the necessary information is available:
    * `data`: key-value storage to track temporary state in the room by the layers using it.
    """
    self.user = user
    self.data = {}

ServiceCallbackConfig = namedtuple("ServiceCallbackConfig", ["callback", "description"])

class ServiceLayer(LayerBase):
  """
  Provides service user-related functionality to the other layers.

  Also handles some generic service user-related activity like service user
  registration and service commands framework.
  """
  def __init__(self, conf, base_handler, messages_layer):
    self.base = base_handler
    self.messages = messages_layer
    self.rooms = defaultdict(ServiceRoom)
    self.callbacks = defaultdict(list)
    self.user = "@{0}:{1}".format(conf["service_localpart"], self.base.hs_host)
    self.display_name = conf["service_display_name"]

  def __enter__(self):
    self.base.add_transaction_callback("m.room.message", self.on_transaction_message)

  def __exit__(self, type_, value, traceback):
    self.base.remove_transaction_callback("m.room.message", self.on_transaction_message)

  def start(self):
    # Service user profile will be empty first time we run.
    # Note: service user registration / presence seems to be handled inconsistently
    # in Synapse, that is - even though the user is not registered, one still can get
    # its presence status, so we cannot use this criteria to decide if the user exists
    # or not. Therefore, use the absence of the service user profile as an indicator
    # that it's not registered and register it then.
    profile = self.base.matrix_client.get_user_profile(self.user)
    if not profile or "displayname" not in profile:
      self.base.matrix_client.register_user(self.user)
      self.base.matrix_client.set_user_display_name(self.user, self.display_name)

  def add_service_callback(self, cmd_id, callback, description):
    """Adds handler for the given service command."""
    self.callbacks[cmd_id].append(ServiceCallbackConfig(callback, description))

  def remove_service_callback(self, cmd_id, callback):
    """Removes previously added handler for the given service command."""
    if cmd_id in self.callbacks:
      for cb_config in self.callbacks[cmd_id]:
        if cb_config.callback == callback:
          self.callbacks[cmd_id].remove(cb_config)
          if not self.callbacks[cmd_id]:
            del self.callbacks[cmd_id]
          return
    raise ValueError("Callback '{0}' not found, cannot remove".format(cmd_id))

  def ensure_room(self, user):
    """Makes sure there's a room to communicate between the given user and service user."""
    for room_id, room in self.rooms.items():
      if room.user == user:
        return room_id
    room_id = self.base.matrix_client.create_room(self.user, [user])
    self.rooms[room_id].user = user
    return room_id

  def send_message(self, room_id, user, text):
    """Sends the message to Matrix from the service user with current time."""
    self.messages.send_message_to_matrix(
        None, room_id, self.user, user, datetime.utcnow(),
        {"msgtype": "m.text", "body": text})

  def on_transaction_message(self, transaction_id, event):
    """Routes the message from Matrix server either to service handlers or via 'normal' path."""
    room_id = event["room_id"]
    message = event["content"]["body"]
    if room_id in self.rooms:
      sender = event["sender"]
      # Process the message only if it isn't us who sent it.
      if sender != self.user:
        if "full-message" in self.callbacks:
          for cb_config in self.callbacks["full-message"]:
            if cb_config.callback(transaction_id, event):
              return
        # Nobody handled the message as a whole - interpret it as a list
        # of commands then.
        cmds = message.split("\n")
        for cmd in cmds:
          args = shlex.split(cmd)
          if args[0] in self.callbacks:
            for cb_config in self.callbacks[args[0]]:
              cb_config.callback(transaction_id, event, args)
            continue
          if args[0] == "help":
            self.send_message(room_id, sender, self._get_service_usage())
            continue
          else:
            self.send_message(
                room_id, sender, "Unknown command: '{0}'\n".format(cmd) +
                self._get_service_usage())
            return
    else:
      # This is not a 'service' message, handle it via 'normal' channel.
      self.messages.process_transaction_message(transaction_id, event)

  def _get_service_usage(self):
    descrs = []
    for cmd_id, cb_configs in self.callbacks.items():
      for cb_config in cb_configs:
        if cmd_id != "full-message":
          descrs.append(cb_config.description)
    return "Usage:\n" + "\n".join(sorted(descrs)) + "\nhelp - this help"
