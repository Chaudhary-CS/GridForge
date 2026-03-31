# cmake-preset-matrix

A tool that auto-generates `CMakePresets.json` from a simple YAML build matrix config.

## The Problem

CMake presets are great for developer experience - you type `cmake --preset linux-release-sm86` instead of a mile-long command. But when your project needs to support multiple operating systems, build types, and GPU architectures, the number of preset combinations explodes. Writing and maintaining all of them by hand in a JSON file is tedious and error-prone.

For a project targeting 2 OSes × 2 build types × 3 CUDA architectures, that's 12 presets - each with its own generator, cache variables, binary directory, and toolchain config. And if you add ARM support tomorrow? Now it's 24.

This tool lets you describe the matrix in a compact YAML file and expands all the combinations automatically.

## Motivation

I built this after reading [Marcus Hanwell's blog post on CMake presets and vcpkg](https://cryos.net/2024/02/cmake-dependencies-superbuilds-and-vcpkg/) where he described wanting a way to auto-generate preset combinations from a matrix specification. This is my take on solving that problem, with CUDA projects specifically in mind.

## Quick Start

```bash
# install
pip install -e .

# generate presets from a YAML config
cmake-preset-matrix generate examples/cuda_project.yaml

# or launch the interactive web UI
cmake-preset-matrix serve
```

## YAML Config Format

```yaml
generator: Ninja
toolchain: vcpkg      # optional: injects vcpkg/conan toolchain

dimensions:
  os:
    - linux
    - windows
  build_type:
    - Release
    - Debug
  cuda_arch:
    - sm_75
    - sm_86
    - sm_90

cache_variables:       # applied to every preset
  CMAKE_CUDA_STANDARD: "17"
  CMAKE_CXX_STANDARD: "17"
  BUILD_TESTS: "ON"
```

Running `cmake-preset-matrix generate config.yaml` on this produces a `CMakePresets.json` with 12 configure presets (2 × 2 × 3) and 12 matching build presets. Each preset gets:

- A descriptive name like `linux-release-sm_86`
- The right generator (Ninja on Linux, VS on Windows)
- Correct `CMAKE_CUDA_ARCHITECTURES` (with `sm_` prefix stripped)
- The vcpkg toolchain file injected automatically
- A unique `binaryDir` so builds don't collide

## Web UI

Run `cmake-preset-matrix serve` to open an interactive preset builder in your browser:

- **Left panel**: add/remove dimensions and their values
- **Center**: see every combination as a visual grid - click any to toggle it on/off
- **Right**: live-updating preview of the generated JSON

This is useful for exploring what your matrix looks like before committing to a config file.

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## How It Works

The core logic is pretty straightforward:

1. Parse the YAML config
2. Take the cartesian product of all dimension values (`itertools.product`)
3. For each combination, build a CMake preset with the right variables
4. Handle special cases (OS-specific generators, CUDA arch formatting, toolchain injection)
5. Output valid CMakePresets.json (schema version 6, requires CMake 3.25+)

## Project Structure

```
cmake_preset_matrix/
├── core.py          # matrix expansion, preset generation, validation
├── cli.py           # click-based command line interface
├── web.py           # flask backend for the web UI
└── templates/
    └── index.html   # the interactive frontend
```
