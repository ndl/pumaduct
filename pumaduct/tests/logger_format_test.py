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

"""Tests formatting using str.format() in logging statements in PuMaDuct code."""

import logging
import unittest

from pumaduct import logger_format

logger = logging.getLogger("pumaduct.logger_format_test")
ext_logger = logging.getLogger("test") # pylint:disable=invalid-name

class LoggerFormatTest(unittest.TestCase):
  """Tests formatting using str.format() in logging statements in PuMaDuct code."""
  def setUp(self):
    logger_format.setup()

  def test_format(self):
    with self.assertLogs() as log_cm:
      logger.info("Format msg {0}, {1}, {2}", "aaa", "bbb", 123)
      logger.info(123)
      self.assertEqual(
          log_cm.output[0],
          "INFO:pumaduct.logger_format_test:Format msg aaa, bbb, 123")
      self.assertEqual(
          log_cm.output[1],
          "INFO:pumaduct.logger_format_test:123")

  def test_ext_logger(self):
    with self.assertLogs() as log_cm:
      ext_logger.info("Format msg %s, %s", "aaa", "bbb")
      self.assertEqual(
          log_cm.output[0],
          "INFO:test:Format msg aaa, bbb")

  def tearDown(self):
    logger_format.clean()
