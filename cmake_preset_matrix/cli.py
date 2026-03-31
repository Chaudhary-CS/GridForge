"""
cli.py - command line interface

Two commands:
  cmake-preset-matrix generate config.yaml    -> writes CMakePresets.json
  cmake-preset-matrix serve                   -> opens the web UI
"""

import sys
import json
import webbrowser
import threading
from pathlib import Path

import click

from .core import load_config, validate_config, generate_presets, presets_to_json


@click.group()
def main():
    """cmake-preset-matrix: auto-generate CMakePresets.json from a simple YAML config.

    Tired of writing 50 preset combinations by hand? Same.
    Describe your build matrix in YAML and let this tool expand it for you.
    """
    pass


@main.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("-o", "--output", default="CMakePresets.json", help="Output file path")
@click.option("--dry-run", is_flag=True, help="Print to stdout instead of writing a file")
def generate(config_file, output, dry_run):
    """Generate CMakePresets.json from a YAML config file."""
    config = load_config(config_file)

    errors = validate_config(config)
    if errors:
        click.echo("Found some problems with your config:", err=True)
        for err in errors:
            click.echo(f"  - {err}", err=True)
        sys.exit(1)

    presets = generate_presets(config)
    json_str = presets_to_json(presets)

    num_presets = len(presets["configurePresets"])

    if dry_run:
        click.echo(json_str)
    else:
        with open(output, "w") as f:
            f.write(json_str)
        click.echo(f"Wrote {num_presets} configure presets to {output}")


@main.command()
@click.option("--port", default=5000, help="Port for the web UI")
@click.option("--no-browser", is_flag=True, help="Don't auto-open the browser")
def serve(port, no_browser):
    """Launch the interactive web UI for building presets visually."""
    # importing here so flask isn't required just for the CLI generate command
    from .web import app

    url = f"http://localhost:{port}"
    click.echo(f"Starting web UI at {url}")

    if not no_browser:
        # open browser after a short delay so the server has time to start
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(port=port, debug=False)


if __name__ == "__main__":
    main()
