"""
core.py - the actual matrix expansion logic

The main idea: you give me a YAML file describing your build dimensions
(like os, build_type, cuda_arch) and I spit out every combination as a
proper CMake preset. This is the heart of the tool.

I kept the functions small so they're easy to test individually.
"""

import itertools
import json
import copy
from pathlib import Path

import yaml


def load_config(filepath):
    """Read the YAML config file and return it as a dict.
    I'm not doing heavy validation here - just making sure the file
    exists and is valid YAML. We validate the structure separately."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(filepath, "r") as f:
        config = yaml.safe_load(f)

    return config


def validate_config(config):
    """Check that the config has the fields we actually need.
    Returns a list of error messages (empty = all good)."""
    errors = []

    if not isinstance(config, dict):
        return ["Config should be a YAML mapping, got something else"]

    if "dimensions" not in config:
        errors.append("Missing 'dimensions' - I need to know what to expand (os, build_type, etc.)")

    dims = config.get("dimensions", {})
    if isinstance(dims, dict):
        for name, values in dims.items():
            if not isinstance(values, list) or len(values) == 0:
                errors.append(f"Dimension '{name}' should be a non-empty list, got: {values}")
    else:
        errors.append("'dimensions' should be a mapping like {os: [linux, windows], ...}")

    return errors


def expand_matrix(dimensions):
    """This is where the magic happens.
    Takes something like:
        {"os": ["linux", "windows"], "build_type": ["Release", "Debug"]}
    and returns:
        [{"os": "linux", "build_type": "Release"},
         {"os": "linux", "build_type": "Debug"},
         {"os": "windows", "build_type": "Release"},
         {"os": "windows", "build_type": "Debug"}]

    Basically just a cartesian product, but we keep track of
    which dimension each value came from.
    """
    dim_names = list(dimensions.keys())
    dim_values = list(dimensions.values())

    combos = []
    for values in itertools.product(*dim_values):
        combo = {}
        for i, name in enumerate(dim_names):
            combo[name] = values[i]
        combos.append(combo)

    return combos


def make_preset_name(combo):
    """Turn a combo dict into a readable preset name.
    {"os": "linux", "build_type": "Release", "cuda_arch": "sm_86"}
    becomes "linux-release-sm_86"

    I lowercase everything and join with hyphens. Keeps it clean."""
    parts = []
    for val in combo.values():
        parts.append(str(val).lower())
    return "-".join(parts)


# -- mappings for how different dimension values affect cmake variables --
# I'm keeping these as simple dicts so it's easy to add more later

OS_DEFAULTS = {
    "linux": {
        "generator": "Ninja",
        "env": {},
    },
    "windows": {
        "generator": "Visual Studio 17 2022",
        "env": {},
    },
    "macos": {
        "generator": "Ninja",
        "env": {},
    },
}

def build_cache_variables(combo, global_vars):
    """Figure out what CMake cache variables this combo needs.

    We start with whatever the user specified globally, then layer on
    stuff based on the specific dimension values (build type, cuda arch, etc.)
    """
    cache_vars = {}

    # start with user-specified global variables
    if global_vars:
        for key, val in global_vars.items():
            cache_vars[key] = {"type": "STRING", "value": str(val)}

    # build type is special - CMake has a dedicated variable for it
    if "build_type" in combo:
        cache_vars["CMAKE_BUILD_TYPE"] = {
            "type": "STRING",
            "value": combo["build_type"],
        }

    # cuda architecture - sets CMAKE_CUDA_ARCHITECTURES
    if "cuda_arch" in combo:
        arch = combo["cuda_arch"]
        # strip the "sm_" prefix if they included it, cmake just wants the number
        arch_num = arch.replace("sm_", "")
        cache_vars["CMAKE_CUDA_ARCHITECTURES"] = {
            "type": "STRING",
            "value": arch_num,
        }

    return cache_vars


def inject_toolchain(preset, toolchain_type):
    """If the user wants vcpkg or conan, we need to inject the toolchain file.
    This is one of those things that's annoying to remember and type every time,
    so we handle it automatically.
    """
    if toolchain_type == "vcpkg":
        preset["toolchainFile"] = "$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake"
    elif toolchain_type == "conan":
        # conan generates this in the build dir
        preset["toolchainFile"] = "${sourceDir}/build/conan_toolchain.cmake"

    return preset


def generate_presets(config, excluded=None):
    """The main function - takes a config dict and produces
    the full CMakePresets.json content as a dict.

    excluded is an optional set of preset names to skip
    (the web UI uses this for toggling combos on/off)
    """
    if excluded is None:
        excluded = set()

    dims = config.get("dimensions", {})
    global_vars = config.get("cache_variables", {})
    toolchain = config.get("toolchain", None)
    default_generator = config.get("generator", "Ninja")

    combos = expand_matrix(dims)

    configure_presets = []
    build_presets = []

    for combo in combos:
        name = make_preset_name(combo)

        if name in excluded:
            continue

        # figure out the generator - use OS-specific default if we know it,
        # otherwise fall back to what the user specified (or Ninja)
        os_val = combo.get("os", "")
        if os_val.lower() in OS_DEFAULTS:
            generator = OS_DEFAULTS[os_val.lower()]["generator"]
        else:
            generator = default_generator

        preset = {
            "name": name,
            "displayName": name,
            "description": f"Auto-generated: {', '.join(f'{k}={v}' for k, v in combo.items())}",
            "generator": generator,
            "binaryDir": f"${{sourceDir}}/build/{name}",
            "cacheVariables": build_cache_variables(combo, global_vars),
        }

        # inject toolchain if needed
        if toolchain:
            preset = inject_toolchain(preset, toolchain)

        configure_presets.append(preset)

        # also make a matching build preset so you can do
        # cmake --build --preset linux-release-sm_86
        build_presets.append({
            "name": name,
            "configurePreset": name,
        })

    output = {
        "version": 6,
        "cmakeMinimumRequired": {"major": 3, "minor": 25, "patch": 0},
        "configurePresets": configure_presets,
        "buildPresets": build_presets,
    }

    return output


def presets_to_json(presets_dict, pretty=True):
    """Just a helper to serialize to JSON string.
    Pretty-print by default because humans read these files too."""
    if pretty:
        return json.dumps(presets_dict, indent=2)
    return json.dumps(presets_dict)
