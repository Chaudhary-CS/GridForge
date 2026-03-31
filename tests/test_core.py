"""
Tests for the core matrix expansion logic.

I tried to cover the main paths:
- basic expansion works
- preset names look right
- cache variables get set correctly
- validation catches bad configs
- exclusion actually excludes stuff
"""

import pytest
import json
from cmake_preset_matrix.core import (
    expand_matrix,
    make_preset_name,
    validate_config,
    generate_presets,
    build_cache_variables,
    presets_to_json,
    load_config,
)


class TestExpandMatrix:
    def test_single_dimension(self):
        dims = {"os": ["linux", "windows"]}
        result = expand_matrix(dims)
        assert len(result) == 2
        assert result[0] == {"os": "linux"}
        assert result[1] == {"os": "windows"}

    def test_two_dimensions(self):
        dims = {
            "os": ["linux", "windows"],
            "build_type": ["Release", "Debug"],
        }
        result = expand_matrix(dims)
        # 2 * 2 = 4 combinations
        assert len(result) == 4

    def test_three_dimensions(self):
        """This is the realistic case - OS x build type x GPU arch."""
        dims = {
            "os": ["linux", "windows"],
            "build_type": ["Release", "Debug"],
            "cuda_arch": ["sm_75", "sm_86", "sm_90"],
        }
        result = expand_matrix(dims)
        # 2 * 2 * 3 = 12
        assert len(result) == 12

    def test_empty_dimensions(self):
        result = expand_matrix({})
        # should give us one empty combo (that's how itertools.product works)
        assert len(result) == 1
        assert result[0] == {}


class TestPresetNames:
    def test_basic_name(self):
        combo = {"os": "linux", "build_type": "Release"}
        assert make_preset_name(combo) == "linux-release"

    def test_name_with_cuda_arch(self):
        combo = {"os": "linux", "build_type": "Debug", "cuda_arch": "sm_86"}
        assert make_preset_name(combo) == "linux-debug-sm_86"

    def test_everything_gets_lowered(self):
        combo = {"os": "Windows", "build_type": "Release"}
        assert make_preset_name(combo) == "windows-release"


class TestBuildCacheVariables:
    def test_build_type_gets_set(self):
        combo = {"build_type": "Release"}
        result = build_cache_variables(combo, {})
        assert result["CMAKE_BUILD_TYPE"]["value"] == "Release"

    def test_cuda_arch_strips_prefix(self):
        combo = {"cuda_arch": "sm_86"}
        result = build_cache_variables(combo, {})
        assert result["CMAKE_CUDA_ARCHITECTURES"]["value"] == "86"

    def test_global_vars_included(self):
        combo = {"os": "linux"}
        global_vars = {"CMAKE_CXX_STANDARD": "17"}
        result = build_cache_variables(combo, global_vars)
        assert result["CMAKE_CXX_STANDARD"]["value"] == "17"

    def test_cuda_arch_without_prefix(self):
        """Sometimes people just write '86' instead of 'sm_86'."""
        combo = {"cuda_arch": "86"}
        result = build_cache_variables(combo, {})
        assert result["CMAKE_CUDA_ARCHITECTURES"]["value"] == "86"


class TestValidation:
    def test_valid_config(self):
        config = {"dimensions": {"os": ["linux"]}}
        errors = validate_config(config)
        assert errors == []

    def test_missing_dimensions(self):
        errors = validate_config({})
        assert len(errors) > 0
        assert "dimensions" in errors[0].lower()

    def test_empty_dimension_values(self):
        config = {"dimensions": {"os": []}}
        errors = validate_config(config)
        assert len(errors) > 0

    def test_not_a_dict(self):
        errors = validate_config("this is wrong")
        assert len(errors) > 0


class TestGeneratePresets:
    def test_basic_generation(self):
        config = {
            "dimensions": {
                "os": ["linux"],
                "build_type": ["Release"],
            },
        }
        result = generate_presets(config)

        assert result["version"] == 6
        assert len(result["configurePresets"]) == 1
        assert len(result["buildPresets"]) == 1
        assert result["configurePresets"][0]["name"] == "linux-release"

    def test_exclusion_works(self):
        config = {
            "dimensions": {
                "os": ["linux", "windows"],
                "build_type": ["Release"],
            },
        }
        excluded = {"windows-release"}
        result = generate_presets(config, excluded=excluded)
        names = [p["name"] for p in result["configurePresets"]]
        assert "linux-release" in names
        assert "windows-release" not in names

    def test_vcpkg_toolchain_injected(self):
        config = {
            "dimensions": {"os": ["linux"]},
            "toolchain": "vcpkg",
        }
        result = generate_presets(config)
        preset = result["configurePresets"][0]
        assert "VCPKG_ROOT" in preset.get("toolchainFile", "")

    def test_generator_from_os(self):
        """Linux should get Ninja, Windows should get VS."""
        config = {
            "dimensions": {
                "os": ["linux", "windows"],
            },
        }
        result = generate_presets(config)
        presets = {p["name"]: p for p in result["configurePresets"]}
        assert presets["linux"]["generator"] == "Ninja"
        assert "Visual Studio" in presets["windows"]["generator"]

    def test_output_is_valid_json(self):
        config = {
            "dimensions": {
                "os": ["linux", "windows"],
                "build_type": ["Release", "Debug"],
                "cuda_arch": ["sm_75", "sm_86"],
            },
            "cache_variables": {"CMAKE_CUDA_STANDARD": "17"},
        }
        result = generate_presets(config)
        json_str = presets_to_json(result)
        # should parse without errors
        parsed = json.loads(json_str)
        assert parsed["version"] == 6


class TestLoadConfig:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("does_not_exist.yaml")
