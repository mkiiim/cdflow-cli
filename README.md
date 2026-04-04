# Cæstudy DonationFlow CLI

DonationFlow CLI is a command-line tool for importing donation data from external sources like CanadaHelps and PayPal into your NationBuilder account. It is designed to be a bridge for organizations that use payment processors not natively integrated with NationBuilder, or for those migrating from other CRM platforms.

DonationFlow CLI is extensible to other payment processor sources through an existing adapter template and a plugin architecture through which organization-specific business rules can be implemented.

DonationFlow CLI was originally developed to help a non-profit charitable organization successfully migrate their donation data from CiviCRM and integrate their existing PayPal and CanadaHelps workflows with NationBuilder.

## Key Features

- **Import from External Sources:** Import donation data from CanadaHelps and PayPal CSV exports.
- **Extensible Design:** The tool is designed to be adaptable to other payment platform sources, includes a generic adapter, and is extensible with plugins.
- **Detailed Logging:** Comprehensive logging of every import job operation, for easy troubleshooting.
- **Auditing:** Job files provide detailed audit trail for each imported donation record.
- **Rollback Capable:** A separate command allows you to safely rollback donation import jobs (deleting the imported transaction(s) from NationBuilder) if needed.

## Prerequisites

- Python 3.8+
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

For development installation, please see the [Contribution Guide](docs/contributing.md).

## Quick Start

1.  **Initialize configuration:** Run `cdflow init` to create template files:

    - `~/.config/cdflow/local.yaml` - Main configuration file (default location)
    - `~/.env/nb_local.env` - OAuth environment variables template (non-configurable location)

    <br>

2.  **Configure OAuth credentials:** Edit `~/.env/nb_local.env` with your NationBuilder OAuth credentials, then load:

    ### Locate the `load-secrets.sh` script

    If you have installed via pip and have created your virtual environment:

    ```bash
    cd <path-to-venv-environment-directory>/lib/python3.13/site-packages/cdflow_cli/scripts/
    ```

    ### Execute the script using your `.env` file as the parameter

    ```bash
    source ./load-secrets.sh ~/.env/nb_local.env
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

    <br>

7.  **Verify in NationBuilder:** Log in to your NationBuilder account and navigate to the Finances section. You should see the newly imported donations in your transaction list.

## Documentation

For more detailed information on configuration, usage, and troubleshooting, please see our full documentation in the repo `/docs` directory.

## Support

Customers and product evaluators can reach out for support at [support@caestudy.com](mailto:support@caestudy.com).

## License

This project is licensed under the **Business Source License 1.1 (BSL)**.

- **Current license:** BSL 1.1 with production use restrictions
- **Converts to:** Apache 2.0 License on **2029-09-01**
- **Full terms:** See the [LICENSE](LICENSE) file for complete details

### Contributing

Contributions are welcome! Please note:

- All contributors must agree to our [Contributor License Agreement (CLA)](CLA.md)
- See [Contributing Guide](docs/contributing.md) for details on the contribution process
- This is a BSL-licensed project (not open source until 2029-09-01)
