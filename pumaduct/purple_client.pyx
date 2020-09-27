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

from pumaduct.purple.account cimport *
from pumaduct.purple.blist cimport *
from pumaduct.purple.buddyicon cimport *
from pumaduct.purple.connection cimport *
from pumaduct.purple.conversation cimport *
from pumaduct.purple.core cimport *
from pumaduct.purple.debug cimport *
from pumaduct.purple.eventloop cimport *
from pumaduct.purple.imgstore cimport *
from pumaduct.purple.prefs cimport *
from pumaduct.purple.request cimport *
from pumaduct.purple.server cimport *
from pumaduct.purple.signals cimport *
from pumaduct.purple.status cimport *
from pumaduct.purple.util cimport *

from datetime import datetime
import logging
from collections import defaultdict

from pumaduct.im_client_base import ClientError, ImClientBase

logger = logging.getLogger(__name__)

class PurpleError(ClientError):
  pass

cdef const char *CLIENT_NAME = b"pumaduct"

CONNECTION_ERRORS = {
  PURPLE_CONNECTION_ERROR_NETWORK_ERROR: "network error",
  PURPLE_CONNECTION_ERROR_INVALID_USERNAME: "invalid username",
  PURPLE_CONNECTION_ERROR_AUTHENTICATION_FAILED: "authentication failed",
  PURPLE_CONNECTION_ERROR_AUTHENTICATION_IMPOSSIBLE: "authentication impossible",
  PURPLE_CONNECTION_ERROR_NO_SSL_SUPPORT: "no ssl support",
  PURPLE_CONNECTION_ERROR_ENCRYPTION_ERROR:" encryption error",
  PURPLE_CONNECTION_ERROR_NAME_IN_USE: "name in use",
  PURPLE_CONNECTION_ERROR_INVALID_SETTINGS: "invalid settings",
  PURPLE_CONNECTION_ERROR_CERT_NOT_PROVIDED: "cert not provided",
  PURPLE_CONNECTION_ERROR_CERT_UNTRUSTED: "cert untrusted",
  PURPLE_CONNECTION_ERROR_CERT_EXPIRED: "cert expired",
  PURPLE_CONNECTION_ERROR_CERT_NOT_ACTIVATED: "cert not activated",
  PURPLE_CONNECTION_ERROR_CERT_HOSTNAME_MISMATCH: "cert hostname mismatch",
  PURPLE_CONNECTION_ERROR_CERT_FINGERPRINT_MISMATCH: "cert fingerprint mismatch",
  PURPLE_CONNECTION_ERROR_CERT_SELF_SIGNED: "cert self signed",
  PURPLE_CONNECTION_ERROR_CERT_OTHER_ERROR: "cert other error",
  PURPLE_CONNECTION_ERROR_OTHER_ERROR: "other error"
}

g_callbacks = defaultdict(list)
g_reconnect_timeouts = {}
g_expected_send_msgs = {}

cdef void user_signed_on_cb(PurpleConnection *gc, gpointer null) with gil:
  cdef PurpleAccount *account = purple_connection_get_account(gc)
  if "user-signed-on" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    for callback in g_callbacks["user-signed-on"]:
      callback(network, user)

cdef void user_signed_off_cb(PurpleConnection *gc, gpointer null) with gil:
  cdef PurpleAccount *account = purple_connection_get_account(gc)
  if "user-signed-off" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    for callback in g_callbacks["user-signed-off"]:
      callback(network, user)

cdef gboolean account_reconnect_cb(PurpleAccount *account) with gil:
  logger.debug("reconnect_cb: {0}", account.username)
  if not purple_account_is_disconnected(account):
    g_reconnect_timeouts[<intptr_t>account] = 0
    return False
  purple_account_connect(account)
  return True

cdef void connection_error_cb(PurpleConnection *gc, PurpleConnectionError reason, const char *description, gpointer data) with gil:
  cdef PurpleAccount *account = purple_connection_get_account(gc)
  logger.debug("connection_error_cb: {0}, {1}, {2}", account.username, reason, description)
  client = <object>data
  if "connection-error" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    if reason in CONNECTION_ERRORS:
      reason_str = CONNECTION_ERRORS[reason]
    else:
      reason_str = "unknown error"
    descr = description.decode("utf8")
    enable_reconnect = True
    for callback in g_callbacks["connection-error"]:
      result = callback(network, user, reason_str, descr)
      enable_reconnect = enable_reconnect and result
    if enable_reconnect and not <intptr_t>account in g_reconnect_timeouts:
      g_reconnect_timeouts[<intptr_t>account] = purple_timeout_add_seconds(client.reconnect_interval, <GSourceFunc>account_reconnect_cb, account)
    if not enable_reconnect and <intptr_t>account in g_reconnect_timeouts:
      purple_timeout_remove(g_reconnect_timeouts[<intptr_t>account])
      del g_reconnect_timeouts[<intptr_t>account]

cdef void emit_contact_status_change(PurpleBuddy *buddy, const char *status_name):
  cdef PurpleAccount *account = buddy.account
  if "contact-status-changed" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    username = account.username.decode("utf8")
    contact = buddy.name.decode("utf8")
    status = status_name.decode("utf8")
    for callback in g_callbacks["contact-status-changed"]:
      callback(network, username, contact, status)

cdef void contact_signed_on_cb(PurpleBuddy *buddy, gpointer null) with gil:
  emit_contact_status_change(buddy, b"online")

cdef void contact_signed_off_cb(PurpleBuddy *buddy, gpointer null) with gil:
  emit_contact_status_change(buddy, b"offline")

cdef const char *map_status_primitive(PurpleStatusPrimitive status_primitive):
  cdef const char *status_name = b"offline"
  # Note: Matrix doesn't really support user statuses right now, so the mapping here is quite lossy.
  # Revisit this code once (if?) there's proper status support in Matrix.
  if status_primitive in (PURPLE_STATUS_UNSET, PURPLE_STATUS_OFFLINE):
    status_name = b"offline"
  elif status_primitive in (PURPLE_STATUS_AVAILABLE, PURPLE_STATUS_MOBILE, PURPLE_STATUS_TUNE, PURPLE_STATUS_MOOD):
    status_name = b"online"
  elif status_primitive in (PURPLE_STATUS_UNAVAILABLE, PURPLE_STATUS_INVISIBLE, PURPLE_STATUS_AWAY, PURPLE_STATUS_EXTENDED_AWAY):
    status_name = b"unavailable"
  return status_name

cdef void contact_status_changed_cb(PurpleBuddy *buddy, PurpleStatus *old_status, PurpleStatus *status, gpointer null) with gil:
  cdef const PurpleStatusType *status_type = purple_status_get_type(status)
  cdef PurpleStatusPrimitive status_primitive = purple_status_type_get_primitive(status_type)
  emit_contact_status_change(buddy, map_status_primitive(status_primitive))

cdef void contact_typing_cb(PurpleAccount *account, const char *name, gpointer null) with gil:
  cdef PurpleConversation *conv = purple_find_conversation_with_account(PURPLE_CONV_TYPE_IM, name, account)
  cdef PurpleTypingState state = PURPLE_NOT_TYPING
  cdef PurpleConvIm *conv_im = NULL
  is_typing = False
  if conv:
    conv_im = purple_conversation_get_im_data(conv)
    if conv_im:
      state = purple_conv_im_get_typing_state(conv_im)
      if state == PURPLE_TYPING:
        is_typing = True
      elif state == PURPLE_TYPED or state == PURPLE_NOT_TYPING:
        is_typing = False
      else:
        logger.error("Unknown typing state: {0}", state)
      if "contact-typing" in g_callbacks:
        network = account.protocol_id.decode("utf8")
        username = account.username.decode("utf8")
        contact = name.decode("utf8")
        for callback in g_callbacks["contact-typing"]:
          callback(network, username, <intptr_t>conv, contact, is_typing)
    else:
      logger.error("Couldn't find IM state for conversation with {0}", name)
  else:
    logger.error("Couldn't find the conversation for {0}", name)

cdef void write_conv(PurpleConversation *conv, const char *who, const char *alias,
                     const char *message, PurpleMessageFlags flags, time_t mtime) with gil:
  cdef PurpleAccount *account = NULL
  cdef const char *name = NULL
  cdef intptr_t conv_id = <intptr_t>conv
  if flags & PURPLE_MESSAGE_SEND:
    if conv_id in g_expected_send_msgs:
      g_expected_send_msgs[conv_id] -= 1
      if g_expected_send_msgs[conv_id] <= 0:
        del g_expected_send_msgs[conv_id]
      return
    dir = "send"
  elif flags & PURPLE_MESSAGE_RECV:
    dir = "recv"
  else:
    logger.debug("Received the message with non-supported flags, skipping: {0}, {1}, {2}, {3}", who, message, flags, mtime)
    return
  if alias and alias[0]:
    name = alias
  elif who and who[0]:
    name = who
  account = purple_conversation_get_account(conv)
  if "new-message" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    contact = who.decode("utf8")
    msg = message.decode("utf8")
    time = datetime.utcfromtimestamp(mtime)
    for callback in g_callbacks["new-message"]:
      callback(network, user, conv_id, contact, dir, msg, time)

cdef void destroy_conv(PurpleConversation *conv):
  cdef PurpleAccount *account = NULL
  cdef intptr_t conv_id = <intptr_t>conv
  if conv_id in g_expected_send_msgs:
    del g_expected_send_msgs[conv_id]
  if "conversation-destroyed" in g_callbacks:
    account = purple_conversation_get_account(conv)
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    for callback in g_callbacks["conversation-destroyed"]:
      callback(network, user, <intptr_t>conv)

# TODO: figure out if destroy_conversation is ever called in normal operation
# and if so - fire callback to remove it from the rooms.
cdef PurpleConversationUiOps conv_uiops = [
  NULL,          # create_conversation
  &destroy_conv, # destroy_conversation
  NULL,          # write_chat
  NULL,          # write_im
  &write_conv,   # write_conv
  NULL,          # chat_add_users
  NULL,          # chat_rename_user
  NULL,          # chat_remove_users
  NULL,          # chat_update_user
  NULL,          # present
  NULL,          # has_focus
  NULL,          # custom_smiley_add
  NULL,          # custom_smiley_write
  NULL,          # custom_smiley_close
  NULL,          # send_confirm
  NULL,
  NULL,
  NULL,
  NULL]

# TODO: figure out the type of the update.
cdef void blist_update(PurpleBuddyList *blist, PurpleBlistNode *node) with gil:
  cdef PurpleBuddy *buddy = NULL
  cdef const char *alias = NULL
  if node.type == PURPLE_BLIST_BUDDY_NODE:
    buddy = <PurpleBuddy*>node
    network = buddy.account.protocol_id.decode("utf8")
    user = buddy.account.username.decode("utf8")
    contact = buddy.name.decode("utf8")
    alias = purple_buddy_get_alias_only(buddy)
    # Some protocols contain the user in the contacts list, skip update in this case.
    if user != contact:
      if "contact-updated" in g_callbacks:
        for callback in g_callbacks["contact-updated"]:
          callback(network, user, contact, alias.decode("utf8") if alias else None)

cdef PurpleBlistUiOps blist_uiops = [
  NULL,          # new_list
  NULL,          # new_node
  NULL,          # show
  &blist_update, # update
  NULL,          # remove
  NULL,          # destroy
  NULL,          # set_visible
  NULL,          # request_add_buddy
  NULL,          # request_add_chat
  NULL,          # request_add_group
  NULL,          # save_node
  NULL,          # remove_node
  NULL,          # save_account
  NULL]

cdef void* request_input(
    const char *title, const char *primary, const char *secondary, const char *default_value,
    gboolean multiline, gboolean masked, char *hint, const char *ok_text, GCallback ok_cb,
    const char *cancel_text, GCallback cancel_cb, PurpleAccount *account,
    const char *who, PurpleConversation *conv, void *user_data):
  def request_callback(callbacks_info, cb_type, msg):
    msg_enc = msg.encode("utf8")
    (<PurpleRequestInputCb><intptr_t>callbacks_info[cb_type])(
        <void*><intptr_t>(callbacks_info["user_data"]), <const char*>(msg_enc))

  if "request-input" in g_callbacks:
    network = account.protocol_id.decode("utf8")
    user = account.username.decode("utf8")
    callbacks_info = {}
    callbacks_info["ok_cb"] = <intptr_t>ok_cb
    callbacks_info["cancel_cb"] = <intptr_t>cancel_cb
    callbacks_info["user_data"] = <intptr_t>user_data
    for callback in g_callbacks["request-input"]:
      callback(
          network, user,
          title.decode("utf8") if title else "",
          primary.decode("utf8") if primary else "",
          secondary.decode("utf8") if secondary else "",
          default_value.decode("utf8") if default_value else "",
          lambda msg: request_callback(callbacks_info, "ok_cb", msg),
          lambda msg: request_callback(callbacks_info, "cancel_cb", msg))
  return NULL

cdef PurpleRequestUiOps request_uiops = [
  &request_input,    # request_input
  NULL,              # request_choice
  NULL,              # request_action
  NULL,              # request_fields
  NULL,              # request_file
  NULL,              # close_request
  NULL,              # request_folder
  NULL,              # request_action_with_icon
  NULL,
  NULL,
  NULL]

cdef void ui_init():
  purple_conversations_set_ui_ops(&conv_uiops)
  purple_blist_set_ui_ops(&blist_uiops)
  purple_request_set_ui_ops(&request_uiops)

cdef PurpleCoreUiOps core_uiops = [
  NULL,
  NULL,
  &ui_init,
  NULL,
  NULL,
  NULL,
  NULL,
  NULL]

ctypedef struct PurpleGLibIOClosure:
  PurpleInputFunction function
  guint result
  gpointer data

cdef GIOCondition PURPLE_GLIB_READ_COND = <GIOCondition>(G_IO_IN | G_IO_HUP | G_IO_ERR)
cdef GIOCondition PURPLE_GLIB_WRITE_COND = <GIOCondition>(G_IO_OUT | G_IO_HUP | G_IO_ERR | G_IO_NVAL)

cdef gboolean purple_glib_io_invoke(GIOChannel *source, GIOCondition condition, gpointer data):
  cdef PurpleGLibIOClosure *closure = <PurpleGLibIOClosure*>data
  cdef PurpleInputCondition purple_cond = <PurpleInputCondition>0

  if condition & PURPLE_GLIB_READ_COND:
    purple_cond = <PurpleInputCondition>(purple_cond | PURPLE_INPUT_READ)
  if condition & PURPLE_GLIB_WRITE_COND:
    purple_cond = <PurpleInputCondition>(purple_cond | PURPLE_INPUT_WRITE)

  closure.function(closure.data, g_io_channel_unix_get_fd(source), purple_cond)

  return True

cdef guint glib_input_add(gint fd, PurpleInputCondition condition, PurpleInputFunction function, gpointer data):
  cdef PurpleGLibIOClosure *closure = <PurpleGLibIOClosure*>g_malloc0(sizeof(PurpleGLibIOClosure))
  cdef GIOChannel *channel = NULL
  cdef GIOCondition cond = <GIOCondition>0

  closure.function = function
  closure.data = data

  if condition & PURPLE_INPUT_READ:
    cond = <GIOCondition>(cond | PURPLE_GLIB_READ_COND)
  if condition & PURPLE_INPUT_WRITE:
    cond = <GIOCondition>(cond | PURPLE_GLIB_WRITE_COND)

  channel = g_io_channel_unix_new(fd)
  closure.result = g_io_add_watch_full(channel, 0, cond, purple_glib_io_invoke, closure, purple_glib_io_destroy)
  g_io_channel_unref(channel)

  return closure.result

cdef void purple_glib_io_destroy(gpointer data):
  g_free(data)

cdef PurpleEventLoopUiOps glib_eventloops = [
  g_timeout_add,
  g_source_remove,
  glib_input_add,
  g_source_remove,
  NULL,
  g_timeout_add_seconds,
  NULL,
  NULL,
  NULL]

class Client(ImClientBase):
  def __init__(self, conf):
    self.purple_db_path = conf["purple_db_path"]
    self.reconnect_interval = conf["purple_reconnect_interval"]
    self.purple_debug = "purple_debug" in conf and conf["purple_debug"]

  def __enter__(self):
    logger.info("Initializing Purple Client")

    purple_util_set_user_dir(self.purple_db_path.encode("utf8"))
    purple_debug_set_enabled(self.purple_debug)
    purple_core_set_ui_ops(&core_uiops)
    purple_eventloop_set_ui_ops(&glib_eventloops)

    if not purple_core_init(CLIENT_NAME):
      raise PurpleError("Failed to initialize libpurple core!")

    purple_set_blist(purple_blist_new())

    # TODO: is this needed, or better let it fetch it on each start?
    purple_blist_load()

    cdef int handle = 0

    purple_signal_connect(
        purple_connections_get_handle(), b"connection-error", &handle,
        <PurpleCallback>connection_error_cb, <void*>self)

    purple_signal_connect(
        purple_connections_get_handle(), b"signed-on", &handle,
        <PurpleCallback>user_signed_on_cb, NULL)

    purple_signal_connect(
        purple_connections_get_handle(), b"signed-off", &handle,
        <PurpleCallback>user_signed_off_cb, NULL)

    purple_signal_connect(
        purple_blist_get_handle(), b"buddy-signed-on", &handle,
        <PurpleCallback>contact_signed_on_cb, NULL)

    purple_signal_connect(
        purple_blist_get_handle(), b"buddy-signed-off", &handle,
        <PurpleCallback>contact_signed_off_cb, NULL)

    purple_signal_connect(
        purple_blist_get_handle(), b"buddy-status-changed", &handle,
        <PurpleCallback>contact_status_changed_cb, NULL)

    purple_signal_connect(
        purple_conversations_get_handle(), b"buddy-typing", &handle,
        <PurpleCallback>contact_typing_cb, NULL)

    purple_signal_connect(
        purple_conversations_get_handle(), b"buddy-typed", &handle,
        <PurpleCallback>contact_typing_cb, NULL)

    purple_signal_connect(
        purple_conversations_get_handle(), b"buddy-typing-stopped", &handle,
        <PurpleCallback>contact_typing_cb, NULL)

    purple_prefs_set_bool("/purple/away/away_when_idle", False)
    purple_prefs_set_string("/purple/away/idle_reporting", "none")
    purple_prefs_set_bool("/purple/logging/log_ims", False)
    purple_prefs_set_bool("/purple/logging/log_chats", False)
    purple_prefs_set_bool("/purple/logging/log_system", False)

    logger.info("Finished Purple Client initialization")

  def __exit__(self, type, value, traceback):
    logger.info("Destroying Purple Client")
    purple_core_quit()

  def add_callback(self, callback_id, callback):
    g_callbacks[callback_id].append(callback)

  def remove_callback(self, callback_id, callback):
    g_callbacks[callback_id].remove(callback)

  def login(self, network, user, password=None, auth_token=None):
    logger.debug("login: {0}, {1}", network, user)
    cdef PurpleAccount *account = purple_account_new(
        user.encode("utf8"), network.encode("utf8"))
    purple_accounts_add(account)
    if auth_token is not None:
      auth_token_enc = auth_token.encode("utf8")
      purple_account_set_password(account, auth_token_enc)
    else:
      pass_enc = password.encode("utf8")
      purple_account_set_password(account, pass_enc)
    purple_account_set_enabled(account, CLIENT_NAME, True)

  def get_auth_token(self, network, user):
    cdef const char *pwd = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      # Note: libpurple doesn't have a distinction in API between
      # the 'password' and 'auth_token'.
      pwd = purple_account_get_password(account)
      return pwd.decode("utf8") if pwd else None
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def logout(self, network, user):
    logger.debug("logout: {0}, {1}", network, user)
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      purple_account_set_enabled(account, CLIENT_NAME, False)
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def create_conversation(self, network, user, contact):
    logger.debug("create_conversation: {0}, {1}, {2}", network, user, contact)
    cdef PurpleConversation *conv = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      conv = purple_find_conversation_with_account(
          PURPLE_CONV_TYPE_IM, contact.encode("utf8"), account)
      if not conv:
        logger.debug("Could not find a conversation, creating the new one")
        conv = purple_conversation_new(
            PURPLE_CONV_TYPE_IM, account, contact.encode("utf8"))
        logger.debug("Conv id: {0}", <intptr_t>conv)
      else:
        logger.debug("Reusing existing conversation")
      return <intptr_t>conv
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def send_message(self, network, user, conversation, message):
    logger.debug(
        "send_message: {0}, {1}, {2}, {3}",
        network, user, conversation, message)
    cdef intptr_t conv_id = conversation
    cdef PurpleConversation *conv = <PurpleConversation*>conv_id
    cdef PurpleConnection *gc = purple_conversation_get_gc(conv)
    if conv_id not in g_expected_send_msgs:
      g_expected_send_msgs[conv_id] = 1
    else:
      g_expected_send_msgs[conv_id] += 1
    cdef int err = serv_send_im(
        gc, purple_conversation_get_name(conv),
        message.encode("utf8"), PURPLE_MESSAGE_SEND)
    return err > 0

  def send_image(self, network, user, conversation, description, content):
    logger.warning(
        "send_image in purple client is NYI: {0}, {1}, {2}, {3}",
        network, user, conversation, description)

  def send_file(self, network, user, conversation, description, content):
    logger.warning(
        "send_file in purple client is NYI: {0}, {1}, {2}, {3}",
        network, user, conversation, description)

  def set_typing(self, network, user, conversation, is_typing):
    logger.debug(
        "set_typing: {0}, {1}, {2}, {3}",
        network, user, conversation, is_typing)
    cdef intptr_t conv_id = conversation
    cdef PurpleTypingState state = PURPLE_NOT_TYPING
    cdef PurpleConversation *conv = <PurpleConversation*>conv_id
    cdef PurpleConnection *gc = purple_conversation_get_gc(conv)
    cdef const char *name = NULL
    if gc:
      name = purple_conversation_get_name(conv)
      if name:
        if purple_conversation_get_type(conv) == PURPLE_CONV_TYPE_IM:
          state = PURPLE_TYPING if is_typing else PURPLE_NOT_TYPING
          serv_send_typing(gc, name, state)
        else:
          raise PurpleError("Conversation is not of IM type!")
      else:
        raise PurpleError("Cannot get conversation name!")
    else:
      raise PurpleError("Cannot get connection for conversation!")

  def get_contacts(self, network, user):
    contacts = []
    cdef GSList *buddies = NULL
    cdef const char *name = NULL
    cdef const char *alias = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      buddies = purple_find_buddies(account, NULL)
      while buddies:
        name = purple_buddy_get_name(<PurpleBuddy*>buddies.data)
        alias = purple_buddy_get_alias_only(<PurpleBuddy*>buddies.data)
        if name:
          name_dec = name.decode("utf8")
          # Some protocols contain the user in the contacts list, skip
          # contact in this case.
          if name_dec != user:
            if alias:
              contacts.append((name_dec, alias.decode("utf8")))
            else:
              contacts.append((name_dec, None))
        buddies = buddies.next
      g_slist_free(buddies)
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))
    return contacts

  def get_contact_status(self, network, user, contact):
    cdef PurpleBuddy *buddy = NULL
    cdef PurplePresence *presence = NULL
    cdef PurpleStatus *status = NULL
    cdef PurpleStatusType *status_type = NULL
    cdef PurpleStatusPrimitive status_primitive = PURPLE_STATUS_OFFLINE
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      buddy = purple_find_buddy(account, contact.encode("utf8"))
      if buddy:
        presence = purple_buddy_get_presence(buddy)
        if presence:
          status = purple_presence_get_active_status(presence)
          if status:
            status_type = purple_status_get_type(status)
            if status_type:
              status_primitive = purple_status_type_get_primitive(status_type)
              return map_status_primitive(status_primitive).decode("utf8")
      logger.error("Failed to get the status for buddy '{0}' of '{1}', '{2}'",
          contact, network, user)
      return "offline"
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def set_account_status(self, network, user, status):
    cdef PurpleStatusType *status_type = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      if status == "offline":
        # Do not set PURPLE_STATUS_OFFLINE so that we don't log out the account.
        status_type = purple_account_get_status_type_with_primitive(account, PURPLE_STATUS_EXTENDED_AWAY)
      elif status == "online":
        status_type = purple_account_get_status_type_with_primitive(account, PURPLE_STATUS_AVAILABLE)
      elif status == "unavailable":
        status_type = purple_account_get_status_type_with_primitive(account, PURPLE_STATUS_AWAY)
      else:
        raise ValueError("Unknown status '{0}' requested for '{1}', '{2}'".format(
            status, network, user))
      if status_type:
        logger.debug("status_type = {0}, id = {1}", <intptr_t>status_type, purple_status_type_get_id(status_type))
        purple_account_set_status(account, purple_status_type_get_id(status_type), True, NULL)
      else:
        logger.error("Cannot get status type for status '{0}' on network '{1}'", status, network)
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def get_account_displayname(self, network, user):
    cdef const char *alias = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      alias = purple_account_get_alias(account)
      return alias.decode("utf8") if alias else None
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def set_account_displayname(self, network, user, alias):
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      purple_account_set_alias(account, alias.encode("utf8"))
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def get_contact_displayname(self, network, user, contact):
    cdef PurpleBuddy *buddy = NULL
    cdef const char *alias = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      buddy = purple_find_buddy(account, contact.encode("utf8"))
      if buddy:
        alias = purple_buddy_get_alias_only(buddy)
        if alias:
          return alias.decode("utf8")
      return None
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def get_account_icon(self, network, user):
    cdef PurpleStoredImage *image = NULL
    cdef const char *icon_data = NULL
    cdef size_t icon_data_len = 0
    cdef const char *icon_ext = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      image = purple_buddy_icons_find_account_icon(account)
      if image:
        icon_data = <const char*>purple_imgstore_get_data(image)
        icon_data_len = purple_imgstore_get_size(image)
        if icon_data and icon_data_len > 0:
          icon_ext = purple_imgstore_get_extension(image)
          result = ((icon_ext.decode("utf8") if icon_ext else None),
              icon_data[:icon_data_len])
          purple_imgstore_unref(image)
          return result
      return (None, None)
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def set_account_icon(self, network, user, icon):
    cdef unsigned char *icon_data = NULL
    cdef size_t icon_data_len = 0
    cdef PurpleStoredImage *image = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      icon_data_len = len(icon)
      # purple_buddy_icons_set_account_icon takes the ownership of the data,
      # so we must pass the properly allocated data, not its temporary copy.
      icon_data = <unsigned char*>g_memdup(<const char*>icon, icon_data_len)
      if icon_data:
        image = purple_buddy_icons_set_account_icon(account, icon_data, icon_data_len)
        return image != NULL
      else:
        raise PurpleError("Failed to allocate the memory for storing the icon")
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))

  def get_contact_icon(self, network, user, contact):
    cdef PurpleBuddyIcon *icon = NULL
    cdef const char *icon_data = NULL
    cdef size_t icon_data_len = 0
    cdef const char *icon_ext = NULL
    cdef PurpleAccount *account = purple_accounts_find(
        user.encode("utf8"), network.encode("utf8"))
    if account:
      icon = purple_buddy_icons_find(account, contact.encode("utf8"))
      if icon:
        icon_data = <const char*>purple_buddy_icon_get_data(icon, &icon_data_len)
        if icon_data:
          icon_ext = purple_buddy_icon_get_extension(icon)
          return ((icon_ext.decode("utf8") if icon_ext else None), icon_data[:icon_data_len])
      return (None, None)
    else:
      raise PurpleError("Account '{0}' is unknown".format(user))
