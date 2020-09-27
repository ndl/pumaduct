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

cdef extern from "libpurple/proxy.h":
  ctypedef enum PurpleProxyType:
    PURPLE_PROXY_USE_GLOBAL
    PURPLE_PROXY_NONE
    PURPLE_PROXY_HTTP
    PURPLE_PROXY_SOCKS4
    PURPLE_PROXY_SOCKS5
    PURPLE_PROXY_USE_ENVVAR
    PURPLE_PROXY_TOR

  ctypedef struct PurpleProxyInfo:
    PurpleProxyType type
    char *host
    int port
    char *username
    char *password
