"""
Example usage of Ultimate Terminal.
"""

from ultimate_terminal import (
    terminal as term,
    RGB,
    Style,
)


# ============================================================================
# BASIC
# ============================================================================

term.banner("XANDEV TERMINAL")

term.success("System initialized")
term.info("Checking environment...")
term.warning("Development mode enabled")
term.error("Example error message")
term.debug("Debug information")
term.trace("Trace information")


# ============================================================================
# THEMES
# ============================================================================

term.section("THEMES")

for theme in (
    "cyber",
    "purple",
    "matrix",
    "ocean",
    "fire",
    "royal",
    "neon",
):
    term.set_theme(theme)
    term.print(
        f"{theme.upper():<10}",
        style="primary",
    )
    term.print(
        "This is the active theme.",
        style="text",
    )


term.set_theme("cyber")


# ============================================================================
# GRADIENTS
# ============================================================================

term.section("GRADIENTS")

term.print(term.gradient("CYBER", "cyber"))
term.print(term.gradient("SUNSET", "sunset"))
term.print(term.gradient("OCEAN", "ocean"))
term.print(term.gradient("FIRE", "fire"))
term.print(term.gradient("MATRIX", "matrix"))
term.print(term.rainbow("RAINBOW"))


# ============================================================================
# STYLES
# ============================================================================

term.section("STYLES")

for name in [
    "primary",
    "secondary",
    "accent",
    "success",
    "error",
    "warning",
    "info",
    "gold",
    "cyan",
    "magenta",
    "lime",
    "teal",
    "muted",
    "command",
    "code",
]:
    term.print(
        f"{name:<18} Example text",
        style=name,
    )


# ============================================================================
# BADGES
# ============================================================================

term.section("BADGES")

term.print(
    term.badge("ONLINE", "success"),
    " ",
    term.badge("WARNING", "warning"),
    " ",
    term.badge("ERROR", "error"),
    " ",
    term.badge("INFO", "info"),
)


# ============================================================================
# PANEL
# ============================================================================

term.section("PANEL")

term.panel(
    [
        "Application: XanDev",
        "Version: 2.0.0",
        "Environment: Development",
        "Status: ONLINE",
        "Terminal: TrueColor",
    ],
    title="SYSTEM INFORMATION",
)


# ============================================================================
# TABLE
# ============================================================================

term.section("TABLE")

term.table(
    [
        ["Python", "3.12", "Installed"],
        ["GPU", "GTX 1650", "Detected"],
        ["Terminal", "TrueColor", "Enabled"],
        ["Theme", "Cyber", "Active"],
    ],
    headers=["Component", "Value", "Status"],
)


# ============================================================================
# PROGRESS
# ============================================================================

term.section("PROGRESS")

term.progress(
    72,
    total=100,
    label="Loading",
    width=40,
)

term.animate_progress(
    total=100,
    label="Building",
    width=40,
    duration=1.5,
)


# ============================================================================
# ANIMATIONS
# ============================================================================

term.section("ANIMATIONS")

term.spinner(
    "Loading modules",
    frames="dots",
    duration=1.5,
)

term.spinner(
    "Scanning files",
    frames="scan",
    duration=1.5,
)

term.spinner(
    "Connecting",
    frames="circle",
    duration=1.5,
)


term.dots(
    "Processing",
    duration=1.5,
)

term.scanner(
    "Scanning",
    duration=1.5,
)


# ============================================================================
# TYPEWRITER
# ============================================================================

term.section("TYPEWRITER")

term.typewrite(
    "Initializing advanced terminal interface...",
    delay=.02,
    style="primary",
)


# ============================================================================
# PULSE
# ============================================================================

term.section("PULSE")

term.pulse(
    "SYSTEM READY",
    cycles=4,
    style="success",
)


# ============================================================================
# RAINBOW ANIMATION
# ============================================================================

term.section("RAINBOW ANIMATION")

term.rainbow_animation(
    "ULTIMATE TERMINAL",
    cycles=2,
)


# ============================================================================
# MARQUEE
# ============================================================================

term.section("MARQUEE")

term.marquee(
    "Welcome to the Ultimate Terminal System",
    width=45,
    cycles=1,
    style="cyber",
)


# ============================================================================
# COUNTDOWN
# ============================================================================

term.section("COUNTDOWN")

term.countdown(
    3,
    label="Launching in",
)


# ============================================================================
# LIVE SPINNER CONTEXT
# ============================================================================

term.section("BACKGROUND SPINNER")

with term.live_spinner(
    "Performing operation",
    frames="dots",
):
    import time
    time.sleep(2)


# ============================================================================
# CUSTOM RGB
# ============================================================================

term.section("CUSTOM RGB")

custom = Style(
    foreground=RGB.from_hex("#FF00FF"),
    background=RGB.from_hex("#101010"),
    bold=True,
    italic=True,
    underline=True,
)

term.print(
    "CUSTOM MAGENTA STYLE",
    style=custom,
)


# ============================================================================
# LOGGING
# ============================================================================

term.section("LOGGING")

term.log("DEBUG", "Debug message")
term.log("TRACE", "Trace message")
term.log("INFO", "Information message")
term.log("SUCCESS", "Operation succeeded")
term.log("WARNING", "Warning message")
term.log("ERROR", "Error message")
term.log("CRITICAL", "Critical message")


term.separator()
term.success("Demo complete.")
