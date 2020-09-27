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

from account cimport _PurpleAccount, PurpleAccount
from status cimport PurpleStatus

cdef extern from "libpurple/blist.h":
  ctypedef enum PurpleBlistNodeType:
    PURPLE_BLIST_GROUP_NODE
    PURPLE_BLIST_CONTACT_NODE
    PURPLE_BLIST_BUDDY_NODE
    PURPLE_BLIST_CHAT_NODE
    PURPLE_BLIST_OTHER_NODE

  ctypedef enum PurpleBlistNodeFlags:
    PURPLE_BLIST_NODE_FLAG_NO_SAVE

  ctypedef enum PurpleMediaCaps:
    PURPLE_MEDIA_CAPS_NONE
    PURPLE_MEDIA_CAPS_AUDIO
    PURPLE_MEDIA_CAPS_AUDIO_SINGLE_DIRECTION
    PURPLE_MEDIA_CAPS_VIDEO
    PURPLE_MEDIA_CAPS_VIDEO_SINGLE_DIRECTION
    PURPLE_MEDIA_CAPS_AUDIO_VIDEO
    PURPLE_MEDIA_CAPS_MODIFY_SESSION
    PURPLE_MEDIA_CAPS_CHANGE_DIRECTION

  cdef struct _PurpleBlistNode
  ctypedef _PurpleBlistNode PurpleBlistNode

  cdef struct _PurpleBlistNode:
    PurpleBlistNodeType type
    PurpleBlistNode *prev
    PurpleBlistNode *next
    PurpleBlistNode *parent
    PurpleBlistNode *child
    GHashTable *settings
    void *ui_data
    PurpleBlistNodeFlags flags

  cdef struct _PurpleBuddyIcon
  ctypedef _PurpleBuddyIcon PurpleBuddyIcon

  cdef struct _PurpleGroup
  ctypedef _PurpleGroup PurpleGroup

  cdef struct _PurplePresence
  ctypedef _PurplePresence PurplePresence

  cdef struct _PurpleBuddyList:
    PurpleBlistNode *root
    GHashTable *buddies
    void *ui_data

  ctypedef _PurpleBuddyList PurpleBuddyList

  cdef struct _PurpleBuddy:
    PurpleBlistNode node
    char *name
    char *alias
    char *server_alias
    void *proto_data
    PurpleBuddyIcon *icon
    PurpleAccount *account
    PurplePresence *presence
    PurpleMediaCaps media_caps

  ctypedef _PurpleBuddy PurpleBuddy

  cdef struct _PurpleBlistUiOps:
    void (*new_list)(_PurpleBuddyList *)
    void (*new_node)(_PurpleBlistNode *)
    void (*show)(_PurpleBuddyList *)
    void (*update)(_PurpleBuddyList *, _PurpleBlistNode *)
    void (*remove)(_PurpleBuddyList *, _PurpleBlistNode *)
    void (*destroy)(_PurpleBuddyList *)
    void (*set_visible)(_PurpleBuddyList *, int)
    void (*request_add_buddy)(_PurpleAccount *, const char *, const char *, const char *)
    void (*request_add_chat)(_PurpleAccount *, _PurpleGroup *, const char *, const char *)
    void (*request_add_group)()
    void (*save_node)(_PurpleBlistNode *)
    void (*remove_node)(_PurpleBlistNode *)
    void (*save_account)(_PurpleAccount *)
    void (*_purple_reserved1)()

  ctypedef _PurpleBlistUiOps PurpleBlistUiOps

  PurpleBuddyList *purple_blist_new()

  void *purple_blist_get_handle()

  void purple_blist_load()

  void purple_blist_set_ui_ops(PurpleBlistUiOps *ops)

  void purple_set_blist(PurpleBuddyList *blist)

  GSList *purple_find_buddies(PurpleAccount *account, const char *name)

  const char *purple_buddy_get_name(const PurpleBuddy *buddy)

  const char *purple_buddy_get_alias_only(PurpleBuddy *buddy)

  PurpleBuddy *purple_find_buddy(PurpleAccount *account, const char *name)

  PurplePresence *purple_buddy_get_presence(const PurpleBuddy *buddy)

  PurpleStatus *purple_presence_get_active_status(const PurplePresence *presence)
