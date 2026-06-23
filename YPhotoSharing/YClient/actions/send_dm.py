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
        content = await llm_service.generate_comment.remote(
            caption="Sending a direct message.",
            author="another_user",
            cluster_id=cluster_id,
            agent_attrs=None
        )
        
        await server.send_dm.remote(sender_id, recipient_id, content, photo_id)
        logger.debug(f"User {sender_id} sent DM to {recipient_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send DM from {sender_id} to {recipient_id}: {exc}")
        return False
