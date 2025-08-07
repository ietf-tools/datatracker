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

from typing import Dict
from typing import List

from selenium.webdriver.common.bidi.common import command_builder


class ClientWindowState:
    """Represents a window state."""

    FULLSCREEN = "fullscreen"
    MAXIMIZED = "maximized"
    MINIMIZED = "minimized"
    NORMAL = "normal"


class ClientWindowInfo:
    """Represents a client window information."""

    def __init__(
        self,
        client_window: str,
        state: str,
        width: int,
        height: int,
        x: int,
        y: int,
        active: bool,
    ):
        self.client_window = client_window
        self.state = state
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.active = active

    def get_state(self) -> str:
        """Gets the state of the client window.

        Returns:
        -------
            str: The state of the client window (one of the ClientWindowState constants).
        """
        return self.state

    def get_client_window(self) -> str:
        """Gets the client window identifier.

        Returns:
        -------
            str: The client window identifier.
        """
        return self.client_window

    def get_width(self) -> int:
        """Gets the width of the client window.

        Returns:
        -------
            int: The width of the client window.
        """
        return self.width

    def get_height(self) -> int:
        """Gets the height of the client window.

        Returns:
        -------
            int: The height of the client window.
        """
        return self.height

    def get_x(self) -> int:
        """Gets the x coordinate of the client window.

        Returns:
        -------
            int: The x coordinate of the client window.
        """
        return self.x

    def get_y(self) -> int:
        """Gets the y coordinate of the client window.

        Returns:
        -------
            int: The y coordinate of the client window.
        """
        return self.y

    def is_active(self) -> bool:
        """Checks if the client window is active.

        Returns:
        -------
            bool: True if the client window is active, False otherwise.
        """
        return self.active

    @classmethod
    def from_dict(cls, data: Dict) -> "ClientWindowInfo":
        """Creates a ClientWindowInfo instance from a dictionary.

        Parameters:
        -----------
            data: A dictionary containing the client window information.

        Returns:
        -------
            ClientWindowInfo: A new instance of ClientWindowInfo.
        """
        return cls(
            client_window=data.get("clientWindow"),
            state=data.get("state"),
            width=data.get("width"),
            height=data.get("height"),
            x=data.get("x"),
            y=data.get("y"),
            active=data.get("active"),
        )


class Browser:
    """
    BiDi implementation of the browser module.
    """

    def __init__(self, conn):
        self.conn = conn

    def create_user_context(self) -> str:
        """Creates a new user context.

        Returns:
        -------
            str: The ID of the created user context.
        """
        result = self.conn.execute(command_builder("browser.createUserContext", {}))
        return result["userContext"]

    def get_user_contexts(self) -> List[str]:
        """Gets all user contexts.

        Returns:
        -------
            List[str]: A list of user context IDs.
        """
        result = self.conn.execute(command_builder("browser.getUserContexts", {}))
        return [context_info["userContext"] for context_info in result["userContexts"]]

    def remove_user_context(self, user_context_id: str) -> None:
        """Removes a user context.

        Parameters:
        -----------
            user_context_id: The ID of the user context to remove.

        Raises:
        ------
            Exception: If the user context ID is "default" or does not exist.
        """
        if user_context_id == "default":
            raise Exception("Cannot remove the default user context")

        params = {"userContext": user_context_id}
        self.conn.execute(command_builder("browser.removeUserContext", params))

    def get_client_windows(self) -> List[ClientWindowInfo]:
        """Gets all client windows.

        Returns:
        -------
            List[ClientWindowInfo]: A list of client window information.
        """
        result = self.conn.execute(command_builder("browser.getClientWindows", {}))
        return [ClientWindowInfo.from_dict(window) for window in result["clientWindows"]]
