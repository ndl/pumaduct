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

from glib cimport *

from account cimport PurpleAccount
from connection cimport PurpleConnection, PurpleConnectionFlags

cdef extern from "libpurple/conversation.h":
  cdef struct _PurpleBuddyIcon
  ctypedef _PurpleBuddyIcon PurpleBuddyIcon

  ctypedef enum PurpleConversationType:
    PURPLE_CONV_TYPE_UNKNOWN
    PURPLE_CONV_TYPE_IM
    PURPLE_CONV_TYPE_CHAT
    PURPLE_CONV_TYPE_MISC
    PURPLE_CONV_TYPE_ANY

  ctypedef enum PurpleMessageFlags:
    PURPLE_MESSAGE_SEND
    PURPLE_MESSAGE_RECV
    PURPLE_MESSAGE_SYSTEM
    PURPLE_MESSAGE_AUTO_RESP
    PURPLE_MESSAGE_ACTIVE_ONLY
    PURPLE_MESSAGE_NICK
    PURPLE_MESSAGE_NO_LOG
    PURPLE_MESSAGE_WHISPER
    PURPLE_MESSAGE_ERROR
    PURPLE_MESSAGE_DELAYED
    PURPLE_MESSAGE_RAW
    PURPLE_MESSAGE_IMAGES
    PURPLE_MESSAGE_NOTIFY
    PURPLE_MESSAGE_NO_LINKIFY
    PURPLE_MESSAGE_INVISIBLE

  ctypedef enum PurpleTypingState:
    PURPLE_NOT_TYPING
    PURPLE_TYPING
    PURPLE_TYPED

  cdef struct _PurpleConversation
  ctypedef _PurpleConversation PurpleConversation

  cdef struct _PurpleConvIm:
    PurpleConversation *conv
    PurpleTypingState typing_state
    guint typing_timeout
    time_t type_again
    guint send_typed_timeout
    PurpleBuddyIcon *icon

  ctypedef _PurpleConvIm PurpleConvIm

  cdef struct _PurpleConvChat:
    PurpleConversation *conv
    GList *in_room
    GList *ignored
    char *who
    char *topic
    int id
    char *nick
    gboolean left
    GHashTable *users

  ctypedef _PurpleConvChat PurpleConvChat

  cdef union ___PurpleConversation_u:
    PurpleConvIm *im
    PurpleConvChat *chat
    void *misc

  ctypedef ___PurpleConversation_u ___PurpleConversation_u_t

  cdef struct _PurpleConversationUiOps:
    void (*create_conversation)(_PurpleConversation *)
    void (*destroy_conversation)(_PurpleConversation *)
    void (*write_chat)(_PurpleConversation *, const char *, const char *, PurpleMessageFlags, long)
    void (*write_im)(_PurpleConversation *, const char *, const char *, PurpleMessageFlags, long)
    void (*write_conv)(_PurpleConversation *, const char *, const char *, const char *, PurpleMessageFlags, long)
    void (*chat_add_users)(_PurpleConversation *, _GList *, int)
    void (*chat_rename_user)(_PurpleConversation *, const char *, const char *, const char *)
    void (*chat_remove_users)(_PurpleConversation *, _GList *)
    void (*chat_update_user)(_PurpleConversation *, const char *)
    void (*present)(_PurpleConversation *)
    int (*has_focus)(_PurpleConversation *)
    int (*custom_smiley_add)(_PurpleConversation *, const char *, int)
    void (*custom_smiley_write)(_PurpleConversation *, const char *, const unsigned char *, int)
    void (*custom_smiley_close)(_PurpleConversation *, const char *)
    void (*send_confirm)(_PurpleConversation *, const char *)
    void (*_purple_reserved1)()
    void (*_purple_reserved2)()
    void (*_purple_reserved3)()
    void (*_purple_reserved4)()

  ctypedef _PurpleConversationUiOps PurpleConversationUiOps

  cdef struct _PurpleConversation:
    PurpleConversationType type
    PurpleAccount *account
    char *name
    char *title
    gboolean logging
    GList *logs
    ___PurpleConversation_u_t u
    PurpleConversationUiOps *ui_ops
    void *ui_data
    GHashTable *data
    PurpleConnectionFlags features
    GList *message_history

  PurpleAccount *purple_conversation_get_account(const PurpleConversation *conv)

  PurpleConnection *purple_conversation_get_gc(const PurpleConversation *conv)

  PurpleConvIm *purple_conversation_get_im_data(const PurpleConversation *conv)

  PurpleConversation *purple_conversation_new(PurpleConversationType type, PurpleAccount *account, const char *name)

  PurpleConversation *purple_find_conversation_with_account(PurpleConversationType type, const char *name, const PurpleAccount *account)

  PurpleConversationType purple_conversation_get_type(const PurpleConversation *conv)

  PurpleTypingState purple_conv_im_get_typing_state(const PurpleConvIm *im)

  const char *purple_conversation_get_name(const PurpleConversation *conv)

  void *purple_conversations_get_handle()

  void purple_conv_im_send(PurpleConvIm *im, const char *message)

  void purple_conversations_set_ui_ops(PurpleConversationUiOps *ops)

  void purple_conv_im_write(PurpleConvIm *im, const char *who, const char *message, PurpleMessageFlags flags, time_t mtime)
