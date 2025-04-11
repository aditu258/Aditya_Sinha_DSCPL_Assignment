from typing import Dict, List, Any
import random
from social_verse_fetcher import SocialVerseFetcher

class VideoContentAgent:
    """Agent that provides video content recommendations based on spiritual topics."""
    
    SYSTEM_PROMPT = """
    You are DSCPL's Video Content Specialist.
    Your role is to help users find video content related to their spiritual journey.
    When recommending videos:
    1. Ensure they are relevant to the user's topic and category
    2. Provide a brief description of each video
    3. Explain why the video would be helpful
    4. Offer 3-5 recommendations at a time
    
    Be helpful, supportive, and considerate of the user's spiritual journey.
    """
    
    def __init__(self):
        self.last_agent = None
        self.fetcher = SocialVerseFetcher()
    
    def get_recommendations(self, category: str, topic: str) -> List[Dict[str, str]]:
        """Get video recommendations based on category and topic."""
        # Get videos from SocialVerse API
        videos = self.fetcher.get_video_content(category, topic)
        
        # If no videos found, return empty list
        if not videos:
            return []
        
        # Randomly select 3-5 videos to recommend
        num_recommendations = min(random.randint(3, 5), len(videos))
        recommended_videos = random.sample(videos, num_recommendations)
        
        return recommended_videos
    
    def format_recommendations(self, videos: List[Dict[str, str]], topic: str, category: str) -> str:
        """Format video recommendations into a readable string."""
        if not videos:
            return (
                f"I couldn't find any videos related to {topic or category} in our content library. "
                f"Would you like to try a different topic or return to your daily content?"
            )
        
        video_list = "\n\n".join([
            f"🎬 **{video['title']}** ({video['duration']})\n"
            f"👤 {video['author']}\n"
            f"📝 {video['description'][:100]}...\n"
            f"🔗 {video['url']}"
            for video in videos
        ])
        
        return (
            f"Here are some video recommendations related to {topic or category}:\n\n"
            f"{video_list}\n\n"
            f"Would you like more recommendations, or would you like to return to your daily content?"
        ) 