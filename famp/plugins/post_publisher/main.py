"""
Post Publisher plugin implementation for FAMP.
"""

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin

logger = logging.getLogger(__name__)


class PostTemplate:
    """Template for Facebook posts."""

    def __init__(self, template: str):
        """Initialize post template.

        Args:
            template: Template string with placeholders
        """
        self.template = template
        self.placeholders = re.findall(r'\{([^}]+)\}', template)

    def render(self, values: Dict[str, str]) -> str:
        """Render template with values.

        Args:
            values: Dictionary of values for placeholders

        Returns:
            Rendered template string
        """
        result = self.template
        for placeholder in self.placeholders:
            if placeholder in values:
                result = result.replace(f"{{{placeholder}}}", values[placeholder])
        return result


class PostPublisherPlugin(Plugin):
    """Plugin for publishing posts to Facebook."""

    name = "post_publisher"
    description = "Publishes posts to Facebook"
    version = "0.1.0"

    def __init__(self):
        """Initialize post publisher plugin."""
        super().__init__()
        self.config = {
            "text": "",  # Post text content
            "image_path": None,  # Path to image file
            "link": None,  # URL to share
            "privacy": "public",  # Post privacy (public, friends, only_me)
            "schedule": None,  # Schedule time (ISO format)
            "template": None,  # Template name or content
            "template_values": {},  # Values for template placeholders
            "repeat": False,  # Whether to repeat the post
            "repeat_interval": 24,  # Hours between repeated posts
            "repeat_count": 1,  # Number of times to repeat
            "validate_content": True,  # Whether to validate content before posting
            "templates_dir": str(Path.home() / ".famp" / "templates"),
        }
        self.templates = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load post templates from templates directory."""
        templates_dir = Path(self.config["templates_dir"])
        if not templates_dir.exists():
            templates_dir.mkdir(parents=True, exist_ok=True)
            # Create sample template
            sample_path = templates_dir / "sample.json"
            with open(sample_path, "w") as f:
                json.dump({
                    "greeting": "Hello {name}! Welcome to {platform}.",
                    "promotion": "Check out our new {product} at {price}! Limited time offer.",
                    "announcement": "We're excited to announce {announcement} starting on {date}."
                }, f, indent=2)

        try:
            # Load templates from JSON files
            for file in templates_dir.glob("*.json"):
                try:
                    with open(file, "r") as f:
                        templates = json.load(f)
                        for name, template in templates.items():
                            self.templates[name] = PostTemplate(template)
                    logger.debug(f"Loaded templates from {file}")
                except Exception as e:
                    logger.error(f"Error loading templates from {file}: {e}")
        except Exception as e:
            logger.error(f"Error loading templates: {e}")

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the post publisher plugin.

        Args:
            tab: nodriver Tab object
            account: Facebook account to use

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Starting post publisher for account {account.account_id}")

        # Navigate to Facebook
        await tab.get("https://www.facebook.com")
        await asyncio.sleep(3)  # Wait for page to load

        # Check if logged in
        if not await self._is_logged_in(tab):
            logger.warning(f"Account {account.account_id} is not logged in")
            return {
                "success": False,
                "status": "not_logged_in",
                "message": "Account is not logged in. Run the login plugin first."
            }

        # Prepare post content
        post_text = await self._prepare_post_text()

        # Validate content if enabled
        if self.config["validate_content"] and not self._validate_content(post_text):
            return {
                "success": False,
                "status": "invalid_content",
                "message": "Post content validation failed."
            }

        # Determine post type and publish
        post_type = await self._determine_post_type()

        try:
            if post_type == "text":
                result = await self._publish_text_post(tab, post_text)
            elif post_type == "image":
                result = await self._publish_image_post(tab, post_text, self.config["image_path"])
            elif post_type == "link":
                result = await self._publish_link_post(tab, post_text, self.config["link"])
            else:
                return {
                    "success": False,
                    "status": "invalid_post_type",
                    "message": f"Invalid post type: {post_type}"
                }

            # Handle scheduling if enabled
            if self.config["schedule"] and result["success"]:
                schedule_result = await self._schedule_post(tab)
                result.update(schedule_result)

            # Handle privacy settings
            if result["success"]:
                privacy_result = await self._set_privacy(tab)
                result.update(privacy_result)

            return result

        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            return {
                "success": False,
                "status": "error",
                "message": f"Error publishing post: {str(e)}"
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

            # Check for create post box
            create_post = await tab.find("What's on your mind", best_match=True, timeout=5)
            if create_post:
                return True

            return False
        except Exception as e:
            logger.debug(f"Error checking login status: {e}")
            return False

    async def _prepare_post_text(self) -> str:
        """Prepare post text content.

        Returns:
            Post text content
        """
        # Use template if specified
        if self.config["template"]:
            template_name = self.config["template"]

            # Check if template is a name or content
            if template_name in self.templates:
                template = self.templates[template_name]
            else:
                # Assume it's a template string
                template = PostTemplate(template_name)

            # Render template with values
            return template.render(self.config["template_values"])

        # Otherwise use direct text
        return self.config["text"]

    def _validate_content(self, content: str) -> bool:
        """Validate post content.

        Args:
            content: Post content to validate

        Returns:
            True if content is valid, False otherwise
        """
        # Check if content is empty
        if not content and not self.config["image_path"]:
            logger.warning("Post content is empty")
            return False

        # Check for potentially problematic content
        problematic_patterns = [
            r'(?i)buy followers',
            r'(?i)buy likes',
            r'(?i)hack (password|account)',
            r'(?i)illegal',
            r'(?i)spam'
        ]

        for pattern in problematic_patterns:
            if re.search(pattern, content):
                logger.warning(f"Post content contains potentially problematic pattern: {pattern}")
                return False

        return True

    async def _determine_post_type(self) -> str:
        """Determine the type of post to publish.

        Returns:
            Post type (text, image, link)
        """
        if self.config["image_path"]:
            return "image"
        elif self.config["link"]:
            return "link"
        else:
            return "text"

    async def _publish_text_post(self, tab: Tab, text: str) -> Dict[str, Any]:
        """Publish a text post.

        Args:
            tab: nodriver Tab object
            text: Post text content

        Returns:
            Dictionary with execution results
        """
        try:
            # Find and click "Create Post" button
            create_post = await tab.find("What's on your mind", best_match=True, timeout=10)
            if not create_post:
                logger.warning("Create post button not found")
                return {"success": False, "status": "create_post_not_found"}

            await create_post.click()
            await asyncio.sleep(2)

            # Find post textarea and enter text
            post_textarea = await tab.select("div[role='textbox'][contenteditable='true']", timeout=10)
            if not post_textarea:
                logger.warning("Post textarea not found")
                return {"success": False, "status": "textarea_not_found"}

            await post_textarea.send_keys(text)
            await asyncio.sleep(1)

            # Find and click Post button
            post_button = await tab.find("Post", best_match=True, timeout=5)
            if not post_button:
                logger.warning("Post button not found")
                return {"success": False, "status": "post_button_not_found"}

            await post_button.click()
            await asyncio.sleep(5)  # Wait for post to be published

            return {
                "success": True,
                "status": "posted",
                "post_type": "text",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error publishing text post: {e}")
            return {"success": False, "status": "error", "message": str(e)}

    async def _publish_image_post(self, tab: Tab, text: str, image_path: str) -> Dict[str, Any]:
        """Publish an image post.

        Args:
            tab: nodriver Tab object
            text: Post text content
            image_path: Path to image file

        Returns:
            Dictionary with execution results
        """
        try:
            # Check if image exists
            if not os.path.exists(image_path):
                logger.warning(f"Image file not found: {image_path}")
                return {"success": False, "status": "image_not_found"}

            # Find and click "Create Post" button
            create_post = await tab.find("What's on your mind", best_match=True, timeout=10)
            if not create_post:
                logger.warning("Create post button not found")
                return {"success": False, "status": "create_post_not_found"}

            await create_post.click()
            await asyncio.sleep(2)

            # Find post textarea and enter text
            post_textarea = await tab.select("div[role='textbox'][contenteditable='true']", timeout=10)
            if not post_textarea:
                logger.warning("Post textarea not found")
                return {"success": False, "status": "textarea_not_found"}

            await post_textarea.send_keys(text)
            await asyncio.sleep(1)

            # Find and click "Add Photos/Videos" button
            photo_button = await tab.find("Photo/Video", best_match=True, timeout=5)
            if not photo_button:
                logger.warning("Photo button not found")
                return {"success": False, "status": "photo_button_not_found"}

            await photo_button.click()
            await asyncio.sleep(2)

            # Upload image file
            file_input = await tab.select("input[type='file']", timeout=5)
            if not file_input:
                logger.warning("File input not found")
                return {"success": False, "status": "file_input_not_found"}

            await file_input.upload_file(image_path)
            await asyncio.sleep(5)  # Wait for upload

            # Find and click Post button
            post_button = await tab.find("Post", best_match=True, timeout=5)
            if not post_button:
                logger.warning("Post button not found")
                return {"success": False, "status": "post_button_not_found"}

            await post_button.click()
            await asyncio.sleep(5)  # Wait for post to be published

            return {
                "success": True,
                "status": "posted",
                "post_type": "image",
                "image_path": image_path,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error publishing image post: {e}")
            return {"success": False, "status": "error", "message": str(e)}

    async def _publish_link_post(self, tab: Tab, text: str, link: str) -> Dict[str, Any]:
        """Publish a link post.

        Args:
            tab: nodriver Tab object
            text: Post text content
            link: URL to share

        Returns:
            Dictionary with execution results
        """
        try:
            # Find and click "Create Post" button
            create_post = await tab.find("What's on your mind", best_match=True, timeout=10)
            if not create_post:
                logger.warning("Create post button not found")
                return {"success": False, "status": "create_post_not_found"}

            await create_post.click()
            await asyncio.sleep(2)

            # Find post textarea and enter text with link
            post_textarea = await tab.select("div[role='textbox'][contenteditable='true']", timeout=10)
            if not post_textarea:
                logger.warning("Post textarea not found")
                return {"success": False, "status": "textarea_not_found"}

            # Add text and link
            full_text = f"{text}\n\n{link}"
            await post_textarea.send_keys(full_text)
            await asyncio.sleep(5)  # Wait for link preview to load

            # Find and click Post button
            post_button = await tab.find("Post", best_match=True, timeout=5)
            if not post_button:
                logger.warning("Post button not found")
                return {"success": False, "status": "post_button_not_found"}

            await post_button.click()
            await asyncio.sleep(5)  # Wait for post to be published

            return {
                "success": True,
                "status": "posted",
                "post_type": "link",
                "link": link,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error publishing link post: {e}")
            return {"success": False, "status": "error", "message": str(e)}

    async def _schedule_post(self, tab: Tab) -> Dict[str, Any]:
        """Schedule a post.

        Args:
            tab: nodriver Tab object

        Returns:
            Dictionary with scheduling results
        """
        try:
            # Check if schedule time is valid
            schedule_time = None
            if isinstance(self.config["schedule"], str):
                try:
                    schedule_time = datetime.fromisoformat(self.config["schedule"])
                except ValueError:
                    logger.warning(f"Invalid schedule time format: {self.config['schedule']}")
                    return {"schedule_success": False, "schedule_status": "invalid_time_format"}

            # Ensure schedule time is in the future
            if schedule_time and schedule_time <= datetime.now():
                logger.warning("Schedule time must be in the future")
                return {"schedule_success": False, "schedule_status": "time_in_past"}

            # Find and click schedule button
            schedule_button = await tab.find("Schedule", best_match=True, timeout=5)
            if not schedule_button:
                logger.warning("Schedule button not found")
                return {"schedule_success": False, "schedule_status": "button_not_found"}

            await schedule_button.click()
            await asyncio.sleep(2)

            # Set date and time
            # Note: This is a simplified implementation and may need adjustment
            # based on Facebook's current UI for scheduling posts
            date_input = await tab.select("input[placeholder='mm/dd/yyyy']", timeout=5)
            if date_input:
                date_str = schedule_time.strftime("%m/%d/%Y")
                await date_input.clear_input()
                await date_input.send_keys(date_str)

            time_input = await tab.select("input[placeholder='h:mm am']", timeout=5)
            if time_input:
                time_str = schedule_time.strftime("%I:%M %p")
                await time_input.clear_input()
                await time_input.send_keys(time_str)

            # Confirm scheduling
            confirm_button = await tab.find("Schedule", best_match=True, timeout=5)
            if confirm_button:
                await confirm_button.click()
                await asyncio.sleep(2)

                return {
                    "schedule_success": True,
                    "schedule_status": "scheduled",
                    "schedule_time": schedule_time.isoformat()
                }
            else:
                return {"schedule_success": False, "schedule_status": "confirm_button_not_found"}

        except Exception as e:
            logger.error(f"Error scheduling post: {e}")
            return {"schedule_success": False, "schedule_status": "error", "schedule_message": str(e)}

    async def _set_privacy(self, tab: Tab) -> Dict[str, Any]:
        """Set post privacy.

        Args:
            tab: nodriver Tab object

        Returns:
            Dictionary with privacy setting results
        """
        try:
            privacy = self.config["privacy"].lower()

            # Map privacy setting to Facebook UI text
            privacy_map = {
                "public": "Public",
                "friends": "Friends",
                "only_me": "Only me"
            }

            if privacy not in privacy_map:
                logger.warning(f"Invalid privacy setting: {privacy}")
                return {"privacy_success": False, "privacy_status": "invalid_setting"}

            # Find and click privacy selector
            privacy_selector = await tab.find("Public", best_match=True, timeout=5)
            if not privacy_selector:
                privacy_selector = await tab.find("Friends", best_match=True, timeout=5)
            if not privacy_selector:
                privacy_selector = await tab.find("Only me", best_match=True, timeout=5)

            if not privacy_selector:
                logger.warning("Privacy selector not found")
                return {"privacy_success": False, "privacy_status": "selector_not_found"}

            await privacy_selector.click()
            await asyncio.sleep(2)

            # Select desired privacy option
            privacy_option = await tab.find(privacy_map[privacy], best_match=True, timeout=5)
            if not privacy_option:
                logger.warning(f"Privacy option '{privacy_map[privacy]}' not found")
                return {"privacy_success": False, "privacy_status": "option_not_found"}

            await privacy_option.click()
            await asyncio.sleep(1)

            return {
                "privacy_success": True,
                "privacy_status": "set",
                "privacy": privacy
            }

        except Exception as e:
            logger.error(f"Error setting privacy: {e}")
            return {"privacy_success": False, "privacy_status": "error", "privacy_message": str(e)}
