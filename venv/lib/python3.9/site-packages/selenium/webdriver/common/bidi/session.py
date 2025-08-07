# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from selenium.webdriver.common.bidi.common import command_builder


class Session:

    def __init__(self, conn):
        self.conn = conn

    def subscribe(self, *events, browsing_contexts=None):
        params = {
            "events": events,
        }
        if browsing_contexts is None:
            browsing_contexts = []
        if browsing_contexts:
            params["browsingContexts"] = browsing_contexts
        return command_builder("session.subscribe", params)

    def unsubscribe(self, *events, browsing_contexts=None):
        params = {
            "events": events,
        }
        if browsing_contexts is None:
            browsing_contexts = []
        if browsing_contexts:
            params["browsingContexts"] = browsing_contexts
        return command_builder("session.unsubscribe", params)

    def status(self):
        """
        The session.status command returns information about the remote end's readiness
        to create new sessions and may include implementation-specific metadata.

        Returns
        -------
        dict
            Dictionary containing the ready state (bool), message (str) and metadata
        """
        cmd = command_builder("session.status", {})
        return self.conn.execute(cmd)
