"""Tests for command_log: footer stripping for captured PFC console output."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pfc-mcp-bridge", "src"))

from pfc_mcp_bridge.utils.command_log import _strip_footer


class TestStripFooter:
    """The footer is exactly the trailing `program log off` echo + 3 banner lines."""

    def test_real_capture_pfc7(self):
        """Sample taken from probe_program_log.pfc7.out, case 1."""
        captured = (
            "pfc3d>ball list\n"
            "  Ball      Radius     A/All Contacts  Fixity      Position\n"
            "-------- ------------- --------------- ------- -------------------------------------------\n"
            "       1  5.000000e-01       0/      0         ( 0.000000e+00, 0.000000e+00, 0.000000e+00)\n"
            "       2  5.000000e-01       0/      0         ( 1.000000e+00, 0.000000e+00, 0.000000e+00)\n"
            "pfc3d>program log off\n"
            "**********************************************\n"
            "* Logging ended at Sun May 10 02:03:46 2026\n"
            "**********************************************\n"
        )
        cleaned = _strip_footer(captured)
        assert cleaned.endswith("0.000000e+00)\n")
        assert "program log off" not in cleaned
        assert "Logging ended" not in cleaned
        assert cleaned.startswith("pfc3d>ball list\n")

    def test_real_capture_pfc9(self):
        """PFC 9 has identical footer format (only header version differs)."""
        captured = (
            "pfc3d>model list information\n"
            "Source         Content\n"
            "General                   Job Title : \n"
            "pfc3d>program log off\n"
            "**********************************************\n"
            "* Logging ended at Sun May 10 02:07:47 2026\n"
            "**********************************************\n"
        )
        cleaned = _strip_footer(captured)
        assert "Job Title" in cleaned
        assert "program log off" not in cleaned

    def test_empty_input(self):
        assert _strip_footer("") == ""

    def test_no_footer_returns_unchanged(self):
        """If for some reason the footer marker is absent, don't lose data."""
        text = "pfc3d>ball list\nsome output\n"
        assert _strip_footer(text) == text

    def test_pfc2d_prompt_prefix(self):
        """PFC 2D builds use `pfc2d>` prompt — strip should still work."""
        captured = (
            "pfc2d>ball list\n"
            "  output line 1\n"
            "pfc2d>program log off\n"
            "**********************************************\n"
            "* Logging ended at Sun May 10 02:03:46 2026\n"
            "**********************************************\n"
        )
        cleaned = _strip_footer(captured)
        assert "output line 1" in cleaned
        assert "program log off" not in cleaned

    def test_user_command_mentions_log_off_literally(self):
        """Edge case: user passes a string containing 'program log off' as an
        argument to some other command. The strip should target the LAST
        occurrence (which is our injected log off), not a literal mention
        earlier in the output."""
        captured = (
            "pfc3d>some-cmd 'this string contains program log off literally'\n"
            "actual output of some-cmd\n"
            "pfc3d>program log off\n"
            "**********************************************\n"
            "* Logging ended at Sun May 10 02:03:46 2026\n"
            "**********************************************\n"
        )
        cleaned = _strip_footer(captured)
        # First occurrence (in user's command echo) is preserved
        assert "this string contains program log off literally" in cleaned
        assert "actual output of some-cmd" in cleaned
        # Footer banner is gone
        assert "Logging ended" not in cleaned
