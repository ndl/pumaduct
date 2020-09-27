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

"""Handles messages delivery both to clients and Matrix."""

import base64
from datetime import datetime
import json
import logging
import urllib.parse

import html2text
import magic
import markdown

from pumaduct.im_client_base import ClientError
from pumaduct.layers.layer_base import LayerBase
from pumaduct.layers.base import InternalError
from pumaduct.utils import get_event_datetime, query_json_path

logger = logging.getLogger(__name__)

class MessagesLayer(LayerBase):
  """
  Handles messages delivery both to clients and Matrix.

  This also includes offline messages management.
  """
  def __init__(self, conf, base_layer):
    self.base = base_layer
    self.offline_delivery_interval = conf["offline_messages_delivery_interval"]
    self.pending_deliveries_to_clients = set()
    # Ideally this should be persisted, so that if AS is restarted between
    # the message is sent and transaction arrives, AS can still handle it correctly.
    self.sent_ids = set()
    self.offline_delivery_to_matrix_cb = None
    self.offline_delivery_to_clients_cb = None
    self.html2text = html2text.HTML2Text()

  def __enter__(self):
    self.base.add_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.add_clients_callback("new-message", self.on_new_message)
    self.base.add_clients_callback("new-image", self.on_new_image)
    self.base.add_clients_callback("new-file", self.on_new_file)
    self.base.add_clients_callback("conversation-destroyed", self.on_conversation_destroyed)

  def __exit__(self, type_, value, traceback):
    self.base.remove_clients_callback("user-signed-on", self.on_user_signed_on)
    self.base.remove_clients_callback("new-message", self.on_new_message)
    self.base.remove_clients_callback("new-image", self.on_new_image)
    self.base.remove_clients_callback("new-file", self.on_new_file)
    self.base.remove_clients_callback("conversation-destroyed", self.on_conversation_destroyed)

  def start(self):
    # Attempt delivering offline messages to Matrix server, if any.
    self._attempt_delivery_to_matrix()
    if self.get_messages_to_matrix().count():
      self._schedule_delivery_to_matrix()

  def stop(self):
    if self.offline_delivery_to_matrix_cb:
      self.base.glib.source_remove(self.offline_delivery_to_matrix_cb)
      self.offline_delivery_to_matrix_cb = None

    if self.offline_delivery_to_clients_cb:
      self.base.glib.source_remove(self.offline_delivery_to_clients_cb)
      self.offline_delivery_to_clients_cb = None

  def on_user_signed_on(self, user, account):
    """Schedules offline messages delivery on user sign on, if necessary."""
    self._attempt_delivery_to_client(user, account)
    # Check if we need to schedule offline messages delivery.
    if self.get_messages_to_client(user, account).count():
      self.pending_deliveries_to_clients.add((user, account))
      self._schedule_delivery_to_clients()
    # The same, but for offline messages that were recorded without account.
    if self.get_messages_to_client(user, None).count():
      self.pending_deliveries_to_clients.add((user, None))
      self._schedule_delivery_to_clients()

  def on_new_message(
      self, user, account, conv_id, ext_contact, direction, body, time):
    """Routes the message received from the client to the relevant Matrix room."""
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    room_id = self.base.ensure_room(user, contact, conv_id)
    if direction == "recv":
      contact, user = user, contact
    payload = self._create_matrix_text_payload(account, body)
    self.send_message_to_matrix(account, room_id, user, contact, time, payload)

  def on_new_image(
      self, user, account, conv_id, ext_contact, direction, description, content, time):
    """Routes the image received from the client to the relevant Matrix room."""
    self._send_file_to_matrix(
        user, account, conv_id, ext_contact, direction,
        description, content, time, "m.image")

  def on_new_file(
      self, user, account, conv_id, ext_contact, direction, description, content, time):
    """Routes the image received from the client to the relevant Matrix room."""
    self._send_file_to_matrix(
        user, account, conv_id, ext_contact, direction,
        description, content, time, "m.file")

  def on_conversation_destroyed(self, user, account, conv_id):
    """Clears removed conversation id from our internal datastructures."""
    del user, account # Unused.
    for _, room in self.base.rooms.items():
      if room.conv_id == conv_id:
        room.conv_id = None

  def process_transaction_message(self, transaction_id, event):
    """Processes messagereceived from Matrix.

    Note: this function is not registered directly as a callback but is called
    from 'ServiceLayer' if it determines the message should be handled as the
    'normal' one."""
    del transaction_id # Unused.
    sender = event["sender"]
    room_id = event["room_id"]
    payload = query_json_path(event, "content")
    if sender in self.base.accounts:
      if event["event_id"] in self.sent_ids:
        self.sent_ids.remove(event["event_id"])
        return
      if room_id in self.base.rooms:
        for member in self.base.rooms[room_id].members:
          self.send_message_to_client(room_id, sender, member, payload)
      else:
        # Unknown room_id - potentially we're not currently tracking
        # the recipient contact, so we cannot determine the exact account to use.
        # Store message as offline so that once the contact is online and its room state
        # is fetched - we can deliver the message.
        self._store_offline_message_to_clients_without_account(
            room_id, sender, get_event_datetime(event), payload)

  def send_message_to_matrix(
      self, account, room_id, sender, recipient, time, payload, offline=False):
    """Sends the message to Matrix room.

    Note: account can be set to None, then `network` and `ext_user` fields won't be set.
    This could be a problem for matching client-originating messages, but in all those
    cases we actually should have account set - the only current case of not having an
    account are the messages from the service to the user and these are deliverable
    without account-level info."""
    result = self.base.matrix_client.send_message(
        room_id, sender, time, payload)
    if result and sender in self.base.accounts:
      self.sent_ids.add(result)
    if not result and not offline:
      self._store_offline_message_to_matrix(
          account, room_id, sender, recipient, time, payload)
    return result

  def send_message_to_client(
      self, room_id, sender, recipient, payload, offline=False):
    """Sends the message to the client contact."""
    account = self.base.find_account_for_contact(sender, recipient)
    # This function is called only when the recipient is known, so
    # the account should always be retrievable.
    if not account:
      raise InternalError(
          "Cannot retrieve account for sender "
          "{0} and recipient {1}".format(sender, recipient))
    if account.connected:
      try:
        if not self.base.rooms[room_id].conv_id:
          ext_contact = self.base.mxid_to_ext_contact(account.network, recipient)
          conv_id = account.client.create_conversation(
              account.network, account.ext_user, ext_contact)
          self.base.rooms[room_id].conv_id = conv_id
        else:
          conv_id = self.base.rooms[room_id].conv_id
        if payload["msgtype"] == "m.text":
          rendered_body = _render_payload_for_client(account, payload)
          if account.client.send_message(
              account.network, account.ext_user, conv_id, rendered_body):
            return True
        elif payload["msgtype"] in ("m.image", "m.file"):
          if self._send_file_to_client(account, conv_id, payload):
            return True
      except ClientError:
        logger.exception("Client failure while attempting to deliver the message")
    # If the message wasn't delivered and it's not offline delivery retry - store it.
    if not offline:
      self._store_offline_message_to_clients(
          account, room_id, sender, recipient, payload)
    return False

  def on_attempt_delivery_to_clients(self):
    """Attempts delivering all pending offline messages to clients."""
    # Keep track of accounts we've delivered to successfully.
    delivered_to_clients = set()
    msgs_before = 0
    msgs_after = 0
    # Iterate over all accounts and try to deliver for each one.
    for (user, account) in self.pending_deliveries_to_clients:
      msgs_before += self.get_messages_to_client(user, account).count()
      self._attempt_delivery_to_client(user, account)
      # If we're successful - put this account onto cleanup queue.
      remaining_msgs = self.get_messages_to_client(user, account).count()
      msgs_after += remaining_msgs
      if not remaining_msgs:
        delivered_to_clients.add((user, account))
    # Delete all accounts from the queue for which delivery was successful.
    for (user, account) in delivered_to_clients:
      self.pending_deliveries_to_clients.remove((user, account))
    # If there are no more deliveries left - clean up the callback and return 'False'
    # below for the callback to stop being called.
    if not self.pending_deliveries_to_clients:
      self.offline_delivery_to_clients_cb = None
    logger.debug(
        "Attempted delivery of {0} offline messages to client, "
        "{1} of them remained", msgs_before, msgs_after)
    return bool(self.pending_deliveries_to_clients)

  def on_attempt_delivery_to_matrix(self):
    """Attempts delivering all pending offline messages to Matrix."""
    msgs_before = self.get_messages_to_matrix().count()
    self._attempt_delivery_to_matrix()
    remaining_msgs = self.get_messages_to_matrix().count()
    logger.debug(
        "Attempted delivery of {0} offline messages to Matrix, "
        "{1} of them remained", msgs_before, remaining_msgs)
    if not remaining_msgs:
      self.offline_delivery_to_matrix_cb = None
    return bool(remaining_msgs)

  def get_messages_to_client(self, user, account):
    """Retrieves all offline messages to the client for given user and account."""
    msg = self.base.message_storage
    return self.base.db_session.query(msg).filter(
        msg.network == (account.network if account else None),
        msg.ext_user == (account.ext_user if account else None),
        msg.sender == user,
        msg.destination == "client").order_by(msg.time)

  def get_messages_to_matrix(self):
    """Retrieves all offline messages to Matrix."""
    msg = self.base.message_storage
    return self.base.db_session.query(msg).filter(
        msg.destination == "matrix").order_by(msg.time)

  def _attempt_delivery_to_client(self, user, account):
    for message in self.get_messages_to_client(user, account):
      payload = json.loads(message.payload)
      if not message.recipient:
        if not message.room_id:
          raise InternalError( # pragma: no cover, this is only to detect potential
              # logical errors in the code - no known triggering scenario.
              "Inconsistent offline message: both recipient and room_id are null!")
        if message.room_id in self.base.rooms:
          for member in self.base.rooms[message.room_id].members:
            logger.debug(
                "Attempting offline message delivery to client without recipient: "
                "room_id '{0}', sender '{1}', member '{2}', payload '{3}'",
                message.room_id, message.sender, member, message.payload)
            if not self.send_message_to_client(
                message.room_id, message.sender, member, payload, offline=True):
              logger.debug("Delivery failed, keeping the message")
              self.base.db_session.commit()
              return
        else:
          # Room / contact is still not available - continue.
          # Note: 'coverage' fails to record the execution of this branch if there's
          # only 'continue' statement here.
          logger.debug("No room '{0}' found, skipping delivery for now", message.room_id)
          continue
      else:
        room_id = message.room_id or self.base.ensure_room(user, message.recipient, None)
        logger.debug(
            "Attempting offline message delivery to client: "
            "room_id '{0}', sender '{1}', recipient '{2}', payload '{3}'",
            room_id, message.sender, message.recipient, message.payload)
        if not self.send_message_to_client(
            room_id, message.sender, message.recipient, payload, offline=True):
          logger.debug("Delivery failed, keeping the message")
          break
      # If we got up until here - the delivery was successful, so it's fine to discard this message.
      self.base.db_session.delete(message)
    self.base.db_session.commit()

  # Matrix server becomes available 'as a whole', not for particlar account only - therefore,
  # there's no sense in trying to do per-user delivery, just try flushing everything in one go.
  def _attempt_delivery_to_matrix(self):
    for message in self.get_messages_to_matrix():
      room_id = self.base.ensure_room(message.recipient, message.sender, None)
      payload = json.loads(message.payload)
      logger.debug(
          "Attempting offline message delivery to matrix: "
          "room_id '{0}', sender '{1}', recipient '{2}', time '{3}', payload '{4}'",
          room_id, message.sender, message.recipient, message.time, payload)
      if "content" in payload:
        url = self.base.matrix_client.upload_content(
            payload["content-type"], base64.b64decode(payload["content"].encode("ascii")))
        if url:
          payload["url"] = url
          del payload["content"], payload["content-type"]
        else:
          break
      if not self.send_message_to_matrix(
          None, room_id, message.sender, message.recipient,
          message.time, payload, offline=True):
        break
      self.base.db_session.delete(message)
    self.base.db_session.commit()

  def _schedule_delivery_to_matrix(self):
    if not self.offline_delivery_to_matrix_cb:
      self.offline_delivery_to_matrix_cb = self.base.glib.timeout_add_seconds(
          self.offline_delivery_interval, self.on_attempt_delivery_to_matrix)

  def _schedule_delivery_to_clients(self):
    if not self.offline_delivery_to_clients_cb:
      self.offline_delivery_to_clients_cb = self.base.glib.timeout_add_seconds(
          self.offline_delivery_interval, self.on_attempt_delivery_to_clients)

  def _store_offline_message_to_matrix( # pylint: disable=invalid-name
      self, account, room_id, sender, recipient, time, payload):
    logger.debug(
        "Storing offline message to matrix for network '{0}', ext user '{1}' "
        "from sender '{2}' to room_id '{3}' and recipient '{4}' at time '{5}': '{6}'",
        account.network, account.ext_user, sender, room_id, recipient, time, payload)
    stored_msg = self.base.message_storage(
        network=(account.network if account else None),
        ext_user=(account.ext_user if account else None),
        room_id=room_id,
        sender=sender,
        recipient=recipient,
        time=time,
        destination="matrix",
        payload=json.dumps(payload))
    self.base.db_session.add(stored_msg)
    self.base.db_session.commit()
    self._schedule_delivery_to_matrix()

  def _store_offline_message_to_clients( # pylint: disable=invalid-name
      self, account, room_id, sender, recipient, payload):
    logger.debug(
        "Storing offline message to client for network '{0}', ext user '{1}' "
        "from room_id '{2}', sender '{3}' to recipient '{4}': '{5}'",
        account.network, account.ext_user, room_id, sender, recipient, payload)
    stored_msg = self.base.message_storage(
        network=account.network,
        ext_user=account.ext_user,
        room_id=room_id,
        sender=sender,
        recipient=recipient,
        time=datetime.utcnow(),
        destination="client",
        payload=json.dumps(payload))
    self.base.db_session.add(stored_msg)
    self.base.db_session.commit()
    self.pending_deliveries_to_clients.add((sender, account))
    self._schedule_delivery_to_clients()

  def _store_offline_message_to_clients_without_account( # pylint: disable=invalid-name
      self, room_id, sender, time, payload):
    logger.debug(
        "Storing offline message to client without account from "
        "sender '{0}' to room id '{1}' at time '{2}': '{3}'",
        sender, room_id, time, payload)
    stored_msg = self.base.message_storage(
        network=None,
        ext_user=None,
        room_id=room_id,
        sender=sender,
        recipient=None,
        time=time,
        destination="client",
        payload=json.dumps(payload))
    self.base.db_session.add(stored_msg)
    self.base.db_session.commit()
    self.pending_deliveries_to_clients.add((sender, None))
    self._schedule_delivery_to_clients()

  def _create_matrix_text_payload(self, account, body):
    text_body = body
    formatted_body = None
    fmt = None
    if account:
      if "convert_to_text" in account.config:
        if account.config["convert_to_text"] == "html2text":
          text_body = self.html2text.handle(body)
          # html2text ends the converted text with two newlines, strip them.
          if text_body.endswith("\n\n"):
            text_body = text_body[:-2]
        else:
          logger.error(
              "PuMaDuct misconfiguration: converter to text '{0}'"
              " for the network '{1}' is unknown.",
              account.config["convert_to_text"], account.network)
      if "format" in account.config:
        fmt = account.config["format"]
        formatted_body = body
    payload = {"body": text_body, "msgtype": "m.text"}
    if fmt:
      payload["format"] = fmt
      payload["formatted_body"] = formatted_body
    return payload

  def _send_file_to_matrix(
      self, user, account, conv_id, ext_contact, direction,
      description, content, time, msgtype):
    contact = self.base.ext_contact_to_mxid(account.network, ext_contact)
    room_id = self.base.ensure_room(user, contact, conv_id)
    if direction == "recv":
      contact, user = user, contact
    payload = {"body": description, "msgtype": msgtype}
    # We don't know the actual content type, so try to guess.
    content_type = magic.from_buffer(content, mime=True)
    url = self.base.matrix_client.upload_content(content_type, content)
    if url:
      payload["url"] = url
      self.send_message_to_matrix(account, room_id, user, contact, time, payload)
    else:
      payload["content"] = base64.b64encode(content).decode("ascii")
      payload["content-type"] = content_type
      self._store_offline_message_to_matrix(
          account, room_id, user, contact, time, payload)

  def _send_file_to_client(self, account, conv_id, payload):
    parts = urllib.parse.urlparse(payload["url"])
    content = self.base.matrix_client.download_content(parts.netloc, parts.path)
    if content:
      if payload["msgtype"] == "m.image":
        send_fun = account.client.send_image
      else:
        send_fun = account.client.send_file
      if send_fun(account.network, account.ext_user, conv_id, payload["body"], content):
        return True
    return False

def _render_payload_for_client(account, payload):
  body = query_json_path(payload, "body")
  fmt = query_json_path(payload, "format")
  formatted_body = query_json_path(payload, "formatted_body")
  rendered_body = body
  if "format" in account.config and fmt and account.config["format"] == fmt:
    rendered_body = formatted_body
  else:
    if "convert_from_text" in account.config:
      if account.config["convert_from_text"] == "markdown":
        rendered_body = markdown.markdown(body)
      else:
        logger.error(
            "PuMaDuct misconfiguration: from text converter '{0}'"
            " for the network '{1}' is unknown.",
            account.config["convert_from_text"], account.network)
  return rendered_body
