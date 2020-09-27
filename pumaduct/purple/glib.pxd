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

cdef extern from "glib.h":
  ctypedef char gchar
  ctypedef unsigned char guchar
  ctypedef int gint
  ctypedef gint gboolean
  ctypedef long __intptr_t
  ctypedef __intptr_t intptr_t
  ctypedef long __time_t
  ctypedef __time_t time_t
  ctypedef unsigned int guint
  ctypedef unsigned long gulong
  ctypedef void *gpointer
  ctypedef const void *gconstpointer

  # Note: no code ATM actually uses it, it is needed only for declarations type checks
  # to pass, so currently not bothering with figuring it out.
  ctypedef void* va_list

  cdef struct _GHashTable
  ctypedef _GHashTable GHashTable

  cdef struct _GList
  ctypedef _GList GList

  cdef struct _GList:
    gpointer data
    GList *next
    GList *prev

  cdef struct _GSList
  ctypedef _GSList GSList

  cdef struct _GSList:
    gpointer data
    GSList *next

  ctypedef enum GIOCondition:
    G_IO_IN
    GLIB_SYSDEF_POLLIN
    G_IO_OUT
    GLIB_SYSDEF_POLLOUT
    G_IO_PRI
    GLIB_SYSDEF_POLLPRI
    G_IO_ERR
    GLIB_SYSDEF_POLLERR
    G_IO_HUP
    GLIB_SYSDEF_POLLHUP
    G_IO_NVAL
    GLIB_SYSDEF_POLLNVAL

  ctypedef void (*GCallback)()

  ctypedef int (*GSourceFunc)(void *)

  ctypedef int (*GIOFunc)(_GIOChannel *, GIOCondition, void *)

  ctypedef gboolean (*GUnixFDSourceFunc)(gint, GIOCondition, gpointer)

  ctypedef void (*GDestroyNotify)(void *)

  cdef struct _GIOChannel
  ctypedef _GIOChannel GIOChannel

  cdef struct _GMainLoop
  ctypedef _GMainLoop GMainLoop

  cdef struct _GMainContext
  ctypedef _GMainContext GMainContext

  GIOChannel *g_io_channel_unix_new(int fd)

  gboolean g_source_remove(guint tag)

  gint g_io_channel_unix_get_fd(GIOChannel *channel)

  gpointer g_malloc0(int n_bytes)

  gpointer g_memdup(gconstpointer mem, guint byte_size)

  guint g_unix_fd_add(gint fd, GIOCondition condition, GUnixFDSourceFunc function, gpointer user_data)

  guint g_io_add_watch_full(GIOChannel *channel, gint priority, GIOCondition condition, GIOFunc func, gpointer user_data, GDestroyNotify notify)

  guint g_timeout_add(guint interval, GSourceFunc function, gpointer data)

  guint g_timeout_add_seconds(guint interval, GSourceFunc function, gpointer data)

  void g_free(gpointer mem)

  void g_io_channel_unref(GIOChannel *channel)

  GMainLoop *g_main_loop_new(GMainContext *context, gboolean is_running)

  void g_main_loop_run(GMainLoop *loop) nogil

  void g_main_loop_quit(GMainLoop *loop)

  void g_main_loop_unref(GMainLoop *loop)

  void g_main_context_invoke(GMainContext *context, GSourceFunc function, gpointer data)

  void g_slist_free(GSList *list)

cdef extern from "glib-unix.h":
  guint g_unix_signal_add(gint signum, GSourceFunc handler, gpointer user_data)
