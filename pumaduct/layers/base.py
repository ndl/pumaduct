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

"""Base layer for the bridge that provides the infrastructure for all other layers."""

from collections import defaultdict
import functools
import logging
import re
import urllib.parse

from cachetools import LRUCache

from pumaduct.layers.layer_base import LayerBase

logger = logging.getLogger(__name__)

class InternalError(Exception):
  """Exception class indicating internal / logic errors in the code."""
  pass

class Account(object):
  """
  Represents single account of the user on the external network.

  Matrix user ID is stored as a key in the corresponding dictionary
  data structure, hence not present here.
  """
  def __init__(self, id_=None, network=None, ext_user=None, password=None,
               auth_token=None, config=None, client=None):
    """
    :param id: ID of the account in the external DB.
    :param network: Network ID of the external network as a string, e.g. 'prpl-jabber'.
    :param ext_user: User ID on the external network, e.g. 'user@jabber.org'.
    :param password: User password on the external network.
    :param auth_token: If set, use this field instead of `password` for auth.
    :param config: Network configuration for the network of this account
        taken from networks config.
    :param client: client that handles the network of this account.

    These fields are set later, once the necessary information is available:
    * `connected`: tracks the connection status of this account, initially `False`.
    * `contacts`: tracks the set of contacts for this account on the external network,
      e.g. 'roster' in XMPP or "contact list" in other protocols. The contacts are
      stored in Matrix ID format, e.g. '@xmpp-user%jabber.org:localhost'.
    """
    self.id = id_ # pylint: disable=invalid-name
    self.network = network
    self.ext_user = ext_user
    self.password = password
    self.auth_token = auth_token
    self.config = config
    self.client = client
    self.connected = False
    self.contacts = set()

class Room(object):
  """
  Represents a single room on the Matrix server.

  Only the rooms that have at least one of the bridge-managed contacts are tracked.
  """
  def __init__(self, user=None, conv_id=None):
    """
    :param user: Matrix ID of the user that either created or owns this room.
    :param conv_id: if set, contains client opaque conversation ID for this conversation.
      This is used for Matrix room <-> libpuple conversation matching and tracking.

    These fields are set later, once the necessary information is available:
    * `members`: tracks the set of members for this room on the external network. Only
      bridge-managed external users are stored here, not every member of the room. The
      contacts are stored in Matrix ID format.
    """
    self.user = user
    self.conv_id = conv_id
    self.members = set()

class ClientsCallbackConfig(object):
  """
  Represents single instance of the callback registered with the clients.
  """
  def __init__(self, callback_id=None, callback=None, map_account=False):
    """
    :param callback_id: ID of the callback on the clients side.
    :param callback: The callback to call, the signature depends on `map_account`.
    :param map_account: If True, try to map 'network, ext_user' parameters received
      from client callback to 'user, account' and call `callback` with these instead.

    These fields are set later, once the necessary information is available:
    * `dispatcher`: the actual thing to call from the client that performs the necessary
      preprocessing before calling `callback`.
    """
    self.callback_id = callback_id
    self.callback = callback
    self.map_account = map_account
    self.dispatcher = None

class BaseLayer(LayerBase): # pylint: disable=too-many-instance-attributes
  """Base layer for the bridge that provides the infrastructure for all other layers."""

  RE_CONTACT_MXID = re.compile(
      r"^@(?P<prefix>[^-%:]+)(-(?P<user>[^%:]+))?(%(?P<host>[^:]+))?:(?P<hs_host>.+)$")
  # If this becomes network-specific, consider moving it to the config.
  USER_CHARS_REMAP = [(":", "#")]
  # We don't currently use any of these, so just silently discard them.
  IGNORED_EVENTS = set([
      "m.room.create",
      "m.room.power_levels",
      "m.room.join_rules",
      "m.room.history_visibility",
      "m.room.guest_access"])
  ADMIN_POWER_LEVEL = 100

  def __init__(self, conf, glib, matrix_client, clients,
               db_session, account_storage, message_storage):
    self.glib = glib
    self.matrix_client = matrix_client
    self.clients = clients
    self.db_session = db_session
    self.account_storage = account_storage
    self.message_storage = message_storage
    self.networks = conf["networks"]
    self.hs_host = _parse_hs_host(conf["hs_server"])
    self.users_blacklist = conf["users_blacklist"]
    self.users_whitelist = conf["users_whitelist"]
    self.accounts = defaultdict(list)
    self.rooms = defaultdict(Room)
    self.transaction_callbacks = defaultdict(list)
    self.clients_callbacks = defaultdict(list)
    self.mxids_to_ext_contacts = LRUCache(maxsize=conf["max_cache_items"])
    self.ext_contacts_to_mxids = LRUCache(maxsize=conf["max_cache_items"])
    self.senders_access = LRUCache(maxsize=conf["max_cache_items"])
    if "user_power_level" in conf:
      self.user_power_level = conf["user_power_level"]
    else:
      self.user_power_level = None

  def add_clients_callback(self, callback_id, callback, map_account=True):
    """Adds new callback to the event 'callback_id' for all clients."""
    cb_config = ClientsCallbackConfig(callback_id, callback, map_account)
    cb_config.dispatcher = functools.partial(self._callback_dispatcher, cb_config)
    self.clients_callbacks[callback_id].append(cb_config)
    for client in self.clients.values():
      client.add_callback(callback_id, cb_config.dispatcher)

  def remove_clients_callback(self, callback_id, callback):
    """Removes previously added clients callback."""
    if callback_id in self.clients_callbacks:
      for cb_config in self.clients_callbacks[callback_id]:
        if cb_config.callback == callback:
          for client in self.clients.values():
            client.remove_callback(callback_id, cb_config.dispatcher)
          self.clients_callbacks[callback_id].remove(cb_config)
          if not self.clients_callbacks[callback_id]:
            del self.clients_callbacks[callback_id]
          return
    raise ValueError("Callback '{0}' not found, cannot remove".format(callback_id))

  def dispatch_callbacks(self, callback_id, *args):
    """
    Forces all callbacks with given ID to be dispatched.

    Clients use direct calls to dispatchers, this is needed only to trigger
    callbacks programmatically, such as after account registration.
    """
    if callback_id in self.clients_callbacks:
      for cb_config in self.clients_callbacks[callback_id]:
        cb_config.dispatcher(*args)

  def add_transaction_callback(self, event_type, callback):
    """Adds transaction callback for the given event type."""
    self.transaction_callbacks[event_type].append(callback)

  def remove_transaction_callback(self, event_type, callback):
    """Removes previously added transaction callback."""
    if event_type in self.transaction_callbacks:
      if callback in self.transaction_callbacks[event_type]:
        self.transaction_callbacks[event_type].remove(callback)
        return
    raise ValueError("Callback '{0}' not found, cannot remove".format(event_type))

  def process_transaction(self, transaction_id, transaction):
    """Processes all transaction events by dispatching these to the appropriate callbacks."""
    for event in transaction["events"]:
      if "type" not in event:
        logger.warning(
            "The event is missing required attributes, "
            "discarding the event {0}", event)
        continue
      if "sender" in event and not self._is_sender_allowed(event["sender"]):
        logger.warning(
            "According to our ACLs, the sender '{0}' is not allowed - "
            "discarding the event {1}", event["sender"], event)
        continue
      if event["type"] in self.transaction_callbacks:
        for callback in self.transaction_callbacks[event["type"]]:
          try:
            callback(transaction_id, event)
          except: # pylint: disable=bare-except
            logger.exception(
                "Exception when processing "
                "transaction '{0}', event {1}:", transaction_id, event)
      elif event["type"] in BaseLayer.IGNORED_EVENTS:
        pass
      else:
        logger.error("Unknown event in transaction, ignoring: {0}", event)
    return True

  def ensure_room(self, user, contact, conv_id):
    """Ensures there's a room that can be used to communicate between the 'user' and 'contact'.

    First tries to find one and then, if not found, creates it."""
    room_id = self._find_room(user, contact, conv_id)
    if room_id:
      # If conv id for this room is not set - associate the current conv id with this room.
      if not self.rooms[room_id].conv_id:
        self.rooms[room_id].conv_id = conv_id
      return room_id
    # Note that even though it's external contact that creates the room, from the point of
    # view of self.rooms data structure our local matrix user is always an implicit member /
    # owner of the group and the 'contact' has to be stored as a 'member'.
    room_id = self.matrix_client.create_room(contact, [user])
    self.rooms[room_id].user = user
    self.rooms[room_id].conv_id = conv_id
    self.rooms[room_id].members.add(contact)
    if self.user_power_level:
      # Make sure to also set contact power level to admin, as if we don't include
      # the contact, Synapse resets its power level to 0 and if contact's power level
      # is too low - PuMaDuct cannot perform the required operations on behalf of that
      # user, such as sending the messages.
      self.matrix_client.set_users_power_levels(
          room_id, contact,
          {user: self.user_power_level,
           contact: BaseLayer.ADMIN_POWER_LEVEL})
    return room_id

  def ext_contact_to_mxid(self, network, ext_contact):
    """Translates external network contact format to Matrix ID."""
    if ext_contact in self.ext_contacts_to_mxids:
      return self.ext_contacts_to_mxids[ext_contact]

    if network in self.networks:
      net_conf = self.networks[network]
      match = re.match(net_conf["ext_pattern"], ext_contact)
      if match:
        matches = match.groupdict()
        if "user" in matches and matches["user"]:
          user_prefix = "{0}-{1}".format(net_conf["prefix"], matches["user"])
        else:
          user_prefix = net_conf["prefix"]
        for repl in BaseLayer.USER_CHARS_REMAP:
          user_prefix = user_prefix.replace(repl[0], repl[1])
        if "host" in matches and matches["host"] and matches["host"] != self.hs_host:
          contact = "@{0}%{1}:{2}".format(user_prefix, matches["host"], self.hs_host)
        else:
          contact = "@{0}:{1}".format(user_prefix, self.hs_host)
        self.ext_contacts_to_mxids[ext_contact] = contact
        return contact
      else:
        raise ValueError("Cannot parse external contact '{0}'".format(ext_contact))
    else:
      raise ValueError("Unknown network '{0}'".format(network))

  def mxid_to_ext_contact(self, network, contact):
    """Translates Matrix ID to external network contact format."""
    if contact in self.mxids_to_ext_contacts:
      return self.mxids_to_ext_contacts[contact]

    if network in self.networks:
      net_conf = self.networks[network]
      match = BaseLayer.RE_CONTACT_MXID.match(contact)
      if match:
        matches = match.groupdict()
        if not matches["host"]:
          matches["host"] = self.hs_host
        if not matches["user"]:
          matches["user"] = ""
        for repl in BaseLayer.USER_CHARS_REMAP:
          matches["user"] = matches["user"].replace(repl[1], repl[0])
        if matches["prefix"] != net_conf["prefix"]:
          raise ValueError("Unexpected service prefix: expected '{0}', got '{1}'".format(
              net_conf["prefix"], matches["prefix"]))
        ext_contact = net_conf["ext_format"].format(**matches)
        self.mxids_to_ext_contacts[contact] = ext_contact
        return ext_contact
      else:
        raise ValueError("Cannot parse Matrix ID '{0}'".format(contact))
    else:
      raise ValueError("Unknown network '{0}'".format(network))

  def find_account_for_contact(self, user, contact):
    """Finds account for the user suitable for communication with the contact."""
    if user in self.accounts:
      for account in self.accounts[user]:
        if contact in account.contacts:
          return account
    return None

  def find_user_and_account(self, network, ext_user):
    """Finds Matrix user and account that match given external user."""
    for user, accounts in self.accounts.items():
      for account in accounts:
        if network == account.network and ext_user == account.ext_user:
          return (user, account)
    return (None, None)

  def has_contact(self, contact):
    """Checks whether given contact is the contact for any of the accounts we know about."""
    for accounts in self.accounts.values():
      for account in accounts:
        if contact in account.contacts:
          return True
    return False

  def _find_room_single_pass(self, user, contact, conv_id):
    for room_id, room in self.rooms.items():
      if (contact in room.members and user == room.user and
          (conv_id == room.conv_id or not conv_id)):
        return room_id

  def _find_room(self, user, contact, conv_id):
    room_id = self._find_room_single_pass(user, contact, conv_id)
    if not room_id:
      room_id = self._find_room_single_pass(user, contact, None)
    return room_id

  def _callback_dispatcher(self, cb_config, *args):
    logger.debug(
        "In _callback_dispatcher for callback '{0}' with args '{1}'",
        cb_config.callback_id, args)
    try:
      if not cb_config.map_account:
        return cb_config.callback(*args)
      else:
        if len(args) < 2:
          raise InternalError(
              "Expected at least two arguments for "
              "callback '{0}' with map_account=True".format(cb_config.callback_id))
        network, ext_user = args[0], args[1]
        user, account = self.find_user_and_account(network, ext_user)
        if user:
          return cb_config.callback(user, account, *args[2:])
    except: # pylint: disable=bare-except
      logger.exception(
          "Exception while processing client "
          "callback '{0}':", cb_config.callback_id)

  def _is_sender_allowed(self, sender):
    if sender in self.senders_access:
      return self.senders_access[sender]
    for blacklist in self.users_blacklist:
      if re.match(blacklist.format(hs_host=self.hs_host), sender):
        self.senders_access[sender] = False
        return False
    for whitelist in self.users_whitelist:
      if re.match(whitelist.format(hs_host=self.hs_host), sender):
        self.senders_access[sender] = True
        return True
    self.senders_access[sender] = False
    return False

def _parse_hs_host(hs_server):
  parts = urllib.parse.urlparse(hs_server)
  ind = parts.netloc.find(":")
  if ind != -1:
    return parts.netloc[:ind]
  else:
    return parts.netloc
