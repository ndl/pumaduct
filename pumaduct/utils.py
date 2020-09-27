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

"""Utility functionality for PuMaDuct."""

from datetime import datetime

def get_event_datetime(event):
  """Converts Matrix server timestamp in the event to datetime()."""
  return datetime.utcfromtimestamp(event["origin_server_ts"] / 1000.0)

def query_json_path(json, *args):
  """Returns json value given its path in the hierarchy or None if not present."""
  for arg in args:
    if arg in json:
      json = json[arg]
    else:
      return None
  return json
