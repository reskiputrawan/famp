"""Tests for FAMP workflow system."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from famp.core.account import FacebookAccount
from famp.plugin import Plugin, PluginManager, PluginError
from famp.workflow import (
    Workflow,
    WorkflowManager,
    WorkflowStep,
    WorkflowStatus,
    WorkflowStepStatus,
    StepCondition
)

@pytest.fixture
def account():
    """Create a test account."""
    return FacebookAccount(
        account_id="test_account",
        email="test@example.com",
        password="test_password",
        user_agent="Test User Agent",
        proxy=None,
        two_factor_secret=None,
        notes="Test account",
        active=True
    )

@pytest.fixture
def mock_tab():
    """Create a mock browser tab."""
    tab = AsyncMock()
    tab.get = AsyncMock()
    tab.text = AsyncMock(return_value="")
    return tab

class TestPlugin(Plugin):
    """Test plugin for workflow testing."""
    name = "test_plugin"
    description = "Test plugin"
    version = "0.1.0"

    async def run(self, tab, account):
        return {"success": True, "test_value": 42}

class FailingPlugin(Plugin):
    """Test plugin that fails."""
    name = "failing_plugin"
    description = "Test plugin that fails"
    version = "0.1.0"

    async def run(self, tab, account):
        raise PluginError(
            "Test failure",
            self.name,
            {"test": True}
        )

@pytest.fixture
def workflow(tmp_path):
    """Create a test workflow."""
    return Workflow(
        name="test_workflow",
        description="Test workflow",
        data_dir=tmp_path,
        steps=[]
    )

@pytest.fixture
def workflow_manager(tmp_path):
    """Create a workflow manager."""
    return WorkflowManager(data_dir=tmp_path)

@pytest.fixture
def plugin_manager():
    """Create a plugin manager with test plugins."""
    pm = PluginManager()
    pm.plugin_instances = {
        "test_plugin": TestPlugin(),
        "failing_plugin": FailingPlugin()
    }
    return pm

@pytest.mark.asyncio
async def test_workflow_creation(workflow_manager):
    """Test workflow creation."""
    workflow = workflow_manager.create_workflow(
        "test",
        "Test workflow"
    )
    assert workflow.name == "test"
    assert workflow.description == "Test workflow"
    assert workflow.status == WorkflowStatus.PENDING
    assert len(workflow.steps) == 0

    # Test duplicate creation
    with pytest.raises(ValueError):
        workflow_manager.create_workflow("test", "Duplicate workflow")

@pytest.mark.asyncio
async def test_workflow_step_addition(workflow):
    """Test adding steps to a workflow."""
    # Add simple step
    workflow.add_step("test_plugin")
    assert len(workflow.steps) == 1
    assert workflow.steps[0].plugin_name == "test_plugin"
    assert workflow.steps[0].status == WorkflowStepStatus.PENDING

    # Add step with configuration
    config = {"test": True}
    workflow.add_step("test_plugin", config=config)
    assert workflow.steps[1].config == config

    # Add step with condition
    condition = StepCondition(
        plugin_name="test_plugin",
        field="test_value",
        operator="eq",
        value=42
    )
    workflow.add_step("test_plugin", condition=condition)
    assert workflow.steps[2].condition == condition

@pytest.mark.asyncio
async def test_workflow_execution(workflow, plugin_manager, mock_tab, account):
    """Test workflow execution."""
    # Add test steps
    workflow.add_step("test_plugin")
    workflow.add_step(
        "test_plugin",
        condition=StepCondition(
            plugin_name="test_plugin",
            field="test_value",
            operator="eq",
            value=42
        )
    )

    # Run workflow
    results = await workflow.run(plugin_manager, mock_tab, account)

    # Check results
    assert workflow.status == WorkflowStatus.COMPLETED
    assert len(results) == 2
    assert workflow.steps[0].status == WorkflowStepStatus.COMPLETED
    assert workflow.steps[1].status == WorkflowStepStatus.COMPLETED

@pytest.mark.asyncio
async def test_workflow_conditional_execution(workflow, plugin_manager, mock_tab, account):
    """Test conditional step execution."""
    # Add steps with conditions
    workflow.add_step("test_plugin")  # First step always runs

    # Second step runs only if first step returns test_value = 42
    workflow.add_step(
        "test_plugin",
        condition=StepCondition(
            plugin_name="test_plugin",
            field="test_value",
            operator="eq",
            value=42
        )
    )

    # Third step runs only if first step returns test_value = 0 (won't run)
    workflow.add_step(
        "test_plugin",
        condition=StepCondition(
            plugin_name="test_plugin",
            field="test_value",
            operator="eq",
            value=0
        )
    )

    # Run workflow
    await workflow.run(plugin_manager, mock_tab, account)

    # Check results
    assert workflow.steps[0].status == WorkflowStepStatus.COMPLETED
    assert workflow.steps[1].status == WorkflowStepStatus.COMPLETED
    assert workflow.steps[2].status == WorkflowStepStatus.SKIPPED

@pytest.mark.asyncio
async def test_workflow_error_handling(workflow, plugin_manager, mock_tab, account):
    """Test workflow error handling."""
    # Add failing step
    workflow.add_step("failing_plugin")
    workflow.add_step("test_plugin")  # This step shouldn't run

    # Run workflow
    with pytest.raises(PluginError):
        await workflow.run(plugin_manager, mock_tab, account)

    # Check workflow state
    assert workflow.status == WorkflowStatus.FAILED
    assert workflow.steps[0].status == WorkflowStepStatus.FAILED
    assert workflow.steps[1].status == WorkflowStepStatus.PENDING
    assert workflow.steps[0].error is not None

@pytest.mark.asyncio
async def test_workflow_persistence(workflow, plugin_manager, mock_tab, account, tmp_path):
    """Test workflow state persistence."""
    # Add steps
    workflow.add_step("test_plugin")
    workflow.add_step("test_plugin")

    # Start execution
    try:
        await workflow.run(plugin_manager, mock_tab, account)
    except Exception:
        pass

    # Check state file exists
    state_file = tmp_path / "workflows" / f"{workflow.name}.json"
    assert state_file.exists()

    # Load workflow from state
    loaded_workflow = await Workflow.load_state(workflow.name, tmp_path)
    assert loaded_workflow is not None
    assert loaded_workflow.name == workflow.name
    assert len(loaded_workflow.steps) == len(workflow.steps)
    assert loaded_workflow.current_step == workflow.current_step

@pytest.mark.asyncio
async def test_workflow_resumption(workflow, plugin_manager, mock_tab, account):
    """Test workflow resumption after interruption."""
    # Add steps
    workflow.add_step("test_plugin")
    workflow.add_step("failing_plugin")
    workflow.add_step("test_plugin")

    # Run workflow (will fail at second step)
    try:
        await workflow.run(plugin_manager, mock_tab, account)
    except PluginError:
        pass

    assert workflow.current_step == 1
    assert workflow.steps[0].status == WorkflowStepStatus.COMPLETED
    assert workflow.steps[1].status == WorkflowStepStatus.FAILED
    assert workflow.steps[2].status == WorkflowStepStatus.PENDING

    # Fix the failing plugin (replace with working one)
    plugin_manager.plugin_instances["failing_plugin"] = TestPlugin()

    # Resume workflow
    results = await workflow.run(plugin_manager, mock_tab, account, resume_from=1)

    # Check completion
    assert workflow.status == WorkflowStatus.COMPLETED
    assert all(step.status == WorkflowStepStatus.COMPLETED for step in workflow.steps)
    assert workflow.current_step == 3

@pytest.mark.asyncio
async def test_workflow_step_conditions(workflow):
    """Test workflow step condition evaluation."""
    condition = StepCondition(
        plugin_name="test_plugin",
        field="value",
        operator="eq",
        value=42
    )

    # Test various operators
    assert condition.evaluate({"test_plugin": {"value": 42}}) is True

    condition.operator = "ne"
    assert condition.evaluate({"test_plugin": {"value": 41}}) is True

    condition.operator = "gt"
    assert condition.evaluate({"test_plugin": {"value": 43}}) is True

    condition.operator = "lt"
    assert condition.evaluate({"test_plugin": {"value": 41}}) is True

    condition.operator = "contains"
    condition.value = "test"
    assert condition.evaluate({"test_plugin": {"value": "this is a test"}}) is True

    # Test non-existent plugin/field
    condition.operator = "eq"
    condition.value = 42
    assert condition.evaluate({"other_plugin": {"value": 42}}) is False
    assert condition.evaluate({"test_plugin": {"other_field": 42}}) is False

@pytest.mark.asyncio
async def test_workflow_deletion(workflow_manager):
    """Test workflow deletion."""
    # Create and then delete workflow
    workflow = workflow_manager.create_workflow("test", "Test workflow")
    assert workflow_manager.get_workflow("test") is not None

    success = workflow_manager.delete_workflow("test")
    assert success is True
    assert workflow_manager.get_workflow("test") is None

    # Test deleting non-existent workflow
    assert workflow_manager.delete_workflow("non-existent") is False
