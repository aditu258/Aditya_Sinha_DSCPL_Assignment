import requests
from typing import Dict, List, Any, Optional

class SocialVerseFetcher:
    """Fetches spiritual content from SocialVerse API."""
    
    API_URL = "https://api.socialverseapp.com/posts/summary/get"
    HEADERS = {
        "Flic-Token": "flic_b1c6b09d98e2d4884f61b9b3131dbb27a6af84788e4a25db067a22008ea9cce5"
    }
    
    def __init__(self):
        self.cached_posts = []
    
    def fetch_posts(self, page: int = 1, page_size: int = 100) -> List[Dict[str, Any]]:
        """Fetch posts from SocialVerse API."""
        params = {
            "page": page,
            "page_size": page_size
        }
        
        try:
            response = requests.get(
                self.API_URL,
                headers=self.HEADERS,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            # Cache the posts for future use
            if data.get("status") == "success" and "posts" in data:
                self.cached_posts = data["posts"]
                return self.cached_posts
            return []
            
        except requests.RequestException as e:
            print(f"Error fetching from SocialVerse API: {e}")
            # Return cached posts if available, otherwise empty list
            return self.cached_posts if self.cached_posts else []
    
    def get_posts_by_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Filter posts by topic."""
        # Fetch posts if cache is empty
        if not self.cached_posts:
            self.fetch_posts()
        
        # Filter by topic (simulated as we don't know the exact API response structure)
        # In a real implementation, we would filter based on actual response fields
        topic_lower = topic.lower()
        return [
            post for post in self.cached_posts 
            if topic_lower in post.get("title", "").lower() 
            or topic_lower in post.get("post_summary", {}).get("description", "").lower()
            or any(topic_lower in keyword.get("keyword", "").lower() 
                  for keyword in post.get("post_summary", {}).get("keywords", []))
        ]
    
    def get_video_content(self, category: str, topic: str) -> List[Dict[str, str]]:
        """Get video content based on category and topic."""
        # Fetch posts if cache is empty
        if not self.cached_posts:
            self.fetch_posts()
        
        # First try filtering by topic
        relevant_posts = self.get_posts_by_topic(topic)
        
        # If no relevant posts found, try filtering by category
        if not relevant_posts:
            relevant_posts = self.get_posts_by_topic(category)
        
        # Extract video content from posts
        videos = []
        for post in relevant_posts:
            # Check if post has video content
            if post.get("video_link"):
                # Get duration from post summary if available
                duration = post.get("post_summary", {}).get("estimated_duration", "Unknown")
                if duration == "N/A":
                    duration = "Unknown"
                
                videos.append({
                    "title": post.get("title", "Untitled Video"),
                    "duration": duration,
                    "author": f"{post.get('first_name', '')} {post.get('last_name', '')}".strip() or "Unknown",
                    "url": post.get("video_link"),
                    "thumbnail": post.get("thumbnail_url", ""),
                    "description": post.get("post_summary", {}).get("description", ""),
                    "keywords": [k.get("keyword") for k in post.get("post_summary", {}).get("keywords", [])],
                    "category": post.get("category", {}).get("name", "Unknown")
                })
        
        return videos
    
    def get_inspirational_content(self, category: str) -> Dict[str, Any]:
        """Get inspirational content based on category."""
        # Ensure we have posts
        if not self.cached_posts:
            self.fetch_posts()
            
        # If API failed or returned no posts, use mock data
        if not self.cached_posts:
            return self._get_mock_content(category)
            
        # Try to find a relevant post
        for post in self.cached_posts:
            if category.lower() in post.get("category", {}).get("name", "").lower():
                return {
                    "title": post.get("title", "Inspirational Message"),
                    "content": post.get("post_summary", {}).get("description", "Stay faithful and strong."),
                    "author": f"{post.get('first_name', '')} {post.get('last_name', '')}".strip() or "Unknown",
                    "source": "SocialVerse API"
                }
                
        # If no relevant post found, use mock data
        return self._get_mock_content(category)
    
    def _get_mock_content(self, category: str) -> Dict[str, Any]:
        """Provide mock content if API fails or no relevant content found."""
        mock_data = {
            "devotion": {
                "title": "Daily Devotional",
                "content": "Trust in the LORD with all your heart and lean not on your own understanding; in all your ways submit to him, and he will make your paths straight. - Proverbs 3:5-6",
                "author": "Solomon",
                "source": "Bible"
            },
            "prayer": {
                "title": "Prayer Guidance",
                "content": "Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God. - Philippians 4:6",
                "author": "Paul",
                "source": "Bible"
            },
            "meditation": {
                "title": "Meditation Focus",
                "content": "Be still, and know that I am God. - Psalm 46:10",
                "author": "David",
                "source": "Bible"
            },
            "accountability": {
                "title": "Accountability Reminder",
                "content": "Therefore confess your sins to each other and pray for each other so that you may be healed. - James 5:16",
                "author": "James",
                "source": "Bible"
            },
            "chat": {
                "title": "Spiritual Guidance",
                "content": "I can do all this through him who gives me strength. - Philippians 4:13",
                "author": "Paul",
                "source": "Bible"
            }
        }
        
        return mock_data.get(category.lower(), mock_data["devotion"])


# For testing
if __name__ == "__main__":
    fetcher = SocialVerseFetcher()
    posts = fetcher.fetch_posts()
    print(f"Fetched {len(posts)} posts")
    
    devotion = fetcher.get_inspirational_content("devotion")
    print(f"Devotion: {devotion['title']} - {devotion['content']}")
    
    videos = fetcher.get_video_content("devotion", "faith")
    print(f"Found {len(videos)} videos")
    for video in videos:
        print(f"\nTitle: {video['title']}")
        print(f"Duration: {video['duration']}")
        print(f"Author: {video['author']}")
        print(f"URL: {video['url']}")
        print(f"Category: {video['category']}") 