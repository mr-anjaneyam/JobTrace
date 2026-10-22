"""JobTrace - Stateful career intelligence, LLM scoring, and Telegram notifications."""
import os

__app_name__ = "JobTrace"
# Release images get the real values from the tag through build arguments
__version__ = os.environ.get("JOBTRACE_VERSION") or "dev"
__commit__ = os.environ.get("JOBTRACE_COMMIT") or ""
