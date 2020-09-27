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

from account cimport PurpleAccount, _PurpleAccount
from conversation cimport PurpleConversation, _PurpleConversation

cdef extern from "libpurple/request.h":
  ctypedef struct PurpleRequestFields:
    GList *groups
    GHashTable *fields
    GList *required_fields
    void *ui_data

  ctypedef struct PurpleRequestUiOps:
    void *(*request_input)(const char *, const char *, const char *, const char *, int, int, char *, const char *, void (*)(), const char *, void (*)(), _PurpleAccount *, const char *, _PurpleConversation *, void *)
    void *(*request_choice)(const char *, const char *, const char *, int, const char *, void (*)(), const char *, void (*)(), _PurpleAccount *, const char *, _PurpleConversation *, void *, va_list)
    void *(*request_action)(const char *, const char *, const char *, int, _PurpleAccount *, const char *, _PurpleConversation *, void *, unsigned long, va_list)
    void *(*request_fields)(const char *, const char *, const char *, PurpleRequestFields *, const char *, void (*)(), const char *, void (*)(), _PurpleAccount *, const char *, _PurpleConversation *, void *)
    void *(*request_file)(const char *, const char *, int, void (*)(), void (*)(), _PurpleAccount *, const char *, _PurpleConversation *, void *)
    void (*close_request)(PurpleRequestType, void *)
    void *(*request_folder)(const char *, const char *, void (*)(), void (*)(), _PurpleAccount *, const char *, _PurpleConversation *, void *)
    # Note: the last argument is supposed to be va_args, but I don't want to bother with figuring it out
    # as this op is currently not used anyhow.
    void *(*request_action_with_icon)(const char *, const char *, const char *, int, _PurpleAccount *, const char *, _PurpleConversation *, const void *, int, void *, unsigned long, va_list)
    void (*_purple_reserved1)()
    void (*_purple_reserved2)()
    void (*_purple_reserved3)()

  ctypedef void (*PurpleRequestInputCb)(void *, const char *)

  void *purple_request_input(void *handle, const char *title, const char *primary, const char *secondary, const char *default_value, gboolean multiline, gboolean masked, gchar *hint, const char *ok_text, GCallback ok_cb, const char *cancel_text, GCallback cancel_cb, PurpleAccount *account, const char *who, PurpleConversation *conv, void *user_data)

  void purple_request_set_ui_ops(PurpleRequestUiOps *ops)
