# EZTalk API Endpoints Reference

Tài liệu này tổng hợp toàn bộ API endpoint hiện có trong backend EZTalk, gồm HTTP endpoints và WebSocket protocol. Mục tiêu là để frontend/mobile team có thể tích hợp trực tiếp mà không cần đọc source code.

Base URL local mặc định:

```txt
http://localhost:8080
ws://localhost:8080
```

Production base URL sẽ phụ thuộc vào Load Balancer/Ingress.

## Authentication

Các endpoint bảo vệ dữ liệu session hiện dùng `api_key`.

HTTP API truyền qua query parameter:

```txt
?api_key=<api_key>
```

WebSocket truyền qua query parameter:

```txt
ws://<host>/ws/chat/{session_id}?api_key=<api_key>
```

Backend sẽ dùng `api_key` để truy vấn bảng `users` và lấy ra `user_id` thật. Client không được tự truyền `user_id`.

Nếu `api_key` không hợp lệ:

HTTP trả:

```json
{
  "detail": "Invalid API key."
}
```

WebSocket trả:

```json
{
  "type": "error",
  "session_id": "session_123",
  "code": "auth_error",
  "message": "API key không hợp lệ hoặc đã hết hạn."
}
```

## Endpoint Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | No | Service metadata. |
| `GET` | `/health` | No | Health check for container/load balancer. |
| `WebSocket` | `/ws/chat/{session_id}?api_key=...` | Yes | Realtime streaming chat with AI. |
| `GET` | `/api/v1/sessions/{session_id}/messages?api_key=...` | Yes | Get persisted chat history. |
| `POST` | `/api/v1/sessions/{session_id}/evaluate?api_key=...` | Yes | Run AI Evaluation for one session. |

## GET `/`

Returns basic service metadata and useful paths.

### Request

```bash
curl http://localhost:8080/
```

### Response `200`

```json
{
  "name": "EZTalk Chat API",
  "status": "running",
  "health": "/health",
  "docs": "/docs",
  "websocket": "/ws/chat/{session_id}"
}
```

## GET `/health`

Lightweight health check endpoint. Intended for Docker healthcheck, load balancer healthcheck, or uptime monitoring.

### Request

```bash
curl http://localhost:8080/health
```

### Response `200`

```json
{
  "status": "ok"
}
```

## WebSocket `/ws/chat/{session_id}`

Realtime chat endpoint. Client sends plain text messages. Server replies with JSON events.

### URL

```txt
ws://localhost:8080/ws/chat/{session_id}?api_key=<api_key>
```

Example:

```txt
ws://localhost:8080/ws/chat/session_123?api_key=ez_live_xxx
```

### Client Message Format

Send plain text WebSocket frames:

```txt
I want to practice small talk about coffee.
```

### Server Event: `connected`

Sent once after the socket is accepted and `api_key` is valid.

```json
{
  "type": "connected",
  "session_id": "session_123",
  "user_id": "user_abc",
  "message": "WebSocket connected."
}
```

### Server Event: `assistant_delta`

Streaming chunk from the AI assistant. Append `delta` to the current assistant message bubble.

```json
{
  "type": "assistant_delta",
  "session_id": "session_123",
  "delta": "That sounds fun! "
}
```

Example stream:

```json
{ "type": "assistant_delta", "session_id": "session_123", "delta": "That sounds " }
{ "type": "assistant_delta", "session_id": "session_123", "delta": "fun! What kind " }
{ "type": "assistant_delta", "session_id": "session_123", "delta": "of coffee do you like?" }
```

### Server Event: `assistant_done`

Marks the end of one assistant response. The `message` field contains the full assistant response.

```json
{
  "type": "assistant_done",
  "session_id": "session_123",
  "message": "That sounds fun! What kind of coffee do you like?"
}
```

Frontend note: if the UI already assembled all `assistant_delta` chunks, do not render `assistant_done.message` as a second duplicate message. Use it as a finalization signal.

### Server Event: `error`

Recoverable or terminal protocol error.

```json
{
  "type": "error",
  "session_id": "session_123",
  "code": "empty_message",
  "message": "Vui lòng gửi một tin nhắn có nội dung."
}
```

Current error codes:

| Code | Meaning | Suggested client behavior |
|---|---|---|
| `auth_error` | Invalid API key, expired API key, or session ownership denied. | Stop chat flow and re-authenticate. |
| `empty_message` | User sent blank text. | Keep socket open and ask user to type a message. |
| `llm_unavailable` | vLLM upstream failed or timed out. | Keep socket open and allow retry. |
| `database_error` | User/assistant message pair could not be persisted. | Warn user that this turn was not saved. |

### JavaScript Example

```js
const sessionId = "session_123";
const apiKey = "ez_live_xxx";
const ws = new WebSocket(
  `ws://localhost:8080/ws/chat/${sessionId}?api_key=${apiKey}`
);

let currentAssistantMessage = "";

ws.onmessage = (event) => {
  const payload = JSON.parse(event.data);

  switch (payload.type) {
    case "connected":
      console.log("Connected as user:", payload.user_id);
      break;

    case "assistant_delta":
      currentAssistantMessage += payload.delta;
      console.log("Streaming:", currentAssistantMessage);
      break;

    case "assistant_done":
      console.log("Final assistant response:", payload.message);
      currentAssistantMessage = "";
      break;

    case "error":
      console.error(payload.code, payload.message);
      break;
  }
};

ws.onopen = () => {
  ws.send("I want to practice ordering coffee in English.");
};
```

## GET `/api/v1/sessions/{session_id}/messages`

Returns all persisted messages for a session owned by the authenticated API key.

Messages are returned in chronological order.

### Request

```bash
curl "http://localhost:8080/api/v1/sessions/session_123/messages?api_key=ez_live_xxx"
```

### Query Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `api_key` | string | yes | API key used to resolve the real user. |

### Response `200`

```json
[
  {
    "id": 1,
    "session_id": "session_123",
    "user_id": "user_abc",
    "role": "user",
    "content": "I want to practice ordering coffee in English.",
    "created_at": "2026-06-28T09:15:30"
  },
  {
    "id": 2,
    "session_id": "session_123",
    "user_id": "user_abc",
    "role": "assistant",
    "content": "Sure! Let's pretend you're at a cafe. What would you like to order?",
    "created_at": "2026-06-28T09:15:32"
  }
]
```

### Response `200` for Empty Session

If the session has no messages for the authenticated user:

```json
[]
```

### Response `401`

```json
{
  "detail": "Invalid API key."
}
```

## POST `/api/v1/sessions/{session_id}/evaluate`

Runs AI Evaluation for one persisted conversation session.

The backend loads the full transcript from DB, sends it to vLLM with structured JSON mode, validates the response using Pydantic, then returns the validated result.

### Request

```bash
curl -X POST "http://localhost:8080/api/v1/sessions/session_123/evaluate?api_key=ez_live_xxx"
```

### Query Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `api_key` | string | yes | API key used to resolve the real user. |

### Response `200`

```json
{
  "grammar_score": 72,
  "vocabulary_score": 68,
  "eq_score": 81,
  "cefr_level": "A2",
  "grammar_errors": [
    {
      "original": "I go to school yesterday.",
      "corrected": "I went to school yesterday.",
      "explanation_vi": "Khi nói về hôm qua, cần dùng thì quá khứ."
    }
  ],
  "suggested_replies": [
    "I went there to meet my classmates.",
    "It was fun, but I felt a little tired."
  ],
  "overall_feedback_vi": "Bạn giao tiếp rõ ý và nên chú ý thì quá khứ."
}
```

### Response Schema

| Field | Type | Validation | Description |
|---|---|---|---|
| `grammar_score` | integer | `0 <= value <= 100` | Grammar score. |
| `vocabulary_score` | integer | `0 <= value <= 100` | Vocabulary score. |
| `eq_score` | integer | `0 <= value <= 100` | EQ / conversation flow score. |
| `cefr_level` | string | `A1`, `A2`, `B1`, `B2`, `C1`, `C2` | Estimated CEFR level. |
| `grammar_errors` | array | list of objects | Grammar corrections. |
| `grammar_errors[].original` | string | required | Original sentence from user. |
| `grammar_errors[].corrected` | string | required | Corrected sentence. |
| `grammar_errors[].explanation_vi` | string | required | Vietnamese explanation. |
| `suggested_replies` | array of strings | required | Suggested natural replies for practice. |
| `overall_feedback_vi` | string | required | Overall feedback in Vietnamese. |

### Radar Chart Mapping

Mobile app can render radar/spider chart using:

```json
[
  {
    "label": "Grammar",
    "value": 72
  },
  {
    "label": "Vocabulary",
    "value": 68
  },
  {
    "label": "EQ",
    "value": 81
  }
]
```

### Response `401`

```json
{
  "detail": "Invalid API key."
}
```

### Response `502`

Returned when the AI Evaluation service or vLLM response is invalid/unavailable.

```json
{
  "detail": "AI evaluation service is temporarily unavailable."
}
```

## OpenAPI Docs

FastAPI auto-generates HTTP API docs at:

```txt
http://localhost:8080/docs
```

Note: WebSocket protocol details are not fully represented in OpenAPI, so frontend should use the WebSocket section in this document as the source of truth.

## Current Limitations

- User creation/admin API is not exposed yet. Users/API keys must currently be seeded directly through backend scripts, DB operations, or test fixtures.
- API key is currently passed as query parameter. For stricter production security, move HTTP auth to `Authorization: Bearer <token>` and use short-lived WebSocket tokens.
- Session list/create/delete endpoints are not implemented yet.
