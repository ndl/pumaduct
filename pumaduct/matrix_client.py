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

"""Subset of Matrix client API enhanced with AS-specific functionality."""

from datetime import timezone
import json
import logging
import urllib.parse
import uuid

import requests

logger = logging.getLogger(__name__)

class Client(object):
  """Subset of Matrix client API enhanced with AS-specific functionality."""

  HTTP_OK = requests.codes.ok # pylint: disable=no-member

  def __init__(self, conf):
    self.hs_server = conf["hs_server"]
    self.access_token = conf["as_access_token"]
    self.verify_hs_cert = conf["verify_hs_cert"]

  def __enter__(self):
    pass

  def __exit__(self, type_, value, traceback):
    pass

  def has_user(self, user):
    """Uses 'presence/status' request to determine whether AS-managed user exists.
       This is likely not the optimal way of doing it, but will do for now."""
    presence_url = self._create_url("/_matrix/client/r0/presence/{user_id}/status", user_id=user)
    resp = requests.get(presence_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def register_user(self, user):
    """Registers new AS-managed user."""
    register_url = self._create_url("/_matrix/client/r0/register", user_id=user)
    payload = {
        "type": "m.login.application_service",
        "username": _get_local_username(user)}
    resp = requests.post(register_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def get_non_managed_user_presence(self, target_user, service_user):
    """Get presence for non AS-managed user.
    Might fail if the user didn't give us permission to see their presence."""
    presence_url = self._create_url(
        "/_matrix/client/r0/presence/{target_user_id}/status",
        target_user_id=target_user, user_id=service_user)
    resp = requests.get(presence_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      result = json.loads(resp.content.decode("utf8"))
      if "presence" in result:
        return result["presence"]
    logger.error("Failed to get the presense for the user '{0}': {1}", target_user, resp.content)
    return None

  def get_presence_list(self, service_user):
    """Returns presence list for the service user.
    TODO: looks like we don't need this API call for now, remove?"""
    presence_list_url = self._create_url(
        "/_matrix/client/r0/presence/list/{user_id}", user_id=service_user)
    resp = requests.get(presence_list_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      return json.loads(resp.content.decode("utf8"))
    logger.error(
        "Failed to get the presense list for the service user '{0}': {1}",
        service_user, resp.content)
    return None

  def add_to_presence_list(self, target_user, service_user):
    """Requests the addition of the given 'target_user' to the presence list of 'service_user'."""
    presence_list_url = self._create_url(
        "/_matrix/client/r0/presence/list/{user_id}", user_id=service_user)
    payload = {"invite": [target_user]}
    resp = requests.post(presence_list_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def set_user_presence(self, user, status):
    """Sets AS-managed user presence."""
    presence_url = self._create_url("/_matrix/client/r0/presence/{user_id}/status", user_id=user)
    payload = {"presence": status}
    resp = requests.put(presence_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def get_user_profile(self, user):
    """Returns AS-managed user profile."""
    profile_url = self._create_url("/_matrix/client/r0/profile/{user_id}", user_id=user)
    resp = requests.get(profile_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      return json.loads(resp.content.decode("utf8"))
    logger.error("Failed to get profile for the user '{0}': {1}", user, resp.content)
    return None

  def set_user_display_name(self, user, display_name):
    """Sets AS-managed user display name."""
    presence_url = self._create_url(
        "/_matrix/client/r0/profile/{user_id}/displayname", user_id=user)
    payload = {"displayname": display_name}
    resp = requests.put(presence_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def set_user_avatar_url(self, user, avatar_url):
    """Sets AS-managed user avatar URL.
    The URL should point to the result of 'upload_content' call."""
    set_avatar_url = self._create_url(
        "/_matrix/client/r0/profile/{user_id}/avatar_url", user_id=user)
    payload = {"avatar_url": avatar_url}
    resp = requests.put(set_avatar_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def upload_content(self, content_type, data):
    """Uploads given content to the server and returns its resulting URL."""
    upload_url = self._create_url("/_matrix/media/r0/upload")
    headers = {"Content-Type": content_type}
    resp = requests.post(upload_url, data, headers=headers, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      result = json.loads(resp.content.decode("utf8"))
      if "content_uri" in result:
        return result["content_uri"]
    logger.error(
        "Failed to upload content of content type '{0}' and size {1}: {2}",
        content_type, len(data), resp.content)
    return None

  def download_content(self, server, media_id):
    """Downloads content from the server given server name and URL path."""
    download_url = self._create_url(
        "/_matrix/media/r0/download/{server}{media_id}", server=server, media_id=media_id)
    resp = requests.get(download_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      return resp.content
    logger.error(
        "Failed to download from '{0}' the media '{1}': {2}", server, media_id, resp.content)
    return None

  def set_user_typing(self, user, room_id, is_typing):
    """Sets typing state for the given AS-managed user in the given room."""
    typing_url = self._create_url(
        "/_matrix/client/r0/rooms/{room_id}/typing/{user_id}", room_id=room_id, user_id=user)
    payload = {"typing": is_typing}
    resp = requests.put(typing_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def send_message(self, room_id, sender, time, payload):
    """Sends the message to the given Matrix room."""
    msg_url = self._create_url(
        "/_matrix/client/r0/rooms/{room_id}/state/m.room.message/{txn_id}",
        room_id=room_id, user_id=sender, txn_id=str(uuid.uuid1()))
    msg_url += "&ts={0}".format(int(time.replace(tzinfo=timezone.utc).timestamp()))
    logger.debug("Sending message: {0}", json.dumps(payload))
    resp = requests.put(msg_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    result = json.loads(resp.content.decode("utf8"))
    if "event_id" in result:
      return result["event_id"]
    else:
      logger.error("Failed to parse the response: {0}", resp.content)
      return None

  def create_room(self, user, invited_contacts):
    """Creates new Matrix room with 'user' as creator and invites 'invited_contacts' to it."""
    create_room_url = self._create_url("/_matrix/client/r0/createRoom", user_id=user)
    payload = {"invite": invited_contacts, "preset": "private_chat"}
    resp = requests.post(create_room_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    result = json.loads(resp.content.decode("utf8"))
    if "room_id" in result:
      return result["room_id"]
    else:
      logger.error("Failed to parse the response: {0}", resp.content)
      return None

  def join_room(self, room_id, user):
    """Requests the server to join AS-managed user to the given room."""
    room_join_url = self._create_url(
        "/_matrix/client/r0/rooms/{room_id}/join", room_id=room_id, user_id=user)
    resp = requests.post(room_join_url, data="{}", verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def get_user_state(self, user, state_filter=None, next_batch=None):
    """Performs single sync request for the given user without waiting."""
    user_state_url = self._create_url("/_matrix/client/r0/sync", user_id=user) + "&full_state=true"
    if next_batch:
      user_state_url += "&since=" + next_batch
    if state_filter:
      user_state_url += "&filter=" + urllib.parse.quote(json.dumps(state_filter))
    resp = requests.get(user_state_url, verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    if resp.status_code == Client.HTTP_OK:
      return json.loads(resp.content.decode("utf8"))
    else:
      logger.error("Sync request failed: {0}", resp.content)
      return None

  def redact_event(self, room_id, user, event_id, reason):
    """Redacts (= essentially removes) given event."""
    redact_event_url = self._create_url(
        "/_matrix/client/r0/rooms/{room_id}/redact/{event_id}/{txn_id}",
        room_id=room_id, event_id=event_id, user_id=user, txn_id=str(uuid.uuid1()))
    payload = {"reason": reason}
    resp = requests.put(redact_event_url, data=json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def set_users_power_levels(self, room_id, sender, users_with_levels):
    """Changes the power level of the given users in the room."""
    power_level_url = self._create_url(
        "/_matrix/client/r0/rooms/{room_id}/state/m.room.power_levels",
        room_id=room_id, user_id=sender)
    # As of 0.19.2 version, Synapse throws an exception if events are not present.
    payload = {"events": {}, "users": users_with_levels}
    resp = requests.put(power_level_url, json.dumps(payload), verify=self.verify_hs_cert)
    logger.debug("Status: {0}, content: {1}", resp.status_code, resp.content)
    return resp.status_code == Client.HTTP_OK

  def _create_url(self, url, **kwargs):
    quoted_args = {}
    for key, value in kwargs.items():
      quoted_args[key] = urllib.parse.quote(value.encode("utf8"))
    formatted_url = url.format(**quoted_args)
    result_url = "{0}{1}?access_token={2}".format(
        self.hs_server, formatted_url, self.access_token)
    if "user_id" in quoted_args:
      result_url += "&user_id={0}".format(quoted_args["user_id"])
    return result_url

def _get_local_username(user):
  parts = user.split(":")
  if len(parts) == 2:
    if parts[0][0] == "@" and len(parts[0]) > 1:
      return parts[0][1:]
  raise ValueError("Invalid Matrix ID '{0}'".format(user))
