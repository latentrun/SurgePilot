# Your First Run

This guide creates the smallest useful loop: environment values → Scenario →
Test Plan → Run → report.

Before you begin, start the [tagged release or source full stack](./quickstart.md).
Source preview is not sufficient because it does not prepare a Runtime or a
Load Node.

::: warning Use a safe target
Choose a non-production endpoint that you own or have explicit permission to
test. Keep the initial load at one concurrent user for 60 seconds.
:::

## 1. Register the first Admin

Open the Web URL printed by startup and select **Sign up**. The first account
becomes an Admin and creates the **Default Workspace**. Later registrations
follow the deployment's signup policy.

## 2. Create an Env Group

An Env Group stores environment-specific values separately from a reusable
Scenario.

1. Open **Assets → Env Groups**.
2. Select **New Env Group**.
3. Name it `local`.
4. Add a plain variable with key `base_url` and the full origin of your test
   target, for example `https://test-api.example.com`.
5. Select **Save Env Group**.

Leave **Secret** cleared for `base_url`. Secret values are write-only and
masked after save; they are intended for credentials, not ordinary target
addresses.

## 3. Prepare a Load Node {#prepare-a-load-node}

A Run requires at least one initialized, idle Load Node. Choose the path that
matches how you started SurgePilot.

### Source full stack: register the Demo node

`make start-full-stack` starts a Compose-internal SSH node and prints its
connection details. From the repository root, verify its host-key fingerprint
and read its generated password locally:

```sh
ssh-keygen -lf .surgepilot/demo-load-node/ssh_host_ed25519_key.pub -E sha256
cat .surgepilot/secrets/demo-load-node-password.secret
```

Treat the password as a secret. Do not paste it into issues, logs, or source
files.

In SurgePilot:

1. Open **Resources → Load Nodes** and select **Register Load Node**.
2. Keep **Scope** set to **Private**.
3. Enter host `demo-load-node`, port `22`, and SSH user `surgepilot`.
4. Select **Scan key**. Compare the displayed SHA-256 fingerprint with the
   `ssh-keygen` output, then keep the scanned key.
5. Select **Password** authentication and enter the generated password.
6. Leave **Runner home** empty to use the API default, then select
   **Register Load Node**.
7. Return to **Load Nodes**, select **Initialize** for `demo-load-node`, and
   wait until its status is **Idle**.

### Tagged release: register an external node

The tagged release keeps the Demo node disabled. Provide a Linux machine with:

- Ubuntu 24.04 or newer, or Debian 12 or newer.
- `x86_64` (`amd64`) or `aarch64` (`arm64`).
- SSH connectivity from the SurgePilot API.
- `tar`, a POSIX shell, Java 11 or newer, and Python 3.12 or newer.

Open **Resources → Load Nodes → Register Load Node**, enter the SSH connection,
scan and independently verify the host-key fingerprint, and supply one of the
supported credential types. After registration, select **Initialize** and wait
for **Idle**. The node must be able to reach the API and InfluxDB node-facing
URLs that you confirmed during `surgepilot up`.

## 4. Create a Scenario

A Scenario is a reusable ordered request flow.

1. Open **Scenarios** and select **Create Scenario**.
2. Name it `health-check` and set **Base URL expression** to `${base_url}`.
3. Open the new Scenario and select **Add Step**.
4. Keep the method as **GET**, enter a safe target path such as `/health`, and
   keep the default expected-status assertion if `200` is correct for your
   target.
5. Select **Save**.

You can use **Debug Run** for focused validation after selecting the `local`
Env Group and an idle node. Debug Runs use one node and do not emit Monitoring
data. You may also continue directly to a low-load Test Plan.

## 5. Create a Test Plan

A Test Plan combines saved Scenarios with an Env Group, load settings,
resources, and optional SLA rules.

1. Open **Test Plans** and select **Create Test Plan**.
2. Name it `health-check-low-load` and create it.
3. Under **Global Context**, select the `local` Env Group.
4. Under **Resource Configuration**, choose **Manual selected nodes**, set
   **Pool Type** to **Private**, select the idle node, and choose **Done**.
5. Under **Scenario Orchestration**, select **Add Scenario** and choose
   `health-check`.
6. Keep **Concurrency / Node** at `1`, **Ramp-up** at `0`, and **Hold-for** at
   `60` for the first run.
7. Optionally add an SLA rule with a threshold appropriate for your target.
8. Select **Save**.
9. Under **Generated YAML Preview**, choose **Standard** and select
   **Preview YAML**. This preview is read-only and reflects the latest saved
   Test Plan revision.

## 6. Run and review

Select **Run Now**. SurgePilot opens the Run Report while the Run progresses.
Wait for a terminal state, then review:

- **Verdict Summary** for Run state, validity, and SLA result.
- **KPI Summary** and **Final Stats Preview** for response and error metrics.
- **Failure Diagnostics** when the Run does not complete as expected.
- **Snapshot Summary** for the immutable configuration used by this Run.
- **Artifacts** for downloadable logs and result files.
- **Nodes** for per-node execution state.

You can return later through **Runs** and select **View Report**. A report is a
record of the saved Run snapshot; later edits to the Env Group, Scenario, or
Test Plan do not rewrite that historical record.
