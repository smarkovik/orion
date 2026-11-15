"""User-agent classification for reader stats: (device, os, browser) from the raw CloudFront log field."""

import re
from urllib.parse import unquote_plus

ENCODED = re.compile(r"%2[0-9A-Fa-f]")
# first match wins
BROWSERS = (
    ("Facebook app", re.compile(r"FBAN|FBAV|FB_IAB")),
    ("Instagram app", re.compile(r"Instagram")),
    ("Edge", re.compile(r"Edg/|EdgA/|EdgiOS/")),
    ("Opera", re.compile(r"OPR/|OPiOS/")),
    ("Samsung Internet", re.compile(r"SamsungBrowser/")),
    ("Firefox", re.compile(r"Firefox/|FxiOS/")),
    ("Chrome", re.compile(r"Chrome/|CriOS/")),
)
OSES = (
    ("Windows", re.compile(r"Windows")),
    ("ChromeOS", re.compile(r"CrOS")),
    ("macOS", re.compile(r"Macintosh")),
    ("Linux", re.compile(r"Linux|X11")),
)
IOS = re.compile(r"iPhone|iPod|iPad")


def _decode(ua: str) -> str:
    ua = unquote_plus(ua)
    return unquote_plus(ua) if ENCODED.search(ua) else ua


def classify(ua: str, touch_mac: bool) -> tuple[str, str, str]:
    """Return (device, os, browser); touch_mac marks an iPad that reports a Mac user agent."""
    ua = _decode(ua)
    mac_ipad = touch_mac and "Macintosh" in ua
    if re.search(r"iPhone|iPod", ua):
        device, os_ = "phone", "iOS"
    elif "iPad" in ua or mac_ipad:
        device, os_ = "tablet", "iPadOS"
    elif "Android" in ua:
        device, os_ = ("phone" if "Mobile" in ua else "tablet"), "Android"
    else:
        device = "tablet" if "Tablet" in ua else "phone" if re.search(r"Mobile|Windows Phone", ua) else "desktop"
        os_ = next((name for name, rx in OSES if rx.search(ua)), "Other")
    browser = next((name for name, rx in BROWSERS if rx.search(ua)), "")
    if not browser:
        browser = "Safari" if ("Safari/" in ua and "Version/" in ua) or IOS.search(ua) or mac_ipad else "Other"
    return device, os_, browser
