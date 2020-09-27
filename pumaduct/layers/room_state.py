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

"""Manages bridge view of the room states in Matrix."""

import logging

from pumaduct.layers.layer_base import LayerBase
from pumaduct.utils import query_json_path

logger = logging.getLogger(__name__)

class RoomStateLayer(LayerBase):
  """
  Manages bridge view of the room states in Matrix.

  * Restores room configuration based on Matrix server state.
  * Handles room membership events.
  """
  def __init__(self, conf, base_layer, service_layer):
    del conf # Unused.
    self.base = base_layer
    self.service = service_layer
    self.contact_rooms_populated = set()

  def __enter__(self):
    self.base.add_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.add_clients_callback("contact-updated", self.on_contact_updated)
    self.base.add_transaction_callback("m.room.member", self.on_transaction_membership)

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.remove_clients_callback("contact-updated", self.on_contact_updated)
    self.base.remove_transaction_callback("m.room.member", self.on_transaction_membership)

  def start(self):
    # Initiate rooms processing for service user, as it won't happen automatically.
    self._populate_service_rooms()

  def on_user_signed_on(self, user, account):
    """Handles room state retrieval on user sign on."""
    # Retrieve all accounts contacts and populate these.
    # Because our callback is called after connection one, account.contacts
    # is populated already.
    for contact in account.contacts:
      ext_contact = self.base.mxid_to_ext_contact(account.network, contact)
      self.on_contact_updated(user, account, ext_contact, None)

  def on_contact_updated(self, user, account, ext_contact, display_name):
    """Populates room state for the contact, if necessary."""
    del display_name # Unused.
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    if (user, contact) not in self.contact_rooms_populated:
      self.contact_rooms_populated.add((user, contact))
      self._populate_contact_rooms(user, contact)

  def on_transaction_membership(self, transaction_id, event):
    """Handles membership requests from Matrix server."""
    del transaction_id # Unused.
    if event["content"]["membership"] == "invite":
      self._handle_invite_event(event)
    elif event["content"]["membership"] in ("leave", "ban"):
      self._handle_leave_event(event)
    elif event["content"]["membership"] == "join":
      self._handle_join_event(event)
    else:
      logger.error("Unknown membership event in transaction, ignoring: {0}", event)

  def _handle_invite_event(self, event):
    # We assume that the presence of the invited user in the contact list of the
    # account implies that they don't require any further request / confirmation to join
    # the room. This is likely the case for all 1:1 chats but might not be the case for
    # multi-user chats.
    sender = event["sender"]
    invited_user = event["state_key"]
    room_id = event["room_id"]
    if invited_user == self.service.user:
      if self.base.matrix_client.join_room(room_id, invited_user):
        self.service.rooms[room_id].user = sender
    elif self.base.find_account_for_contact(sender, invited_user):
      if not self._room_has_member(room_id, invited_user):
        if self.base.matrix_client.join_room(room_id, invited_user):
          if room_id not in self.base.rooms:
            self.base.rooms[room_id].user = sender
          self.base.rooms[room_id].members.add(invited_user)

  def _handle_leave_event(self, event):
    # We assume that we don't need to send any notification to the external
    # user whenever they're leaving / being banned from the room.
    sender = event["sender"]
    left_user = event["state_key"]
    room_id = event["room_id"]
    if left_user == self.service.user:
      if room_id in self.service.rooms:
        del self.service.rooms[room_id]
      else:
        logger.error(
            "Tried to remove service user '{0}' from the room '{1}' "
            "but no service room with this ID was found", left_user, room_id)
    elif self.base.find_account_for_contact(sender, left_user):
      if self._room_has_member(room_id, left_user):
        self.base.rooms[room_id].members.remove(left_user)

  def _handle_join_event(self, event):
    sender = event["sender"]
    joined_user = event["state_key"]
    room_id = event["room_id"]
    if joined_user == self.service.user:
      if room_id not in self.service.rooms:
        logger.error(
            "Service user '{0}' joined the room '{1}' but this is "
            "not recorded in our state", joined_user, room_id)
    elif self.base.find_account_for_contact(sender, joined_user):
      if (room_id not in self.base.rooms or
          joined_user not in self.base.rooms[room_id].members):
        logger.error(
            "User '{0}' joined the room '{1}' but this is "
            "not recorded in our state", joined_user, room_id)

  def _room_has_member(self, room_id, member):
    return room_id in self.base.rooms and member in self.base.rooms[room_id].members

  def _populate_contact_rooms(self, user, contact):
    state = self._get_rooms_state(contact)
    for room_id, members in _get_joined_members(state):
      if user in members and contact in members:
        self.base.rooms[room_id].user = user
        self.base.rooms[room_id].members.add(contact)

  def _populate_service_rooms(self):
    state = self._get_rooms_state(self.service.user)
    for room_id, members in _get_joined_members(state):
      if self.service.user in members and len(members) > 1:
        members.remove(self.service.user)
        self.service.rooms[room_id].user = members.pop()

  def _get_rooms_state(self, contact):
    # There seems to be no easy way to just get the current state of the room, or
    # even just to know which 'since' token should be used to get to the end of the
    # timeline :-(
    # Therefore we perform repeated 'sync' events until we stop getting new next_batch
    # and assume this is the end of the current timeline, so that the state associated
    # with this token can be used as the current state.
    # To reduce the traffic, we heavily filter the result to include only the info we're
    # eventually interested in.
    state_filter = {
        "room": {
            "state": {"types": ["m.room.member"]},
            "timeline": {"types": []},
            "ephemeral": {"types": []}
        },
        "account_data": {"types": []},
        "presence": {"types": []},
        "event_fields": ["type", "content.membership", "state_key"]
    }

    prev_batch = None
    next_batch = None
    while not next_batch or next_batch != prev_batch:
      state = self.base.matrix_client.get_user_state(
          contact, state_filter=state_filter, next_batch=next_batch)
      if state and "next_batch" in state:
        prev_batch = next_batch
        next_batch = state["next_batch"]
      else:
        break
    return state

def _get_joined_members(state):
  if state and "rooms" in state and "join" in state["rooms"]:
    for room_id, room_state in state["rooms"]["join"].items():
      members = set()
      events = query_json_path(room_state, "state", "events")
      if events:
        for event in events:
          state_key = query_json_path(event, "state_key")
          if state_key and query_json_path(event, "content", "membership") == "join":
            members.add(state_key)
      yield room_id, members
