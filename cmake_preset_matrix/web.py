"""
web.py - flask backend for the interactive preset builder

This serves a single-page app where you can visually build your
preset matrix and see the generated JSON update in real time.

The frontend does most of the heavy lifting (it's all in the template),
this just handles the API calls for generating presets.
"""

import os
from flask import Flask, render_template, request, jsonify

from .core import (
    expand_matrix,
    generate_presets,
    presets_to_json,
    make_preset_name,
    validate_config,
)

# when installed as a package Flask can't find templates via __name__ alone,
# so we point it explicitly to the templates folder next to this file
_here = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(_here, "templates"))


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Takes a config (same format as the YAML but as JSON) and
    returns the generated CMakePresets.json content.

    The frontend sends us the dimensions, options, and which
    presets are excluded, and we do the expansion + generation.
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    config = {
        "dimensions": data.get("dimensions", {}),
        "cache_variables": data.get("cache_variables", {}),
        "toolchain": data.get("toolchain", None),
        "generator": data.get("generator", "Ninja"),
    }

    errors = validate_config(config)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    excluded = set(data.get("excluded", []))
    presets = generate_presets(config, excluded=excluded)
    json_output = presets_to_json(presets)

    return jsonify({
        "presets_json": json_output,
        "num_configure": len(presets["configurePresets"]),
        "num_build": len(presets["buildPresets"]),
    })


@app.route("/api/expand", methods=["POST"])
def api_expand():
    """Just expand the matrix and return the list of combo names.
    The frontend uses this to build the visual grid without
    needing the full preset JSON.
    """
    data = request.get_json()
    dims = data.get("dimensions", {})

    if not dims:
        return jsonify({"combos": [], "names": []})

    combos = expand_matrix(dims)
    names = [make_preset_name(c) for c in combos]

    return jsonify({
        "combos": combos,
        "names": names,
    })
