# cæstudy. DonationFlow CLI

A command-line bridge for importing external donation data into NationBuilder with auditable output, source-specific adapters, and safe rollback support.

- **Purpose** — Move CanadaHelps and PayPal exports into NationBuilder without rebuilding your upstream payment workflow.
- **Architecture** — Adapters map source exports, plugins encode organization rules, and job artifacts preserve an audit trail.
- **Operational posture** — Verbose logging, success and fail CSVs, and rollback tooling make import runs inspectable rather than opaque.

DonationFlow CLI is a command-line tool for importing donation data from external sources like CanadaHelps and PayPal into your NationBuilder account. It is designed to be a bridge for organizations that use payment processors not natively integrated with NationBuilder, or for those migrating from other CRM platforms.

DonationFlow CLI is extensible to other payment processor sources through an existing adapter template and a plugin architecture through which organization-specific business rules can be implemented.

DonationFlow CLI was originally developed to help a non-profit charitable organization successfully migrate their donation data from CiviCRM and integrate their existing PayPal and CanadaHelps workflows with NationBuilder.

## System Profile

**Core capabilities**

- **Import from External Sources:** Import donation data from CanadaHelps and PayPal CSV exports.
- **Extensible Design:** Adapt to other payment platforms using the generic adapter and plugin hooks. Plugins are enabled per adapter through an explicit `plugins.yaml` whitelist beside the plugin files — filenames carry no enabled/disabled meaning.
- **Detailed Logging:** Human-readable console output plus a single rotating log file capture every import job operation for troubleshooting and auditing; on macOS, `--log-os-log` mirrors logs to Console.app.
- **Rollback Capable:** Remove imported transactions when a run needs to be reversed.

**Typical use case** — Use DonationFlow when your fundraising data originates outside NationBuilder but needs to land there with repeatable transforms, deterministic outputs, and a paper trail that operations staff can review later.

## Prerequisites

- Python 3.9+
- A NationBuilder account with API access.
- A configured NationBuilder OAuth application.
- Donation data exported as CSV files from CanadaHelps or PayPal.

## Installation

Create an environment and activate

```bash
python3 -m venv <my-environment-name>
source <my-environment-name>/bin/activate
```

Install using PIP

```bash
pip install cdflow-cli
```

For development installation, please see the [Contribution Guide](https://mkiiim.github.io/cdflow-cli/contributing/).

## Quick Start

1.  **Initialize configuration:** Run `cdflow init` to create template files:

    - `~/.config/caestudy/local.yaml` - Main configuration file (default location)
    - `~/.env/nb_local.env` - OAuth environment variables template (non-configurable location)

2.  **Configure OAuth credentials:** Edit `~/.env/nb_local.env` with your NationBuilder OAuth credentials, then load:

    ### Locate the `load-secrets.sh` script

    ```bash
    python3 -c "import cdflow_cli; from pathlib import Path; print(Path(cdflow_cli.__file__).parent / 'scripts' / 'load-secrets.sh')"
    ```

    ### Execute the script using your `.env` file as the parameter

    ```bash
    source /path/printed/above/load-secrets.sh ~/.env/nb_local.env
    ```

3.  **Update the import configuration:** In your configuration file (e.g., `local.yaml`), update the `cli_import` section to point to your CSV file(s).

4.  **Place your CSV file:** Put your CanadaHelps or PayPal CSV file in the `cli_source` directory you specified in your configuration.

5.  **Run the import:**

    ```bash
    cdflow import --config /path/to/your/local.yaml
    ```

    Or with less verbose output

    ```bash
    cdflow import --config /path/to/your/local.yaml --log-level NOTICE
    ```

    **Alternative: Override import settings via CLI flags**

    You can override the import type and file path from the config using CLI flags:

    ```bash
    # Override with relative path
    cdflow import --type canadahelps --file donations/emergency.csv --config /path/to/your/local.yaml
    # Override with absolute path
    cdflow import --type paypal --file /tmp/paypal_donations.csv --config /path/to/your/local.yaml
    ```

6.  **Review the results:** The tool will provide real-time feedback in the console. After the import is complete, you can review the results in the `output` directory you specified in your configuration.

    - `_success.csv`: This file contains all the records that were successfully imported, along with the new NationBuilder Person ID and Donation ID.
    - `_fail.csv`: This file contains any records that failed to import, along with any error message(s) in the `NB Error Message` column.

7.  **Verify in NationBuilder:** Log in to your NationBuilder account and navigate to the Finances section. You should see the newly imported donations in your transaction list.

## Documentation

For more detailed information on configuration, usage, plugins, and troubleshooting, please see the full documentation at [mkiiim.github.io/cdflow-cli](https://mkiiim.github.io/cdflow-cli/).

## Support

Customers and product evaluators can reach out for support at [support@caestudy.com](mailto:support@caestudy.com).

## License

This project is licensed under the **Business Source License 1.1 (BSL)**.

- **Current license:** BSL 1.1 with production use restrictions
- **Converts to:** Apache 2.0 License on **2029-09-01**
- **Full terms:** See the [LICENSE](https://github.com/mkiiim/cdflow-cli/blob/main/LICENSE) file for complete details

### Contributing

Contributions are welcome! Please note:

- All contributors must agree to our [Contributor License Agreement (CLA)](https://github.com/mkiiim/cdflow-cli/blob/main/CLA.md)
- See the [Contributing Guide](https://mkiiim.github.io/cdflow-cli/contributing/) for details on the contribution process
- This is a BSL-licensed project (not open source until 2029-09-01)
