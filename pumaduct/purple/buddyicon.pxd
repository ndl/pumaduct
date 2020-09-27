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
from imgstore cimport PurpleStoredImage

cdef extern from "libpurple/buddyicon.h":
  cdef struct _PurpleBuddyIcon
  ctypedef _PurpleBuddyIcon PurpleBuddyIcon

  PurpleBuddyIcon *purple_buddy_icons_find(PurpleAccount *account, const char *username)

  gconstpointer purple_buddy_icon_get_data(const PurpleBuddyIcon *icon, size_t *len)

  PurpleStoredImage *purple_buddy_icons_find_account_icon(PurpleAccount *account)

  PurpleStoredImage *purple_buddy_icons_set_account_icon(PurpleAccount *account, guchar *icon_data, size_t icon_len)

  const char *purple_buddy_icon_get_extension(const PurpleBuddyIcon *icon)
