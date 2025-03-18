"""Workflow system for FAMP plugins."""

import asyncio
import datetime
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from nodriver import Tab
from pydantic import BaseModel

from famp.core.account import FacebookAccount
from famp.plugin import Plugin, PluginError, PluginManager

logger = logging.getLogger(__name__)

class WorkflowStepStatus(str, Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class WorkflowStatus(str, Enum):
    """Status of a workflow."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class StepCondition(BaseModel):
    """Condition for workflow step execution."""
    plugin_name: str
    field: str
    operator: str
    value: Any

    def evaluate(self, results: Dict[str, Any]) -> bool:
        """Evaluate the condition.

        Args:
            results: Dictionary of previous step results

        Returns:
            True if condition is met, False otherwise
        """
        if self.plugin_name not in results:
            return False

        plugin_results = results[self.plugin_name]
        if self.field not in plugin_results:
            return False

        actual_value = plugin_results[self.field]

        if self.operator == "eq":
            return actual_value == self.value
        elif self.operator == "ne":
            return actual_value != self.value
        elif self.operator == "gt":
            return actual_value > self.value
        elif self.operator == "lt":
            return actual_value < self.value
        elif self.operator == "contains":
            return self.value in actual_value
        elif self.operator == "exists":
            return True
        else:
            logger.warning(f"Unknown operator: {self.operator}")
            return False

class WorkflowStep(BaseModel):
    """A step in a workflow."""
    plugin_name: str
    config: Optional[Dict[str, Any]] = None
    condition: Optional[StepCondition] = None
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None

    def should_run(self, previous_results: Dict[str, Any]) -> bool:
        """Check if step should run based on condition.

        Args:
            previous_results: Results from previous steps

        Returns:
            True if step should run, False otherwise
        """
        if not self.condition:
            return True
        return self.condition.evaluate(previous_results)

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary.

        Returns:
            Dictionary representation of step
        """
        return {
            "plugin_name": self.plugin_name,
            "config": self.config,
            "condition": self.condition.model_dump() if self.condition else None,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        """Create step from dictionary.

        Args:
            data: Dictionary representation of step

        Returns:
            WorkflowStep instance
        """
        if data.get("condition"):
            data["condition"] = StepCondition(**data["condition"])
        if data.get("start_time"):
            data["start_time"] = datetime.datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            data["end_time"] = datetime.datetime.fromisoformat(data["end_time"])
        return cls(**data)

class Workflow(BaseModel):
    """A workflow of plugin steps."""
    name: str
    description: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    results: Dict[str, Dict[str, Any]] = {}
    created_at: datetime.datetime = datetime.datetime.now()
    updated_at: datetime.datetime = datetime.datetime.now()
    data_dir: Optional[Path] = None

    def add_step(
        self,
        plugin_name: str,
        config: Optional[Dict[str, Any]] = None,
        condition: Optional[StepCondition] = None
    ) -> None:
        """Add a step to the workflow.

        Args:
            plugin_name: Name of plugin to run
            config: Optional plugin configuration
            condition: Optional condition for running step
        """
        step = WorkflowStep(
            plugin_name=plugin_name,
            config=config,
            condition=condition
        )
        self.steps.append(step)
        self.updated_at = datetime.datetime.now()

    async def run(
        self,
        plugin_manager: PluginManager,
        tab: Tab,
        account: FacebookAccount,
        resume_from: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run the workflow.

        Args:
            plugin_manager: Plugin manager instance
            tab: Browser tab
            account: Facebook account to use
            resume_from: Optional step index to resume from

        Returns:
            Dictionary with workflow results
        """
        if resume_from is not None:
            self.current_step = resume_from

        self.status = WorkflowStatus.RUNNING

        try:
            while self.current_step < len(self.steps):
                step = self.steps[self.current_step]

                # Check if step should run
                if not step.should_run(self.results):
                    step.status = WorkflowStepStatus.SKIPPED
                    self.current_step += 1
                    continue

                # Run step
                step.status = WorkflowStepStatus.RUNNING
                step.start_time = datetime.datetime.now()

                try:
                    result = await plugin_manager.run_plugin(
                        step.plugin_name,
                        tab,
                        account,
                        config=step.config
                    )
                    step.result = result
                    step.status = WorkflowStepStatus.COMPLETED
                    self.results[step.plugin_name] = result
                except PluginError as e:
                    step.error = e.to_dict()
                    step.status = WorkflowStepStatus.FAILED
                    self.status = WorkflowStatus.FAILED
                    raise
                finally:
                    step.end_time = datetime.datetime.now()
                    await self.save_state()

                self.current_step += 1

            self.status = WorkflowStatus.COMPLETED
            await self.save_state()

            return self.results

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            await self.save_state()
            raise

    async def save_state(self) -> None:
        """Save workflow state to disk."""
        if not self.data_dir:
            return

        self.updated_at = datetime.datetime.now()

        # Create workflow directory
        workflow_dir = self.data_dir / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Save workflow state
        state_file = workflow_dir / f"{self.name}.json"
        state = self.model_dump()

        # Convert paths to strings
        if state.get("data_dir"):
            state["data_dir"] = str(state["data_dir"])

        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")

    @classmethod
    async def load_state(cls, name: str, data_dir: Path) -> Optional["Workflow"]:
        """Load workflow state from disk.

        Args:
            name: Workflow name
            data_dir: Data directory

        Returns:
            Workflow instance or None if not found
        """
        state_file = data_dir / "workflows" / f"{name}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            # Convert string paths back to Path objects
            if state.get("data_dir"):
                state["data_dir"] = Path(state["data_dir"])

            # Convert step dictionaries to WorkflowStep instances
            state["steps"] = [
                WorkflowStep.from_dict(step) for step in state["steps"]
            ]

            # Convert datetime strings back to datetime objects
            state["created_at"] = datetime.datetime.fromisoformat(state["created_at"])
            state["updated_at"] = datetime.datetime.fromisoformat(state["updated_at"])

            return cls(**state)
        except Exception as e:
            logger.error(f"Failed to load workflow state: {e}")
            return None

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that can handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

class WorkflowManager:
    """Manages FAMP workflows."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize workflow manager.

        Args:
            data_dir: Directory to store workflow data
        """
        self.data_dir = data_dir or Path.home() / ".famp"
        self.workflows: Dict[str, Workflow] = {}
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Load saved workflows from disk."""
        workflow_dir = self.data_dir / "workflows"
        if not workflow_dir.exists():
            return

        for state_file in workflow_dir.glob("*.json"):
            try:
                workflow = asyncio.run(Workflow.load_state(
                    state_file.stem,
                    self.data_dir
                ))
                if workflow:
                    self.workflows[workflow.name] = workflow
            except Exception as e:
                logger.error(f"Failed to load workflow {state_file.name}: {e}")

    def _save_workflow_sync(self, workflow: Workflow) -> None:
        """Save workflow state to disk synchronously.

        Args:
            workflow: Workflow to save
        """
        if not workflow.data_dir:
            return

        # Create workflow directory
        workflow_dir = workflow.data_dir / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Save workflow state
        state_file = workflow_dir / f"{workflow.name}.json"
        state = workflow.model_dump()

        # Convert paths to strings
        if state.get("data_dir"):
            state["data_dir"] = str(state["data_dir"])

        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")

    def create_workflow(self, name: str, description: str) -> Workflow:
        """Create a new workflow.

        Args:
            name: Workflow name
            description: Workflow description

        Returns:
            New workflow instance

        Raises:
            ValueError: If workflow name already exists
        """
        if name in self.workflows:
            raise ValueError(f"Workflow {name} already exists")

        workflow = Workflow(
            name=name,
            description=description,
            data_dir=self.data_dir,
            steps=[]
        )
        self.workflows[name] = workflow

        # Immediately save the workflow to disk
        self._save_workflow_sync(workflow)

        return workflow

    def get_workflow(self, name: str) -> Optional[Workflow]:
        """Get a workflow by name.

        Args:
            name: Workflow name

        Returns:
            Workflow instance or None if not found
        """
        return self.workflows.get(name)

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows.

        Returns:
            List of workflow information dictionaries
        """
        return [
            {
                "name": workflow.name,
                "description": workflow.description,
                "status": workflow.status,
                "step_count": len(workflow.steps),
                "current_step": workflow.current_step,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
            }
            for workflow in self.workflows.values()
        ]

    async def run_workflow(
        self,
        name: str,
        plugin_manager: PluginManager,
        tab: Tab,
        account: FacebookAccount,
        resume: bool = False
    ) -> Dict[str, Any]:
        """Run a workflow.

        Args:
            name: Workflow name
            plugin_manager: Plugin manager instance
            tab: Browser tab
            account: Facebook account to use
            resume: Whether to resume from last step

        Returns:
            Workflow results

        Raises:
            ValueError: If workflow not found
        """
        workflow = self.get_workflow(name)
        if not workflow:
            raise ValueError(f"Workflow {name} not found")

        resume_from = workflow.current_step if resume else None
        return await workflow.run(plugin_manager, tab, account, resume_from)

    def delete_workflow(self, name: str) -> bool:
        """Delete a workflow.

        Args:
            name: Workflow name

        Returns:
            True if workflow was deleted, False otherwise
        """
        if name not in self.workflows:
            return False

        # Remove workflow state file
        if self.data_dir:
            state_file = self.data_dir / "workflows" / f"{name}.json"
            try:
                state_file.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to delete workflow state file: {e}")

        # Remove from workflows dict
        del self.workflows[name]
        return True
