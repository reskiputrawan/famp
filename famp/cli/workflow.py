"""
Workflow management commands.
"""

import asyncio
from typing import Any, Optional

import click

from famp.cli.utils import pass_context, handle_error, display_table, load_json_config
from famp.workflow import WorkflowManager, StepCondition

@click.group(name="workflow")
@click.pass_context
def workflow_group(ctx):
    """Manage and run workflows."""
    pass

@workflow_group.command("create")
@click.argument("name")
@click.argument("description")
@pass_context
@handle_error
def create_workflow(ctx, name: str, description: str):
    """Create a new workflow."""
    workflow_manager = WorkflowManager(ctx.settings.data_dir)
    try:
        workflow = workflow_manager.create_workflow(name, description)
        click.echo(f"Created workflow: {workflow.name}")
    except ValueError as e:
        click.echo(f"Error: {str(e)}", err=True)

@workflow_group.command("list")
@pass_context
@handle_error
def list_workflows(ctx):
    """List all workflows."""
    workflow_manager = WorkflowManager(ctx.settings.data_dir)
    workflows = workflow_manager.list_workflows()

    if not workflows:
        click.echo("No workflows found.")
        return

    table_data = []
    for wf in workflows:
        table_data.append([
            wf["name"],
            wf["description"],
            wf["status"],
            f"{wf['current_step']}/{wf['step_count']}",
            wf["created_at"],
            wf["updated_at"]
        ])

    headers = ["Name", "Description", "Status", "Progress", "Created", "Updated"]
    display_table(table_data, headers)

@workflow_group.command("delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this workflow?")
@pass_context
@handle_error
def delete_workflow(ctx, name: str):
    """Delete a workflow."""
    workflow_manager = WorkflowManager(ctx.settings.data_dir)
    if workflow_manager.delete_workflow(name):
        click.echo(f"Deleted workflow: {name}")
    else:
        click.echo(f"Workflow {name} not found.", err=True)

@workflow_group.command("add-step")
@click.argument("workflow_name")
@click.argument("plugin_name")
@click.option("--config", "-c", type=click.Path(exists=True),
              help="Plugin configuration file")
@click.option("--condition-plugin", help="Plugin name for condition")
@click.option("--condition-field", help="Field to check in plugin results")
@click.option("--condition-operator", type=click.Choice(["eq", "ne", "gt", "lt", "contains", "exists"]),
              help="Condition operator")
@click.option("--condition-value", help="Value to compare against")
@pass_context
@handle_error
def add_workflow_step(ctx, workflow_name: str, plugin_name: str, config: Optional[str],
                     condition_plugin: Optional[str], condition_field: Optional[str],
                     condition_operator: Optional[str], condition_value: Any):
    """Add a step to a workflow."""
    workflow_manager = WorkflowManager(ctx.settings.data_dir)
    workflow = workflow_manager.get_workflow(workflow_name)

    if not workflow:
        click.echo(f"Workflow {workflow_name} not found.", err=True)
        return

    # Load plugin configuration if provided
    plugin_config = None
    if config:
        plugin_config = load_json_config(config)
        if plugin_config is None:
            return

    # Create step condition if parameters provided
    condition = None
    if all([condition_plugin, condition_field, condition_operator]):
        condition = StepCondition(
            plugin_name=condition_plugin,
            field=condition_field,
            operator=condition_operator,
            value=condition_value
        )

    # Add step to workflow
    workflow.add_step(plugin_name, config=plugin_config, condition=condition)
    click.echo(f"Added step {plugin_name} to workflow {workflow_name}")

@workflow_group.command("run")
@click.argument("name")
@click.argument("account_id")
@click.option("--resume/--no-resume", default=False,
              help="Resume from last step if workflow was interrupted")
@click.option("--headless/--no-headless", default=None,
              help="Run in headless mode (overrides settings)")
@pass_context
@handle_error
async def run_workflow(ctx, name: str, account_id: str, resume: bool, headless: Optional[bool]):
    """Run a workflow for a specific account."""
    # Check if account exists
    account = ctx.account_manager.get_account(account_id)
    if not account:
        click.echo(f"Account {account_id} not found.", err=True)
        return

    workflow_manager = WorkflowManager(ctx.settings.data_dir)
    workflow = workflow_manager.get_workflow(name)
    if not workflow:
        click.echo(f"Workflow {name} not found.", err=True)
        return

    try:
        # Use settings default if headless not specified
        use_headless = headless if headless is not None else ctx.settings.browser.default_headless

        # Get browser tab for account
        tab = await ctx.browser_manager.get_tab(
            account_id,
            headless=use_headless,
            proxy=account.proxy,
            user_agent=account.user_agent or ctx.settings.browser.default_user_agent
        )

        click.echo(f"Running workflow {name} for account {account_id}...")

        # Run workflow with timeout from settings
        async with asyncio.timeout(ctx.settings.browser.default_timeout):
            results = await workflow_manager.run_workflow(
                name,
                ctx.plugin_manager,
                tab,
                account,
                resume=resume
            )

        # Display results
        click.echo(f"\nWorkflow {name} completed with status: {workflow.status}")
        click.echo("\nStep Results:")
        click.echo("-" * 50)

        for step in workflow.steps:
            status_color = {
                "completed": "green",
                "failed": "red",
                "skipped": "yellow"
            }.get(step.status, "white")

            click.secho(f"\nStep: {step.plugin_name}", bold=True)
            click.secho(f"Status: {step.status}", fg=status_color)
            if step.error:
                click.secho(f"Error: {step.error.get('message', 'Unknown error')}", fg="red")
            elif step.result:
                click.echo("Result:")
                for key, value in step.result.items():
                    if key not in ["success", "status"]:
                        click.echo(f"  {key}: {value}")

    except asyncio.TimeoutError:
        click.echo(
            f"Workflow {name} timed out after {ctx.settings.browser.default_timeout}s",
            err=True
        )
    except Exception as e:
        click.echo(f"Error running workflow: {e}", err=True)
        ctx.logger.exception("Workflow execution error")
    finally:
        # Save cookies and close browser
        try:
            await ctx.browser_manager.save_cookies(account_id)
            await ctx.browser_manager.close_browser(account_id)
        except Exception as e:
            ctx.logger.error(f"Error during cleanup: {e}")
