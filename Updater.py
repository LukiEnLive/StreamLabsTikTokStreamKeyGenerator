from _version import __version__
from packaging import version
import requests


class VersionChecker:
    REPO = "LukiEnLive/StreamLabsTikTokStreamKeyGenerator"

    @classmethod
    def check_update(cls):
        try:
            response = requests.get(
                f"https://api.github.com/repos/{cls.REPO}/releases/latest",
                timeout=5
            )
            response.raise_for_status()

            release = response.json()
            latest = release["tag_name"].lstrip("v")

            current_version = version.parse(__version__)
            latest_version = version.parse(latest)

            return {
                "current": __version__,
                "latest": latest,
                "url": release["html_url"],
                "notes": release.get("body", ""),
                "update_available": latest_version > current_version,
            }

        except (requests.RequestException, KeyError, ValueError):
            return None