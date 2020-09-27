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

from connection cimport PurpleConnection
from log cimport PurpleLog
from privacy cimport PurplePrivacyType
from proxy cimport PurpleProxyInfo

cdef extern from "libpurple/account.h":
  cdef struct _PurpleAccount

  cdef struct _PurplePresence
  ctypedef _PurplePresence PurplePresence

  ctypedef void (*PurpleAccountRegistrationCb)(_PurpleAccount *, int, void *)

  cdef struct _PurpleAccount:
    char *username
    char *alias
    char *password
    char *user_info
    char *buddy_icon_path
    gboolean remember_pass
    char *protocol_id
    PurpleConnection *gc
    gboolean disconnecting
    GHashTable *settings
    GHashTable *ui_settings
    PurpleProxyInfo *proxy_info
    GSList *permit
    GSList *deny
    PurplePrivacyType perm_deny
    GList *status_types
    PurplePresence *presence
    PurpleLog *system_log
    void *ui_data
    PurpleAccountRegistrationCb registration_cb
    void *registration_cb_user_data
    gpointer priv

  ctypedef _PurpleAccount PurpleAccount

  PurpleAccount *purple_account_new(const char *username, const char *protocol_id)

  PurpleAccount *purple_connection_get_account(const PurpleConnection *gc)

  void purple_account_connect(PurpleAccount *account)

  void purple_account_set_enabled(PurpleAccount *account, const char *ui, gboolean value)

  const char *purple_account_get_password(const PurpleAccount *account)

  void purple_account_set_password(PurpleAccount *account, const char *password)

  const char *purple_account_get_alias(const PurpleAccount *account)

  void purple_account_set_alias(PurpleAccount *account, const char *alias)

  void purple_accounts_add(PurpleAccount *account)

  PurpleAccount *purple_accounts_find(const char *name, const char *protocol)

  gboolean purple_account_is_disconnected(const PurpleAccount *account)
