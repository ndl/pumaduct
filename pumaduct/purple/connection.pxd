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

cdef extern from "libpurple/connection.h":
  ctypedef enum PurpleConnectionFlags:
    PURPLE_CONNECTION_HTML
    PURPLE_CONNECTION_NO_BGCOLOR
    PURPLE_CONNECTION_AUTO_RESP
    PURPLE_CONNECTION_FORMATTING_WBFO
    PURPLE_CONNECTION_NO_NEWLINES
    PURPLE_CONNECTION_NO_FONTSIZE
    PURPLE_CONNECTION_NO_URLDESC
    PURPLE_CONNECTION_NO_IMAGES
    PURPLE_CONNECTION_ALLOW_CUSTOM_SMILEY
    PURPLE_CONNECTION_SUPPORT_MOODS
    PURPLE_CONNECTION_SUPPORT_MOOD_MESSAGES

  ctypedef enum PurpleConnectionError:
    PURPLE_CONNECTION_ERROR_NETWORK_ERROR
    PURPLE_CONNECTION_ERROR_INVALID_USERNAME
    PURPLE_CONNECTION_ERROR_AUTHENTICATION_FAILED
    PURPLE_CONNECTION_ERROR_AUTHENTICATION_IMPOSSIBLE
    PURPLE_CONNECTION_ERROR_NO_SSL_SUPPORT
    PURPLE_CONNECTION_ERROR_ENCRYPTION_ERROR
    PURPLE_CONNECTION_ERROR_NAME_IN_USE
    PURPLE_CONNECTION_ERROR_INVALID_SETTINGS
    PURPLE_CONNECTION_ERROR_CERT_NOT_PROVIDED
    PURPLE_CONNECTION_ERROR_CERT_UNTRUSTED
    PURPLE_CONNECTION_ERROR_CERT_EXPIRED
    PURPLE_CONNECTION_ERROR_CERT_NOT_ACTIVATED
    PURPLE_CONNECTION_ERROR_CERT_HOSTNAME_MISMATCH
    PURPLE_CONNECTION_ERROR_CERT_FINGERPRINT_MISMATCH
    PURPLE_CONNECTION_ERROR_CERT_SELF_SIGNED
    PURPLE_CONNECTION_ERROR_CERT_OTHER_ERROR
    PURPLE_CONNECTION_ERROR_OTHER_ERROR

  cdef struct _PurpleConnection
  ctypedef _PurpleConnection PurpleConnection

  void *purple_connections_get_handle()
