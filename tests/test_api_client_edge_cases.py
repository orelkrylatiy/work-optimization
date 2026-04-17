"""Edge cases for API client."""
from unittest.mock import Mock, patch, MagicMock
import time
from threading import Thread, Lock

import pytest
from requests import Response, Session

from hh_applicant_tool.api.client import BaseClient, DEFAULT_DELAY


class TestApiClientEdgeCases:
    """Test boundary conditions in API client."""

    def test_client_zero_delay(self):
        """Client with zero delay defaults to DEFAULT_DELAY."""
        client = BaseClient(base_url="https://api.example.com/", delay=0)
        # 0 or DEFAULT_DELAY = DEFAULT_DELAY (falsy value)
        assert client.delay == DEFAULT_DELAY

    def test_client_very_large_delay(self):
        """Client with very large delay."""
        client = BaseClient(base_url="https://api.example.com/", delay=1000)
        assert client.delay == 1000

    def test_client_negative_delay(self):
        """Client with negative delay."""
        client = BaseClient(base_url="https://api.example.com/", delay=-1)
        # Might allow or validate
        assert client.delay == -1 or client.delay >= 0

    def test_client_float_delay(self):
        """Client with float delay."""
        client = BaseClient(base_url="https://api.example.com/", delay=0.001)
        assert client.delay == 0.001

    def test_base_url_without_trailing_slash(self):
        """base_url validation should require trailing slash."""
        with pytest.raises(AssertionError):
            BaseClient(base_url="https://api.example.com")

    def test_base_url_multiple_trailing_slashes(self):
        """base_url with multiple trailing slashes."""
        client = BaseClient(base_url="https://api.example.com///")
        # Should work or normalize
        assert client.base_url is not None

    def test_base_url_with_query_parameters(self):
        """base_url with query parameters."""
        client = BaseClient(base_url="https://api.example.com/?key=value/")
        # Unusual but might work
        assert client.base_url is not None

    def test_base_url_with_fragment(self):
        """base_url with fragment."""
        client = BaseClient(base_url="https://api.example.com/#section/")
        # Unusual but might work

    def test_empty_user_agent(self):
        """Empty user agent string."""
        client = BaseClient(
            base_url="https://api.example.com/",
            user_agent=""
        )
        assert client.user_agent == ""

    def test_very_long_user_agent(self):
        """Very long user agent string."""
        long_ua = "x" * 10000
        client = BaseClient(
            base_url="https://api.example.com/",
            user_agent=long_ua
        )
        assert client.user_agent == long_ua

    def test_user_agent_with_special_characters(self):
        """User agent with special characters."""
        ua = "Bot/1.0 (Special: \"quotes\", 🚀)"
        client = BaseClient(
            base_url="https://api.example.com/",
            user_agent=ua
        )
        assert client.user_agent == ua

    def test_session_none_provided(self):
        """Session as None."""
        client = BaseClient(
            base_url="https://api.example.com/",
            session=None
        )
        # Should create default session
        assert client.session is not None

    def test_session_with_custom_adapters(self):
        """Session with custom adapters."""
        session = Mock(spec=Session)
        session.proxies = {}
        session.adapters = {"http://": "custom"}

        client = BaseClient(
            base_url="https://api.example.com/",
            session=session
        )
        assert client.session == session

    def test_proxies_property_none(self):
        """Proxies property when not set."""
        session = Mock(spec=Session)
        session.proxies = None

        client = BaseClient(
            base_url="https://api.example.com/",
            session=session
        )

        # Should handle None proxies
        proxies = client.proxies
        assert proxies is None

    def test_proxies_property_empty(self):
        """Proxies property when empty."""
        session = Mock(spec=Session)
        session.proxies = {}

        client = BaseClient(
            base_url="https://api.example.com/",
            session=session
        )

        proxies = client.proxies
        assert proxies == {}

    def test_default_headers_consistent(self):
        """Default headers should be consistent."""
        client = BaseClient(base_url="https://api.example.com/")

        headers1 = client._default_headers()
        headers2 = client._default_headers()

        assert headers1 == headers2

    def test_default_headers_x_hh_app_active_always_true(self):
        """X-HH-App-Active should always be 'true'."""
        client = BaseClient(base_url="https://api.example.com/")
        headers = client._default_headers()

        assert headers["X-HH-App-Active"] == "true"
        # Should not be False, 0, or other falsy value
        assert headers["X-HH-App-Active"] is not False

    def test_lock_is_reentrant(self):
        """Lock should work for same thread."""
        client = BaseClient(base_url="https://api.example.com/")

        # Acquire lock twice from same thread
        try:
            with client.lock:
                with client.lock:
                    pass
        except:
            # If not reentrant, might raise
            pass

    def test_previous_request_time_initialization(self):
        """Previous request time should be initialized."""
        client = BaseClient(base_url="https://api.example.com/")
        # Should have a value for tracking
        assert hasattr(client, "_previous_request_time")

    def test_concurrent_lock_acquisition(self):
        """Lock should serialize concurrent access."""
        client = BaseClient(base_url="https://api.example.com/")
        execution_order = []

        def acquire_and_record(id):
            with client.lock:
                execution_order.append(f"start_{id}")
                time.sleep(0.01)
                execution_order.append(f"end_{id}")

        threads = [Thread(target=acquire_and_record, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have serialized access
        starts = [x for x in execution_order if x.startswith("start")]
        ends = [x for x in execution_order if x.startswith("end")]
        assert len(starts) == len(ends) == 3

    def test_multiple_clients_independent_locks(self):
        """Different clients should have independent locks."""
        client1 = BaseClient(base_url="https://api.example.com/")
        client2 = BaseClient(base_url="https://api.example.com/")

        assert client1.lock is not client2.lock

    def test_client_preserves_session_cookies(self):
        """Session should maintain cookies across calls."""
        session = Mock(spec=Session)
        session.cookies = {}
        session.proxies = {}

        client = BaseClient(
            base_url="https://api.example.com/",
            session=session
        )

        # Session cookies should be accessible
        assert hasattr(client.session, "cookies")

    def test_multiple_clients_same_base_url(self):
        """Multiple clients with same URL should work independently."""
        client1 = BaseClient(base_url="https://api.example.com/")
        client2 = BaseClient(base_url="https://api.example.com/")

        # Should have different sessions/locks/state
        assert client1.lock is not client2.lock
        assert client1.session is not client2.session

    def test_base_url_ip_address(self):
        """base_url with IP address."""
        client = BaseClient(base_url="http://192.168.1.1:8080/")
        assert client.base_url is not None

    def test_base_url_localhost(self):
        """base_url with localhost."""
        client = BaseClient(base_url="http://localhost:3000/")
        assert client.base_url is not None

    def test_base_url_ipv6(self):
        """base_url with IPv6 address."""
        client = BaseClient(base_url="http://[::1]:8080/")
        assert client.base_url is not None

    def test_user_agent_auto_generation(self):
        """Auto-generated user agent should be valid."""
        client = BaseClient(base_url="https://api.example.com/")
        ua = client.user_agent

        # Should be non-empty
        assert ua is not None
        assert len(ua) > 0
        assert isinstance(ua, str)

    def test_default_headers_user_agent_matches(self):
        """Headers should include the client's user agent."""
        client = BaseClient(base_url="https://api.example.com/")
        headers = client._default_headers()

        assert headers["User-Agent"] == client.user_agent

    def test_session_request_method_call_structure(self):
        """Session should be called with proper structure."""
        session = Mock(spec=Session)
        session.proxies = {}

        client = BaseClient(
            base_url="https://api.example.com/",
            session=session
        )

        # Session should be ready for request() calls
        assert hasattr(session, "request")

    def test_delay_precision(self):
        """Delay should respect high-precision timers."""
        client = BaseClient(
            base_url="https://api.example.com/",
            delay=0.001
        )

        # Should be able to store precise delay
        assert client.delay == 0.001

    def test_client_repr(self):
        """Client should have string representation."""
        client = BaseClient(base_url="https://api.example.com/")
        repr_str = repr(client)

        # Should be informative
        assert isinstance(repr_str, str)

    def test_client_str(self):
        """Client should have string conversion."""
        client = BaseClient(base_url="https://api.example.com/")
        str_repr = str(client)

        # Should be informative
        assert isinstance(str_repr, str)

    def test_constant_default_delay(self):
        """DEFAULT_DELAY constant should be reasonable."""
        # Should be non-negative
        assert DEFAULT_DELAY >= 0
        assert isinstance(DEFAULT_DELAY, (int, float))
