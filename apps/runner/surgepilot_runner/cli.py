import click


@click.group()
def cli() -> None:
    """SurgePilot runner CLI."""


@cli.command()
def version() -> None:
    """Print the Runner version."""
    click.echo("SurgePilot Runner 0.1.0")
