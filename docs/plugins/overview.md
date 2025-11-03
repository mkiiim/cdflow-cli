# DonationFlow CLI Plugin Examples

This directory contains example plugins demonstrating the DonationFlow CLI plugin system.

## What are Plugins?

Plugins allow you to customize donation data processing without modifying the core DonationFlow CLI code. They execute at different stages of the import process:

- **row_transformer**: Transform CSV data during mapper initialization (dictionary phase)
- **field_processor**: Process individual fields during parsing (future, not implemented)
- **donation_validator**: Validate/modify complete donation objects (future, not implemented)

### Execution Phases

**Dictionary Phase (row_transformer):**
- Executes during `DonationMapper.__init__()` before object construction completes
- Works with row data as a dictionary (Python `dict`)
- Can read/modify dictionary entries
- Can add underscore fields (`_field_name`) that mappers will consume
- Cannot access mapper object properties (they don't exist yet)
- This is where plugins set business logic fields via underscore convention

**Object Phase (field_processor, donation_validator - future):**
- Would execute after mapper object is fully constructed
- Would work with `DonationMapper` object and its `NBfield_name` properties
- Would have full access to all NationBuilder fields
- Not yet implemented

## Installation

Plugin examples are automatically copied when you run `cdflow init`:

```bash
cdflow init
```

This creates:
- `~/.config/cdflow/plugins/canadahelps/` - CanadaHelps plugin examples
- `~/.config/cdflow/plugins/paypal/` - PayPal plugin examples

All plugin files start with `_` prefix (disabled by default). To enable a plugin, remove the `_` prefix:

```bash
# Example: Enable the eligibility filter plugin
cd ~/.config/cdflow/plugins/canadahelps/
mv _99_eligibility_filter.py 99_eligibility_filter.py
```

Then configure plugins in your `~/.config/cdflow/local.yaml`:

```yaml
plugins:
  canadahelps:
    enabled: true
    dir: "~/.config/cdflow/plugins/canadahelps"
  paypal:
    enabled: true
    dir: "~/.config/cdflow/plugins/paypal"
```

## Available Examples

### CanadaHelps Plugins (`cdflow_cli/examples/plugins/canadahelps/`)

#### `00_check_number_formatter.py`
Formats check numbers with "CH_" prefix using the transaction number field.

#### `10_anonymous_email.py`
Handles anonymous donor emails. Sets custom email addresses for anonymous CanadaHelps donations.

#### `20_tracking_code_mapper.py`
Maps donations to tracking codes based on MONTHLY GIFT ID field. Monthly donations get a different tracking code than one-time donations.

#### `30_payment_type_mapper.py`
Maps CanadaHelps payment methods to NationBuilder payment types (e.g., "ApplePay" → "Apple Pay", "Cheque" → "Check").

#### `40_sanitize_anon_fields.py`
Replaces all "ANON" values with empty strings. CanadaHelps uses "ANON" to mark anonymous donor information.

#### `99_eligibility_filter.py`
Filters ineligible donations. Sets `_skip_row` flag for records missing receiptable amount or missing both name and email.

### PayPal Plugins (`cdflow_cli/examples/plugins/paypal/`)

#### `00_check_number_formatter.py`
Formats check numbers with "PP_" prefix using the transaction ID field.

#### `10_external_id_lookup.py`
Person lookup by external ID for PayPal transactions.

#### `20_tracking_code_mapper.py`
Maps Item Title to tracking codes using substring matching (e.g., "month" → membership_paypal_monthly).

#### `30_payment_type_mapper.py`
Maps PayPal transaction types to NationBuilder payment types.

#### `99_eligibility_filter.py`
Filters ineligible donations. Sets `_skip_row` flag for duplicate records (Custom Number populated) or records missing both name and email.

## Creating Your Own Plugins

### Basic Template

```python
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def my_custom_plugin(row_data: dict) -> dict:
    """
    Describe what your plugin does.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data
    """
    # Your transformation logic here

    return row_data
```

### Plugin Types

**row_transformer** - Transforms raw CSV row data before parsing
```python
@register_plugin("canadahelps", "row_transformer")
def my_transformer(row_data: dict) -> dict:
    # Modify row_data dictionary
    return row_data
```

**field_processor** *(coming soon)* - Processes individual field values
```python
@register_plugin("canadahelps", "field_processor")
def my_processor(field_name: str, value: any, row_data: dict) -> any:
    # Modify specific field value
    return value
```

**donation_validator** *(coming soon)* - Validates/modifies complete donation objects
```python
@register_plugin("canadahelps", "donation_validator")
def my_validator(donation: DonationMapper) -> DonationMapper:
    # Validate or modify donation object
    return donation
```

## Plugin Execution

- Plugins execute in **alphabetical order** by filename
- Use numeric prefixes (`00_`, `10_`, `20_`, etc.) to control execution order
- Disable plugins by prefixing filename with underscore (e.g., `_99_eligibility_filter.py`)
- Example plugins from `cdflow init` start disabled with `_` prefix - remove `_` to enable

### Recommended Ordering Convention

**00-09**: Special operations (formatting, person lookup, etc.)
**10-89**: Data transformations (tracking codes, payment types, field mapping)
**90-99**: Filtering/validation (eligibility checks, _skip_row flags)

Example:
```
00_check_number_formatter.py # Format: standardize check numbers
10_external_id_lookup.py     # Lookup: person by external ID
20_tracking_code_mapper.py   # Transform: set tracking code
30_payment_type_mapper.py    # Transform: set payment type
40_sanitize_anon_fields.py   # Transform: clean anonymous fields
99_eligibility_filter.py     # Filter: skip ineligible records (LAST)
```

**Why this order?** Transform data first, then filter. This is more efficient and ensures filtering decisions are based on complete, transformed data.

### Plugin-to-Mapper Communication API

Plugins communicate with mappers through an **underscore field convention**. This is an intentional API contract where plugins set `_field_name` entries in the row dictionary, and the mapper base class consumes them to populate corresponding `NBfield_name` properties.

#### Business Logic Fields

These underscore fields map directly to NationBuilder donation fields:

| Plugin Sets | Mapper Reads As | Purpose |
|-------------|----------------|---------|
| `_check_number` | `NBcheck_number` | Formatted check/transaction number |
| `_payment_type` | `NBpayment_type_name` | Payment type (e.g., "Check", "Apple Pay") |
| `_tracking_code` | `NBtracking_code_slug` | Campaign tracking code |

**Example:**
```python
# Plugin sets underscore field
row_data["_check_number"] = f"CH_{transaction_number}"

# Base class reads it (donation.py line 77)
self.NBcheck_number = data.get("_check_number", "")
```

#### Control Fields

These fields control import processing behavior:

- `_skip_row`: Set to `True` to mark record as ineligible (skips donation creation)
- `_skip_reason`: Detailed reason for skipping (logged in fail file)

#### Important Notes

- **Underscore fields are intentional**: Plugins explicitly know they're providing values for NationBuilder fields
- **Fields are filtered**: Underscore fields don't appear in CSV output files
- **Execution timing**: Plugins run during mapper initialization, before the mapper object is fully constructed
- **Dictionary phase**: Plugins work with the row dictionary; they cannot access mapper object properties or methods

## Tips

- **Keep plugins simple** - One plugin should do one thing well
- **Handle errors gracefully** - Plugin errors are logged but don't stop the import
- **Test with small datasets** first before running on production data
- **Document your plugins** - Future you will thank you

## Adapter Support

Currently supported adapters:
- `canadahelps`
- `paypal`

Each adapter has its own plugins directory.

## Need Help?

- Check the [main documentation](../../docs/)
- Review the example plugins in this directory
- Test plugins with a small CSV file first
