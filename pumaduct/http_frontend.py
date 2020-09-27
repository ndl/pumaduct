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

"""HTTP frontend that Matrix server sends transactions / requests to."""

from http import HTTPStatus, server
import json
import logging
import re
import threading
import urllib.parse

logger = logging.getLogger(__name__)

class HttpRequestHandler(server.BaseHTTPRequestHandler):
  """HTTP handler that contains the actual logic for requests processing."""

  USER_ID_RE = re.compile(r"^/users/(?P<user_id>.+)$")
  TRANSACTION_ID_RE = re.compile(r"^/transactions/(?P<transaction_id>.+)$")
  DOMAIN_PREFIX = "CH.ENDL.PUMADUCT_"

  def _send_json_response(self, code=HTTPStatus.OK, data=None):
    if data is not None:
      payload = json.dumps(data).encode("utf8")
    else:
      payload = b"{}" # pylint: disable=redefined-variable-type
    self.send_response(code)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", len(payload))
    self.end_headers()
    self.wfile.write(payload)

  def _send_json_error(self, code, error):
    if code == HTTPStatus.BAD_REQUEST:
      errcode = HttpRequestHandler.DOMAIN_PREFIX + "BAD_REQUEST"
    elif code == HTTPStatus.NOT_FOUND:
      errcode = HttpRequestHandler.DOMAIN_PREFIX + "NOT_FOUND"
    elif code == HTTPStatus.UNAUTHORIZED:
      errcode = HttpRequestHandler.DOMAIN_PREFIX + "UNAUTHORIZED"
    elif code == HTTPStatus.FORBIDDEN:
      errcode = HttpRequestHandler.DOMAIN_PREFIX + "FORBIDDEN"
    else:
      raise ValueError("Unknown error code {0}".format(code))
    logger.error("Error code '{0}' with text '{1}'", errcode, error)
    self._send_json_response(code=code, data={"errcode": errcode, "error": error})

  def _enforce_access(self, url_details):
    args = urllib.parse.parse_qs(url_details.query)
    if "access_token" not in args:
      self._send_json_error(HTTPStatus.UNAUTHORIZED, "Missing access_token in request")
      return False
    elif args["access_token"][0] != self.server.hs_access_token:
      self._send_json_error(HTTPStatus.FORBIDDEN, "Incorrect access_token value")
      return False
    else:
      return True

  def _handle_users(self, path):
    match = HttpRequestHandler.USER_ID_RE.match(path)
    if match:
      user_id = urllib.parse.unquote(match.group("user_id"))
      if self.server.backend.has_contact(user_id):
        self._send_json_response(HTTPStatus.OK)
      else:
        self._send_json_error(
            HTTPStatus.NOT_FOUND,
            "user_id '{0}' doesn't exist".format(user_id))
    else:
      self._send_json_error(
          HTTPStatus.BAD_REQUEST,
          "Failed to extract 'user_id' from the request")

  def _handle_transactions(self, raw_request):
    match = HttpRequestHandler.TRANSACTION_ID_RE.match(self.path)
    if match:
      transaction_id = urllib.parse.unquote(match.group("transaction_id"))
      if self.server.backend.process_transaction(
          transaction_id, json.loads(raw_request.decode("utf8"))):
        self._send_json_response(HTTPStatus.OK)
      else:
        self._send_json_error(
            HTTPStatus.BAD_REQUEST,
            "Failed to process transaction '{0}'".format(transaction_id))
    else:
      self._send_json_error(
          HTTPStatus.BAD_REQUEST,
          "Failed to extract 'transaction_id' from the request")

  def do_GET(self):
    """Handles GET requests from Matrix server."""

    logger.debug("In GET for request {0}", self.path)
    url_details = urllib.parse.urlparse(self.path)
    if self._enforce_access(url_details):
      if url_details.path.startswith("/users/"):
        self._handle_users(url_details.path)
      else:
        self._send_json_error(
            HTTPStatus.NOT_FOUND,
            "Unrecognized URL: '{0}'".format(url_details.path))
    return True

  def do_PUT(self):
    """Handles PUT requests from Matrix server."""

    logger.debug("In PUT for request {0}", self.path)
    url_details = urllib.parse.urlparse(self.path)
    if self._enforce_access(url_details):
      if "content-length" in self.headers:
        length = int(self.headers["content-length"])
        raw_request = self.rfile.read(length)
        if url_details.path.startswith("/transactions/"):
          self._handle_transactions(raw_request)
        else:
          self._send_json_error(
              HTTPStatus.NOT_FOUND,
              "Unrecognized URL: '{0}'".format(url_details.path))
      else:
        self._send_json_error(
            HTTPStatus.BAD_REQUEST,
            "No 'content-length' received for the request '{0}'".format(self.path))
    return True

class FrontendHttpServer(server.HTTPServer):
  """HTTP server implementation."""

  def __init__(self, conf, backend):
    super(FrontendHttpServer, self).__init__(
        (conf["bind_address"], conf["port"]), HttpRequestHandler)
    self.hs_access_token = conf["hs_access_token"]
    self.backend = backend

class HttpFrontend(object):
  """HTTP frontend that manages HTTP server."""

  def __init__(self, conf, backend):
    self.shutdown_poll_interval = conf["shutdown_poll_interval"]
    self.httpd = FrontendHttpServer(conf, backend)
    self.httpd_thread = None

  def __enter__(self):
    self.httpd_thread = threading.Thread(
        target=lambda: self.httpd.serve_forever(poll_interval=self.shutdown_poll_interval))
    self.httpd_thread.start()

  def __exit__(self, type_, value, traceback):
    self.stop()

  def stop(self):
    """Initiates server shutdown."""
    if self.httpd:
      self.httpd.shutdown()
      self.httpd = None
    if self.httpd_thread:
      self.httpd_thread.join()
      self.httpd_thread = None
