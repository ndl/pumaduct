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

cdef extern from "libpurple/status.h":
  ctypedef enum PurpleStatusPrimitive:
    PURPLE_STATUS_UNSET
    PURPLE_STATUS_OFFLINE
    PURPLE_STATUS_AVAILABLE
    PURPLE_STATUS_UNAVAILABLE
    PURPLE_STATUS_INVISIBLE
    PURPLE_STATUS_AWAY
    PURPLE_STATUS_EXTENDED_AWAY
    PURPLE_STATUS_MOBILE
    PURPLE_STATUS_TUNE
    PURPLE_STATUS_MOOD
    PURPLE_STATUS_NUM_PRIMITIVES

  cdef struct _PurplePresence
  ctypedef _PurplePresence PurplePresence

  cdef struct _PurpleStatus
  ctypedef _PurpleStatus PurpleStatus

  cdef struct _PurpleStatusType
  ctypedef _PurpleStatusType PurpleStatusType

  PurpleStatusPrimitive purple_status_type_get_primitive(const PurpleStatusType *status_type)

  PurpleStatusType *purple_status_get_type(const PurpleStatus *status)

  PurpleStatusType *purple_account_get_status_type_with_primitive(const PurpleAccount *account, PurpleStatusPrimitive primitive)

  const char *purple_status_get_name(const PurpleStatus *status)

  const char *purple_status_type_get_id(const PurpleStatusType *status_type)

  void purple_account_set_status(PurpleAccount *account, const char *status_id, gboolean active, gpointer vargs)
