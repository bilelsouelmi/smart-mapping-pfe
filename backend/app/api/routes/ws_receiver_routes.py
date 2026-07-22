"""
Test Receiver Route
POST /api/ws-receiver/receive  - Receive XML from REST pipeline (test endpoint)
GET  /api/ws-receiver/messages - List all received messages
DELETE /api/ws-receiver/messages - Clear all received messages
"""
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for received messages (for testing purposes)
received_messages = []


@router.post("/receive", status_code=status.HTTP_200_OK)
async def receive_xml(request: Request):
    """
    Web service endpoint that receives XML sent by the REST pipeline.
    Simulates an external system consuming the transformed ISO 20022 XML.
    """
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        authorization = request.headers.get("authorization", "")

        xml_content = body.decode("utf-8")

        # Store the received message
        message = {
            "id": len(received_messages) + 1,
            "received_at": datetime.utcnow().isoformat(),
            "content_type": content_type,
            "size_bytes": len(body),
            "authorization": authorization[:50] if authorization else None,
            "xml_preview": xml_content[:500],
            "xml_full": xml_content,
        }
        received_messages.append(message)

        logger.info(f"✅ REST receiver: received message #{message['id']} ({len(body)} bytes)")

        return {
            "status": "received",
            "message_id": message["id"],
            "received_at": message["received_at"],
            "size_bytes": len(body),
            "message": f"XML received successfully ({len(body)} bytes)"
        }

    except Exception as e:
        logger.error(f"REST receiver error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@router.get("/messages")
async def list_received_messages():
    """
    List all messages received by the test web service endpoint.
    """
    return {
        "total": len(received_messages),
        "messages": [
            {
                "id": m["id"],
                "received_at": m["received_at"],
                "content_type": m["content_type"],
                "size_bytes": m["size_bytes"],
                "xml_preview": m["xml_preview"],
            }
            for m in received_messages
        ]
    }


@router.get("/messages/{message_id}")
async def get_received_message(message_id: int):
    """
    Get the full XML content of a specific received message.
    """
    msg = next((m for m in received_messages if m["id"] == message_id), None)
    if not msg:
        return JSONResponse(status_code=404, content={"detail": "Message not found"})
    return msg


@router.delete("/messages")
async def clear_received_messages():
    """
    Clear all received messages from memory.
    """
    count = len(received_messages)
    received_messages.clear()
    return {"message": f"Cleared {count} message(s)"}