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

"""Layer base class that all other layers derive from."""

from abc import ABCMeta

class LayerBase(metaclass=ABCMeta):
  """Layer base class that all other layers derive from."""

  def __enter__(self):
    """Prepares for subsequent operations, e.g. sets callbacks.

    SHOULD NOT yet perform any actual operations (e.g. contacting
    servers, etc) as other parts of the system are not yet ready.
    """
    pass

  def __exit__(self, type_, value, traceback):
    """Cleans up the layer after its operations stopped."""
    pass

  def start(self):
    """Initiates start-up of layer operations."""
    pass

  def stop(self):
    """Initiates shutdown of layer operations."""
    pass

  def stopped(self): # pylint: disable=no-self-use
    """Returns True if layer operations have stopped."""
    return True
