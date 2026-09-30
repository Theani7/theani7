#!/usr/bin/env python3
"""
Generate GitHub contribution grid SVG with numbers inside active cells,
matching the dark-mode aesthetic from user profile.
"""

import argparse
from datetime import datetime, timedelta
import json
import os
import sys
import urllib.request


def fetch_contributions(username, token=None):
    """Fetch contributions via GitHub GraphQL if token present, or fallback to public API."""
    if token:
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                    contributionLevel
                  }
                }
              }
            }
          }
        }
        """
        req_data = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=req_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "Contribution-Numbers-SVG",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                weeks = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                by_date = {}
                level_map = {
                    "NONE": 0,
                    "FIRST_QUARTILE": 1,
                    "SECOND_QUARTILE": 2,
                    "THIRD_QUARTILE": 3,
                    "FOURTH_QUARTILE": 4,
                }
                for w in weeks:
                    for d in w["contributionDays"]:
                        by_date[d["date"]] = {
                            "date": d["date"],
                            "count": d["contributionCount"],
                            "level": level_map.get(d["contributionLevel"], 0),
                        }
                return by_date
        except Exception as e:
            print(f"[Warning] GitHub GraphQL failed: {e}. Falling back to public API...", file=sys.stderr)

    # Fallback to public endpoint
    url = f"https://github-contributions-api.jogruber.de/v4/{username}?y=last"
    req = urllib.request.Request(url, headers={"User-Agent": "Contribution-Numbers-SVG"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        by_date = {c["date"]: c for c in data["contributions"]}
        return by_date


def get_level(count, api_level):
    if count == 0:
        return 0
    if api_level:
        return api_level
    if count >= 60:
        return 4
    if count >= 25:
        return 3
    if count >= 10:
        return 2
    return 1


def render_svg(username, by_date, num_weeks=26, with_cat=False, dark_theme=True):
    # Today's date and align to end of the week (Saturday) or current weekday
    now = datetime.now()
    # Find the current week's Sunday
    # In python weekday: Mon=0, Sun=6. Sunday is (weekday + 1) % 7 days from start of week.
    days_since_sunday = (now.weekday() + 1) % 7
    start_of_current_week = (now - timedelta(days=days_since_sunday)).date()

    # Build weeks array from (now - (num_weeks - 1) weeks)
    start_week = start_of_current_week - timedelta(weeks=num_weeks - 1)

    weeks_data = []
    month_labels = []  # list of (week_idx, month_name)
    last_month = None

    for w in range(num_weeks):
        w_start = start_week + timedelta(weeks=w)
        days = []
        for d in range(7):
            cur_date = w_start + timedelta(days=d)
            ds = cur_date.strftime("%Y-%m-%d")
            # If date is in future, don't show or count 0
            if cur_date > now.date():
                info = {"date": ds, "count": 0, "level": 0, "future": True}
            else:
                raw = by_date.get(ds, {"date": ds, "count": 0, "level": 0})
                info = {
                    "date": ds,
                    "count": raw.get("count", 0),
                    "level": get_level(raw.get("count", 0), raw.get("level", 0)),
                    "future": False,
                }
            days.append(info)

        # Check for month label on the first day of week or month change
        m = w_start.strftime("%b")
        if m != last_month:
            month_labels.append((w, m))
            last_month = m

        weeks_data.append(days)

    # Layout dimensions
    cell_size = 26
    cell_gap = 6
    cell_step = cell_size + cell_gap
    corner_radius = 5

    pad_x = 28
    pad_top = 48
    pad_bottom = 28

    grid_width = num_weeks * cell_step - cell_gap
    grid_height = 7 * cell_step - cell_gap

    svg_width = grid_width + 2 * pad_x
    svg_height = grid_height + pad_top + pad_bottom

    # Color themes
    if dark_theme:
        bg_color = "#0e1117"
        border_color = "#21262d"
        text_month_color = "#8b949e"
        empty_cell_fill = "#161b22"
        empty_cell_stroke = "#21262d"
        # Green levels matching GitHub dark theme
        levels = {
            1: "#0e4429",
            2: "#006d32",
            3: "#26a641",
            4: "#39d353",
        }
        text_colors = {
            1: "#ffffff",
            2: "#ffffff",
            3: "#ffffff",
            4: "#03210d",  # crisp dark text on brightest green for readability
        }
    else:
        bg_color = "#ffffff"
        border_color = "#d0d7de"
        text_month_color = "#57606a"
        empty_cell_fill = "#ebedf0"
        empty_cell_stroke = "#e1e4e8"
        levels = {
            1: "#9be9a8",
            2: "#40c463",
            3: "#30a14e",
            4: "#216e39",
        }
        text_colors = {
            1: "#1b1f24",
            2: "#ffffff",
            3: "#ffffff",
            4: "#ffffff",
        }

    svg_lines = [
        f'<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">',
        f'  <style>',
        f'    .month {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 500; fill: {text_month_color}; }}',
        f'    .count-text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-weight: 600; text-anchor: middle; dominant-baseline: central; }}',
        f'  </style>',
        f'  <rect width="{svg_width}" height="{svg_height}" rx="14" fill="{bg_color}" stroke="{border_color}" stroke-width="1"/>',
    ]

    # Month labels
    for w_idx, month_name in month_labels:
        # Don't place month label too close to the right edge
        if w_idx < num_weeks - 1:
            mx = pad_x + w_idx * cell_step + 4
            my = pad_top - 18
            svg_lines.append(f'  <text x="{mx}" y="{my}" class="month">{month_name}</text>')

    # Grid cells
    for w_idx, week in enumerate(weeks_data):
        x = pad_x + w_idx * cell_step
        for d_idx, day in enumerate(week):
            y = pad_top + d_idx * cell_step
            count = day["count"]
            lvl = day["level"]

            if count > 0 and lvl > 0:
                fill = levels.get(lvl, levels[1])
                svg_lines.append(
                    f'  <rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="{corner_radius}" fill="{fill}"/>'
                )
                text_col = text_colors.get(lvl, "#ffffff")
                font_sz = "10px" if count >= 100 else ("11.5px" if count >= 10 else "12px")
                svg_lines.append(
                    f'  <text x="{x + cell_size/2:.1f}" y="{y + cell_size/2 + 0.5:.1f}" class="count-text" '
                    f'fill="{text_col}" font-size="{font_sz}">{count}</text>'
                )
            else:
                svg_lines.append(
                    f'  <rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="{corner_radius}" '
                    f'fill="{empty_cell_fill}" stroke="{empty_cell_stroke}" stroke-width="1"/>'
                )

    # Optional pixel cat sitting on the grid (matching oneko from screenshot)
    if with_cat:
        # Position sitting around col 16, row 3-4
        cat_x = pad_x + 16 * cell_step - 8
        cat_y = pad_top + 3 * cell_step + 4
        # Pixel cat SVG group
        svg_lines.append(f'  <!-- Pixel Cat (Oneko) -->')
        svg_lines.append(f'  <g transform="translate({cat_x}, {cat_y}) scale(1.6)">')
        # Simple pixel art cat body and ears
        svg_lines.append('    <path d="M4 2h1v1h-1zM11 2h1v1h-1zM3 3h3v1h-3zM10 3h3v1h-3zM3 4h10v1h-10zM2 5h12v1h-12zM2 6h12v1h-12zM2 7h12v1h-12zM3 8h10v1h-10zM4 9h8v1h-8zM5 10h6v1h-6zM3 11h10v1h-10zM2 12h12v1h-12zM1 13h14v1h-14zM1 14h14v1h-14z" fill="#ffffff"/>')
        svg_lines.append('    <path d="M4 1h1v1h-1zM11 1h1v1h-1zM3 2h1v1h-1zM5 2h1v1h-1zM10 2h1v1h-1zM12 2h1v1h-1zM2 3h1v1h-1zM6 3h4v1h-4zM13 3h1v1h-1zM1 4h1v1h-1zM14 4h1v1h-1zM1 5h1v3h-1zM14 5h1v3h-1zM2 8h1v1h-1zM13 8h1v1h-1zM3 9h1v1h-1zM12 9h1v1h-1zM4 10h1v1h-1zM11 10h1v1h-1zM2 11h1v1h-1zM13 11h1v1h-1zM0 12h1v3h-1zM15 12h1v3h-1zM1 15h14v1h-14zM5 5h2v2h-2zM9 5h2v2h-2zM7 7h2v1h-2z" fill="#000000"/>')
        svg_lines.append('  </g>')

    svg_lines.append('</svg>\n')
    return '\n'.join(svg_lines)


def main():
    parser = argparse.ArgumentParser(description="Generate contribution graph SVG with numbers.")
    parser.add_argument("--username", default="Theani7", help="GitHub username")
    parser.add_argument("--weeks", type=int, default=26, help="Number of weeks to show (default: 26)")
    parser.add_argument("--with-cat", action="store_true", help="Include the pixel cat sitting on the grid")
    parser.add_argument("--outdir", default="dist", help="Output directory")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    print(f"Fetching contributions for {args.username}...")
    by_date = fetch_contributions(args.username, token=token)
    print(f"Total days available: {len(by_date)}")

    os.makedirs(args.outdir, exist_ok=True)

    # 1. Dark theme (primary, matching screenshot)
    svg_dark = render_svg(args.username, by_date, num_weeks=args.weeks, with_cat=args.with_cat, dark_theme=True)
    # 2. Light theme
    svg_light = render_svg(args.username, by_date, num_weeks=args.weeks, with_cat=args.with_cat, dark_theme=False)

    # Save SVG outputs
    files_to_save = {
        "github-contribution-grid-numbers-dark.svg": svg_dark,
        "github-contribution-grid-numbers.svg": svg_dark,  # default is dark
        "github-contribution-grid-numbers-light.svg": svg_light,
        # Also save to old snake filenames so existing links update seamlessly
        "github-contribution-grid-snake-dark.svg": svg_dark,
        "github-contribution-grid-snake.svg": svg_dark,
    }

    for filename, content in files_to_save.items():
        path = os.path.join(args.outdir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated: {path}")


if __name__ == "__main__":
    main()
