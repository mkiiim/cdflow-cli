import pytest
from unittest.mock import Mock, patch
from cdflow_cli.services.auth_service import UnifiedAuthService, AuthState, AuthContext


class TestUnifiedAuthServiceSimple:
    """Simple tests for the authentication service."""
    
    def test_auth_state_creation(self):
        """Test AuthState dataclass creation."""
        state = AuthState(
            is_authenticated=True,
            access_token='test-token',
            expires_at=1234567890
        )
        
        assert state.is_authenticated is True
        assert state.access_token == 'test-token'
        assert state.expires_at == 1234567890
    
    def test_auth_context_enum(self):
        """Test AuthContext enum values."""
        assert AuthContext.CLI.value == 'cli'
        assert AuthContext.API.value == 'api'
        assert AuthContext.TEST.value == 'test'
    
    @pytest.fixture
    def mock_config_provider(self):
        """Mock configuration provider."""
        mock_config = Mock()
        mock_config.get_nationbuilder_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        return mock_config
    
    @patch('cdflow_cli.services.auth_service.NationBuilderOAuth')
    def test_service_creation(self, mock_oauth_class, mock_config_provider):
        """Test service can be created."""
        # Need to mock get_oauth_config to return proper config
        mock_config_provider.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        
        # Mock the OAuth class to avoid initialization issues
        mock_oauth_instance = Mock()
        mock_oauth_class.return_value = mock_oauth_instance
        
        service = UnifiedAuthService(
            config=mock_config_provider,  # Use 'config' not 'config_provider'
            context=AuthContext.CLI
        )
        assert service is not None
        assert service.context == AuthContext.CLI
        # Verify that service was created successfully and OAuth was initialized
        mock_oauth_class.assert_called_once()

    @patch('cdflow_cli.services.auth_service.NationBuilderOAuth')
    def test_service_exposes_token_provider_and_nation_slug(
        self, mock_oauth_class, mock_config_provider
    ):
        """Test shared-core accessors expose token provider and nation slug."""
        mock_config_provider.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'redirect_uri': 'http://localhost:8000/callback',
        }

        mock_oauth_instance = Mock()
        mock_oauth_instance.slug = 'test-nation'
        mock_oauth_instance.token_provider = Mock()
        mock_oauth_class.return_value = mock_oauth_instance

        service = UnifiedAuthService(config=mock_config_provider, context=AuthContext.CLI)

        assert service.get_token_provider() is mock_oauth_instance.token_provider
        assert service.get_nation_slug() == 'test-nation'
        mock_oauth_instance._sync_token_state_from_legacy_attrs.assert_called_once()

    @patch('cdflow_cli.services.auth_service.NationBuilderOAuth')
    def test_invalidate_clears_instance_state(
        self, mock_oauth_class, mock_config_provider
    ):
        """Test invalidate() clears only instance-owned auth state."""
        mock_config_provider.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
        }

        mock_oauth_instance = Mock()
        mock_oauth_instance.token_state = Mock()
        mock_oauth_class.return_value = mock_oauth_instance

        service = UnifiedAuthService(config=mock_config_provider, context=AuthContext.CLI)
        service.invalidate()

        mock_oauth_instance.token_state.clear.assert_called_once()
        assert mock_oauth_instance.nb_jwt_token is None
        assert mock_oauth_instance.nb_refresh_token is None
        assert mock_oauth_instance.nb_token_created_at is None
        assert mock_oauth_instance.nb_token_expires_in is None
