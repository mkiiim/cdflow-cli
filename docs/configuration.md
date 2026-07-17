<div class="df-hero__eyebrow">cdflow-cli docs · configuration.md</div>

# Configuration

DonationFlow CLI is configured using a YAML configuration file and environment variables for OAuth credentials. The configuration file contains application settings while OAuth credentials are provided via environment variables for security.

## Generating Configuration Templates

The `cdflow init` command generates configuration templates that you can customize for your deployment. See the [Usage Guide](usage.md#setting-up-configuration-cdflow-init) for detailed instructions.

```bash
cdflow init
# Creates templates in ~/.config/caestudy/ and ~/.env/
```

This creates:
- `~/.config/caestudy/local.yaml` - Main application configuration file
- `~/.env/nb_local.env` - OAuth environment variables template
- `~/.config/caestudy/plugins/` - Plugin examples for customization 

## Application Configuration File (e.g., `local.yaml`)

This is the main application configuration file. It contains settings for storage, logging, and the import process itself. Below is a breakdown of the sections relevant to the CLI tool.

The config shape is shared with `ccflow-app`, so some sections remain present even when the current CLI flow does not actively use every field.

### `deployment`

This section remains part of the shared config shape even in CLI-oriented setups.

```yaml
deployment:
  pattern: local
  hostname: "localhost"
  api_port: 8801
  frontend_port: 8800
```

- `pattern`: deployment mode - `local`, `network`, or `container`
- `hostname`: deployment hostname for the shared config instance
- `api_port`: app/API port for that deployment
- `frontend_port`: frontend port for that deployment

For CLI-local usage, these fields can remain in the file even when the active CLI flow mainly cares about storage, import settings, and the callback contract.

### `nboauth`

This section carries the shared OAuth callback contract.

```yaml
nboauth:
  redirect_uri: "http://localhost:8801/callback"
  callback:
    bind_host: "localhost"
    bind_port: 8801
```

- `redirect_uri`: the exact callback URI registered in NationBuilder
- `callback.bind_host`: callback receiver host in the shared config shape
- `callback.bind_port`: callback receiver port in the shared config shape

Recommended rule:

1. set `redirect_uri` to the exact NationBuilder callback URL
2. populate `callback.bind_host` and `callback.bind_port` from the host/port in `redirect_uri`

For local CLI use, `cdflow-cli` actively uses the `callback.bind_*` values for its temporary OAuth listener. In app-focused flows, those fields may still exist for shared-schema consistency and be ignored by the active runtime path.

### `api`

This section remains part of the shared config shape used across `cdflow-cli` and `ccflow-app`.

```yaml
api:
  host: 0.0.0.0
  port: 8000
  cors:
    origins: []
```

- `host`: API binding address for app-facing deployments
- `port`: API port for app-facing deployments
- `cors.origins`: browser-facing CORS origins for app-facing deployments

For CLI-only workflows, these values can remain present without affecting the import flow.

### `frontend`

This section remains part of the shared config shape used across `cdflow-cli` and `ccflow-app`.

```yaml
frontend:
  host: 0.0.0.0
  port: 8000
```

- `host`: frontend binding address for app-facing deployments
- `port`: frontend port for app-facing deployments

For CLI-only workflows, these values can remain present without affecting the import flow.

### `storage`

This section defines the paths for various files used by the application. You will need to customize these paths for your system.

```yaml
storage:
  paths:
    jobs: "/path/to/your/jobs"
    logs: "/path/to/your/logs"
    output: "/path/to/your/output"
    cli_source: "/path/to/your/import_source"
```

-   `jobs`: The directory where the application will store JSON job files. These files contain a summary of each import run and are useful for auditing.
-   `logs`: The directory where the application writes its rotating log file, `cdflow.log` (10 MB per file, 3 rotated backups). All runs log to this single file rather than one file per run.
-   `output`: The directory where the application will write the `_success.csv` and `_fail.csv` files of the records that have been successfully imported or have failed import
-   `cli_source`: The directory where the application will look for your CSV files to be imported, if not specified on the command line.

### `logging`

This section controls log output levels and destinations.

```yaml
logging:
  file_level: "DEBUG"                      # Rotating log file level, or "NONE" to disable file logging
  console_level: "INFO"                    # Default console level (the --log-level CLI flag overrides this)
```

-   `file_level`: Level written to the rotating `cdflow.log` file in your `storage.paths.logs` directory. Set to `NONE` to disable file logging entirely.
-   `console_level`: Default console verbosity. The `--log-level` command-line flag takes precedence when provided.
-   `os_log` (optional, macOS only): Set to `true` to also send logs to macOS unified logging (viewable in Console.app under subsystem `com.caestudy.cdflow`). Equivalent to passing `--log-os-log` on the command line.

### `cli_import`

This section configures the specifics of the default CLI import run, when no file and type are specified on the command line

```yaml
cli_import:
  type: canadahelps
  file: ch/import.csv
```

-   `type`: The source of the import. Use `canadahelps` or `paypal`.
-   `file`: The path to the CSV file to be imported, relative to the `cli_source` directory.

### `logos`

This section remains part of the shared config shape used across `cdflow-cli` and `ccflow-app`.

```yaml
logos:
  use_custom: true
  custom_path: "assets/logos/custom"
```

- `use_custom`: enable custom organizational logos
- `custom_path`: directory for custom logo files

For CLI-only workflows, these values can remain present without affecting the import flow.

### Automatic Job Tracking Fields

DonationFlow CLI automatically detects and populates job tracking fields of donation records when they exist in your NationBuilder nation:

- `import_job_id`: Unique identifier for the import job that imported the donation record
- `import_job_source`: JSON metadata including context, hostname, IP, and version info to audit and track down what machine ran the job that imported the donation record

These fields are **automatically detected** via API call during import initialization. If the fields exist in your nation's donation schema, they will be populated. If they don't exist, they are silently omitted - no manual configuration required.

To add these fields to your NationBuilder nation:
1. Go to Settings > Nation > Custom fields in your NationBuilder admin
2. Add custom fields to the Donations section:
   - Field name: `import_job_id`, Type: Text
   - Field name: `import_job_source`, Type: Text area

### `plugins`

This section configures the plugin system for customizing donation data processing:

```yaml
plugins:
  canadahelps:
    enabled: true
    dir: "~/.config/caestudy/plugins/canadahelps"
  paypal:
    enabled: true
    dir: "~/.config/caestudy/plugins/paypal"
```

- `enabled`: Set to `true` to load and execute plugins for this adapter
- `dir`: Directory containing plugin files (supports `~` for home directory)

Plugins allow you to customize data transformations, tracking code mapping, payment type normalization, and eligibility filtering without modifying core code. See the [Plugin Examples](plugins/overview.md) for more information.

## OAuth Configuration (Environment Variables)

OAuth credentials are provided to DonationFlow CLI via environment variables for security. The `cdflow init` command creates a reference template at `~/.env/nb_local.env`:

### Edit the OAuth template

After running `cdflow init`, edit `~/.env/nb_local.env` with your NationBuilder credentials:

```bash
NB_CLIENT_ID=your_actual_client_id
NB_CLIENT_SECRET=your_actual_client_secret
NB_SLUG=your_nation_slug
NB_CONFIG_NAME=development
```

### Load OAuth credentials into environment

Use the included `load-secrets.sh` script to source your credentials:

```bash
# Find the script location
python3 -c "import cdflow_cli; from pathlib import Path; print(Path(cdflow_cli.__file__).parent / 'scripts' / 'load-secrets.sh')"

# Source the credentials (use the path from above)
source /path/to/load-secrets.sh ~/.env/nb_local.env
```

Alternatively, manually export the environment variables:

```bash
export NB_CLIENT_ID=your_actual_client_id
export NB_CLIENT_SECRET=your_actual_client_secret
export NB_SLUG=your_nation_slug
export NB_CONFIG_NAME=development
```

### About `.env` files

The `.env` files are provided as reference and templates for the environment variables that are required for `cdflow` to authenticate and connect to your nation instance on NationBuilder.

In a development scenario an `.env` file can be used to quickly and easily "`source`" the set of environment variables for a specific environment. Multiple `.env` files can be created, one for each unique environment, and can facilitate the easy switching between the multiple environments.

In a production environment, as a security and privacy best practice, **it is best to NOT store these secrets in plain text files** and to instead use your system's secrets management and procedures to create the environment variables in the session(s) in which `cdflow` is needed. 
