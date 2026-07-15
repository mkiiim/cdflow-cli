import pytest
from contextlib import nullcontext
from unittest.mock import Mock, patch, MagicMock
from cdflow_cli.services.import_service import DonationImportService
from cdflow_cli.plugins.registry import PluginBundle


class TestDonationImportServiceSimple:
    """Simple tests for the donation import service."""
    
    @pytest.fixture
    def mock_config_provider(self):
        """Mock configuration provider."""
        mock_config = Mock()
        mock_config.get_nationbuilder_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        # Mock logging config to return proper values
        mock_config.get_logging_config.return_value = {
            'file_level': 'DEBUG',
            'console_level': 'INFO'
        }
        # Mock paths configuration
        mock_config.get_app_setting.return_value = './storage'
        return mock_config
    
    def test_init_with_config_provider(self, mock_config_provider):
        """Test initialization with existing config provider."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_paths:
            with nullcontext():
                # Mock paths system
                mock_paths.side_effect = RuntimeError('Not initialized')

                service = DonationImportService(config_provider=mock_config_provider)
                assert service.config == mock_config_provider
                assert service.job_context is None
    
    def test_init_with_job_context(self, mock_config_provider):
        """Test initialization with job context."""
        job_context = {'job_id': 'test-123', 'machine_info': 'test-machine'}
        
        with patch('cdflow_cli.services.import_service.get_paths') as mock_paths:
            with nullcontext():
                # Mock paths system
                mock_paths.side_effect = RuntimeError('Not initialized')

                service = DonationImportService(
                    config_provider=mock_config_provider,
                    job_context=job_context
                )
                assert service.config == mock_config_provider
                assert service.job_context == job_context

    def test_append_row_to_file_filters_plugin_fields(self, mock_config_provider, tmp_path):
        """Test that _append_row_to_file filters out plugin-added fields."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                # Mock paths to use tmp_path
                mock_paths = Mock()
                mock_paths.output = tmp_path
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)

                # Create a row with both regular and plugin fields
                row = {
                    "Name": "John Doe",
                    "Email": "john@example.com",
                    "Amount": "25.00",
                    "_tracking_code": "membership_paypal_monthly",  # Plugin field
                    "_payment_type": "Recurring Credit Card",  # Plugin field
                    "_skip_row": False  # Plugin field
                }

                fieldnames = ["Name", "Email", "Amount"]
                filename = "test_output.csv"

                # Initialize the file first
                service._initialize_output_file(filename, fieldnames, "utf-8")

                # Append the row
                service._append_row_to_file(filename, row, fieldnames, "utf-8")

                # Read the file and verify plugin fields were filtered
                output_file = tmp_path / filename
                content = output_file.read_text(encoding="utf-8")

                # Should contain regular fields
                assert "John Doe" in content
                assert "john@example.com" in content
                assert "25.00" in content

                # Should NOT contain plugin field values
                assert "_tracking_code" not in content
                assert "membership_paypal_monthly" not in content
                assert "_payment_type" not in content
                assert "Recurring Credit Card" not in content
                assert "_skip_row" not in content

    def test_lookup_person_with_plugins_uses_explicit_bundle(self, mock_config_provider):
        """Test that person lookup uses the run-scoped bundle before the global registry."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.people = Mock()

                donation = Mock()
                donation.lookup_person.return_value = (111, True, "default")

                def bundle_lookup(donation_data_row, people_client, default_lookup):
                    return (222, True, "bundle")

                bundle = PluginBundle(
                    adapter="paypal",
                    all_plugins=[("bundle_lookup", bundle_lookup)],
                    by_type={
                        "row_transformer": [],
                        "field_processor": [],
                        "donation_validator": [],
                        "person_lookup": [("bundle_lookup", bundle_lookup)],
                    },
                )

                person_id, success, message = service._lookup_person_with_plugins(
                    donation, "paypal", plugin_bundle=bundle
                )

                assert (person_id, success, message) == (222, True, "bundle")
                donation.lookup_person.assert_not_called()

    def test_lookup_person_with_plugins_falls_back_to_default_when_bundle_empty(
        self, mock_config_provider
    ):
        """Test that empty bundles still fall back to donation default lookup."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.people = Mock()

                donation = Mock()
                donation.lookup_person.return_value = (333, True, "default")

                bundle = PluginBundle(
                    adapter="paypal",
                    all_plugins=[],
                    by_type={
                        "row_transformer": [],
                        "field_processor": [],
                        "donation_validator": [],
                        "person_lookup": [],
                    },
                )

                person_id, success, message = service._lookup_person_with_plugins(
                    donation, "paypal", plugin_bundle=bundle
                )

                assert (person_id, success, message) == (333, True, "default")
                donation.lookup_person.assert_called_once_with(service.people)

    def test_resolve_import_adapter_returns_paypal_mapper_and_bundle(self, mock_config_provider):
        """Test adapter resolution returns the mapper class and run-scoped bundle."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                bundle = PluginBundle(
                    adapter="paypal",
                    all_plugins=[],
                    by_type={
                        "row_transformer": [],
                        "field_processor": [],
                        "donation_validator": [],
                        "person_lookup": [],
                    },
                )

                with patch.object(service, "_load_plugins_if_configured", return_value=bundle):
                    source_type_lower, donation_class, adapter_kwargs, resolved_bundle = (
                        service._resolve_import_adapter("paypal")
                    )

                assert source_type_lower == "paypal"
                assert donation_class.__name__ == "PPDonationMapper"
                assert adapter_kwargs == {}
                assert resolved_bundle is bundle

    def test_ensure_person_record_creates_and_updates_when_lookup_misses(
        self, mock_config_provider
    ):
        """Test person creation/update path remains isolated in the extracted helper."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.people = Mock()
                create_payloads = []

                def create_person_side_effect(payload):
                    create_payloads.append(dict(payload))
                    return (456, True, "created")

                service.people.create_person.side_effect = create_person_side_effect
                service.people.update_person.return_value = (456, True, "updated")

                people_data = {"phone": "555-1212", "email": "jane@example.com"}

                person_id, created_person, message = service._ensure_person_record(
                    None, False, people_data
                )

                assert (person_id, created_person, message) == (456, True, "updated")
                assert create_payloads == [{"phone": "", "email": "jane@example.com"}]
                service.people.update_person.assert_called_once_with(
                    456, {"phone": "555-1212", "email": "jane@example.com"}
                )

    def test_find_or_create_donation_returns_existing_donation(self, mock_config_provider):
        """Test donation helper preserves existing-donation semantics."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.donation = Mock()
                service.donation.get_donationid_by_params.return_value = (
                    789,
                    True,
                    "already exists",
                )

                donation_data = {
                    "succeeded_at": "2025-01-01T17:43:11-05:00",
                    "check_number": "PP_123",
                }

                donation_id, existed, message = service._find_or_create_donation(111, donation_data)

                assert (donation_id, existed, message) == (789, True, "Donation already existed")
                service.donation.create_donation.assert_not_called()

    def test_record_successful_row_writes_ids_and_existing_message(self, mock_config_provider):
        """Test success-row helper writes IDs and only keeps message for existing donations."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                row = {"Email": "john@example.com"}

                with patch.object(service, "_append_row_to_file") as mock_append:
                    service._record_successful_row(
                        "success.csv",
                        row,
                        ["Email", "NB Donation ID", "NB People ID", "NB Error Message"],
                        "utf-8",
                        123,
                        456,
                        "Donation already existed",
                        True,
                    )

                assert row["NB Donation ID"] == 123
                assert row["NB People ID"] == 456
                assert row["NB Error Message"] == "Donation already existed"
                mock_append.assert_called_once()

    def test_handle_processing_failure_deletes_created_person_when_donation_fails(
        self, mock_config_provider
    ):
        """Test failure helper cleans up created people and continues on successful cleanup."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.people = Mock()
                service.people.delete_person.return_value = (True, "deleted")

                row = {"Email": "john@example.com", "NB Error Message": "donation failed"}
                donation_data_row = Mock()
                donation_data_row.data = {}

                with patch.object(service, "_append_row_to_file") as mock_append:
                    should_continue = service._handle_processing_failure(
                        "fail.csv",
                        row,
                        ["Email", "NB Error Message"],
                        "utf-8",
                        donation_data_row,
                        True,
                        False,
                        456,
                        "donation failed",
                    )

                assert should_continue is True
                service.people.delete_person.assert_called_once_with(456)
                mock_append.assert_called_once()

    def test_handle_unexpected_row_failure_records_prefixed_message(self, mock_config_provider):
        """Test unexpected-failure helper writes a prefixed error message."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                row = {"Email": "john@example.com"}

                with patch.object(service, "_append_row_to_file") as mock_append:
                    service._handle_unexpected_row_failure(
                        "fail.csv",
                        row,
                        ["Email", "NB Error Message"],
                        "utf-8",
                        RuntimeError("boom"),
                    )

                assert row["NB Error Message"] == "Unexpected error: boom"
                mock_append.assert_called_once()

    def test_prepare_import_rows_returns_none_when_csv_has_no_rows(self, mock_config_provider):
        """Test import preparation stops cleanly on empty CSV content."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_paths.app_processing = Mock()
                mock_paths.app_processing.__truediv__ = Mock(return_value="ignored.csv")
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                service.config.is_cleanup_enabled = Mock(return_value=False)
                progress_callback = Mock()

                with patch('cdflow_cli.services.import_service.safe_read_text_file', return_value="Email\n"):
                    prepared = service._prepare_import_rows(
                        "ignored.csv",
                        "paypal",
                        "success.csv",
                        "fail.csv",
                        "utf-8",
                        Mock(),
                        progress_callback,
                    )

                assert prepared is None
                progress_callback.assert_called_once_with(100, "No data rows found in file")

    def test_process_single_row_returns_failure_for_invalid_row(self, mock_config_provider):
        """Test single-row processing short-circuits invalid rows."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)
                donation_class = Mock()
                donation_class.validate_row.return_value = (False, "bad row")
                row = {"Email": "bad@example.com"}

                with patch.object(service, "_record_failed_row") as mock_record_failed:
                    row_succeeded, should_continue = service._process_single_row(
                        row,
                        1,
                        "paypal",
                        donation_class,
                        {},
                        PluginBundle(
                            adapter="paypal",
                            all_plugins=[],
                            by_type={
                                "row_transformer": [],
                                "field_processor": [],
                                "donation_validator": [],
                                "person_lookup": [],
                            },
                        ),
                        "success.csv",
                        "fail.csv",
                        ["Email", "NB Error Message"],
                        "utf-8",
                        Mock(),
                    )

                assert (row_succeeded, should_continue) == (False, True)
                mock_record_failed.assert_called_once()

    @patch('cdflow_cli.services.import_service.NBDonation')
    @patch('cdflow_cli.services.import_service.NBPeople')
    def test_initialize_api_clients_uses_auth_service_token_provider(
        self, mock_people_class, mock_donation_class, mock_config_provider
    ):
        """Test interactive initialization consumes the auth-service token provider seam."""
        mock_config_provider.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'redirect_uri': 'http://localhost:8000/callback',
        }

        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                with patch('cdflow_cli.services.import_service.create_cli_auth_service') as mock_create_auth_service:
                    mock_paths = Mock()
                    mock_get_paths.return_value = mock_paths

                    mock_token_provider = Mock()
                    mock_auth_service = Mock()
                    mock_auth_service.authenticate.return_value = True
                    mock_auth_service.get_token_provider.return_value = mock_token_provider
                    mock_auth_service.get_nation_slug.return_value = 'test-nation'
                    mock_auth_service.get_oauth_instance.return_value = Mock()
                    mock_create_auth_service.return_value = mock_auth_service

                    mock_donation = Mock()
                    mock_donation.detect_custom_donation_fields.return_value = {
                        'import_job_id': True,
                        'import_job_source': True,
                    }
                    mock_donation_class.return_value = mock_donation

                    service = DonationImportService(config_provider=mock_config_provider)

                    result = service.initialize_api_clients()

                assert result is True
                mock_create_auth_service.assert_called_once()
                mock_auth_service.authenticate.assert_called_once()
                mock_people_class.assert_called_once_with(token_provider=mock_token_provider)
                mock_donation_class.assert_called_once_with(token_provider=mock_token_provider)
                assert service.token_provider is mock_token_provider
                assert service.nation_slug == 'test-nation'

    @patch('cdflow_cli.services.import_service.NBDonation')
    @patch('cdflow_cli.services.import_service.NBPeople')
    def test_initialize_api_clients_with_tokens_uses_token_provider(
        self, mock_people_class, mock_donation_class, mock_config_provider
    ):
        """Test token-seeded initialization builds API clients from a shared-core token provider."""
        mock_config_provider.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'redirect_uri': 'http://localhost:8000/callback',
        }

        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with nullcontext():
                mock_paths = Mock()
                mock_get_paths.return_value = mock_paths

                mock_people = Mock()
                mock_people.get_person_by_id.side_effect = Exception('404 Not Found')
                mock_people_class.return_value = mock_people

                mock_donation = Mock()
                mock_donation.detect_custom_donation_fields.return_value = {
                    'import_job_id': False,
                    'import_job_source': False,
                }
                mock_donation_class.return_value = mock_donation

                service = DonationImportService(config_provider=mock_config_provider)
                oauth_tokens = {
                    'access_token': 'test-token',
                    'refresh_token': 'refresh-token',
                    'expires_in': 3600,
                    'created_at': 1234567890.0,
                }

                result = service.initialize_api_clients_with_tokens(oauth_tokens)

                assert result is True
                assert service.token_provider is not None
                assert service.nation_slug == 'test-nation'
                mock_people_class.assert_called_once()
                mock_donation_class.assert_called_once()
                assert mock_people_class.call_args.kwargs['token_provider'] is service.token_provider
                assert mock_donation_class.call_args.kwargs['token_provider'] is service.token_provider
