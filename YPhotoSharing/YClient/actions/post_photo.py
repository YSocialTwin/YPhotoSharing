"""
Photo posting action for YPhotoSharing agents.

Agents call post_photo() to publish a new image on the simulated platform.
The LLM generates the caption; the server persists the record.
"""

import logging
import uuid
from typing import Any, Dict, Optional
from YPhotoSharing.YClient.LLM_interactions.image_generation_service import ImageGenerationService

logger = logging.getLogger(__name__)
async def post_photo(
    server,
    llm_service,
    user_id: str,
    cluster_id: int,
    round_id: str,
    day: int,
    slot: int,
    topic: str = "general",
    image_url: Optional[str] = None,
    filter_name: Optional[str] = None,
    location_name: Optional[str] = None,
    agent_attrs: Optional[Dict[str, Any]] = None,
    image_gen_service = None,
) -> Optional[str]:
    """
    Generate a caption with the LLM and persist a new photo via the server.

    Args:
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
        user_id: UUID of the posting user
        cluster_id: Agent persona cluster
        round_id: Current simulation round UUID
        day: Simulation day
        slot: Hour slot within the day
        topic: Topic used to generate the caption
        image_url: URL of the photo (simulated or real)
        filter_name: Instagram-style filter name
        location_name: Optional location tag
        agent_attrs: Extra agent attributes forwarded to the LLM

    Returns:
        UUID of the created photo, or None on failure
    """
    if agent_attrs is None:
        agent_attrs = {}

    # Fetch usernames of followers to allow mentions
    try:
        following_ids = await server.get_following.remote(user_id)
        if following_ids:
            # Just sample a few to avoid huge prompts
            import random
            sample_ids = random.sample(following_ids, min(3, len(following_ids)))
            following_usernames = []
            for fid in sample_ids:
                u = await server.get_user.remote(fid)
                if u and u.get("username"):
                    following_usernames.append(u["username"])
            agent_attrs["following_usernames"] = following_usernames
    except Exception as e:
        logger.warning(f"Could not fetch following usernames for mentions: {e}")

    try:
        caption = await llm_service.generate_caption.remote(
            topic=topic,
            day=day,
            slot=slot,
            cluster_id=cluster_id,
            agent_attrs=agent_attrs,
        )
    except Exception as exc:
        logger.warning(f"Caption generation failed for user {user_id}: {exc}")
        caption = f"#{topic}"

    # Generate media url using Phase 7 Image Generation Service
    try:
        raw_media = await image_gen_service.generate_image(caption, topic) if image_gen_service else None
        if raw_media:
            final_media_url = await server.save_media.remote(raw_media, "jpg")
        else:
            final_media_url = None
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        final_media_url = None
        
    # If image generation service is active, require a generated photo
    if image_gen_service:
        if not final_media_url:
            logger.warning(f"Aborting post for {user_id} because photo generation failed.")
            return None
        image_url_val = final_media_url
    else:
        image_url_val = image_url or f"https://placeholder.photos/{uuid.uuid4().hex[:8]}"

    photo_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "round": round_id,
        "image_url": image_url_val,
        "media_url": final_media_url,
        "caption": caption,
        "filter_name": filter_name,
        "location_name": location_name,
    }

    try:
        photo_id = await server.post_photo.remote(photo_data)
        
        # YSimulator Stage 4: Extract and save emotion
        try:
            emotion = await llm_service.extract_emotion.remote(caption)
            if emotion:
                await server.add_photo_emotion.remote(photo_id, emotion)
        except Exception as e:
            logger.warning(f"Failed to extract emotion for photo {photo_id}: {e}")

        # Stage 5: Sentiment Annotation
        if agent_attrs and agent_attrs.get("enable_sentiment"):
            try:
                sentiment_score = await llm_service.extract_sentiment.remote(caption)
                await server.update_photo_sentiment.remote(photo_id, sentiment_score)
            except Exception as e:
                logger.warning(f"Failed to extract sentiment for photo {photo_id}: {e}")
            
        logger.debug(f"User {user_id} posted photo {photo_id}")
        return photo_id
    except Exception as exc:
        logger.error(f"Failed to persist photo for user {user_id}: {exc}")
        return None
