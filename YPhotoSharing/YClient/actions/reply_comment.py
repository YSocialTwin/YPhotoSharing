import logging

logger = logging.getLogger(__name__)

async def reply_comment(
    server,
    llm_service,
    user_id: str,
    photo_id: str,
    parent_comment_id: str,
    round_id: str,
    day: int,
    slot: int,
    cluster_id: int
) -> bool:
    """
    Generate a reply to a specific comment via the LLM and post it.
    """
    try:
        reply_body = await llm_service.generate_comment.remote(
            caption="Replying to comment thread",
            author="another_user",
            cluster_id=cluster_id,
            agent_attrs=None
        )
        
        await server.post_comment.remote(
            user_id=user_id,
            photo_id=photo_id,
            body=reply_body,
            round_id=round_id,
            parent_comment_id=parent_comment_id
        )
        logger.debug(f"User {user_id} replied to comment {parent_comment_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to reply for user {user_id}: {exc}")
        return False
