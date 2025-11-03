# Usage

This guide provides detailed instructions for using the `cdflow init`, `cdflow import` and `cdflow rollback` commands.

## Setting Up Configuration (`cdflow init`)

Before using `cdflow`, you need to set up configuration files and set environment variables. The `cdflow init` command creates a template configuration .yaml file that you can customize and oauth .env files as a check list of environment variables required for authentication to NationBuilder.

The default location for configuration `.yaml` files is `~/.config/cdflow/`. The location of config files is configurable.
The default location for oauth `.env` files is `~/.env/`. The location of environment files is NOT configurable.

### About `.env` files

A `.env` file is provided as a reference and template for the environment variables required for `cdflow` to authenticate and connect to your nation instance on NationBuilder.

In a development scenario a `.env` file can be used to quickly and easily "`source`" the set of environment variables for a specific environment. Multiple `.env` files can be created, one for each unique environment, and can facilitate the easy switching between the multiple environments.

In a production environment, as a security and privacy best practice, it is best to not store these secrets in plain text files and to instead use your system's secrets management and procedures to create the environment variables in the session(s) in which `cdflow` is needed.
  
### Basic Usage
  
```bash
cdflow init
# creates config templates in default location (~/.config/cdflow/)
# creates oauth .env files in non-configurable location (~/.env/)

cdflow init --config-dir /path/to/config
# creates config templates in the specified location (/path/to/config)
# creates oauth .env files in non-configurable locaiton (~/.env/)
```

This creates:  
- `~/.config/cdflow/local.yaml` - Main application configuration file (default location)  
- `~/.env/nb_local.env` - OAuth environment variables template (non-configurable location)
  
### Options
  
- `--config-dir`: Directory to specify the location to write configuration template file (default: `~/.config/cdflow/`)
- `--force`: Overwrite existing files with templates without prompting
  
### File Conflict Handling
  
If configuration and/or oauth files with the same filename(s) already exist, `cdflow init` will prompt you to choose:
- **Overwrite**: Replace existing files with fresh templates
- **Skip**: Create only missing files, keep existing ones unchanged
- **Cancel**: Exit without making changes

Use `--force` to automatically overwrite without prompting.
  
### Setting Up OAuth Credentials
  
After running `cdflow init`, you need to configure your NationBuilder OAuth credentials:

1. **Edit the OAuth template:**
   ```bash
   nano ~/.env/nb_local.env
   ```

2. **Add your credentials:**
   ```bash
   NB_CLIENT_ID=your_actual_client_id
   NB_CLIENT_SECRET=your_actual_client_secret
   NB_SLUG=your_nation_slug
   NB_CONFIG_NAME=name_for_this_configuration_eg_develoment
   ```

3. **Source the environment using the provided `load-secrets.sh` shell script:**

    #### Locate the `load-secrets.sh` script

    If you are in the source repo:
    ```bash
    cd ./scripts/
    ```
    If you have installed via pip and have created your virtual environment:
    ```bash
    cd <path-to-venv-environment-directory>/lib/python3.13/site-packages/cdflow_cli/scripts/
    ```

    #### Execute the script using your `.env` file as the parameter
    ```bash
    ./load-secrets.sh ~/.env/nb_local.env
    ```
  
## Importing Donations (`cdflow import`)
  
This is the main command for importing donations into NationBuilder.
  
### Workflow
  
1.  **Prepare your CSV file:** Download your donation transaction report from CanadaHelps or PayPal. Ensure that the file is in the correct format (see [Data Formats](data_formats.md) for details).

2.  **Place the CSV file:** Move your CSV file into the appropriate subdirectory within the `cli_source` directory you defined in your configuration file. You can further organize your imports use `ch` for CanadaHelps files and `pp` for PayPal subdirectories to organize your imports by source system.

3.  **Configure the import:** Open your configuration file (e.g., `local.yaml`) and update the `cli_import` section to specify the `type` (either `canadahelps` or `paypal`) and the `file` path (relative to `cli_source`).

    ```yaml
    cli_import:
      type: canadahelps
      file: ch/your_donation_file.csv
    ```

4.  **Run the import command:** Open your terminal and run the following command, replacing the path to your configuration file:

    ```bash
    cdflow import --config /path/to/your/local.yaml
    ```

    **Alternative: Override import settings via CLI flags:**

    You can override the import type and file path from the config using CLI flags:

    ```bash
    # Override with relative path
    cdflow import --type canadahelps --file donations/emergency.csv --config /path/to/your/local.yaml
    # Override with absolute path
    cdflow import --type paypal --file /tmp/paypal_donations.csv --config /path/to/your/local.yaml
    ```
    
    **Important:** When using CLI flags, both `--type` and `--file` must be used together. The configuration file is still required for OAuth settings, storage paths, and other configurations.

    ### Log Level Control

    Control the verbosity of console output with the `--log-level` option:

    ```bash
    # Show only errors
    cdflow import --config local.yaml --log-level ERROR

    # Show important milestones and errors
    cdflow import --config local.yaml --log-level NOTICE

    # Show all information (default, recommended)
    cdflow import --config local.yaml --log-level INFO

    # Show everything including debug details
    cdflow import --config local.yaml --log-level DEBUG
    ```

    **Log Levels:**
    - `ERROR`: Only show errors and failures
    - `NOTICE`: Show important milestones, confirmations, and errors
    - `INFO`: Show detailed progress and all of the levels above (default, recommended)
    - `DEBUG`: Show all diagnostic information and all of the levels above

    The default `INFO` level provides the right balance of detail for most users.

5.  **Monitor the progress:** The application will print real-time progress updates to the console. You will see information about each record being processed.

6.  **Review the results:** After the import is complete, you can review the results in the `output` directory you specified in your configuration.
    *   `_success.csv`: This file contains all the records that were successfully imported, along with the new NationBuilder Person ID and Donation ID.
    *   `_fail.csv`: This file contains any records that failed to import, along with any error message(s) in the `NB Error Message` column.

    <br>

7.  **Verify in NationBuilder:** Log in to your NationBuilder account and navigate to the Finances section. You should see the newly imported donations in your transaction list.

## Rolling Back Donations (`cdflow rollback`)

This command allows you to delete donations that were previously imported. This is useful for correcting mistakes or for testing purposes.

**Warning:** This is a destructive operation. Please be sure you want to remove the donations from your nation before running this command.

### Workflow

1.  **Run the rollback command:** Open your terminal and run the following command, replacing the path to your configuration file:

    ```bash
    cdflow rollback --config /path/to/your/config.yaml

    # Or with custom log level
    cdflow rollback --config /path/to/your/config.yaml --log-level NOTICE
    ```

2.  **Select the import to rollback:** The tool will scan your `output` directory for `_success.csv` files and present them as a list of completed imports. Use arrow keys to highlight the import and press enter to select

3.  **Confirm the operation:** The tool will show you a summary of the rollback operation and ask for your confirmation before proceeding.

4.  **Monitor the progress:** The application will output real-time progress updates to the console as it removes each donation in the selected `_success.csv` file, in the reverse order in which they were added.

5.  **Review the results:** A new `_rollback.csv` file will be created in your `output` directory, containing the results of the rollback operation.

## Storage Configuration

DonationFlow supports flexible storage configuration to accommodate different deployment scenarios.

### Basic Configuration (Default)

By default, storage paths are resolved relative to your current working directory:

```yaml
storage:
  paths:
    jobs: "storage/jobs"                     # Created relative to pwd
    logs: "storage/logs"                     # Created relative to pwd
    output: "storage/output"                 # Created relative to pwd
    app_upload: "storage/app_upload"         # Created relative to pwd
    app_processing: "storage/app_processing" # Created relative to pwd
    cli_source: "storage/import_source"      # Created relative to pwd
```

### Centralized Storage with Base Path

For server deployments or when you want all storage in a consistent location, use the `base_path` option:

```yaml
storage:
  base_path: "/opt/cdflow-data"               # Base directory for all storage
  paths:
    jobs: "jobs"                             # Resolves to /opt/cdflow-data/jobs
    logs: "logs"                             # Resolves to /opt/cdflow-data/logs
    output: "output"                         # Resolves to /opt/cdflow-data/output
    app_upload: "app_upload"                 # Resolves to /opt/cdflow-data/app_upload
    app_processing: "app_processing"         # Resolves to /opt/cdflow-data/app_processing
    cli_source: "import_source"              # Resolves to /opt/cdflow-data/import_source
```

### Mixed Configuration

You can combine `base_path` with absolute path overrides for specific directories:

```yaml
storage:
  base_path: "/opt/cdflow-data"                # Base for relative paths
  paths:
    logs: "logs"                              # Using base_path, resolves to: /opt/cdflow-data/logs
    jobs: "jobs"                              # Using base_path, resolves to: /opt/cdflow-data/jobs
    output: "output"                          # Using base_path, resolves to: /opt/cdflow-data/output
    app_upload: "app_upload"                  # Using base_path, resolves to: /opt/cdflow-data/app_upload
    app_processing: "app_processing"          # Using base_path, resolves to: /opt/cdflow-data/app_upload
    cli_source: "/path/to/your/import_source" # Using absolute path: /path/to/your/import_source
```

### Benefits of Base Path

- **Server Deployments**: Centralize all application data in one location
- **Permissions**: Easier to manage file permissions for a single directory tree
- **Backups**: Simple to backup entire application data directory
- **Docker**: Clean separation of application data from container filesystem
- **Multi-User**: Each user can have their own base_path in shared environments
