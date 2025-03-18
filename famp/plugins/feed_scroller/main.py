"""
Feed Scroller plugin implementation for FAMP.
"""

import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin

logger = logging.getLogger(__name__)


class FeedScrollerPlugin(Plugin):
    """Plugin for scrolling through Facebook feed and collecting data."""

    name = "feed_scroller"
    description = "Scrolls through Facebook feed and collects post data"
    version = "0.1.0"

    def __init__(self):
        """Initialize feed scroller plugin."""
        super().__init__()
        self.config = {
            "scroll_count": 5,  # Number of times to scroll
            "scroll_delay": 2,  # Delay between scrolls in seconds
            "data_collection": True,  # Whether to collect post data
            "export_format": "json",  # Export format (json, csv)
            "export_dir": str(Path.home() / ".famp" / "data" / "feed"),
            "max_posts": 50,  # Maximum number of posts to collect
            "include_images": True,  # Whether to extract image URLs
            "include_reactions": True,  # Whether to extract reaction counts
            "include_comments": False,  # Whether to extract comment previews
            "feed_url": "https://www.facebook.com/",
        }
        self.posts = []

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the feed scroller plugin.

        Args:
            tab: nodriver Tab object
            account: Facebook account to use

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Starting feed scroller for account {account.account_id}")

        # Navigate to feed
        await tab.get(self.config["feed_url"])
        await asyncio.sleep(3)  # Wait for feed to load

        # Check if logged in
        if not await self._is_logged_in(tab):
            logger.warning(f"Account {account.account_id} is not logged in")
            return {
                "success": False,
                "status": "not_logged_in",
                "message": "Account is not logged in. Run the login plugin first."
            }

        # Scroll through feed
        scroll_count = self.config["scroll_count"]
        posts_collected = 0
        self.posts = []

        for i in range(scroll_count):
            logger.info(f"Scroll {i+1}/{scroll_count}")

            # Collect post data if enabled
            if self.config["data_collection"]:
                new_posts = await self._extract_posts(tab)
                posts_collected += len(new_posts)
                self.posts.extend(new_posts)

                logger.info(f"Collected {len(new_posts)} posts in this scroll")

                # Check if we've reached the maximum
                if posts_collected >= self.config["max_posts"]:
                    logger.info(f"Reached maximum post count ({self.config['max_posts']})")
                    break

            # Scroll down
            await self._scroll_down(tab)

            # Wait between scrolls
            await asyncio.sleep(self.config["scroll_delay"])

        # Export collected data
        export_path = None
        if self.config["data_collection"] and self.posts:
            export_path = await self._export_data(account.account_id)

        return {
            "success": True,
            "status": "completed",
            "posts_collected": len(self.posts),
            "scrolls_performed": i + 1,
            "export_path": export_path
        }

    async def _is_logged_in(self, tab: Tab) -> bool:
        """Check if user is logged in.

        Args:
            tab: nodriver Tab object

        Returns:
            True if logged in, False otherwise
        """
        try:
            # Look for elements that indicate user is logged in
            profile_link = await tab.find("your profile", best_match=True, timeout=5)
            if profile_link:
                return True

            # Check for feed elements
            feed = await tab.select("[aria-label='News Feed']", timeout=5)
            if feed:
                return True

            # Check for create post box
            create_post = await tab.find("What's on your mind", best_match=True, timeout=5)
            if create_post:
                return True

            return False
        except Exception as e:
            logger.debug(f"Error checking login status: {e}")
            return False

    async def _scroll_down(self, tab: Tab) -> None:
        """Scroll down the page.

        Args:
            tab: nodriver Tab object
        """
        await tab.evaluate("window.scrollBy(0, window.innerHeight)")

    async def _extract_posts(self, tab: Tab) -> List[Dict[str, Any]]:
        """Extract post data from the current view.

        Args:
            tab: nodriver Tab object

        Returns:
            List of post data dictionaries
        """
        posts = []

        try:
            # Find post containers
            # This selector might need adjustment based on Facebook's current DOM structure
            post_elements = await tab.select_all("div[role='article']")

            for post_element in post_elements:
                post_data = {
                    "timestamp": datetime.now().isoformat(),
                    "text": "",
                    "author": "",
                    "images": [],
                    "reactions": {},
                    "comments": []
                }

                # Extract post text
                try:
                    text_element = await post_element.select("div[data-ad-preview='message']")
                    if text_element:
                        post_data["text"] = await text_element.text()
                except Exception as e:
                    logger.debug(f"Error extracting post text: {e}")

                # Extract author
                try:
                    author_element = await post_element.select("h4 span")
                    if author_element:
                        post_data["author"] = await author_element.text()
                except Exception as e:
                    logger.debug(f"Error extracting post author: {e}")

                # Extract images if enabled
                if self.config["include_images"]:
                    try:
                        image_elements = await post_element.select_all("img")
                        for img in image_elements:
                            src = await img.get_attribute("src")
                            if src and "scontent" in src:  # Filter for content images
                                post_data["images"].append(src)
                    except Exception as e:
                        logger.debug(f"Error extracting post images: {e}")

                # Extract reactions if enabled
                if self.config["include_reactions"]:
                    try:
                        reaction_element = await post_element.find("Like", best_match=True)
                        if reaction_element:
                            reaction_text = await reaction_element.text()
                            if reaction_text and any(c.isdigit() for c in reaction_text):
                                post_data["reactions"]["likes"] = reaction_text
                    except Exception as e:
                        logger.debug(f"Error extracting post reactions: {e}")

                # Extract comments if enabled
                if self.config["include_comments"]:
                    try:
                        comment_elements = await post_element.select_all("ul > li")
                        for comment_element in comment_elements:
                            comment_text = await comment_element.text()
                            if comment_text:
                                post_data["comments"].append(comment_text)
                    except Exception as e:
                        logger.debug(f"Error extracting post comments: {e}")

                # Add post if it has content and isn't a duplicate
                if post_data["text"] or post_data["images"]:
                    # Check if this post is already in our list (avoid duplicates)
                    is_duplicate = False
                    for existing_post in posts:
                        if existing_post["text"] == post_data["text"] and existing_post["author"] == post_data["author"]:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        posts.append(post_data)

            logger.info(f"Extracted {len(posts)} posts")
            return posts

        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            return []

    async def _export_data(self, account_id: str) -> Optional[str]:
        """Export collected post data.

        Args:
            account_id: Account ID for filename

        Returns:
            Path to exported file or None if export failed
        """
        if not self.posts:
            logger.warning("No posts to export")
            return None

        try:
            # Create export directory
            export_dir = Path(self.config["export_dir"])
            export_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"feed_{account_id}_{timestamp}"

            # Export based on format
            if self.config["export_format"].lower() == "json":
                export_path = export_dir / f"{filename}.json"
                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(self.posts, f, indent=2, ensure_ascii=False)

            elif self.config["export_format"].lower() == "csv":
                export_path = export_dir / f"{filename}.csv"
                with open(export_path, "w", encoding="utf-8", newline="") as f:
                    # Flatten the post data for CSV
                    fieldnames = ["timestamp", "author", "text", "image_count", "reaction_count"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for post in self.posts:
                        writer.writerow({
                            "timestamp": post["timestamp"],
                            "author": post["author"],
                            "text": post["text"],
                            "image_count": len(post["images"]),
                            "reaction_count": sum(int(v.split()[0]) if v and v[0].isdigit() else 0
                                               for v in post["reactions"].values())
                        })
            else:
                logger.warning(f"Unsupported export format: {self.config['export_format']}")
                return None

            logger.info(f"Exported {len(self.posts)} posts to {export_path}")
            return str(export_path)

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return None
