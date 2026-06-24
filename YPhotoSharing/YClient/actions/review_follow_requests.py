import logging
import random

logger = logging.getLogger(__name__)

async def review_follow_requests(
    server,
    llm_service,
    user_id: str,
    round_id: str,
    cluster_id: int = 0
) -> bool:
    """
    Checks pending follow requests and uses the LLM to accept or reject them based on profile.
    """
    try:
        pending = await server.get_pending_follow_requests.remote(user_id)
        if not pending:
            return True
            
        import ray
        for req in pending:
            # Get requester's profile
            requester = ray.get(server.get_user.remote(req["follower_id"]))
            if not requester:
                action = "rejected"
            else:
                action = await llm_service.decide_follow_request.remote(
                    username=requester.get("username", "Unknown"),
                    bio=requester.get("bio", ""),
                    cluster_id=cluster_id
                )
                action = action.lower()
                if action not in ["accepted", "rejected"]:
                    action = "accepted"  # default fallback
                    
            await server.review_follow_request.remote(req["follower_id"], user_id, action, round_id)
            logger.debug(f"User {user_id} {action} follow request from {req['follower_id']}")
            
            # Stage 7: Followback
            if action == "accepted":
                user_data = ray.get(server.get_user.remote(user_id))
                prob_fb = user_data.get("probability_of_follow_back", 0.0) if user_data else 0.0
                if prob_fb > 0:
                    if random.random() < prob_fb:
                        await server.follow_user.remote(user_id, req["follower_id"], round_id)
                        logger.debug(f"User {user_id} followed back {req['follower_id']}")
            
        return True
    except Exception as exc:
        logger.error(f"Failed to review follow requests for user {user_id}: {exc}")
        return False
