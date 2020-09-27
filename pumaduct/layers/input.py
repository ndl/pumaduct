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

"""Handles client requests for extra user input."""

import logging
import re

from collections import namedtuple

from pumaduct.layers.layer_base import LayerBase

logger = logging.getLogger(__name__)

PendingInput = namedtuple(
    "PendingInput",
    ["input_conf", "network", "ext_user", "ok_cb", "cancel_cb"])

class InputLayer(LayerBase):
  """
  Handles client requests for extra user input.

  Achieves this by exchanging Matrix messages between the user and service user.
  """
  def __init__(self, conf, base_layer, messages_layer, service_layer, registration_layer):
    del conf # Unused.
    self.base = base_layer
    self.messages = messages_layer
    self.service = service_layer
    self.registration = registration_layer

  def __enter__(self):
    self.base.add_clients_callback("request-input", self.on_request_input, map_account=False)
    self.service.add_service_callback("full-message", self.on_service_input, None)

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("request-input", self.on_request_input)
    self.service.remove_service_callback("full-message", self.on_service_input)

  def on_request_input( # pylint: disable=too-many-locals
      self, network, ext_user, title, primary, secondary,
      default_value, ok_cb, cancel_cb):
    """Handles initial input request from client."""
    if network in self.base.networks:
      net_conf = self.base.networks[network]
      for inp in net_conf["inputs"]:
        if re.match(inp["pattern"], primary):
          user, _ = self.base.find_user_and_account(network, ext_user)
          if not user:
            if (network, ext_user) in self.registration.pending:
              reg = self.registration.pending[(network, ext_user)]
              user = self.service.rooms[reg.room_id].user
          if user:
            room_id = self.service.ensure_room(user)
            self.service.rooms[room_id].data["pending-input"] = PendingInput(
                inp, network, ext_user, ok_cb, cancel_cb)
            self.service.send_message(
                room_id, user,
                inp["message"].format(
                    title=title,
                    primary=primary,
                    secondary=secondary,
                    default_value=default_value,
                    hs_host=self.base.hs_host))
            return
          else:
            logger.error(
                "User not found for network '{0}' and ext user '{1}' when "
                "processing input request '{2}'", network, ext_user, primary)
      logger.error(
          "Unknown input request for "
          "network '{0}': '{1}'", network, primary)
    else:
      logger.error(
          "No configuration found for network '{0}' when "
          "processing input request '{1}'", network, primary)

  def on_service_input(self, transaction_id, event):
    """Handles user response to the input request message sent earlier."""
    del transaction_id # Unused.
    room_id = event["room_id"]
    if "pending-input" in self.service.rooms[room_id].data:
      inp = self.service.rooms[room_id].data["pending-input"]
      del self.service.rooms[room_id].data["pending-input"]
      message = event["content"]["body"]
      inp.ok_cb(message.strip())
      return True
    else:
      return False
