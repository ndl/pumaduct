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

"""Allow formatting using str.format() in logging statements in PuMaDuct code."""

import logging

class LogRecordWithFormatStyle(logging.LogRecord):
  """Refinement of 'LogRecord' class that performs str.format() formatting."""

  def __init__(self, *args, **kwargs):
    super(LogRecordWithFormatStyle, self).__init__(*args, **kwargs)

  def getMessage(self):
    return str(self.msg).format(*self.args)

def setup():
  """Activates our LogRecord implementation with str.format()."""
  global _prev_log_record_factory
  if _prev_log_record_factory is None:
    _prev_log_record_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(_record_factory)

def clean():
  """Deactivates our LogRecord implementation with str.format()."""
  global _prev_log_record_factory
  if _prev_log_record_factory is not None:
    logging.setLogRecordFactory(_prev_log_record_factory)
    _prev_log_record_factory = None

def _record_factory(*args, **kwargs):
  global _prev_log_record_factory # pylint: disable=global-variable-not-assigned
  if args[0].startswith("pumaduct."):
    return LogRecordWithFormatStyle(*args, **kwargs)
  else:
    return _prev_log_record_factory(*args, **kwargs)

_prev_log_record_factory = None
