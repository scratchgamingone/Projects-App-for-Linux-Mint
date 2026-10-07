"""
API Key Verification Engine for Mint Environment Manager.
Performs non-destructive network validation checks for various developer and system API keys.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TestResult:
    success: bool
    service_id: str
    service_name: str
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    summary: str = ""
    details: str = ""
    account_info: Dict[str, str] = field(default_factory=dict)


SERVICES_CATALOG: List[Tuple[str, str]] = [
    ("auto", "🔍 Auto-Detect Provider"),
    ("steam", "🎮 Steam Web API"),
    ("github", "🐙 GitHub Personal Access Token"),
    ("openai", "🤖 OpenAI API"),
    ("gemini", "♊ Google Gemini API"),
    ("anthropic", "🧠 Anthropic Claude API"),
    ("groq", "⚡ Groq Cloud API"),
    ("realdebrid", "📥 Real-Debrid API"),
    ("huggingface", "🤗 Hugging Face Token"),
    ("discord", "💬 Discord Webhook"),
    ("tmdb", "🎬 The Movie Database (TMDB)"),
    ("weatherapi", "⛅ WeatherAPI"),
    ("mistral", "🌪️ Mistral AI"),
    ("cohere", "🧬 Cohere API"),
    ("custom", "🌐 Custom HTTP Endpoint"),
]


def _make_request(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    data: Optional[bytes] = None,
    timeout: float = 8.0,
) -> Tuple[int, Dict[str, str], str]:
    """Helper using standard library urllib for zero external runtime dependency."""
    req_headers = {"User-Agent": "Mint-Env-Manager/1.0 (Linux Mint)"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = dict(resp.headers.items())
            body = resp.read().decode("utf-8", errors="replace")
            return status, resp_headers, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers.items()), body
    except urllib.error.URLError as e:
        raise ConnectionError(f"Connection failed: {e.reason}")
    except Exception as e:
        raise ConnectionError(f"Network error: {str(e)}")


def test_api_key(
    service_id: str,
    key: str,
    custom_url: Optional[str] = None,
    var_name: str = "",
) -> TestResult:
    """
    Tests an API key against the specified service.
    Returns a structured TestResult with latency, status, and account information.
    """
    key = key.strip()
    if not key:
        return TestResult(
            success=False,
            service_id=service_id,
            service_name="Unknown",
            summary="API key value is empty.",
            details="Please enter a valid API key or token before testing.",
        )

    # Auto-detection
    try:
        from mint_env_manager.env_parser import detect_service
    except ImportError:
        from env_parser import detect_service

    if service_id == "auto":
        detected_id, detected_name, _ = detect_service(var_name, key)
        if detected_id in ("system_path", "generic"):
            return TestResult(
                success=False,
                service_id="unknown",
                service_name="Unrecognized Service",
                summary="Could not auto-detect API service provider.",
                details=f"The variable '{var_name}' does not match standard API key naming patterns. Please select a specific service provider from the dropdown.",
            )
        service_id = detected_id

    start_t = time.perf_counter()

    try:
        if service_id == "steam":
            return _test_steam(key, start_t)
        elif service_id == "github":
            return _test_github(key, start_t)
        elif service_id == "openai":
            return _test_openai(key, start_t)
        elif service_id == "gemini":
            return _test_gemini(key, start_t)
        elif service_id == "anthropic":
            return _test_anthropic(key, start_t)
        elif service_id == "groq":
            return _test_groq(key, start_t)
        elif service_id == "realdebrid":
            return _test_realdebrid(key, start_t)
        elif service_id == "huggingface":
            return _test_huggingface(key, start_t)
        elif service_id == "discord":
            return _test_discord(key, start_t)
        elif service_id == "tmdb":
            return _test_tmdb(key, start_t)
        elif service_id == "weatherapi":
            return _test_weatherapi(key, start_t)
        elif service_id == "mistral":
            return _test_mistral(key, start_t)
        elif service_id == "cohere":
            return _test_cohere(key, start_t)
        elif service_id == "custom":
            return _test_custom(key, custom_url, start_t)
        else:
            return TestResult(
                success=False,
                service_id=service_id,
                service_name=service_id.capitalize(),
                summary=f"Unknown service '{service_id}'",
                details="Selected provider has no test handler implemented.",
            )
    except Exception as e:
        latency = (time.perf_counter() - start_t) * 1000
        return TestResult(
            success=False,
            service_id=service_id,
            service_name=service_id.capitalize(),
            latency_ms=round(latency, 1),
            summary=f"Connection Error: {e}",
            details=f"Failed to reach API endpoint. Please check your internet connection or URL.\n\nError: {e}",
        )


def _test_steam(key: str, start_t: float) -> TestResult:
    url = f"https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/?key={urllib.parse.quote(key)}"
    status, _, body = _make_request(url)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        info = {}
        try:
            data = json.loads(body)
            info["Server Time"] = str(data.get("servertimestring", data.get("servertime", "OK")))
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="steam",
            service_name="Steam Web API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="Steam Web API Key is valid and authorized!",
            details="Successfully queried Steam Web API server information.\nResponse: " + body[:200],
            account_info=info,
        )
    elif status == 403:
        return TestResult(
            success=False,
            service_id="steam",
            service_name="Steam Web API",
            status_code=403,
            latency_ms=round(latency, 1),
            summary="Access Denied (HTTP 403): Invalid Steam Web API Key",
            details="Steam rejected the key. Verify that your 32-character key from https://steamcommunity.com/dev/apikey is entered correctly.",
        )
    else:
        return TestResult(
            success=False,
            service_id="steam",
            service_name="Steam Web API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Steam API returned HTTP {status}",
            details=body[:300],
        )


def _test_github(key: str, start_t: float) -> TestResult:
    url = "https://api.github.com/user"
    headers = {"Authorization": f"Bearer {key}"}
    status, resp_headers, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        info = {}
        try:
            data = json.loads(body)
            info["Username"] = f"@{data.get('login', 'Unknown')}"
            if data.get("name"):
                info["Name"] = data.get("name")
            info["Public Repos"] = str(data.get("public_repos", 0))
            scopes = resp_headers.get("x-oauth-scopes", "None")
            info["Scopes"] = scopes or "Fine-Grained PAT"
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="github",
            service_name="GitHub API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"GitHub Token is valid! Authenticated as {info.get('Username', 'user')}.",
            details=f"Token verified against GitHub REST API v3.\nScopes: {info.get('Scopes', 'N/A')}",
            account_info=info,
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="github",
            service_name="GitHub API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Bad Credentials (HTTP 401): Token invalid or expired",
            details="GitHub returned 401 Bad Credentials. Generate a new token at https://github.com/settings/tokens",
        )
    else:
        return TestResult(
            success=False,
            service_id="github",
            service_name="GitHub API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"GitHub API returned HTTP {status}",
            details=body[:300],
        )


def _test_openai(key: str, start_t: float) -> TestResult:
    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        count = 0
        try:
            data = json.loads(body)
            count = len(data.get("data", []))
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="openai",
            service_name="OpenAI API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"OpenAI API Key is valid! ({count} models available)",
            details="Successfully queried /v1/models endpoint.",
            account_info={"Available Models": str(count)},
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="openai",
            service_name="OpenAI API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Incorrect OpenAI API Key",
            details="Verify key at https://platform.openai.com/api-keys",
        )
    elif status == 429:
        return TestResult(
            success=False,
            service_id="openai",
            service_name="OpenAI API",
            status_code=429,
            latency_ms=round(latency, 1),
            summary="Rate Limited / Quota Exceeded (HTTP 429)",
            details="API Key is valid but quota exceeded or rate limit hit.",
        )
    else:
        return TestResult(
            success=False,
            service_id="openai",
            service_name="OpenAI API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"OpenAI returned HTTP {status}",
            details=body[:300],
        )


def _test_gemini(key: str, start_t: float) -> TestResult:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key)}"
    status, _, body = _make_request(url)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        count = 0
        try:
            data = json.loads(body)
            count = len(data.get("models", []))
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="gemini",
            service_name="Google Gemini API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"Google Gemini API Key is valid! ({count} models found)",
            details="Successfully verified against Google Generative Language API.",
            account_info={"Gemini Models": str(count)},
        )
    elif status in (400, 403):
        return TestResult(
            success=False,
            service_id="gemini",
            service_name="Google Gemini API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Invalid API Key (HTTP {status})",
            details="Google rejected the key. Check API key at https://aistudio.google.com/app/apikey",
        )
    else:
        return TestResult(
            success=False,
            service_id="gemini",
            service_name="Google Gemini API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Gemini API returned HTTP {status}",
            details=body[:300],
        )


def _test_anthropic(key: str, start_t: float) -> TestResult:
    url = "https://api.anthropic.com/v1/models"
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="anthropic",
            service_name="Anthropic Claude API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="Anthropic Claude API Key is valid and active!",
            details="Successfully queried /v1/models.",
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="anthropic",
            service_name="Anthropic Claude API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid Anthropic API Key",
            details="Verify key at https://console.anthropic.com/settings/keys",
        )
    else:
        return TestResult(
            success=False,
            service_id="anthropic",
            service_name="Anthropic Claude API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Anthropic returned HTTP {status}",
            details=body[:300],
        )


def _test_groq(key: str, start_t: float) -> TestResult:
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="groq",
            service_name="Groq Cloud API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="Groq Cloud API Key is valid!",
            details="Successfully queried Groq models endpoint.",
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="groq",
            service_name="Groq Cloud API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid Groq API Key",
            details="Check key at https://console.groq.com/keys",
        )
    else:
        return TestResult(
            success=False,
            service_id="groq",
            service_name="Groq Cloud API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Groq returned HTTP {status}",
            details=body[:300],
        )


def _test_realdebrid(key: str, start_t: float) -> TestResult:
    url = "https://api.real-debrid.com/rest/1.0/user"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        info = {}
        try:
            data = json.loads(body)
            info["User"] = data.get("username", "Unknown")
            info["Status"] = data.get("type", "Free").capitalize()
            info["Expiration"] = str(data.get("expiration", "N/A"))
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="realdebrid",
            service_name="Real-Debrid API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"Real-Debrid Key Valid! User: {info.get('User')} ({info.get('Status')})",
            details=f"Account valid. Expiration: {info.get('Expiration')}",
            account_info=info,
        )
    elif status in (401, 403):
        return TestResult(
            success=False,
            service_id="realdebrid",
            service_name="Real-Debrid API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary="Invalid Real-Debrid API Key",
            details="Generate or check key at https://real-debrid.com/apitoken",
        )
    else:
        return TestResult(
            success=False,
            service_id="realdebrid",
            service_name="Real-Debrid API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Real-Debrid returned HTTP {status}",
            details=body[:300],
        )


def _test_huggingface(key: str, start_t: float) -> TestResult:
    url = "https://huggingface.co/api/whoami-v2"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        info = {}
        try:
            data = json.loads(body)
            info["User"] = data.get("name", "Unknown")
            info["Role"] = data.get("type", "user")
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="huggingface",
            service_name="Hugging Face API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"Hugging Face Token Valid! User: {info.get('User', 'User')}",
            details="Authenticated against /api/whoami-v2.",
            account_info=info,
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="huggingface",
            service_name="Hugging Face API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid HF Token",
            details="Check tokens at https://huggingface.co/settings/tokens",
        )
    else:
        return TestResult(
            success=False,
            service_id="huggingface",
            service_name="Hugging Face API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Hugging Face returned HTTP {status}",
            details=body[:300],
        )


def _test_discord(key: str, start_t: float) -> TestResult:
    # Discord webhook: key should be URL https://discord.com/api/webhooks/...
    webhook_url = key.strip()
    if not webhook_url.startswith("http"):
        return TestResult(
            success=False,
            service_id="discord",
            service_name="Discord Webhook",
            summary="Invalid Webhook URL format",
            details="Value must be a full URL like: https://discord.com/api/webhooks/ID/TOKEN",
        )
    status, _, body = _make_request(webhook_url)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        info = {}
        try:
            data = json.loads(body)
            info["Webhook Name"] = data.get("name", "Unknown")
            info["Guild ID"] = str(data.get("guild_id", "N/A"))
        except Exception:
            pass
        return TestResult(
            success=True,
            service_id="discord",
            service_name="Discord Webhook",
            status_code=200,
            latency_ms=round(latency, 1),
            summary=f"Discord Webhook is active! ({info.get('Webhook Name', 'Connected')})",
            details="Webhook metadata retrieved without triggering channel notifications.",
            account_info=info,
        )
    elif status in (401, 404):
        return TestResult(
            success=False,
            service_id="discord",
            service_name="Discord Webhook",
            status_code=status,
            latency_ms=round(latency, 1),
            summary="Invalid Webhook (HTTP 401/404): Webhook does not exist or has been deleted",
            details="Verify webhook URL in Discord Channel Settings -> Integrations.",
        )
    else:
        return TestResult(
            success=False,
            service_id="discord",
            service_name="Discord Webhook",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Discord returned HTTP {status}",
            details=body[:300],
        )


def _test_tmdb(key: str, start_t: float) -> TestResult:
    url = f"https://api.themoviedb.org/3/authentication?api_key={urllib.parse.quote(key)}"
    status, _, body = _make_request(url)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="tmdb",
            service_name="TMDB API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="TMDB API Key is valid and authenticated!",
            details="The Movie Database (TMDB) API key verified successfully.",
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="tmdb",
            service_name="TMDB API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid TMDB API Key",
            details="Verify key at https://www.themoviedb.org/settings/api",
        )
    else:
        return TestResult(
            success=False,
            service_id="tmdb",
            service_name="TMDB API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"TMDB returned HTTP {status}",
            details=body[:300],
        )


def _test_weatherapi(key: str, start_t: float) -> TestResult:
    url = f"https://api.weatherapi.com/v1/current.json?key={urllib.parse.quote(key)}&q=London"
    status, _, body = _make_request(url)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="weatherapi",
            service_name="WeatherAPI",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="WeatherAPI Key is valid and active!",
            details="Successfully queried WeatherAPI current data.",
        )
    elif status in (401, 403):
        return TestResult(
            success=False,
            service_id="weatherapi",
            service_name="WeatherAPI",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Invalid WeatherAPI Key (HTTP {status})",
            details="Verify key at https://www.weatherapi.com/my/",
        )
    else:
        return TestResult(
            success=False,
            service_id="weatherapi",
            service_name="WeatherAPI",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"WeatherAPI returned HTTP {status}",
            details=body[:300],
        )


def _test_mistral(key: str, start_t: float) -> TestResult:
    url = "https://api.mistral.ai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="mistral",
            service_name="Mistral AI",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="Mistral AI API Key is valid!",
            details="Successfully queried /v1/models.",
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="mistral",
            service_name="Mistral AI",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid Mistral API Key",
            details="Verify key at https://console.mistral.ai/api-keys/",
        )
    else:
        return TestResult(
            success=False,
            service_id="mistral",
            service_name="Mistral AI",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Mistral AI returned HTTP {status}",
            details=body[:300],
        )


def _test_cohere(key: str, start_t: float) -> TestResult:
    url = "https://api.cohere.com/v1/check-api-key"
    headers = {"Authorization": f"Bearer {key}"}
    status, _, body = _make_request(url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if status == 200:
        return TestResult(
            success=True,
            service_id="cohere",
            service_name="Cohere API",
            status_code=200,
            latency_ms=round(latency, 1),
            summary="Cohere API Key is valid!",
            details="Verified against /v1/check-api-key.",
        )
    elif status == 401:
        return TestResult(
            success=False,
            service_id="cohere",
            service_name="Cohere API",
            status_code=401,
            latency_ms=round(latency, 1),
            summary="Unauthorized (HTTP 401): Invalid Cohere API Key",
            details="Verify key at https://dashboard.cohere.com/api-keys",
        )
    else:
        return TestResult(
            success=False,
            service_id="cohere",
            service_name="Cohere API",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Cohere returned HTTP {status}",
            details=body[:300],
        )


def _test_custom(key: str, custom_url: Optional[str], start_t: float) -> TestResult:
    if not custom_url or not custom_url.startswith("http"):
        return TestResult(
            success=False,
            service_id="custom",
            service_name="Custom Endpoint",
            summary="Custom URL is missing or invalid.",
            details="Please enter a valid HTTP/HTTPS endpoint URL to test against.",
        )

    # If URL contains {key}, replace it, otherwise add Authorization header
    headers = {}
    if "{key}" in custom_url:
        target_url = custom_url.replace("{key}", urllib.parse.quote(key))
    else:
        target_url = custom_url
        headers["Authorization"] = f"Bearer {key}"

    status, _, body = _make_request(target_url, headers=headers)
    latency = (time.perf_counter() - start_t) * 1000

    if 200 <= status < 300:
        return TestResult(
            success=True,
            service_id="custom",
            service_name="Custom Endpoint",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Custom Endpoint responded with HTTP {status} OK!",
            details=f"Response snippet:\n{body[:300]}",
        )
    else:
        return TestResult(
            success=False,
            service_id="custom",
            service_name="Custom Endpoint",
            status_code=status,
            latency_ms=round(latency, 1),
            summary=f"Custom Endpoint returned HTTP {status}",
            details=f"Response snippet:\n{body[:300]}",
        )
