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

"""Main program for PuMaDict: initializes the server and runs the main loop."""

import argparse
import contextlib
from datetime import datetime
import functools
import logging
import logging.config
import os
import signal
import sys
import yaml

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from pumaduct import backend
from pumaduct import glib
from pumaduct import http_frontend
from pumaduct import logger_format
from pumaduct import matrix_client

from pumaduct.storage import Base, Account, Message

logger_format.setup()
logger = logging.getLogger("pumaduct.main")

# Give purple import extra protection as it is the most risky place.
try:
  # Work-around the issues with Python symbols loading for libpurple plugins.
  sys.setdlopenflags(sys.getdlopenflags() | os.RTLD_GLOBAL)
  from pumaduct import purple_client # pylint: disable=no-name-in-module
except Exception: # pylint: disable=broad-except
  logger.exception("Failed to import purple client extension")
  sys.exit(1)

class ShutdownHandler(object):
  """Performs graceful shutdown of the server with timeout."""

  def __init__(self, loop, pumaduct_backend, poll_interval, timeout):
    self.loop = loop
    self.pumaduct_backend = pumaduct_backend
    self.poll_interval = poll_interval
    self.timeout = timeout
    self.initiated = None

  def termination_handler(self, sig):
    """Called when the server receives one of the termination signals."""
    logger.info("Received signal {0}, initiating shutdown", sig)
    self.pumaduct_backend.stop()
    self.initiated = datetime.utcnow()
    glib.timeout_add_seconds(self.poll_interval, self._shutdown_check)
    return False

  def _shutdown_check(self):
    if ((datetime.utcnow() - self.initiated).seconds > self.timeout or
        self.pumaduct_backend.stopped()):
      self.loop.quit()
      return False
    return True

def load_main_config():
  """Loads main config, exits on error."""
  parser = argparse.ArgumentParser(
      description="PuMaDuct Application Server.")
  parser.add_argument(
      "-c",
      "--config",
      default="/etc/synapse/pumaduct.yaml",
      help="Path to the YAML config")
  args = parser.parse_args()

  # Read main config.
  try:
    with open(args.config, "r") as config_file:
      return yaml.load(config_file)
  except yaml.YAMLError:
    logger.exception("Configuration file error")
    sys.exit(1)
  except IOError:
    logger.exception("Configuration IO error")
    sys.exit(1)

def load_logging_config(conf):
  """Loads logging config if set, exits on error."""
  # Read and apply logging config, if specified.
  if "logging_config_file" in conf:
    logger.info("Switching to user-specified logging configuration")
    try:
      with open(conf["logging_config_file"], "r") as logging_config_file:
        logging.config.dictConfig(yaml.load(logging_config_file))
    except yaml.YAMLError:
      logger.exception("Logging configuration file error")
      sys.exit(1)
    except IOError:
      logger.exception("Configuration IO error")
      sys.exit(1)

def configure_db(conf):
  """Configures database, exits on error."""
  try:
    engine = create_engine(conf["db_spec"])
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
  except SQLAlchemyError:
    logger.exception("DB configuration error")
    sys.exit(1)

def create_clients(conf):
  """Creates all clients."""
  clients = {}
  clients["purple"] = purple_client.Client(conf) # pylint: disable=no-member
  try:
    from pumaduct import skpy_client
    clients["skpy"] = skpy_client.Client(conf)
  except ImportError:
    logger.warning("SkPy import failed, SkPy client won't be available")

  mx_client = matrix_client.Client(conf)

  return clients, mx_client

def main():
  # User-specified configuration is applied after reading
  # the main config, but meanwhile apply basic config
  # to be able to output at least smth.
  logging.basicConfig(level=logging.INFO)
  logger.info("Starting PuMaDuct Application Server")

  conf = load_main_config()
  load_logging_config(conf)
  db_session = configure_db(conf)
  clients, mx_client = create_clients(conf)

  pumaduct_backend = backend.Backend(
      conf, glib, mx_client, clients, db_session, Account, Message)
  httpd = http_frontend.HttpFrontend(conf, pumaduct_backend)

  context_manager = contextlib.ExitStack()
  for client in clients.values():
    context_manager.enter_context(client)

  try:
    with mx_client, pumaduct_backend, httpd:
      loop = glib.MainLoop()
      shutdown_handler = ShutdownHandler(
          loop, pumaduct_backend,
          conf["shutdown_poll_interval"],
          conf["shutdown_timeout"])
      for sig in [signal.SIGINT, signal.SIGTERM]:
        glib.unix_signal_add(
            sig,
            functools.partial(shutdown_handler.termination_handler, sig))
      logger.info("Entering the main loop")
      loop.run()
      logger.info("Exiting the main loop")
      loop.unref()
      loop = None
  finally:
    context_manager.close()

  logger.info("Stopped PuMaDuct Application Server")

if __name__ == "__main__":
  main()
