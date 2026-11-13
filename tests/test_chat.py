import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.chat_manager import chat_manager

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_chat_manager():
    """Ensure clean chat manager state before each test."""
    chat_manager._rooms.clear()
    yield
    chat_manager._rooms.clear()


def test_chat_html_page() -> None:
    response = client.get("/chat/test-room")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Room: <span id=\"roomLabel\">test-room</span>" in response.text


def test_room_status_endpoint() -> None:
    room_id = "status-room"
    response = client.get(f"/api/chat/rooms/{room_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["room_id"] == room_id
    assert data["count"] == 0
    assert data["is_full"] is False
    assert data["active_users"] == []

    with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Alice"):
        res = client.get(f"/api/chat/rooms/{room_id}")
        assert res.status_code == 200
        d = res.json()
        assert d["count"] == 1
        assert d["is_full"] is False
        assert d["active_users"] == ["Alice"]

    # After Alice leaves
    res = client.get(f"/api/chat/rooms/{room_id}")
    assert res.json()["count"] == 0


def test_user_connect_waiting_for_peer() -> None:
    room_id = "room-wait"
    with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Alice") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "status"
        assert msg["user_count"] == 1
        assert "Waiting for peer" in msg["message"]


def test_two_users_chat_exchange() -> None:
    room_id = "room-duo"
    with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Alice") as ws_alice:
        # Alice receives initial waiting status
        init_alice = ws_alice.receive_json()
        assert init_alice["user_count"] == 1

        with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Bob") as ws_bob:
            # Bob connecting triggers start status to both Alice and Bob
            bob_joined_alice = ws_alice.receive_json()
            assert bob_joined_alice["type"] == "status"
            assert bob_joined_alice["user_count"] == 2
            assert "chat started" in bob_joined_alice["message"].lower()

            bob_joined_bob = ws_bob.receive_json()
            assert bob_joined_bob["type"] == "status"
            assert bob_joined_bob["user_count"] == 2

            # Alice sends a message
            ws_alice.send_text(json.dumps({"message": "Hello Bob!"}))

            # Both Alice and Bob should receive Alice's message
            msg_for_alice = ws_alice.receive_json()
            assert msg_for_alice["sender"] == "Alice"
            assert msg_for_alice["message"] == "Hello Bob!"

            msg_for_bob = ws_bob.receive_json()
            assert msg_for_bob["sender"] == "Alice"
            assert msg_for_bob["message"] == "Hello Bob!"

            # Bob sends a message as raw string
            ws_bob.send_text("Hey Alice, nice to meet you!")

            msg2_for_alice = ws_alice.receive_json()
            assert msg2_for_alice["sender"] == "Bob"
            assert msg2_for_alice["message"] == "Hey Alice, nice to meet you!"


def test_third_user_rejected_when_room_full() -> None:
    room_id = "room-capacity"
    with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Alice"):
        with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Bob"):
            # Room has 2 users now. Charlie attempts to join
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Charlie"):
                    pass
            assert exc_info.value.code == 1008


def test_disconnect_notifies_peer() -> None:
    room_id = "room-disconnect"
    with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Alice") as ws_alice:
        ws_alice.receive_json()  # Waiting status

        with client.websocket_connect(f"/ws/chat/{room_id}?client_id=Bob") as ws_bob:
            ws_alice.receive_json()  # Bob joined status
            ws_bob.receive_json()  # Bob joined status

        # Bob has now disconnected
        leave_notification = ws_alice.receive_json()
        assert leave_notification["type"] == "status"
        assert leave_notification["user_count"] == 1
        assert "Bob has disconnected" in leave_notification["message"]
