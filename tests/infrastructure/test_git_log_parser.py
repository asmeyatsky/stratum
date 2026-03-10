"""
Tests for GitLogParser — Infrastructure adapter for git log parsing.

Tests validate:
- Parsing of standard git log format
- FileChange extraction from numstat lines
- Binary file handling
- Empty input handling
- Malformed line graceful skipping
- Timestamp parsing
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.adapters.git_log_parser import GitLogParser
from domain.entities.commit import Commit
from domain.entities.file_change import FileChange


@pytest.fixture
def parser():
    """Create a GitLogParser instance."""
    return GitLogParser()


class TestGitLogParserParsing:
    """Test basic git log parsing."""

    @pytest.mark.asyncio
    async def test_parse_single_commit(self, parser, tmp_path):
        """Parse a single commit from git log file."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123def456|author@example.com|Author Name|2024-01-15 10:00:00 +0000|Initial commit\n"
            "10\t5\tsrc/main.py\n"
            "3\t1\tREADME.md\n"
        )

        commits = await parser.parse(str(log_file))

        assert len(commits) == 1
        commit = commits[0]
        assert commit.hash == "abc123def456"
        assert commit.author_email == "author@example.com"
        assert commit.author_name == "Author Name"
        assert commit.message == "Initial commit"
        assert len(commit.file_changes) == 2

    @pytest.mark.asyncio
    async def test_parse_multiple_commits(self, parser, tmp_path):
        """Parse multiple commits separated by blank lines."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|First commit\n"
            "10\t5\tsrc/main.py\n"
            "\n"
            "def456|other@example.com|Other|2024-01-16 11:00:00 +0000|Second commit\n"
            "20\t10\tsrc/module.py\n"
        )

        commits = await parser.parse(str(log_file))

        assert len(commits) == 2
        assert commits[0].hash == "abc123"
        assert commits[1].hash == "def456"

    @pytest.mark.asyncio
    async def test_parse_commits_sorted_chronologically(self, parser, tmp_path):
        """Commits are returned in chronological order (oldest first)."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "def456|author@example.com|Author|2024-01-16 11:00:00 +0000|Second commit\n"
            "20\t10\tsrc/module.py\n"
            "\n"
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|First commit\n"
            "10\t5\tsrc/main.py\n"
        )

        commits = await parser.parse(str(log_file))

        # Should be sorted by timestamp (oldest first)
        assert len(commits) == 2
        assert commits[0].timestamp < commits[1].timestamp

    @pytest.mark.asyncio
    async def test_parse_file_changes_extraction(self, parser, tmp_path):
        """Parse numstat lines into FileChange entities."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Commit\n"
            "10\t5\tsrc/main.py\n"
            "20\t3\tlib/module.py\n"
            "0\t15\ttest/test_main.py\n"
        )

        commits = await parser.parse(str(log_file))

        assert len(commits) == 1
        changes = commits[0].file_changes
        assert len(changes) == 3

        assert changes[0].file_path == "src/main.py"
        assert changes[0].lines_added == 10
        assert changes[0].lines_deleted == 5

        assert changes[1].file_path == "lib/module.py"
        assert changes[1].lines_added == 20
        assert changes[1].lines_deleted == 3

        assert changes[2].file_path == "test/test_main.py"
        assert changes[2].lines_added == 0
        assert changes[2].lines_deleted == 15


class TestGitLogParserBinaryFiles:
    """Test handling of binary files."""

    @pytest.mark.asyncio
    async def test_parse_binary_file_uses_zero_counts(self, parser, tmp_path):
        """Binary files use '-' for counts; parser converts to 0/0."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Add image\n"
            "-\t-\tassets/logo.png\n"
        )

        commits = await parser.parse(str(log_file))

        assert len(commits) == 1
        changes = commits[0].file_changes
        assert len(changes) == 1

        assert changes[0].file_path == "assets/logo.png"
        assert changes[0].lines_added == 0
        assert changes[0].lines_deleted == 0
        assert changes[0].is_binary is True

    @pytest.mark.asyncio
    async def test_parse_mixed_text_and_binary_files(self, parser, tmp_path):
        """Parse mix of text and binary files in same commit."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Mixed commit\n"
            "10\t5\tsrc/main.py\n"
            "-\t-\tassets/image.jpg\n"
            "3\t2\tREADME.md\n"
        )

        commits = await parser.parse(str(log_file))

        changes = commits[0].file_changes
        assert len(changes) == 3

        # Text files have counts
        assert changes[0].lines_added == 10
        assert changes[2].lines_added == 3

        # Binary file has 0/0
        assert changes[1].lines_added == 0
        assert changes[1].lines_deleted == 0


class TestGitLogParserEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_parse_empty_file_returns_empty_list(self, parser, tmp_path):
        """Empty file returns empty list of commits."""
        log_file = tmp_path / "git.log"
        log_file.write_text("")

        commits = await parser.parse(str(log_file))

        assert commits == []

    @pytest.mark.asyncio
    async def test_parse_malformed_header_skipped(self, parser, tmp_path):
        """Malformed commit header is skipped with warning."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "malformed|header\n"  # Missing fields
            "10\t5\tsrc/main.py\n"
            "\n"
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Good commit\n"
            "10\t5\tsrc/main.py\n"
        )

        commits = await parser.parse(str(log_file))

        # Only the well-formed commit is parsed
        assert len(commits) == 1
        assert commits[0].hash == "abc123"

    @pytest.mark.asyncio
    async def test_parse_unparseable_timestamp_skipped(self, parser, tmp_path):
        """Commit with unparseable timestamp is skipped."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|INVALID_DATE|Bad timestamp\n"
            "10\t5\tsrc/main.py\n"
            "\n"
            "def456|author@example.com|Author|2024-01-15 10:00:00 +0000|Good commit\n"
            "10\t5\tsrc/main.py\n"
        )

        commits = await parser.parse(str(log_file))

        # Only the commit with valid timestamp is parsed
        assert len(commits) == 1
        assert commits[0].hash == "def456"

    @pytest.mark.asyncio
    async def test_parse_malformed_numstat_line_skipped(self, parser, tmp_path):
        """Malformed numstat lines are skipped gracefully."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Commit\n"
            "10\t5\tsrc/main.py\n"
            "invalid numstat format\n"  # Malformed
            "3\t2\tREADME.md\n"
        )

        commits = await parser.parse(str(log_file))

        # Well-formed numstat lines are parsed, malformed is skipped
        changes = commits[0].file_changes
        assert len(changes) == 2
        assert changes[0].file_path == "src/main.py"
        assert changes[1].file_path == "README.md"

    @pytest.mark.asyncio
    async def test_parse_file_not_found_raises_error(self, parser):
        """Parsing non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await parser.parse("/nonexistent/git.log")

    @pytest.mark.asyncio
    async def test_parse_is_not_a_file_raises_error(self, parser, tmp_path):
        """Parsing a directory instead of file raises ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            await parser.parse(str(tmp_path))


class TestGitLogParserTimestamps:
    """Test timestamp parsing."""

    @pytest.mark.asyncio
    async def test_parse_timestamp_standard_git_format(self, parser, tmp_path):
        """Parse standard git %ai format: YYYY-MM-DD HH:MM:SS +ZZZZ."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 14:30:00 +0100|Commit\n"
            "10\t5\tsrc/main.py\n"
        )

        commits = await parser.parse(str(log_file))

        commit = commits[0]
        # Timestamp should be parsed with timezone
        assert commit.timestamp.year == 2024
        assert commit.timestamp.month == 1
        assert commit.timestamp.day == 15
        assert commit.timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_parse_timestamp_utc(self, parser, tmp_path):
        """Parse UTC timezone correctly."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Commit\n"
            "10\t5\tsrc/main.py\n"
        )

        commits = await parser.parse(str(log_file))

        assert commits[0].timestamp.tzinfo == timezone.utc


class TestGitLogParserRenaming:
    """Test git rename notation handling."""

    @pytest.mark.asyncio
    async def test_parse_rename_curly_brace_notation(self, parser, tmp_path):
        """Handle git rename with curly braces: src/{old.py => new.py}."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Rename\n"
            "0\t0\tsrc/{old_name.py => new_name.py}\n"
        )

        commits = await parser.parse(str(log_file))

        changes = commits[0].file_changes
        assert len(changes) == 1
        # Should use the new path
        assert changes[0].file_path == "src/new_name.py"

    @pytest.mark.asyncio
    async def test_parse_rename_plain_arrow_notation(self, parser, tmp_path):
        """Handle git rename with plain arrow: old_path => new_path."""
        log_file = tmp_path / "git.log"
        log_file.write_text(
            "abc123|author@example.com|Author|2024-01-15 10:00:00 +0000|Rename\n"
            "0\t0\told/path/file.py => new/path/file.py\n"
        )

        commits = await parser.parse(str(log_file))

        changes = commits[0].file_changes
        assert len(changes) == 1
        # Should use the new path
        assert changes[0].file_path == "new/path/file.py"
