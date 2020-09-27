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

cdef extern from "libpurple/eventloop.h":
  ctypedef enum PurpleInputCondition:
    PURPLE_INPUT_READ
    PURPLE_INPUT_WRITE

  ctypedef void (*PurpleInputFunction)(void *, int, PurpleInputCondition)

  cdef struct _PurpleEventLoopUiOps:
    unsigned int (*timeout_add)(unsigned int, int (*)(void *), void *)
    int (*timeout_remove)(unsigned int)
    unsigned int (*input_add)(int, PurpleInputCondition, void (*)(void *, int, PurpleInputCondition), void *)
    int (*input_remove)(unsigned int)
    int (*input_get_error)(int, int *)
    unsigned int (*timeout_add_seconds)(unsigned int, int (*)(void *), void *)
    void (*_purple_reserved2)()
    void (*_purple_reserved3)()
    void (*_purple_reserved4)()

  ctypedef _PurpleEventLoopUiOps PurpleEventLoopUiOps

  PurpleEventLoopUiOps *purple_eventloop_get_ui_ops()

  gboolean purple_input_remove(guint handle)

  gboolean purple_timeout_remove(guint handle)

  guint purple_input_add(int fd, PurpleInputCondition cond, PurpleInputFunction func, gpointer user_data)

  guint purple_timeout_add(guint interval, GSourceFunc function, gpointer data)

  guint purple_timeout_add_seconds(guint interval, GSourceFunc function, gpointer data)

  int purple_input_get_error(int fd, int *error)

  void purple_eventloop_set_ui_ops(PurpleEventLoopUiOps *ops)
