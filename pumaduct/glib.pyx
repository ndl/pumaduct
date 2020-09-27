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

import logging

from pumaduct.purple.glib cimport *

logger = logging.getLogger(__name__)

class MainLoop(object):
  def __init__(self):
    cdef intptr_t loop_ptr = <intptr_t>g_main_loop_new(NULL, True)
    self.loop = loop_ptr

  def run(self):
    cdef intptr_t loop_ptr = self.loop
    with nogil:
      g_main_loop_run(<GMainLoop*>loop_ptr)

  def quit(self):
    cdef intptr_t loop_ptr = self.loop
    g_main_loop_quit(<GMainLoop*>loop_ptr)

  def unref(self):
    cdef intptr_t loop_ptr = self.loop
    g_main_loop_unref(<GMainLoop*>loop_ptr)
    self.loop = None

# We need to store callbacks to prevent them being garbage collected
# and we also map them to tags to cross-link with the structure below.
g_callbacks = {}
# We need to store tags mapping to callbacks so that we can remove
# callback by its tag.
g_tags = {}

cdef void add_callback(object callback, object tag):
  g_callbacks[callback] = tag
  if tag is not None:
    g_tags[tag] = callback

cdef void remove_callback(object callback):
  tag = g_callbacks[callback]
  del g_callbacks[callback]
  if tag is not None:
    del g_tags[tag]

cdef gboolean on_onetime_cb(gpointer data) with gil:
  callback = <object>data
  try:
    callback()
  except:
    logger.exception("Exception when processing one-time callback")
  remove_callback(callback)
  return False

cdef gboolean on_fd_repeated_cb(gint fd, GIOCondition condition, gpointer data) with gil:
  callback = <object>data
  try:
    result = callback(fd, condition)
  except:
    logger.exception("Exception when processing FD repeated callback")
    result = True
  if not result:
    remove_callback(callback)
  return result

cdef gboolean on_repeated_cb(gpointer data) with gil:
  callback = <object>data
  try:
    result = callback()
  except:
    logger.exception("Exception when processing repeated callback")
    result = True
  if not result:
    remove_callback(callback)
  return result

def main_context_invoke(callback):
  add_callback(callback, None)
  g_main_context_invoke(NULL, <GSourceFunc>on_onetime_cb, <gpointer>callback)

def timeout_add_seconds(interval, callback):
  tag = g_timeout_add_seconds(interval, <GSourceFunc>on_repeated_cb, <gpointer>callback)
  add_callback(callback, tag)
  return tag

def unix_fd_add(fd, cond, callback):
  tag = g_unix_fd_add(fd, cond, <GUnixFDSourceFunc>on_fd_repeated_cb, <gpointer>callback)
  add_callback(callback, tag)
  return tag

def unix_signal_add(signum, callback):
  tag = g_unix_signal_add(signum, <GSourceFunc>on_repeated_cb, <gpointer>callback)
  add_callback(callback, tag)
  return tag

def source_remove(tag):
  if tag not in g_tags:
    raise ValueError("Attempting to remove the source with unknown tag {0}".format(tag))
  callback = g_tags[tag]
  remove_callback(callback)
  return g_source_remove(tag)
