import json
import logging
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse

from app.schemas.chat import ChatMessage, RoomStatusResponse
from app.services.chat_manager import chat_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


@router.websocket("/ws/chat/{room_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    room_id: str,
    client_id: str = Query(..., description="Unique name or ID for the chatter"),
) -> None:
    """Two-user real-time WebSocket chat endpoint.
    
    Accepts connections up to 2 users per room_id. Third user attempt is rejected
    with status code 1008 (WS_1008_POLICY_VIOLATION).
    """
    connected = await chat_manager.connect(websocket, room_id, client_id)
    if not connected:
        return

    try:
        while True:
            raw_data = await websocket.receive_text()
            # Support both raw text and JSON message payloads
            try:
                payload = json.loads(raw_data)
                if isinstance(payload, dict) and "message" in payload:
                    text_content = str(payload["message"])
                else:
                    text_content = raw_data
            except (json.JSONDecodeError, TypeError):
                text_content = raw_data

            chat_msg = ChatMessage(
                sender=client_id,
                message=text_content,
            )
            await chat_manager.broadcast_to_room(room_id, chat_msg.model_dump())
    except WebSocketDisconnect:
        await chat_manager.disconnect(room_id, client_id)
    except Exception as exc:
        logger.error(f"WebSocket error in room '{room_id}' for client '{client_id}': {exc}")
        await chat_manager.disconnect(room_id, client_id)


@router.get("/api/chat/rooms/{room_id}", response_model=RoomStatusResponse)
def get_room_status(room_id: str) -> RoomStatusResponse:
    """Return status and active user count for a chat room."""
    return chat_manager.get_room_status(room_id)


@router.get("/chat/{room_id}", response_class=HTMLResponse)
def chat_page(room_id: str) -> HTMLResponse:
    """Interactive HTML web client for testing 2-user WebSocket chat."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FastForge 2-User Chat - Room: {room_id}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --card-border: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --peer-bubble: #334155;
            --self-bubble: #2563eb;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        body {{
            background: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 16px;
        }}
        .chat-container {{
            width: 100%;
            max-width: 640px;
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            height: 85vh;
            overflow: hidden;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .chat-header {{
            padding: 16px;
            border-bottom: 1px solid var(--card-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
        }}
        .room-title {{
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
        }}
        .badge-disconnected {{ background: #475569; color: #cbd5e1; }}
        .badge-waiting {{ background: #d97706; color: #fef3c7; }}
        .badge-connected {{ background: var(--success); color: white; }}
        .badge-error {{ background: var(--danger); color: white; }}

        .setup-bar {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--card-border);
            display: flex;
            gap: 8px;
            background: #192231;
        }}
        .input-field {{
            background: #0f172a;
            border: 1px solid var(--card-border);
            color: var(--text);
            padding: 8px 12px;
            border-radius: 6px;
            outline: none;
            flex: 1;
            font-size: 0.9rem;
        }}
        .input-field:focus {{
            border-color: var(--primary);
        }}
        .btn {{
            background: var(--primary);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.9rem;
            transition: background 0.15s ease;
        }}
        .btn:hover {{ background: var(--primary-hover); }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .btn-danger {{ background: var(--danger); }}
        .btn-danger:hover {{ background: #dc2626; }}

        .hint-bar {{
            background: #1e3a8a33;
            border-bottom: 1px solid #1d4ed855;
            padding: 8px 16px;
            font-size: 0.8rem;
            color: #93c5fd;
        }}

        .messages-area {{
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .message-bubble {{
            max-width: 75%;
            padding: 10px 14px;
            border-radius: 10px;
            font-size: 0.95rem;
            word-break: break-word;
            line-height: 1.4;
        }}
        .msg-self {{
            align-self: flex-end;
            background: var(--self-bubble);
            color: white;
            border-bottom-right-radius: 2px;
        }}
        .msg-peer {{
            align-self: flex-start;
            background: var(--peer-bubble);
            color: var(--text);
            border-bottom-left-radius: 2px;
        }}
        .msg-meta {{
            font-size: 0.72rem;
            opacity: 0.75;
            margin-bottom: 3px;
        }}
        .msg-status {{
            align-self: center;
            background: rgba(148, 163, 184, 0.12);
            color: var(--text-muted);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.8rem;
            max-width: 90%;
            text-align: center;
        }}

        .chat-input-bar {{
            padding: 14px 16px;
            border-top: 1px solid var(--card-border);
            display: flex;
            gap: 8px;
            background: rgba(15, 23, 42, 0.6);
        }}
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div>
                <div class="room-title">Room: <span id="roomLabel">{room_id}</span></div>
                <div style="font-size:0.75rem; color:var(--text-muted);">Max capacity: 2 users</div>
            </div>
            <div id="statusBadge" class="badge badge-disconnected">Disconnected</div>
        </div>

        <div class="hint-bar">
            💡 Open this page in a second browser window/tab to test chatting as the second user!
        </div>

        <div class="setup-bar" id="connectionControls">
            <input type="text" id="usernameInput" class="input-field" placeholder="Enter username / ID" />
            <button id="connectBtn" class="btn" onclick="toggleConnection()">Connect</button>
        </div>

        <div class="messages-area" id="messagesArea">
            <div class="msg-status">Enter your username above and click Connect to start chatting.</div>
        </div>

        <div class="chat-input-bar">
            <input type="text" id="messageInput" class="input-field" placeholder="Type a message..." disabled onkeypress="handleKeyPress(event)" />
            <button id="sendBtn" class="btn" onclick="sendMessage()" disabled>Send</button>
        </div>
    </div>

    <script>
        const roomId = "{room_id}";
        let ws = null;
        let myClientId = "";

        // Prepopulate random username
        document.getElementById("usernameInput").value = "User-" + Math.floor(1000 + Math.random() * 9000);

        function updateStatus(state, text) {{
            const badge = document.getElementById("statusBadge");
            badge.className = "badge badge-" + state;
            badge.innerText = text;
        }}

        function toggleConnection() {{
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {{
                ws.close();
            }} else {{
                connectWebSocket();
            }}
        }}

        function connectWebSocket() {{
            const username = document.getElementById("usernameInput").value.trim();
            if (!username) {{
                alert("Please enter a username");
                return;
            }}
            myClientId = username;

            const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            const wsUrl = `${{protocol}}//${{window.location.host}}/ws/chat/${{roomId}}?client_id=${{encodeURIComponent(username)}}`;

            updateStatus("waiting", "Connecting...");
            document.getElementById("connectBtn").disabled = true;
            document.getElementById("usernameInput").disabled = true;

            ws = new WebSocket(wsUrl);

            ws.onopen = () => {{
                updateStatus("waiting", "Waiting for peer");
                document.getElementById("connectBtn").innerText = "Disconnect";
                document.getElementById("connectBtn").className = "btn btn-danger";
                document.getElementById("connectBtn").disabled = false;
                document.getElementById("messageInput").disabled = false;
                document.getElementById("sendBtn").disabled = false;
                document.getElementById("messageInput").focus();
            }};

            ws.onmessage = (event) => {{
                try {{
                    const data = JSON.parse(event.data);
                    renderMessage(data);
                }} catch (e) {{
                    renderMessage({{ type: "message", sender: "Unknown", message: event.data }});
                }}
            }};

            ws.onclose = (event) => {{
                if (event.code === 1008) {{
                    updateStatus("error", "Room Full");
                    appendStatusBubble("🚫 Connection rejected: Room is full (2 participants already connected).");
                }} else {{
                    updateStatus("disconnected", "Disconnected");
                    appendStatusBubble("🔌 Disconnected from chat room.");
                }}
                resetControls();
            }};

            ws.onerror = (err) => {{
                updateStatus("error", "Error");
                console.error("WebSocket error:", err);
            }};
        }}

        function resetControls() {{
            document.getElementById("connectBtn").innerText = "Connect";
            document.getElementById("connectBtn").className = "btn";
            document.getElementById("connectBtn").disabled = false;
            document.getElementById("usernameInput").disabled = false;
            document.getElementById("messageInput").disabled = true;
            document.getElementById("sendBtn").disabled = true;
        }}

        function renderMessage(data) {{
            const area = document.getElementById("messagesArea");
            if (data.type === "status") {{
                appendStatusBubble(data.message);
                if (data.user_count === 2) {{
                    updateStatus("connected", "Active (2/2)");
                }} else if (data.user_count === 1) {{
                    updateStatus("waiting", "Waiting for peer (1/2)");
                }}
            }} else {{
                const isSelf = data.sender === myClientId;
                const bubble = document.createElement("div");
                bubble.className = "message-bubble " + (isSelf ? "msg-self" : "msg-peer");

                const meta = document.createElement("div");
                meta.className = "msg-meta";
                const timeStr = data.timestamp ? new Date(data.timestamp).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : "";
                meta.innerText = (isSelf ? "You" : data.sender) + (timeStr ? " • " + timeStr : "");

                const text = document.createElement("div");
                text.innerText = data.message;

                bubble.appendChild(meta);
                bubble.appendChild(text);
                area.appendChild(bubble);
                area.scrollTop = area.scrollHeight;
            }}
        }}

        function appendStatusBubble(text) {{
            const area = document.getElementById("messagesArea");
            const bubble = document.createElement("div");
            bubble.className = "msg-status";
            bubble.innerText = text;
            area.appendChild(bubble);
            area.scrollTop = area.scrollHeight;
        }}

        function sendMessage() {{
            const input = document.getElementById("messageInput");
            const text = input.value.trim();
            if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

            ws.send(JSON.stringify({{ message: text }}));
            input.value = "";
            input.focus();
        }}

        function handleKeyPress(e) {{
            if (e.key === "Enter") {{
                sendMessage();
            }}
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
