import logging

from YPhotoSharing.YClient.actions.dynamics_helpers import (
    build_memory_context,
    record_memory_event,
)

logger = logging.getLogger(__name__)

async def send_dm(
    server,
    llm_service,
    sender_id: str,
    recipient_id: str,
    photo_id: str = None,
    day: int = 0,
    slot: int = 0,
    cluster_id: int = 0
) -> bool:
    """
    Generate and send a direct message to a user, optionally attaching a photo.
    """
    try:
        agent_attrs = {}
        try:
            memory_context = await build_memory_context(
                server,
                run_id="default",
                agent_user_id=sender_id,
                other_user_id=recipient_id,
                label="Past interactions with this user",
            )
            if memory_context:
                agent_attrs["memory_context"] = memory_context
        except Exception as e:
            logger.warning(f"Could not retrieve memories for DM: {e}")

        content = await llm_service.generate_comment.remote(
            caption="Sending a direct message.",
            author="another_user",
            cluster_id=cluster_id,
            agent_attrs=agent_attrs
        )
        
        await server.send_dm.remote(sender_id, recipient_id, content, photo_id)
        
        try:
            event_data = {
                "run_id": "default",
                "agent_user_id": sender_id,
                "other_user_id": recipient_id,
                "event_type": "sent_dm",
                "description": f"Sent DM: {content[:50]}...",
                "round_id": day * 24 + slot
            }
            await record_memory_event(server, enabled=True, event_data=event_data)
        except Exception as e:
            logger.warning(f"Could not save memory event: {e}")
            
        logger.debug(f"User {sender_id} sent DM to {recipient_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send DM from {sender_id} to {recipient_id}: {exc}")
        return False
