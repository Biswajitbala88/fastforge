import json
import logging
from typing import Any
from fastapi import WebSocket, status

from app.schemas.chat import ChatMessage, ChatStatus, RoomStatusResponse

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections partitioned by room with a 2-user limit."""

    MAX_PARTICIPANTS: int = 2

    def __init__(self) -> None:
        # room_id -> {client_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = {}

    def get_room_participants(self, room_id: str) -> dict[str, WebSocket]:
        return self._rooms.get(room_id, {})

    def get_room_status(self, room_id: str) -> RoomStatusResponse:
        participants = self.get_room_participants(room_id)
        count = len(participants)
        return RoomStatusResponse(
            room_id=room_id,
            count=count,
            max_users=self.MAX_PARTICIPANTS,
            is_full=count >= self.MAX_PARTICIPANTS,
            active_users=list(participants.keys()),
        )

    async def connect(self, websocket: WebSocket, room_id: str, client_id: str) -> bool:
        """Connect a client to a room.
        
        Rejects connection with WS 1008 if room is already full with 2 users.
        """
        participants = self._rooms.setdefault(room_id, {})

        if len(participants) >= self.MAX_PARTICIPANTS and client_id not in participants:
            logger.warning(
                f"Connection rejected: Room '{room_id}' is full ({len(participants)}/{self.MAX_PARTICIPANTS})."
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Room is full (maximum 2 participants allowed)",
            )
            return False

        await websocket.accept()
        participants[client_id] = websocket

        count = len(participants)
        if count == 1:
            welcome_status = ChatStatus(
                message=f"Joined room '{room_id}' as {client_id}. Waiting for peer to join...",
                user_count=1,
            )
            await self.send_personal_message(websocket, welcome_status.model_dump())
        else:
            ready_status = ChatStatus(
                message=f"{client_id} connected. Both users are connected, chat started!",
                user_count=count,
            )
            await self.broadcast_to_room(room_id, ready_status.model_dump())

        return True

    async def disconnect(self, room_id: str, client_id: str) -> None:
        """Remove client and notify remaining peer or prune empty room."""
        if room_id not in self._rooms:
            return

        participants = self._rooms[room_id]
        if client_id in participants:
            del participants[client_id]

        if not participants:
            del self._rooms[room_id]
            logger.info(f"Room '{room_id}' closed (no active users).")
        else:
            remaining_count = len(participants)
            leave_status = ChatStatus(
                message=f"{client_id} has disconnected.",
                user_count=remaining_count,
            )
            await self.broadcast_to_room(room_id, leave_status.model_dump())

    async def send_personal_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send message directly to a websocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_room(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude_client: str | None = None,
    ) -> None:
        """Broadcast JSON message to all participants in the room, optionally excluding a client."""
        participants = self.get_room_participants(room_id)
        if not participants:
            return

        payload = json.dumps(message)
        dead_clients: list[str] = []

        for cid, ws in participants.items():
            if exclude_client is not None and cid == exclude_client:
                continue
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.error(f"Failed to send to client {cid}: {e}")
                dead_clients.append(cid)

        for cid in dead_clients:
            await self.disconnect(room_id, cid)


chat_manager = ConnectionManager()
