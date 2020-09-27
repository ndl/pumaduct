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

"""Persistent storage data structures for PuMaDict."""

from sqlalchemy import Column, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Account(Base):
  """Account of the Matrix user on the external network."""

  __tablename__ = "pumaduct_account"
  id = Column(Integer, nullable=False, primary_key=True) # pylint: disable=invalid-name
  user = Column(String, nullable=False)
  network = Column(String, nullable=False)
  ext_user = Column(String, nullable=False)
  password = Column(String, nullable=False)
  auth_token = Column(String, nullable=True)
  __table_args__ = (
      UniqueConstraint("network", "ext_user"),)

class Message(Base):
  """Offline message stored for later delivery."""

  __tablename__ = "pumaduct_message"
  id = Column(Integer, nullable=False, primary_key=True) # pylint: disable=invalid-name
  network = Column(String)
  ext_user = Column(String)
  room_id = Column(String)
  sender = Column(String, nullable=False)
  recipient = Column(String)
  destination = Column(Enum("client", "matrix", name="DestinationType"), nullable=False)
  time = Column(DateTime, nullable=False)
  payload = Column(String, nullable=False)
