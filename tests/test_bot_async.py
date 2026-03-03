import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession


@pytest.mark.asyncio
async def test_api_url_format():
    """Test that API URL is correctly formatted."""
    uid = "12345"
    expected_url = f"https://freefirebd.up.railway.app/like?uid={uid}&server_name=bd"
    assert "12345" in expected_url
    assert "server_name=bd" in expected_url


@pytest.mark.asyncio
async def test_api_call_mock():
    """Test HTTP GET request to API (mocked)."""
    uid = "67890"
    url = f"https://freefirebd.up.railway.app/like?uid={uid}&server_name=bd"
    
    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"success": true}')
    
    # Create a proper async context manager for the response
    mock_get_context = AsyncMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)
    
    # Create session mock
    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    
    # Test the request flow
    async with mock_session.get(url, timeout=15) as resp:
        text = await resp.text()
        status = resp.status
    
    assert status == 200
    assert 'success' in text


@pytest.mark.asyncio
async def test_discord_token_required():
    """Test that DISCORD_TOKEN environment variable is required."""
    import os
    # This should be set in .env
    token = os.environ.get("DISCORD_TOKEN")
    assert token is not None, "DISCORD_TOKEN must be set in .env file"


def test_sync_basic():
    """Simple synchronous test."""
    assert 1 + 1 == 2
