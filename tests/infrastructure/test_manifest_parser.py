"""
Tests for ManifestParser — Infrastructure adapter for dependency manifest parsing.

Tests validate:
- Parsing package.json (npm) with dependencies and devDependencies
- Parsing requirements.txt (pip) with pinned and ranged versions
- Handling comments and empty lines in requirements.txt
- Correct ecosystem values in parsed Dependency entities
- Error handling for invalid files
"""

import pytest
import json
from pathlib import Path

from infrastructure.adapters.manifest_parser import ManifestParser
from domain.entities.dependency import Dependency


@pytest.fixture
def parser():
    """Create a ManifestParser instance."""
    return ManifestParser()


class TestManifestParserNpm:
    """Test npm package.json parsing."""

    @pytest.mark.asyncio
    async def test_parse_package_json_with_dependencies(self, parser, tmp_path):
        """Parse package.json with dependencies section."""
        package_json = tmp_path / "package.json"
        content = {
            "name": "my-app",
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0",
            },
        }
        package_json.write_text(json.dumps(content))

        deps = await parser.parse(str(package_json))

        assert len(deps) == 2
        assert any(d.name == "react" for d in deps)
        assert any(d.name == "react-dom" for d in deps)
        assert all(d.ecosystem == "npm" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_package_json_with_dev_dependencies(self, parser, tmp_path):
        """Parse package.json with devDependencies section."""
        package_json = tmp_path / "package.json"
        content = {
            "name": "my-app",
            "devDependencies": {
                "jest": "^29.0.0",
                "eslint": "^8.0.0",
            },
        }
        package_json.write_text(json.dumps(content))

        deps = await parser.parse(str(package_json))

        assert len(deps) == 2
        assert any(d.name == "jest" for d in deps)
        assert any(d.name == "eslint" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_package_json_dependencies_and_dev_dependencies(self, parser, tmp_path):
        """Parse both dependencies and devDependencies."""
        package_json = tmp_path / "package.json"
        content = {
            "name": "my-app",
            "dependencies": {
                "react": "^18.0.0",
            },
            "devDependencies": {
                "jest": "^29.0.0",
            },
        }
        package_json.write_text(json.dumps(content))

        deps = await parser.parse(str(package_json))

        assert len(deps) == 2
        assert any(d.name == "react" for d in deps)
        assert any(d.name == "jest" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_package_json_preserves_version_strings(self, parser, tmp_path):
        """Version strings from package.json are preserved (with operators)."""
        package_json = tmp_path / "package.json"
        content = {
            "dependencies": {
                "react": "^18.0.0",
                "lodash": "~4.17.0",
                "express": ">=4.0.0",
            },
        }
        package_json.write_text(json.dumps(content))

        deps = await parser.parse(str(package_json))

        react_dep = next(d for d in deps if d.name == "react")
        lodash_dep = next(d for d in deps if d.name == "lodash")
        express_dep = next(d for d in deps if d.name == "express")

        # Versions are preserved as-is
        assert react_dep.current_version == "^18.0.0"
        assert lodash_dep.current_version == "~4.17.0"
        assert express_dep.current_version == ">=4.0.0"

    @pytest.mark.asyncio
    async def test_parse_package_json_manifest_path_recorded(self, parser, tmp_path):
        """Parsed dependencies record the manifest file path."""
        package_json = tmp_path / "package.json"
        content = {
            "dependencies": {
                "react": "^18.0.0",
            },
        }
        package_json.write_text(json.dumps(content))

        deps = await parser.parse(str(package_json))

        assert deps[0].manifest_path == str(package_json)

    @pytest.mark.asyncio
    async def test_parse_invalid_package_json_returns_empty_list(self, parser, tmp_path):
        """Invalid JSON returns empty list."""
        package_json = tmp_path / "package.json"
        package_json.write_text("{ invalid json }")

        deps = await parser.parse(str(package_json))

        assert deps == []


class TestManifestParserPip:
    """Test pip requirements.txt parsing."""

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_pinned_versions(self, parser, tmp_path):
        """Parse requirements.txt with pinned versions (==)."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django==3.2.0\n"
            "requests==2.28.0\n"
            "flask==2.0.0\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 3
        assert any(d.name == "django" and d.current_version == "3.2.0" for d in deps)
        assert any(d.name == "requests" and d.current_version == "2.28.0" for d in deps)
        assert any(d.name == "flask" and d.current_version == "2.0.0" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_ranged_versions(self, parser, tmp_path):
        """Parse requirements.txt with ranged versions (>=, <, etc)."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django>=3.0,<4.0\n"
            "requests>=2.0\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2
        # Version spec is preserved
        assert any(d.name == "django" for d in deps)
        assert any(d.name == "requests" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_no_version_specifier(self, parser, tmp_path):
        """Parse requirements.txt with no version specifier."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django\n"
            "requests\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2
        # No version spec defaults to "*"
        assert all(d.current_version == "*" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_skips_comments(self, parser, tmp_path):
        """Comments are skipped."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "# Main dependencies\n"
            "django==3.2.0\n"
            "# Testing\n"
            "pytest==7.0.0\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2
        assert any(d.name == "django" for d in deps)
        assert any(d.name == "pytest" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_skips_empty_lines(self, parser, tmp_path):
        """Empty lines are skipped."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django==3.2.0\n"
            "\n"
            "requests==2.28.0\n"
            "\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_skips_options(self, parser, tmp_path):
        """Option flags (-e, -r, --index-url) are skipped."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "--index-url https://pypi.org/simple\n"
            "django==3.2.0\n"
            "-e git+https://github.com/user/repo.git#egg=package\n"
            "requests==2.28.0\n"
        )

        deps = await parser.parse(str(requirements))

        # Only actual packages are parsed
        assert len(deps) == 2
        assert any(d.name == "django" for d in deps)
        assert any(d.name == "requests" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_ecosystem_is_pip(self, parser, tmp_path):
        """Parsed dependencies have ecosystem set to 'pip'."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("django==3.2.0\n")

        deps = await parser.parse(str(requirements))

        assert deps[0].ecosystem == "pip"

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_manifest_path_recorded(self, parser, tmp_path):
        """Parsed dependencies record the manifest file path."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("django==3.2.0\n")

        deps = await parser.parse(str(requirements))

        assert deps[0].manifest_path == str(requirements)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_with_extras(self, parser, tmp_path):
        """Parse packages with extras: package[extra]==1.0."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "requests[security]==2.28.0\n"
            "sqlalchemy[postgresql]==1.4.0\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2
        # Extras should be stripped from name
        assert any(d.name == "requests" for d in deps)
        assert any(d.name == "sqlalchemy" for d in deps)

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_with_environment_markers(self, parser, tmp_path):
        """Parse packages with environment markers: package==1.0; python_version>='3.8'."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django==3.2.0; python_version>='3.8'\n"
            "typing-extensions==4.0.0; python_version<'3.10'\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2
        # Environment markers should be stripped
        assert any(d.name == "django" and d.current_version == "3.2.0" for d in deps)


class TestManifestParserErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_parse_nonexistent_file_raises_error(self, parser):
        """Parsing non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await parser.parse("/nonexistent/manifest.json")

    @pytest.mark.asyncio
    async def test_parse_directory_instead_of_file_raises_error(self, parser, tmp_path):
        """Parsing a directory instead of file raises ValueError."""
        with pytest.raises(ValueError, match="Not a file"):
            await parser.parse(str(tmp_path))

    @pytest.mark.asyncio
    async def test_parse_unsupported_manifest_type_raises_error(self, parser, tmp_path):
        """Unsupported manifest file type raises ValueError."""
        unsupported = tmp_path / "Gemfile"
        unsupported.write_text("ruby 'gems'")

        with pytest.raises(ValueError, match="Unsupported manifest type"):
            await parser.parse(str(unsupported))


class TestManifestParserPipEdgeCases:
    """Test edge cases in pip requirements parsing."""

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_inline_comments(self, parser, tmp_path):
        """Inline comments are stripped."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "django==3.2.0  # Main framework\n"
            "requests==2.28.0\n"
        )

        deps = await parser.parse(str(requirements))

        assert len(deps) == 2

    @pytest.mark.asyncio
    async def test_parse_requirements_txt_tilde_version(self, parser, tmp_path):
        """Parse tilde version specifier (~=)."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("django~=3.2\n")

        deps = await parser.parse(str(requirements))

        assert len(deps) == 1
        assert deps[0].name == "django"
