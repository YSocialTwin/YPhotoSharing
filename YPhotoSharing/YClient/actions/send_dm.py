import logging

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
        # YSimulator Stage 4: Retrieve memory events for this specific recipient
        # Actually get_memory_events returns all memories. We need to filter or get specific.
        try:
            memories = await server.get_memory_events.remote(run_id="default", agent_user_id=sender_id, limit=50)
            recipient_mems = [m for m in memories if m.get("other_user_id") == recipient_id]
            if recipient_mems:
                mem_texts = [m.get("event_type", "interaction") for m in recipient_mems[:5]]
                agent_attrs["memory_context"] = f"Past interactions with this user: {', '.join(mem_texts)}"
        except Exception as e:
            logger.warning(f"Could not retrieve memories for DM: {e}")

        content = await llm_service.generate_comment.remote(
            caption="Sending a direct message.",
            author="another_user",
            cluster_id=cluster_id,
            agent_attrs=agent_attrs
        )
        
        await server.send_dm.remote(sender_id, recipient_id, content, photo_id)
        
        # YSimulator Stage 4: Store post-interaction summary
        try:
            event_data = {
                "run_id": "default",
                "agent_user_id": sender_id,
                "other_user_id": recipient_id,
                "event_type": "sent_dm",
                "description": f"Sent DM: {content[:50]}...",
                "round_id": day * 24 + slot
            }
            await server.add_memory_event.remote(event_data)
        except Exception as e:
            logger.warning(f"Could not save memory event: {e}")
            
        logger.debug(f"User {sender_id} sent DM to {recipient_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send DM from {sender_id} to {recipient_id}: {exc}")
        return False
