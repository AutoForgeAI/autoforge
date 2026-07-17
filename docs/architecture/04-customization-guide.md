# Customization Guide

## Overview

AutoForge can be customized for virtually any project type through 10 major customization points. While it defaults to web applications (React/Vite/Express/SQLite), the architecture is designed to support any technology stack, including event-sourced systems, embedded platforms, and non-web applications.

## Customization Points

### 1. Prompt Templates (Per-Project Overrides)

**Location:** `{project_dir}/.autoforge/prompts/`

The prompt loading system uses a two-level fallback chain:
1. **Project-specific** (highest priority): `{project_dir}/.autoforge/prompts/{name}.md`
2. **Base template** (fallback): `.claude/templates/{name}.template.md`

Four templates can be overridden:

| Template | Purpose |
|----------|---------|
| `coding_prompt.md` | Workflow instructions for coding agents |
| `initializer_prompt.md` | Feature creation and project setup |
| `testing_prompt.md` | Regression testing instructions |
| `app_spec.txt` | Project specification (XML format) |

To customize: simply edit the files in your project's `.autoforge/prompts/` directory. Changes take effect on the next agent session. During scaffolding, templates are only copied if the destination doesn't exist, preserving your customizations.

### 2. App Specification (XML)

**Location:** `{project_dir}/.autoforge/prompts/app_spec.txt`

The app spec uses a flexible XML format:

```xml
<project_specification>
  <project_name>My Project</project_name>
  <overview>Description of the project</overview>
  <technology_stack>
    <frontend>...</frontend>
    <backend>...</backend>
    <communication>...</communication>
  </technology_stack>
  <prerequisites>
    <environment_setup>...</environment_setup>
  </prerequisites>
  <feature_count>N</feature_count>
  <core_features>
    <category_name>
      - Feature description (testable)
    </category_name>
  </core_features>
  <!-- Additional sections: database_schema, api_endpoints_summary,
       ui_layout, design_system, implementation_steps, success_criteria -->
</project_specification>
```

The technology stack section is fully flexible -- any combination of languages, frameworks, and tools is supported. The only structural requirement is the `<project_specification>` root tag.

### 3. Per-Project Allowed Commands

**Location:** `{project_dir}/.autoforge/allowed_commands.yaml`

For non-standard toolchains, add custom commands:

```yaml
version: 1
commands:
  # Exact command names
  - name: cargo
    description: Rust package manager

  # Prefix wildcards
  - name: swift*
    description: All Swift development tools

  # Local scripts
  - name: ./scripts/build.sh
    description: Project build script

pkill_processes:        # Extra process names pkill can target
  - uvicorn
  - gunicorn
```

Supports exact matches, prefix wildcards (`swift*` matches `swift`, `swiftc`, `swiftlint`), and script paths. Maximum 100 commands per project.

### 4. Organization-Wide Configuration

**Location:** `~/.autoforge/config.yaml`

```yaml
version: 1

# Commands available to ALL projects
allowed_commands:
  - name: jq
    description: JSON processor
  - name: protoc
    description: Protocol buffer compiler

# Commands blocked across ALL projects (cannot be overridden)
blocked_commands:
  - aws
  - kubectl
```

### 5. Project-Level CLAUDE.md

**Location:** `{project_dir}/CLAUDE.md`

A standard Claude Code convention. The agent loads this automatically via `setting_sources=["project"]`. Use it for:
- Project-specific coding conventions
- Architecture decisions
- API documentation references
- Environment setup notes
- Custom workflow instructions

### 6. Dev Server Command

**Location:** `{project_dir}/.autoforge/config.json`

```json
{
  "dev_command": "cargo run --release"
}
```

Auto-detection supports: Node.js (Vite/CRA), Python (Poetry/Django/FastAPI), Rust, Go. For anything else, set a custom dev command.

### 7. Browser Configuration

**Location:** `{project_dir}/.playwright/cli.config.json`

```json
{
  "browser": {
    "browserName": "chromium",
    "launchOptions": {
      "channel": "chrome",
      "headless": true
    },
    "contextOptions": {
      "viewport": { "width": 1280, "height": 720 }
    },
    "isolated": true
  }
}
```

Can be changed to `firefox`, `webkit`, or `msedge`. Viewport, headless mode, and isolation are all configurable.

### 8. YOLO Mode

**Flag:** `--yolo` or UI toggle

Strips all browser testing instructions from prompts and replaces with lint/type-check verification only. Useful for:
- Rapid prototyping phases
- Non-web projects where browser testing is irrelevant
- Projects with their own testing infrastructure

### 9. Extra Read Paths

**Environment variable:** `EXTRA_READ_PATHS`

```bash
EXTRA_READ_PATHS=/path/to/docs,/path/to/shared-libs,/path/to/reference
```

Allows the agent to read files from directories outside the project folder. All paths must be absolute, must exist as directories, and are validated against a blocklist of sensitive directories (`.ssh`, `.aws`, `.gnupg`, etc.). Only read operations (Read, Glob, Grep) are permitted on these paths.

### 10. API Provider Configuration

**Via Settings UI or `.env`**

Supports Claude (default), GLM, Ollama, Kimi, Vertex AI, and custom providers. Configuration is done through the Settings panel in the UI or by editing `~/.autoforge/.env` directly.

---

## Adapting for Non-Standard Project Types

The key to adapting AutoForge for non-standard projects is modifying three files in `{project_dir}/.autoforge/prompts/`:

1. **`app_spec.txt`** -- Define the project's architecture, technology stack, and features
2. **`coding_prompt.md`** -- Rewrite the step-by-step workflow for your development process
3. **`initializer_prompt.md`** -- Adjust how features are categorized and structured

Additionally:
- **`allowed_commands.yaml`** -- Add your toolchain's commands
- **`CLAUDE.md`** -- Add project-specific conventions and architecture docs
- **`.autoforge/config.json`** -- Set the dev/run command

### What to Change in the Coding Prompt

The default coding prompt (`coding_prompt.template.md`) assumes a web app workflow:
1. Read spec and progress
2. Start dev server (`init.sh`)
3. Claim and implement feature
4. Verify with browser automation (Playwright)
5. Commit and update progress

For non-web projects, you typically need to modify:
- **STEP 2 (Start Servers)**: Replace with your build/run process
- **STEP 4 (Implement)**: Adjust implementation guidance for your architecture
- **STEP 5 (Verify)**: Replace browser testing with your verification method
- **STEP 5.5-5.7 (Checklist)**: Adapt verification criteria
- **Allowed Tools**: You may want to add/remove built-in tools

### What to Change in the Initializer Prompt

The default initializer assumes web app features:
- 5 mandatory Infrastructure features (database connection, schema, persistence, no mock data, real queries)
- 20 mandatory categories including UI-Backend Integration, Responsive, Accessibility, etc.

For non-web projects:
- Replace or remove the mandatory Infrastructure features
- Redefine the mandatory categories to match your domain
- Adjust the feature writing rules for your testing approach

---

## Example 1: Event-Sourced CQRS System (NATS JetStream)

This example shows how to adapt AutoForge for a fully event-sourced CQRS system using Go, NATS JetStream for the event store, and SQLite (modernc/sqlite) with NATS KV for projections.

### `app_spec.txt`

```xml
<project_specification>
  <project_name>order-management-cqrs</project_name>
  <overview>
    Event-sourced order management system using CQRS pattern. Commands produce
    domain events stored in NATS JetStream streams. Projections consume events
    and build read models in SQLite (modernc/sqlite pure Go driver) and NATS KV
    stores for real-time queries.
  </overview>

  <technology_stack>
    <language>Go 1.22+</language>
    <event_store>NATS JetStream (event streams per aggregate)</event_store>
    <projections>
      <persistent>SQLite via modernc.org/sqlite (pure Go, no CGO)</persistent>
      <realtime>NATS KV buckets (in-memory or file-backed)</realtime>
      <in_memory>Go sync.Map for hot caches</in_memory>
    </projections>
    <messaging>NATS Core (pub/sub for commands, replies)</messaging>
    <api>gRPC + Connect-Go for external API</api>
    <testing>
      <unit>Go testing + testify</unit>
      <integration>testcontainers-go with NATS container</integration>
      <event_store>In-memory NATS server (nats-server -js)</event_store>
    </testing>
    <build>Go modules + make</build>
  </technology_stack>

  <prerequisites>
    <environment_setup>
      Go 1.22+, NATS Server with JetStream enabled, protoc for gRPC definitions.
      init.sh should: install Go deps, start embedded NATS server, create JetStream
      streams and KV buckets, run initial migrations.
    </environment_setup>
  </prerequisites>

  <feature_count>85</feature_count>

  <architecture>
    <pattern>CQRS + Event Sourcing</pattern>
    <aggregate_design>
      Each aggregate (Order, Customer, Product) has:
      - Command handler (validates, produces events)
      - Event stream in JetStream (ORDERS.*, CUSTOMERS.*, etc.)
      - Aggregate root (applies events to rebuild state)
    </aggregate_design>
    <projection_design>
      Projections are independent consumers:
      - SQLite projections for complex queries (joins, aggregations)
      - NATS KV projections for key-value lookups (by ID)
      - In-memory projections for hot data (current prices, active sessions)
      Each projection tracks its own consumer sequence for replay.
    </projection_design>
    <command_flow>
      1. API receives command via gRPC/Connect
      2. Command handler loads aggregate from event stream
      3. Aggregate validates and produces events
      4. Events published to JetStream stream
      5. Projections consume events asynchronously
    </command_flow>
  </architecture>

  <core_features>
    <infrastructure>
      - NATS connection pool initializes with JetStream context
      - Event streams created per aggregate type with retention policy
      - SQLite database initialized with modernc/sqlite driver (no CGO)
      - NATS KV buckets created for each projection type
      - Event serialization uses protobuf with schema registry
    </infrastructure>
    <aggregate_order>
      - CreateOrder command validates items and produces OrderCreated event
      - AddItem command appends ItemAdded event with idempotency check
      - Order aggregate rebuilds from event stream on load
      - Concurrent command handling uses optimistic concurrency (expected sequence)
    </aggregate_order>
    <projections>
      - Order list projection builds SQLite table from OrderCreated/Updated events
      - Order-by-ID projection uses NATS KV for O(1) lookups
      - Revenue dashboard projection aggregates across all order events
      - Projection rebuild from stream position zero completes without errors
    </projections>
    <queries>
      - Query orders by date range returns from SQLite projection
      - Query order by ID returns from NATS KV projection
      - Revenue report aggregates from dashboard projection
      - All queries return eventually consistent data with sequence metadata
    </queries>
    <error_handling>
      - Command rejection returns domain error (not infrastructure error)
      - Projection consumer handles poison messages with dead-letter queue
      - Event stream replay resumes from last acknowledged sequence
      - Circuit breaker on NATS connection with exponential backoff
    </error_handling>
  </core_features>

  <success_criteria>
    <functionality>All commands produce correct events, all projections build correct read models</functionality>
    <consistency>Event ordering preserved within aggregate, projection lag under 100ms</consistency>
    <resilience>System recovers from NATS restart, projections rebuild from zero</resilience>
    <testing>Integration tests run against real NATS with JetStream in testcontainer</testing>
  </success_criteria>
</project_specification>
```

### `allowed_commands.yaml`

```yaml
version: 1
commands:
  - name: go
    description: Go compiler and tools
  - name: go*
    description: Go toolchain (gofmt, golint, etc.)
  - name: make
    description: Build automation
  - name: nats*
    description: NATS CLI tools (nats-server, nats)
  - name: protoc
    description: Protocol buffer compiler
  - name: buf
    description: Protobuf linting and breaking change detection
  - name: grpcurl
    description: gRPC testing tool
  - name: sqlite3
    description: SQLite CLI for inspection
pkill_processes:
  - nats-server
  - order-management
```

### `coding_prompt.md` (Key Changes)

Replace the web-specific steps with an event-sourcing workflow:

**STEP 2 (Start Services):**
```
Run init.sh to:
1. Start embedded NATS server with JetStream: nats-server -js -sd /tmp/nats-data
2. Create/verify JetStream streams and KV buckets
3. Run SQLite migrations
4. Start the application in development mode
```

**STEP 5 (Verify -- replaces browser testing):**
```
## VERIFICATION

Instead of browser testing, verify features using:

1. **Unit tests**: Run `go test ./... -v -count=1` for the changed packages
2. **Integration tests**: Run `go test ./integration/... -v -tags=integration`
3. **Event verification**: Use NATS CLI to inspect streams:
   - `nats stream info ORDERS` - verify events were published
   - `nats consumer info ORDERS <projection>` - verify consumer caught up
4. **Projection verification**: Query SQLite and NATS KV to confirm read models
5. **gRPC verification**: Use `grpcurl` to test API endpoints:
   - `grpcurl -plaintext localhost:8080 orders.v1.OrderService/CreateOrder`

ONLY MARK A FEATURE AS PASSING AFTER ALL RELEVANT TESTS PASS.
```

### `CLAUDE.md` (Project Root)

```markdown
# CLAUDE.md

## Architecture: Event-Sourced CQRS with NATS JetStream

### Key Patterns
- Every state change is an event in a JetStream stream
- Never modify events after publishing (append-only)
- Aggregate state is rebuilt by replaying events
- Projections are independent - can be rebuilt from zero
- Use optimistic concurrency via JetStream expected sequence numbers

### Directory Structure
- `cmd/` - Application entry points
- `internal/aggregate/` - Aggregate roots (order, customer, product)
- `internal/command/` - Command handlers
- `internal/event/` - Event definitions (protobuf)
- `internal/projection/` - Read model builders
- `internal/query/` - Query handlers
- `api/proto/` - gRPC/Connect service definitions
- `integration/` - Integration tests with testcontainers

### Testing
- Unit tests: `go test ./internal/... -v`
- Integration tests: `go test ./integration/... -v -tags=integration`
- Always test event replay: rebuild projection from zero and verify state
```

---

## Example 2: ESPHome Embedded Project

This example shows how to adapt AutoForge for ESPHome-based embedded projects, which have a fundamentally different infrastructure and programming model compared to web applications.

### `app_spec.txt`

```xml
<project_specification>
  <project_name>smart-greenhouse-controller</project_name>
  <overview>
    ESPHome-based smart greenhouse controller running on ESP32. Monitors
    temperature, humidity, soil moisture, and light levels. Controls
    ventilation fans, irrigation pumps, and grow lights via relays.
    Integrates with Home Assistant for remote monitoring and automation.
  </overview>

  <technology_stack>
    <platform>ESP32 (ESP-WROOM-32)</platform>
    <framework>ESPHome (YAML-based configuration)</framework>
    <language>YAML (ESPHome configs) + C++ (custom components)</language>
    <communication>
      <local>ESPHome native API (protobuf over TCP)</local>
      <mqtt>Optional MQTT for third-party integration</mqtt>
      <web>Built-in web server for status page</web>
    </communication>
    <sensors>
      <temperature>DHT22 (GPIO4)</temperature>
      <humidity>DHT22 (GPIO4, same sensor)</humidity>
      <soil_moisture>Capacitive soil sensor (ADC GPIO36)</soil_moisture>
      <light>BH1750 (I2C SDA=21, SCL=22)</light>
    </sensors>
    <actuators>
      <fan>Relay module (GPIO25)</fan>
      <pump>Relay module (GPIO26)</pump>
      <lights>Relay module (GPIO27)</lights>
    </actuators>
    <testing>
      <validation>ESPHome config validation (esphome config)</validation>
      <compilation>ESPHome compile (esphome compile)</compilation>
      <simulation>No hardware simulation - validate config + compile only</simulation>
    </testing>
  </technology_stack>

  <prerequisites>
    <environment_setup>
      Python 3.11+ with ESPHome installed (pip install esphome).
      init.sh should: install esphome, validate the base config compiles,
      create the secrets.yaml template.
    </environment_setup>
  </prerequisites>

  <feature_count>45</feature_count>

  <core_features>
    <infrastructure>
      - Base ESPHome YAML configures ESP32 board, WiFi, OTA, and API
      - secrets.yaml template provides WiFi credentials and API password
      - ESPHome config validates without errors (esphome config greenhouse.yaml)
      - ESPHome compiles successfully (esphome compile greenhouse.yaml)
      - Web server component serves status page on port 80
    </infrastructure>
    <sensor_integration>
      - DHT22 sensor reports temperature in Celsius with 60s update interval
      - DHT22 sensor reports humidity percentage with 60s update interval
      - Capacitive soil moisture sensor calibrated to 0-100% range
      - BH1750 light sensor reports lux via I2C
      - All sensors have filters: sliding_window_moving_average, delta
    </sensor_integration>
    <actuator_control>
      - Fan relay toggles via switch component with interlock
      - Irrigation pump activates via switch with configurable duration limit
      - Grow lights switch with daily on/off schedule
      - All actuators expose switches to Home Assistant via native API
    </actuator_control>
    <automation>
      - Temperature threshold triggers fan (above 30C on, below 25C off, hysteresis)
      - Soil moisture threshold triggers irrigation (below 30% on, above 60% off)
      - Light level below 5000 lux triggers grow lights during daytime hours
      - Automation rules defined in ESPHome automation YAML blocks
    </automation>
    <safety>
      - Pump maximum runtime of 5 minutes per activation (hardware safety)
      - Watchdog reboot if WiFi disconnected for 15 minutes
      - All GPIO pins initialize to safe (OFF) state on boot
      - Status LED indicates connection state (fast blink = no WiFi, solid = connected)
    </safety>
    <home_assistant_integration>
      - All sensors visible as entities in Home Assistant
      - All switches controllable from Home Assistant
      - Binary sensors for threshold alerts (too hot, too dry, too dark)
      - Template sensors for aggregated status (greenhouse health score)
    </home_assistant_integration>
  </core_features>

  <success_criteria>
    <functionality>All YAML configs validate and compile without errors</functionality>
    <sensor_accuracy>Sensor filters produce stable, reasonable readings</sensor_accuracy>
    <safety>All safety interlocks present and correctly configured</safety>
    <integration>All entities properly exposed via ESPHome native API</integration>
  </success_criteria>
</project_specification>
```

### `allowed_commands.yaml`

```yaml
version: 1
commands:
  - name: esphome
    description: ESPHome CLI (validate, compile, upload)
  - name: pip
    description: Python package installer
  - name: python3
    description: Python interpreter
  - name: platformio
    description: PlatformIO build system (used by ESPHome internally)
  - name: pio
    description: PlatformIO CLI shorthand
```

### `coding_prompt.md` (Key Changes)

The ESPHome workflow is fundamentally different from web development:

**STEP 1 (Get Bearings):**
```
# 1. Check project structure
ls -la
cat greenhouse.yaml
# 2. Check current config validity
esphome config greenhouse.yaml
# 3. Check compilation status
esphome compile greenhouse.yaml 2>&1 | tail -20
# 4. Read progress notes
tail -500 claude-progress.txt
# 5. Check feature status
feature_get_stats
```

**STEP 2 (No server to start):**
```
## STEP 2: VALIDATE ENVIRONMENT

ESPHome projects don't have a "dev server". Instead, verify:
1. ESPHome is installed: `esphome version`
2. Base config validates: `esphome config greenhouse.yaml`
3. secrets.yaml exists with placeholder values
```

**STEP 4 (Implement):**
```
## STEP 4: IMPLEMENT THE FEATURE

ESPHome features are implemented by modifying YAML configuration files:

1. Read the feature description carefully
2. Identify which YAML section needs changes (sensor, switch, automation, etc.)
3. Add/modify the relevant YAML blocks
4. Validate after every change: `esphome config greenhouse.yaml`
5. If adding C++ custom components, create files in `custom_components/`

**YAML Best Practices:**
- Use !include for large sections
- Use substitutions for reusable values
- Keep automations close to their triggers
- Comment complex lambda expressions
```

**STEP 5 (Verify -- replaces browser testing):**
```
## STEP 5: VERIFY THE FEATURE

ESPHome verification is compile-based (no hardware in the loop):

1. **Config validation**: `esphome config greenhouse.yaml`
   - Must pass with zero errors
   - Warnings are acceptable but should be addressed

2. **Full compilation**: `esphome compile greenhouse.yaml`
   - Must compile successfully
   - Check binary size is within ESP32 flash limits

3. **Manual review**:
   - Verify GPIO pins don't conflict
   - Verify I2C addresses are unique
   - Verify automation logic is correct (thresholds, hysteresis)
   - Verify safety interlocks are present

ONLY MARK A FEATURE AS PASSING AFTER `esphome config` AND `esphome compile` SUCCEED.
```

### `initializer_prompt.md` (Key Changes)

Replace the web-focused mandatory categories:

```
### MANDATORY CATEGORIES (for ESPHome projects)

Replace the default 20 categories with these domain-specific categories:

1. **Infrastructure** - Base config, WiFi, OTA, API, web server
2. **Sensor Integration** - Each physical sensor's configuration
3. **Actuator Control** - Each relay/motor/output configuration
4. **Automation** - Threshold-based and schedule-based automations
5. **Safety** - Watchdog, interlocks, safe defaults, runtime limits
6. **Filtering** - Sensor data smoothing, calibration, delta filters
7. **Home Assistant** - Entity naming, grouping, template sensors
8. **Status & Diagnostics** - WiFi signal, uptime, memory, status LED
9. **Power Management** - Deep sleep, wake triggers (if battery-powered)
10. **Error Handling** - Sensor failure fallbacks, connection recovery
```

Remove the mandatory Infrastructure features (database connection, schema, etc.) since ESPHome projects have no database.

### `CLAUDE.md` (Project Root)

```markdown
# CLAUDE.md

## ESPHome Project: Smart Greenhouse Controller

### Key Concepts
- This is a YAML-first project. Most features are YAML configuration, not code.
- ESPHome compiles YAML into C++ and flashes to ESP32.
- "Testing" means: config validates + compiles. No runtime testing without hardware.
- NEVER use browser automation. This is not a web project.

### File Structure
- `greenhouse.yaml` - Main ESPHome configuration
- `secrets.yaml` - WiFi credentials, API passwords (gitignored)
- `common/` - Shared YAML includes (WiFi, OTA, base config)
- `custom_components/` - C++ custom ESPHome components (if needed)
- `automations/` - YAML automation includes

### Verification Commands
- `esphome config greenhouse.yaml` - Validate YAML config
- `esphome compile greenhouse.yaml` - Full compile to firmware binary
- Never use `esphome run` or `esphome upload` - no hardware available

### GPIO Pin Map
- GPIO4: DHT22 (temperature + humidity)
- GPIO36: Soil moisture (ADC)
- GPIO21/22: I2C SDA/SCL (BH1750 light sensor)
- GPIO25: Fan relay
- GPIO26: Pump relay
- GPIO27: Grow lights relay
- GPIO2: Status LED (built-in)
```

---

## General Adaptation Strategy

When adapting AutoForge for a new project type, follow these steps:

### Step 1: Define the Spec

Write `app_spec.txt` with your technology stack, architecture patterns, and testable features. The XML format is flexible -- add custom sections as needed (`<architecture>`, `<hardware>`, `<protocols>`, etc.).

### Step 2: Customize the Coding Prompt

Focus on three areas:
1. **Environment setup** (STEP 2): How to build/start your project
2. **Verification** (STEP 5): Replace browser testing with your verification method
3. **Feature workflow** (STEP 4): Add domain-specific implementation guidance

### Step 3: Customize the Initializer Prompt

Redefine:
- Mandatory feature categories for your domain
- Whether "Infrastructure" features are needed (database, networking, etc.)
- Dependency patterns between features

### Step 4: Add Toolchain Commands

Update `allowed_commands.yaml` with all CLI tools your project needs. Use prefix wildcards for tool families (e.g., `swift*` for `swift`, `swiftc`, `swiftlint`, `swiftformat`).

### Step 5: Write CLAUDE.md

Provide the agent with:
- Architecture overview and key patterns
- Directory structure conventions
- Testing and verification commands
- Domain-specific rules and constraints

### Step 6: Consider YOLO Mode

For projects where browser testing is irrelevant (embedded, CLI tools, libraries, backend services), either:
- Use `--yolo` flag to skip browser testing entirely
- Customize the coding prompt to replace browser testing with your verification method (preferred for production use, since it lets you define your own verification steps)

### Key Principle

AutoForge's power comes from the prompt templates and MCP feature tracking -- not from any specific technology assumptions. The feature lifecycle (claim, implement, verify, mark passing) works for any project type. What changes between project types is the content of the implementation and verification steps, not the orchestration mechanics.
