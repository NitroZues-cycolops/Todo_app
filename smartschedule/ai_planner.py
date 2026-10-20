"""
Groq AI integration for SmartSchedule AI Planner.
Handles API calls to Groq for task/event extraction and planning.
"""

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from groq import Groq


class GroqAIError(Exception):
    """Raised when Groq API call fails."""
    pass


class AIPlanner:
    """Wrapper for Groq AI planning functionality."""

    def __init__(self):
        """Initialize Groq client from environment."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise GroqAIError(
                "GROQ_API_KEY not set in environment. "
                "Get one at https://console.groq.com"
            )
        self.client = Groq(api_key=api_key)
        # Use models available via Groq API
        # qwen/qwen3.8-27b - Alibaba Qwen 3.8B (good for JSON, fast)
        self.model = "qwen/qwen3.8-27b"
        # Fallback models if primary not available
        self.model_fallbacks = [
            "openai/gpt-oss-20b",
            "meta-llama/llama-prompt-guard-2-86m"
        ]
        # Note: Vision not available with these models, handle gracefully
        self.vision_model = None

    def plan_from_text(
        self,
        user_input: str,
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        existing_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract tasks and events from natural language input.

        Args:
            user_input: User's natural language description of plans
            existing_tasks: List of existing tasks for conflict detection
            existing_events: List of existing events for conflict detection

        Returns:
            Dict with keys: tasks, events, conflicts, raw_text, metadata
        """
        prompt = self._build_planning_prompt(
            user_input, existing_tasks, existing_events
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Validate and normalize response
            return self._normalize_result(result, user_input)

        except json.JSONDecodeError as e:
            raise GroqAIError(f"Groq returned invalid JSON: {e}")
        except Exception as e:
            raise GroqAIError(f"Groq API error: {e}")

    def plan_from_file(
        self,
        file_content: str,
        file_type: str,
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        existing_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract tasks and events from uploaded file content.

        Args:
            file_content: Extracted file content or base64-encoded image
            file_type: One of "text", "pdf", "image"
            existing_tasks: List of existing tasks for conflict detection
            existing_events: List of existing events for conflict detection

        Returns:
            Dict with keys: tasks, events, conflicts, raw_text, metadata
        """
        if file_type == "image":
            return self._plan_from_image(
                file_content, existing_tasks, existing_events
            )
        else:
            # For PDF and text, treat as text content
            return self.plan_from_text(
                file_content, existing_tasks, existing_events
            )

    def _plan_from_image(
        self,
        image_base64: str,
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        existing_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Extract tasks/events from an image using vision model.

        Note: Current Groq models don't support vision. Return helpful message.
        """
        raise GroqAIError(
            "Image timetables aren't supported yet. Upload PDF/CSV/XLSX/text."
        )

    def _build_planning_prompt(
        self,
        user_input: str,
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        existing_events: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build the prompt for Groq AI."""
        schema = self._get_json_schema()

        prompt = f"""You are a smart scheduling assistant. Extract tasks and events from the user's plan.

User's plan:
{user_input}

Current date: {date.today().isoformat()}

Extract the following information from the plan and return ONLY a JSON object (no markdown, no explanation):

{json.dumps(schema, indent=2)}

Guidelines:
- Extract all mentioned tasks and events
- For dates: Use ISO format (YYYY-MM-DD). If relative (e.g., "Monday"), calculate from today.
- For times: Use 24-hour format (HH:MM). Assume morning (08:00) if not specified.
- For priority: Use "high", "medium", or "low"
- For duration: In minutes. Assume 60 for events if not specified.
- Conflict detection: Check if items overlap with existing schedule
- Return empty arrays if nothing can be extracted"""

        if existing_tasks or existing_events:
            prompt += self._build_conflict_context(
                existing_tasks, existing_events
            )

        return prompt

    def _build_conflict_context(
        self,
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        existing_events: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build context about existing calendar for conflict detection."""
        context = "\n\nExisting schedule:"

        if existing_tasks:
            context += "\nTasks:\n"
            for task in existing_tasks[:5]:  # Limit to 5 for brevity
                context += f"- {task.get('title', 'Untitled')} (due: {task.get('due_date', 'no date')})\n"

        if existing_events:
            context += "\nEvents:\n"
            for event in existing_events[:5]:  # Limit to 5 for brevity
                start = event.get("start_date", "")
                start_time = event.get("start_time", "")
                title = event.get("title", "Untitled")
                context += f"- {title} ({start} {start_time})\n"

        context += "\nFlag any conflicts with these existing items in the 'conflicts' array."

        return context

    def _get_json_schema(self) -> Dict[str, Any]:
        """Get the expected JSON schema for AI responses."""
        return {
            "tasks": [
                {
                    "title": "Task name",
                    "due_date": "YYYY-MM-DD (optional)",
                    "due_time": "HH:MM in 24-hour format (optional)",
                    "priority": "high|medium|low (default: medium)",
                    "description": "Details (optional)",
                    "conflict": False,
                }
            ],
            "events": [
                {
                    "title": "Event name",
                    "start_date": "YYYY-MM-DD",
                    "start_time": "HH:MM in 24-hour format (optional, default: 09:00)",
                    "duration_minutes": "Duration in minutes (optional, default: 60)",
                    "location": "Location (optional)",
                    "description": "Details (optional)",
                    "conflict": False,
                }
            ],
            "conflicts": [
                {
                    "type": "task|event",
                    "ai_item": "Item name from extraction",
                    "existing_item": "Conflicting existing item",
                    "overlap": "Time/date of overlap",
                }
            ],
        }

    def _normalize_result(
        self, result: Dict[str, Any], user_input: str
    ) -> Dict[str, Any]:
        """Normalize and validate Groq response."""
        normalized = {
            "tasks": [],
            "events": [],
            "conflicts": [],
            "raw_text": user_input,
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "total_items": 0,
            },
        }

        # Process tasks
        if "tasks" in result and isinstance(result["tasks"], list):
            for task in result["tasks"]:
                if isinstance(task, dict) and "title" in task:
                    desc = task.get("description", "")
                    if desc and str(desc).lower() == "none":
                        desc = ""
                    normalized["tasks"].append(
                        {
                            "title": str(task.get("title", ""))[:100],
                            "due_date": self._validate_date(
                                task.get("due_date")
                            ),
                            "due_time": self._validate_time(
                                task.get("due_time")
                            ),
                            "priority": self._validate_priority(
                                task.get("priority", "medium")
                            ),
                            "description": str(desc)[:500],
                            "conflict": bool(task.get("conflict", False)),
                        }
                    )

        # Process events
        if "events" in result and isinstance(result["events"], list):
            for event in result["events"]:
                if isinstance(event, dict) and "title" in event:
                    desc = event.get("description", "")
                    if desc and str(desc).lower() == "none":
                        desc = ""
                    loc = event.get("location", "")
                    if loc and str(loc).lower() == "none":
                        loc = ""
                    normalized["events"].append(
                        {
                            "title": str(event.get("title", ""))[:100],
                            "start_date": self._validate_date(
                                event.get("start_date")
                            ),
                            "start_time": self._validate_time(
                                event.get("start_time", "09:00")
                            ),
                            "duration_minutes": self._validate_duration(
                                event.get("duration_minutes", 60)
                            ),
                            "location": str(loc)[:200],
                            "description": str(desc)[:500],
                            "conflict": bool(event.get("conflict", False)),
                        }
                    )

        # Process conflicts
        if "conflicts" in result and isinstance(result["conflicts"], list):
            normalized["conflicts"] = result["conflicts"][:10]  # Limit to 10

        normalized["metadata"]["total_items"] = (
            len(normalized["tasks"]) + len(normalized["events"])
        )

        return normalized

    @staticmethod
    def _validate_date(value: Any) -> Optional[str]:
        """Validate and format date string."""
        if not value:
            return None
        try:
            # Try to parse and reformat
            if isinstance(value, str):
                parsed = datetime.fromisoformat(value.split("T")[0])
                return parsed.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass
        return None

    @staticmethod
    def _validate_time(value: Any) -> Optional[str]:
        """Validate and format time string."""
        if not value:
            return None
        try:
            if isinstance(value, str):
                # Parse HH:MM format
                parts = value.split(":")
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        return f"{hour:02d}:{minute:02d}"
        except (ValueError, AttributeError):
            pass
        return None

    @staticmethod
    def _validate_priority(value: Any) -> str:
        """Validate and normalize priority."""
        if isinstance(value, str):
            lower = value.lower()
            if lower in ("high", "medium", "low"):
                return lower
        return "medium"

    @staticmethod
    def _validate_duration(value: Any) -> int:
        """Validate and normalize duration in minutes."""
        try:
            duration = int(value)
            if 1 <= duration <= 1440:  # 1 min to 24 hours
                return duration
        except (ValueError, TypeError):
            pass
        return 60


def get_ai_planner() -> AIPlanner:
    """Factory function to create and cache AIPlanner instance."""
    return AIPlanner()
