"""
Tradiesignal :: brand
=====================
One place for the logo, so every page draws the same mark.

The mark is a tick with two signal waves radiating from its tip: "approved,
and here's your lead". The tick takes the text colour of wherever the logo
sits; the waves take --green (lime), so the logo reads correctly on the dark
green nav, masthead and footer without per-page variants.

Palette
  #0E5A3A  brand green   (primary; text-safe on white)
  #C6F04A  lime          (accent; use on dark green, never as text on white)
  #10231A  ink           (body text)
  #0B2A1E  deep green    (nav, masthead, dark sections)
Type
  Schibsted Grotesk (display, logo) / IBM Plex Sans (body) / IBM Plex Mono (data)

Source files (SVG/PNG, profile photo, email signature) live in /brand and are
published at /brand/ by build_site.py.
"""

from __future__ import annotations

from urllib.parse import quote

GREEN = "#0E5A3A"
LIME = "#C6F04A"
INK = "#10231A"
DEEP = "#0B2A1E"

# Tick + waves in a tight viewBox. Tick uses currentColor; waves use --green.
_TICK = ('<path d="M20 54 L38 71 L70 36" fill="none" stroke="currentColor" '
         'stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>')
_WAVES = ('<path d="M68.8 22.05 A14 14 0 0 1 84 36" fill="none" stroke-width="6" '
          'stroke-linecap="round" style="stroke:{w}"/>'
          '<path d="M67.8 11.1 A25 25 0 0 1 95 36" fill="none" stroke-width="6" '
          'stroke-linecap="round" style="stroke:{w}"/>')


def mark_svg(wave: str = f"var(--green,{LIME})", cls: str = "logo-mark", style: str = "") -> str:
    st = f' style="{style}"' if style else ""
    return (f'<svg class="{cls}" viewBox="12 6 88 74" aria-hidden="true" focusable="false"{st}>'
            f'{_TICK}{_WAVES.format(w=wave)}</svg>')


def logo_html(style: str = "") -> str:
    """The inline logo used in navs, mastheads and footers (styled by .logo CSS)."""
    st = f' style="{style}"' if style else ""
    return (f'<span class="logo" role="img" aria-label="Tradiesignal"{st}>'
            f'{mark_svg()}<span aria-hidden="true">tradie<span class="sig">signal</span></span></span>')


# Favicon: white tick and one heavier lime wave on a brand-green tile.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    f"<rect width='100' height='100' rx='22' fill='{GREEN}'/>"
    "<g transform='translate(2.5 13.5) scale(.852)'>"
    "<path d='M20 54 L38 71 L70 36' fill='none' stroke='#fff' stroke-width='13' "
    "stroke-linecap='round' stroke-linejoin='round'/>"
    f"<path d='M67 20 A16 16 0 0 1 86 36' fill='none' stroke='{LIME}' stroke-width='8' "
    "stroke-linecap='round'/></g></svg>"
)
FAVICON = "data:image/svg+xml," + quote(_FAVICON_SVG, safe="/:='")


def apply_logo(html: str) -> str:
    """Swap the %%LOGO%% / %%LOGO|<inline style>%% placeholders the page builders emit."""
    import re
    html = re.sub(r"%%LOGO\|([^%]*)%%", lambda m: logo_html(m.group(1)), html)
    return html.replace("%%LOGO%%", logo_html())
