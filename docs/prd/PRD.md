# SurgePilot Performance Stress Testing Platform PRD

- Document status: Draft / For use by the AI and R&D team to develop the first version
- Scope of application: Define the product positioning, functional scope, information architecture, core processes, page paths and acceptance criteria of the first version of SurgePilot.
- Design principles: **With the user completing the closed loop of performance load testing as the center, the product concept, page organization, user path, copywriting and acceptance criteria directly adopt the definitions in this article. **
- Scope principle: **The functional scope of the first version maintains the focus on core capabilities and does not actively expand new functions; P0 aims to "run through the intranet MVP first" and prioritizes ensuring a complete closed loop from asset accumulation, test plan arrangement, single-node load testing execution to report judgment. **

---

## 1. Product positioning

### 1.1 Positioning in one sentence

SurgePilot is a performance load testing platform based on Taurus execution capabilities. It helps R&D, testing and performance engineers quickly turn API/business flows into reusable load testing scenarios, configure resources and load strategies, initiate execution, and obtain traceable reports and products after the execution.

### 1.2 Products should not be defined as

This product should not be defined as:

- Taurus YAML web editor;
- Simple JMeter launcher;
- Single load testing script upload tool;
- A file management system that only displays artifacts.

A more accurate product mentality should be:

> **Asset accumulation → Test plan arrangement → Load testing execution → Report judgment → Reuse and iteration** closed-loop platform.

### 1.3 Taurus' role in the product

Taurus is the underlying execution compatibility layer, not the primary user mind.

Most Taurus details should be hidden from the product side and only appear explicitly in:

- In-product Help / Script Help (P2);
- Advanced configuration explanation;
- Report artifact name or underlying execution log;
- R&D troubleshooting scenarios.

The relationship between product models and Taurus:

| Product Concept | Taurus Correspondence | User Mind |
| ------------------ | --------------------------------- | ------------------- |
| Scenario | `scenarios` / JMeter requests | A reusable business link |
| Env Group | `settings.env` / CLI env override | A set of environment variables, such as domain name, Token, region |
| Dependency File | JMeter running dependency file | Data files, scripts, certificates, tool files |
| Test Plan | Taurus top-level `execution` arrangement | One-time reusable load testing plan |
| SLA Rule | Taurus `passfail` | Load testing quality gate |
| Run | One `bzt` running instance | One actual execution record |
| Report / Artifacts | Taurus/JMeter output directory | Results, logs, CSV, HTML reports |

---

## 2. Design basis and product principles

### 2.1 Core product capabilities

The first version of the product main link consists of the following capabilities:

- Overview: Platform overview;
- Scenarios: scene design;
- Test Plans: test plan arrangement;
- Runs: execution records and reports;
- Env Groups: environment variable group;
- Dependency Files: dependency files;
- API Catalog: P2 API document asset management, only used for upload/list/details/delete of OpenAPI/Swagger Spec, without blocking P0/P1 execution closed loop;
- Load Nodes: load node management;
- Observability: monitoring entrance (P1, does not block P0 to execute closed loop);
- Help: In-product help page (P2); engineering documents such as README, deployment, operation and maintenance are not restricted;
- Admin: Platform basic management.

These capabilities constitute the product functional boundary, and subsequent chapters define concepts, pages, processes, and acceptance criteria respectively; the priority of P0/P1/P2 is subject to Section 13.

### 2.2 Product design judgment

1. **Separation of Scenario and Test Plan**

   - Scenario is responsible for "what to test".
   - Test Plan is responsible for "how to test, what resources to use, how long to press, and what are the passing standards."

2. **Run must save execution snapshot**

   - Execution records cannot change with subsequent modifications of Test Plan, Scenario, Env Group, and Dependency File.
   - Product and data model layers should make it clear that "execution snapshots" are a required component of Run.

3. **P1 Import only refers to cURL; API Catalog is the P2 document asset management capability**

   - OpenAPI/Swagger Spec is only used as a document asset management object in P2 and does not serve as a generation entry for P1.
   - P0 execution closed loop does not rely on API Catalog or cURL import; P0 is first created manually to complete Scenario → Test Plan → Run → Report.
   - P1 no longer contains any generation links for OpenAPI / API Catalog → Scenario / Test Plan; P1 Import only refers to cURL import.
   - P2 API Catalog is document asset management only and does not create, update or generate Scenario/Test Plan.

4. **Dependency Files are part of Scenario capabilities**

   - Parameterized data, uploaded samples, certificates and auxiliary scripts all need to be managed and traceable as assets.

5. **Run details page must be centered on the report conclusion**

   - When users enter the results page, they must first know: whether it has been completed, whether it passed, whether it is valid, and where the failure occurred.
   - Artifacts are troubleshooting material and should not be the primary focus of the results page.

### 2.3 Terminology and Experience Decisions

| Design Concerns | Product Decisions | Why |
| ----------- | ------------------------------- | ------------------- |
| Naming of reusable load testing solutions | Uniform use of **Test Plan/Test Plan** | More in line with the performance testing user mentality |
| Naming of an actual execution record | For users, it is uniformly called **Run / execution** | Exload testing a run record more naturally |
| Execution details experience | Run details page is **Run Report** | Give conclusions first, then products and logs |
| API document assets | P2 is collectively called **API Catalog** | It is the API document asset management entrance, not the P1 import or generation entrance |
| Environment variable management | collectively called **Env Groups/Environment Groups** | Product entities actually manage variables according to environment groups |
| Stress resource management | collectively called **Load Nodes / Load Nodes** | What users really manage are nodes |
| Taurus concept exposed | The product layer uses business terms, and Taurus details enter the product Help (P2) or engineering documents | Reduce the understanding cost for ordinary users |

---

## 3. Product goals and non-goals

### 3.1 Goals of this version

1. Define the first version of product concept, information architecture, page path and acceptance criteria.
2. Maintain the focus on the functional boundaries of the first version, and prioritize opening up the core closed loop; P0 is divided into Core (first to run through the intranet MVP) and Stability (to prevent stuck/pollution/mis-pressure), P1 will further enhance the experience, and P2 will undertake enterprise-level security and subsequent expansion.
3. Allow users to complete a complete closed loop from API/scenario creation to load testing execution and result viewing.
4. Allow the AI or R&D team to independently develop the first version of the product according to this article.
5. Design the Run Report as a "report and judgment entry" rather than a "product list".

### 3.2 New capabilities not added in this version

Except for subsequent independent items, this version will not do:

- AI generation scenario/AI parameter adjustment/AI report analysis;
- Independent Load Profile template library;
- Multi-tenant complex permission model;
- P0/P1 does not do OAuth 2.0 / OIDC / SAML / LDAP and other enterprise SSO integration; OAuth 2.0 / OIDC is put into P2;
- P0 does not provide email verification links, email password retrieval, or invitation-only registration;
- Load testinging resource queuing system;
- Automatic expansion and contraction or automatic procurement of cloud resources;
- Real-time link tracking/APM deep integration;
- Trend comparison, capacity baseline, historical regression analysis;
- Notification subscription and alarm push;
- Self-developed load testing execution engine replaces Taurus;
- Standalone script scene mode, Postman Collection, raw JMeter JMX upload;
- Independent API coverage analysis platform.

### 3.3 Success Criteria

The success of this version is not measured by "how many new features are added", but by the following indicators:

- New users can complete a Visual Scenario Debug Run within 15 minutes;
- Open source deployment users can complete the first Admin initialization through their email password and do not rely on enterprise SSO;
- Users can create editable Visual Scenario/Test Plan through manual configuration;
- Users can clearly distinguish between Scenario, Test Plan and Run;
- Users can judge whether the execution was successful, effective, and the main reason for failure on the Run Report homepage;
- Resources, environments, and dependency files can all be clearly understood as load testing assets instead of scattered configurations.

---

## 4. User roles and core tasks

### 4.1 Main user roles

| Role | Goal | Typical Behavior |
| ------- | ------------------- | ---------------------------------------------------------------------------- |
| RD / QA | Quickly construct interfaces or business link load testings | Manually create Scenario, Debug Run, view security failure reasons, logs and artifacts; P1 can be accelerated through cURL/API import and failed requests plug-in preview; register the Private Load Node of this Workspace on demand |
| Performance Engineer | Design a formal load testing plan and determine the results | Arrange multiple scenarios, configure resources and SLA, execute and analyze reports; manage the team's own Private Load Node |
| Resource Manager | Manage public load nodes | Register and maintain Public Load Node, initialize nodes, view node status and logs |
| System administrator | Complete platform initialization, configuration check and basic account management | Be the first to register as Admin, view Setup Status, P1 management system-level configuration |
| Observer | View the overall status of the platform and historical execution | View the Overview, Run list, report, and monitoring pages |

### 4.2 User core tasks

1. (P1) I have an API document and want to quickly generate a load testing plan.
2. I have a business link and want to configure requests, extract variables and assertions visually.
3. I want to use specified environment variables to perform load testing.
4. I hope to manually select a load node in P0; P1 supports automatic allocation and multi-node execution.
5. I want to define an SLA and know whether it passed or not after execution.
6. I want to see statistics, failure reasons, logs, and full artifacts; a preview of the failed requests plugin is available on P1.
7. I want to mark a certain abnormal execution as Invalid to avoid polluting the statistical caliber.
8. As an open source deployment user, I hope to quickly register and log in using my email and password, without relying on enterprise SSO.
9. As an administrator, I want to know whether the system configuration is complete, such as whether the default Workspace, Load Node, and Runner internal token are available; after enabling Monitoring on P1, I also need to check whether the Grafana and InfluxDB configurations are complete.
10. As a business team member, I hope to self-register the Private Load Node of this Workspace to avoid handing over the SSH username and key to the platform administrator.

---

## 5. Core concepts and naming conventions

### 5.1 Workspace / workspace

Workspace is a user-understandable boundary for data isolation and collaboration.

- Each Scenario, Test Plan, Env Group, Dependency File, Run, and Load Node private pool resources belong to a Workspace; after P2 enables API Catalog, the API Spec also belongs to the Workspace.
- P0 must have a Workspace-aware data model and request context: business data must not be designed to be globally shared or implicitly unowned.
- P0 only exposes a default Workspace to users, which is used to run through the core execution closed loop first; the frontend can display the current Workspace, but does not provide Workspace switching, creation, editing, archiving, member management or permission system.
- P1 enables user-visible multi-Workspace capabilities based on P0's Workspace-aware, including Workspace switching, as well as management capabilities such as creation, editing, and archiving.
- URLs, APIs, and data models should all be designed around Workspace.
- Most business API requests must carry workspace context, and it is recommended to use `x-workspace-id` or equivalent authentication context.
- When P1 enables Workspace switching, the details page should return to the corresponding list page to avoid displaying detailed data from other spaces.

Naming requirements:

- The user interface is unified using **Workspace/Workspace**.

### 5.2 Account / User / Role

P0 adopts a local account system, giving priority to low-threshold use of open source deployment and local deployment.

Account rules:

- Users use email + password to register and log in;
- The mailbox is globally unique;
- Do not require email verification link to be sent;
- P0 is not required to provide email to retrieve the password;
- Passwords must be stored in a secure hash, plain text or reversibly encrypted storage is not allowed;
- The basic user fields include at least: Email, Display Name, Role, Status, Created At, and Last Login At.

Initialization rules:

- When the system does not have any users, the first successfully registered user automatically becomes Admin;
- Subsequent registered users will become User by default;
- Whether open registration is allowed is controlled by deployment-level configuration. It is recommended that the configuration item is `ALLOW_SIGNUP` or equivalent; this configuration only affects new user registration after the first Admin is initialized;
- When the system does not have any users, it must be allowed to complete the initialization of the first Admin, or by the deployer through the equivalent bootstrap admin configuration;
- If open registration is turned off and the system already has an Admin, new user creation/invitation capabilities will be placed in P1 user management.

Role rules:

| Role | P0 Permission Boundary |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Admin | Can access Admin Setup Status, manage Public Load Nodes, view default Workspace data, and perform normal user operations; can view the basic status of all Load Nodes and Disable abnormal nodes for platform security; cannot view or export sensitive credentials of Private Load Nodes |
| User | can create and manage Scenario, Test Plan, Env Group, Dependency File within their own authority; can initiate Run and view reports; can register and manage Private Load Nodes of the current Workspace |

P1 enhancement:

- User list, disable/enable users;
- Admin manually creates users or resets user passwords;
- Workspace switching and basic management; no fine-grained roles such as Workspace Owner / Resource Manager are introduced.

P2 enhancements:

- OAuth 2.0 / OIDC login;
- SSO group to Admin/User mapping;

### 5.3 Scenario / scene

Scenario is a reusable visual load testing link.

This version only supports **Visual Scenario**:

| Pattern | User Mind | Typical Sources | Description |
| ------ | ------- | ------------------------ | ------------------------------ |
| Visual | Visual interface link | P0 is created manually; P1 can be imported from cURL or API Spec | Corresponding to JMeter/Taurus requests capability subset |

This version does not support standalone script scene mode, Postman Collection, raw JMeter JMX upload and other Scenario modes.

Step in Visual Scenario should contain:

- Method
- Path / URL Preview
- Headers
- Query Params
- Body
- Upload Files
- Extractors
- Assertions
- Scripts (only refers to JMeter JSR223 / Groovy Step scripts, configurable before request / after response, does not represent independent script scenario mode)
- Settings, such as think time, timeout

### 5.4 Env Group / Environment variable group

Env Group is a set of runtime variables.

Typical variables:

- base_url
- token
- region
- tenant
- app_key / app_secret

Principles of use:

- Variables should be referenced in Scenarios rather than hard-coded environment differences;
- Test Plan selects an Env Group;
- Debug Run can also select Env Group;
- P0 treats the Env Group variable as a normal variable, which is suitable for intranet MVP and test credentials;
- Secret type variables, sensitive value display/replication restrictions, and Secret encryption and decryption boundaries in Run Snapshot are placed in P2.

### 5.5 Dependency File / dependency file

Dependency File is a file that needs to be mounted or downloaded to the running environment for load testing execution.

Typical documents:

- CSV parameterized data;
- JMeter JSR223 script;
- Upload the sample files required by the interface;
- Certificates and configuration files;
- P2 can extend ZIP / TAR / TGZ and other dependent packages.

Product requirements:

- P0 only supports MinIO as the object storage backend for Dependency File and artifacts, and does not support local file storage, AWS S3 or other cloud object storage;
- P0 supports ordinary file upload, list, download and deletion based on MinIO;
- P0 does not require file preview, version management or automatic decompression of compressed packages;
- P1 only adds Dependency File single file preview;
- Env Group / Dependency File tag is permanently removed and does not enter any stage;
- P2 can support safe decompression of ZIP / TAR / TGZ dependent packages at runtime;
- The relative directory structure within the package must be retained after P2 is decompressed, and flattening is not allowed;
- P2 decompression must reject files that escape target directories such as path traversal, absolute paths, illegal soft links, etc.;
- When Scenario references dependent files, the reference relationship needs to be preserved in the execution snapshot;
- Before deleting dependent files, you need to be reminded that it may affect existing scenarios or perform reproduction.

### 5.6 Test Plan / Test Plan

Test Plan is a reusable load testing plan.

> Products uniformly use **Test Plan/Test Plan** as the product name, page name and domain name of the reusable load testing solution.

Test Plan includes:

-Basic information: name, label, remarks;
- Global Context: environment variable group, execution mode;
- Resource Configuration: resource pool, number of nodes, automatic/manual selection;
- Scenario Orchestration: one or more Scenarios and their load parameters;
- SLA Rules: pass/fail/stop rules;
- Global Settings: timeout;
- Run Actions: P0 supports Run Now and Debug; P2 supports Schedule Run.

### 5.7 Load Settings / Load parameters

This version does not add a new independent Load Profile template library, but the Load Settings of each Scenario should be clearly presented in the Test Plan.

Fields:

- concurrency per node
- ramp-up
- hold-for
- iterations
- throughput
- steps
- delay

Rules:

- Visual Scenario works with full load parameters;
- Bulk Apply is only a batch filling tool within the current Test Plan, not a reusable template.

### 5.8 Run / execute

Run is an actual run record.

Key attributes:

- Status: Initializing, Running, Stopping, Finished, Failed, Aborted;
- Type: Standard, Debug;
- Validity: Valid, Invalid;
- SLA results: Passed, Failed, Not Evaluated;
- Trigger person, trigger source;
- Trigger source enumeration: Test Plan Run, Test Plan Debug, Scenario Debug; P2 adds Schedule after enabling Schedule Run;
- Start time, end time, heartbeat time;
- Belonging to Test Plan or Scenario Debug Run;
- Execute snapshot;
- Node records;
- Report summaries and artifacts.

### 5.9 Report / Execution report

Report is not a separate new entity, but a product representation of Run Report.

Report should summarize:

- Execution status;
- Is it valid?
- Whether the SLA is met;
- Summary of core indicators;
- Reasons for security failure and diagnostic tips;
- P0 does not contain failed_requests plug-in preview; P1 can extend this capability;
- finalstats preview;
- Test Plan snapshot;
- Artifacts list and download entrance;
- Node information.

---

## 6. Information Architecture

### 6.1 Main Navigation

The product uses the following information architecture:

1. **Overview**: Platform overview and quick entry
2. **Design**: Design the load testing object
   - Scenarios
   - API Catalog(P2)
3. **Plan**: Arrange load testing plan
   - Test Plans
4. **Runs**: Execution records and reports
   - Runs & Reports
5. **Assets**: running assets
   - Env Groups
   - Dependency Files
6. **Resources**: Pressure resources
   - Load Nodes
7. **Observability**: External monitoring entrance (P1)
   - Monitoring
8. **Admin**: Startup configuration, account and system management
9. **Help**: In-product help page (P2); project README/deployment/operation and maintenance documents are not restricted

### 6.2 Recommended routing structure

New developments should directly adopt a semantically clear routing structure:

| Page | Recommended Route | Description |
| --------------------- | --------------------------- | ----------------------- |
| Landing | `/` | P2: ADR-0013 authorized public static Marketing Landing; visible without authentication, authenticated jump `/overview` |
| Login | `/login` | Email password login |
| Register | `/register` | Email and password registration; the first registered user automatically becomes Admin |
| Overview | `/overview` | Platform Overview |
| API Catalog | `/api-catalog` | P2: API document asset list and upload |
| API Spec Detail | `/api-catalog/:specId` | P2: API document details; no import entry is provided |
| Scenarios | `/scenarios` | Scenario List |
| Scenario Designer | `/scenarios/:scenarioId` | Visual Scenario editing portal |
| Test Plans | `/test-plans` | Test Plan List |
| Test Plan Editor | `/test-plans/:planId` | Create and edit test plans |
| Runs | `/runs` | Execution record list |
| Run Report | `/runs/:runId` | Execution details are the report page |
| Env Groups | `/assets/env-groups` | Environment Group Management |
| Dependency Files | `/assets/dependency-files` | Dependency file management |
| Load Nodes | `/resources/load-nodes` | Pressure Node Management |
| Register Load Node | `/resources/load-nodes/new` | Register Node |
| Monitoring | `/observability/monitoring` | Monitoring entrance (P1) |
| Help | `/help` | P2: In-product help documentation |
| Admin | `/admin` | System management entrance |
| Admin Setup Status | `/admin/setup-status` | P0 read-only configuration and health status |
| Admin Users | `/admin/users` | P1 User Management |
| Admin System Settings | `/admin/system-settings` | P1 System Configuration UI |

### 6.2.1 P0 interface language

The first version of the P0 front-end interface uses English monolingual user copy.

Constraints:

1. P0 does not introduce i18n framework.
2. P0 does not provide a language switcher.
3. P0 is not going to hide locale bundles.
4. User-visible copywriting should be managed centrally to avoid being scattered in business logic.
5. Error display should prioritize front-end copy mapping based on stable errors `code` and field-level `details[].code`.
6. API `message` is English fallback copywriting and is not used as front-end business logic or localization key.


### 6.2.2 P2 Static Marketing Landing

ADR-0013 Only the static `/` Marketing Landing and Stitch Logo visual migration is authorized to be published. This license does not add new Docs, API Guide, Community, Security, GitHub, Help, CMS, SDK, MCP or other product capabilities. Unauthenticated access to `/` can display Landing; authenticated access to `/` must jump to `/overview`. Landing's interactive links can only point to implemented `/login` , `/register` or in-page anchors; items without real targets must be rendered disabled / non-interactive.

### 6.3 Page hierarchy

```text
Overview

Scenarios
  ├─ Scenario List
  ├─ Create Scenario
  └─ Scenario Designer
      ├─ Visual Designer
      ├─ Import from cURL [P1]
      └─ Debug Run

Test Plans
  ├─ Test Plan List
  ├─ Create Test Plan
  └─ Test Plan Editor
      ├─ Basic Info
      ├─ Global Context
      ├─ Resource Configuration
      ├─ Scenario Orchestration
      ├─ SLA Rules
      ├─ Global Settings
      ├─ Run Now
      ├─ Debug
      └─ Schedule Run [P2]

Runs
  ├─ Run List
  └─ Run Report
      ├─ Verdict Summary
      ├─ KPI Summary
      ├─ Failed Requests Preview
      ├─ Final Stats Preview
      ├─ Test Plan Snapshot
      ├─ Artifacts
      └─ Nodes

Assets
  ├─ Env Groups
  ├─ Dependency Files
  └─ API Catalog [P2]
      ├─ API Spec List
      ├─ Upload Spec
      └─ API Spec Detail

Resources
  ├─ Load Node List
  ├─ Register Node
  ├─ Edit Node
  ├─ Initialize Node
  └─ Init Logs

Observability [P1]
  └─ Monitoring
      ├─ Read-only Grafana Dashboard entry
      ├─ JMeter Backend Listener / InfluxDB write configuration
      └─ Not Configured State

Admin
  ├─ Setup Status
  ├─ Users [P1]
  ├─ Workspace Management [P1]
  └─ System Settings [P1]
```

---

## 7. Core user flow

### 7.1 API Document Asset Management (P2)

Goal: The user already has OpenAPI/Swagger documentation and wants to save, view, and delete API documentation assets in the platform.

Priority description: This process is P2 document asset management capability. P0/P1 does not depend on API Catalog; P1 Import only refers to cURL import.

Process:

1. The user enters the API Catalog.
2. Upload OpenAPI/Swagger Spec.
3. The system saves the document assets and displays them in the list.
4. The user views Spec details.
5. The user deletes Specs that are no longer needed.

Design description:

- `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.`
- P2 API Catalog does not include version diff, operation import, coverage analysis, API → Scenario/Test Plan generation.
- P1 no longer contains any generation links for OpenAPI / API Catalog → Scenario / Test Plan; P1 Import only refers to cURL import.

Acceptance criteria:

- Spec can be seen in the list after successful upload.
- The Spec details page can display structured API documents and fall back to display the original content in case of failure.
- Spec can be deleted.
- API Catalog does not provide API document-based import, create Test Plan action or OpenAPI Step automatic generation entry.

### 7.2 Manually create Visual Scenario and Debug

Goal: The user wants to visually create an interface link.

Process:

1. The user enters Scenarios.
2. Create a Visual Scenario.
3. Configure Global Config in Scenario Designer.
4. Add Step manually; P1 can import Step from cURL. P1 does not provide API Catalog / OpenAPI import step.
5. Configure request parameters, extractors, assertions, scripts, and Step Settings.
6. Select Env Group.
7. Click Debug Run.
8. Manually select an Idle stress node.
9. The system saves the current Scenario and creates a Debug Run.
10. The user jumps to the Run Report to view the results.

Acceptance criteria:

- Automatically save Visual Scenario before Debug Run;
- P0 must manually select an available node;
- The Run type created by Debug Run is Debug;
- Debug Run uses low-risk default workloads: single node, single concurrency, single or minimal iteration;
- Show understandable errors on failure instead of just the underlying exception.

### 7.3 Create a formal Test Plan and execute it

Goal: The user arranges one or more scenarios into a formal load testing plan.

Process:

1. The user enters Test Plans.
2. Create or edit a Test Plan.
3. Fill in the basic information.
4. Select Env Group and execution mode: Parallel / Sequential.
5. Configure resources: Public/Private, and manually select an Idle node.
6. Add one or more scenarios.
7. Configure Load Settings for each scenario.
8. Configure SLA Rules.
9. Save the Test Plan.
10. The user selects Run Now or Debug.
11. The system creates Run.
12. The user views the Run Report.

Acceptance criteria:

- Official Run cannot be executed without adding Scenario;
- P0 only supports manual selection of an available node;
- P1 now supports Auto allocation, Node Count and multi-node execution;
- Give understandable errors when resources are unavailable;
- Save the Test Plan snapshot when Run is created;
- Artifacts can be downloaded after execution.
- Standard Run defaults to Valid, Debug Run defaults to Invalid.

### 7.4 Manage pressure-generating nodes

Goal: Make the platform have available load resources while avoiding centralizing the team's private machine credentials to the platform administrator.

Management boundaries:

- Public Load Node is a public resource of the platform, which is registered, initialized and maintained by Admin/resource administrator and can be used by multiple Workspaces;
- Workspace Private Load Node is a team-owned resource that is self-registered, initialized and maintained by the current Workspace user. It is only visible and available to the current Workspace;
- Admin can view the basic status and health of Private Load Node, and can disable abnormal nodes for platform security, but is not allowed to view or export its SSH password, private key and other sensitive credentials.

Process:

1. The user enters Resources / Load Nodes.
2. Register the node and fill in the IP, SSH Port, SSH User, authentication method, Pool Type, Maintainer, and Remark.
3. Select a password, upload a private key or the platform generates a key.
4. Initialize the node.
5. Check the initialization log.
6. After the node enters Idle, it can be allocated.

Acceptance criteria:

- New nodes are not directly operational by default and need to be initialized;
- Initialization log can be viewed;
- Node status is clearly displayed: Idle, Busy, Offline, Uninitialized;
- Busy nodes cannot be allocated repeatedly;
- Public nodes can only be created, edited, and deleted by Admin/resource administrator;
- Private nodes belong to the current Workspace, and current Workspace users can create, edit, initialize, and delete them by themselves;
- The credentials of the Private node are not echoed in text after being saved, nor are they displayed to the Admin.

---

## 8. Functional requirements

### 8.1 Overview

Goal: Give users an overview of platform operation and a quick entry.

Should show:

- Overview of recent executions;
- Execution status statistics;
- Summary of resource status;
- Common entrances: Create Scenario, Create Test Plan, Runs; after P2 is enabled, the API Catalog document asset management entrance can be added.

Statistical caliber:

- Overview only counts Valid's Standard Run by default;
- Debug Run does not enter Overview result statistics by default;
- After P2 enables Schedule Run, the Scheduled Job does not enter the Overview Run statistics before triggering the creation of a Run, and can be displayed separately as the "upcoming execution" number;
- Invalid Run does not enter the default statistics, but can be viewed in Run List / Run Report.

This version does not require new complex trend analysis.

### 8.2 Workspace

P0 function:

- Automatically initialize or bind a default Workspace;
- Display the current default Workspace as read-only context information;
- The Workspace context should be retained in the URL, but P0 does not provide an entry for users to actively switch Workspaces;
- API requests should automatically bring Workspace context;
- The existing Scenario, Test Plan, Run, Report, Env Group, Dependency File, Private Load Node and other functions of P0 all apply to the current default Workspace.

P1 function:

- Support users to switch between multiple Workspaces;
- Support Workspace creation, editing, archiving and other management capabilities;
- Supports a more complete Workspace management entrance.

Priority description:

- The focus of P0 is to isolate data by Workspace from the bottom of the system, but the product form is still a "core closed loop under the default Workspace";
- The focus of P1 is to increase the user operation capabilities of multiple workspaces without destroying the core functions of P0;
- After P1 switches Workspace, the existing functions of P0 continue to be available, but the data range is switched to the new current Workspace.

Interaction requirements:

- After P1 enables switching Workspace, if you are currently on the details page, you should jump back to the corresponding list page;
- When the Workspace is missing, the wrong space data should not be silently requested and the user should be prompted for selection.

### 8.2.1 Accounts & Access

Positioning:

The account system serves the rapid availability and execution audit of open source deployment, and P0 does not introduce enterprise SSO dependencies.

P0 function:

- Email + password registration;
- Email + password login;
- Logout;
- Get the current logged in user information;
- The first registered user automatically becomes Admin;
- Subsequent registered users will become User by default;
- When `ALLOW_SIGNUP` is closed, the first Admin must still be allowed to initialize; after the initialization of the first Admin is completed, ordinary users are no longer allowed to self-register;
- All creation, update, and execution actions after logging in should record the user's identity for Created By, Updated By, and Triggered By;
- Admin can access Admin Setup Status;
- The Admin navigation entrance is only visible to Admin;
- Users who are not logged in cannot access the business page and business API.

P0 does not do:

- Email verification link;
- Retrieve password via email;
- Invite registration;
- Complex RBAC;
- Workspace member permissions;
- OAuth 2.0 / OIDC / SAML / LDAP;
- General log and error message desensitization framework.

Security requirements:

- Passwords must be saved using a secure hash algorithm;
- There should be basic current limiting or anti-explosion protection if login fails;
- Session/Access Token should have expiration time;
- The client should clean up the login state after Logout;
- P0 does not build general sensitive information desensitization capabilities, and the default deployment boundary is the enterprise intranet or controlled network; passwords, password hashes, and login status should not be returned to the frontend as business fields.

P1 enhancement:

- User management UI: user list, disable/enable, reset password or create users;
- Configurable whether to turn off local registration;
- Does not introduce fine-grained roles such as Workspace Owner / Resource Manager.

P2 enhancements:

- OAuth 2.0/OIDC login for enterprise SSO;
- A local User is automatically created when an SSO user logs in for the first time;
- SSO group/claim to Admin/User mapping;
- Desensitization of general sensitive information in logs and error messages.

### 8.3 API Catalog(P2)

Positioning:

API Catalog is P2 API document asset management capability. P0/P1 does not depend on API Catalog; the main process of P0 is subject to manual creation, and P1 Import only refers to cURL import.

Fixed caliber: `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.`

P2 basic functions:

- Upload OpenAPI/Swagger Spec;
- Spec list;
-Spec details display;
- Delete Spec.

Fields:

- Title
- Version
- Original Filename
- Size
- Content Format
- MD5
- Created By
- Updated At

Interaction requirements:

- The list is refreshed after the upload is successful;
- The details page gives priority to displaying structured API documents, and falls back to display the original content in case of failure;
- API Catalog does not provide the action of creating Test Plan;
- API Catalog does not provide an import entry based on API documents;
- API Catalog does not create, update, or generate Scenario/Test Plans.

OpenAPI Step automatically generates:

OpenAPI Step automatically generates data from P1 to P2, and does not fall within the basic scope of P2 API Catalog document asset management. If you make a separate project in P2 later, you still cannot extend the API Catalog to Scenario/Test Plan to generate links. P2 API Catalog also does not include version diff, operation import, coverage analysis, API → Scenario/Test Plan generation.

P2 If the independent item OpenAPI Step is automatically generated, consider supporting:

- Spec format: Swagger 2.0, OpenAPI 3.0, OpenAPI 3.1;
- Path parameter: `/users/{id}` generates `/users/${id}`, and prompts in the generated result that `id` needs to be filled in the Env Group or Step default value;
- Required Query parameter: fill in the example value when there is example/default, otherwise the `${paramName}` placeholder will be generated; the Optional Query parameter will not be generated by default unless Spec provides example/default;
- Header parameter: Reserved Spec required header; public authentication header is injected by Auth & Common Headers, and the value uses variable expression;
- JSON Body: Use OpenAPI example first, then use default, and then generate the minimum example according to the schema; if it cannot be generated safely, leave it blank and prompt the user to supplement;
- Unsupported Body/Schema: Does not prevent import, but must display warning in the generated results to avoid users mistakenly thinking that the request body has been completely generated.

Subsequent enhancements may consider supporting:

- `application/x-www-form-urlencoded`: Generate editable key-value rows;
- `multipart/form-data`: Generate text fields and file placeholders. The file field needs to prompt the user to select Dependency File or upload a sample file;
- More complete example generation for complex schemas, such as oneOf / anyOf / allOf, deeply nested objects, array examples, etc.

Spec update rules:

- API Specs are managed as document assets; re-uploading new documents for the same service should form a new Spec record or coverage strategy, as determined by P2 design.
- P2 API Catalog does not perform difference detection, version diff, operation import, coverage analysis or API → Scenario/Test Plan generation after API Spec update; if subsequent enhancements are made, the project must be re-opened.

### 8.4 Scenarios

#### 8.4.1 Scenario List

Function:

- List display Scenario;
- Search/Filter;
- Label display;
- create;
- Edit;
- clone;
- Delete.

Fields:

- Name
- Tags
- Updated At
- Updated By
- Remark / Description

Tag stage caliber: `This is existing metadata, not a new P1 deliverable. P1 does not expand tags to other assets.` Scenario tags are retained as existing lightweight metadata; P1 does not add a new front-end list to filter the UI by tag.

#### 8.4.2 Visual Scenario Designer

Function:

- Step list;
- Add/Delete/Sort Step;
- Edit request method, path, Headers, Params, Body, Files;
- Configure Extractors;
- Configure Assertions;
- Configure Scripts;
-Configuration Settings;
- Global Config;
- Import from cURL(P1);
- View Generated YAML (P1, read-only);
- Save;
- Debug Run.

Design requirements:

- The Step editing area should be highlighted to request preview;
- Extractor and Assertion should be enabled;
- P1 When cURL import is enabled, sensitive information risks should be prompted;
- P1 does not contain any OpenAPI/API Catalog → Scenario/Test Plan generated links; P1 Import only refers to cURL import;
- Necessary verification should be done before saving, such as extractor naming and file reference validity.
- Scripts only supports JMeter JSR223 / Groovy fragments, and the execution time is limited to before request and after response; Python, Shell or any long life cycle scripts are not supported.
- View Generated YAML is a P1 diagnostic capability: a read-only drawer is used to display the current Visual Scenario translated Taurus/JMeter execution configuration to help advanced users and developers locate translation issues; editing of YAML is not allowed here.

### 8.5 Env Groups

Function:

- Env Group list;
- Create/Edit/Delete;
- Manage variable key values;
- Support copying Env Group.

Design requirements:

- Env Group should be expressed as "running environment", not an isolated KV;
- When used by Test Plan or Debug Run, the name should be displayed instead of the ID;
- P0 does not provide Secret types, sensitive value copy restrictions, or sensitive value display protection; these capabilities enter P2.

### 8.6 Dependency Files

Function:

- Upload ordinary files;
- list;
- Download;
- Delete unreferenced files;
- P1 only supports single file preview;
- P2 supports ZIP/TAR/TGZ dependency package upload and runtime safe decompression;
- Env Group / Dependency File tags are permanently removed and do not enter any stage.

Design requirements:

- P0 files and products are written to MinIO uniformly; no local disk storage mode or AWS S3 / other cloud object storage adaptation is provided;
- Clearly distinguish the file name, display name, version, and type;
- P0 does not require online editing of file content;
- When a file is referenced by a Scenario, it should be clearly visible in the Scenario;
- The P0 file reference path shall be based on a single file name or a relative file path;
- Files referenced by Scenario/Test Plan are not allowed to be deleted directly;
- P1 single file preview cannot be expanded to compressed package decompression, online editing or tag system;
- P2 dependent packages are automatically decompressed when running, and the directory structure within the package is maintained;
- The P2 file reference path should be based on the relative path after decompression, such as `lib/utils.groovy`, `data/users.csv`;
- P2 prohibits flattening compressed package contents into the same directory;
- P2 should give clear errors for illegal compressed packages, such as path crossing, empty package, and size limit exceeded.

### 8.7 Test Plans

#### 8.7.1 Test Plan List

Function:

- List display Test Plan;
- Search/Filter;
- Label display;
- create;
- Edit;
- clone;
- Delete;
- Run quickly.

Fields:

- Name
- Tags
- Run Mode
- Env Group
- Selected Node
- Updated At
- Updated By

Tag stage caliber: `This is existing metadata, not a new P1 deliverable. P1 does not expand tags to other assets.` Test Plan tags are retained as existing lightweight metadata; P1 does not add a new front-end list to filter the UI by tag.

#### 8.7.2 Test Plan Editor

Page structure:

1. Basic Information
2. Global Context
3. Resource Configuration
4. Scenario Orchestration
5. SLA Rules
6. Global Settings
7. Actions

##### Basic Information

Fields:

- Test Plan Name
- Tags
- Remark

##### Global Context

Fields:

- Env Group
- Run Mode:Parallel / Sequential

Rules:

- Parallel: Multiple Scenarios are executed simultaneously;
- Sequential: Execute in the order of the Scenario list.

##### Resource Configuration

P0 field:

- Pool Type:Public / Private
- Selected Node

P0 rules:

- P0 only supports Manual single node mode, the user must select a specific Idle node;
- Public Pool uses platform public nodes and is maintained by Admin/resource administrator;
- Private Pool only uses the Private Load Nodes of the current Workspace and is maintained by the team itself;
- Private Pool nodes are subject to Workspace constraints and cannot be allocated by other Workspaces;
- The selected node must be Idle; Busy / Offline nodes are not executable;
- Block execution when the node is unavailable and prompt the reason why the node is unavailable;
- The resource configuration area should display the expected concurrency of the single node to help users understand the actual pressure scale.

P1 enhancement:

- Resource Mode:Auto / Manual;
- Node Count;
- Selected Nodes;
- Auto mode automatically allocates Idle nodes according to Node Count;
- Manual multi-node mode allows users to select multiple nodes;
- In multi-node mode, the Node Count is automatically derived from the number of Selected Nodes. The field should be read-only or hidden. The inconsistent state of "Node Count=5 but only 3 units are selected" is not allowed;
- The resource configuration area should show the expected total concurrency: `Node Count × per-node concurrency`.

##### Scenario Orchestration

Function:

- Add Scenario;
- Remove Scenario;
- Adjust the order;
- Configure Load Settings for each Scenario;
- Bulk Apply to the current list.

Fields:

- Scenario
- Concurrency / Node
- Ramp-up
- Hold-for
- Iterations
- Throughput
- Steps
- Delay

Rules:

- At least one Scenario can be officially executed;
- Bulk Apply does not save as template.
- Bulk Apply only overwrites fields that users have filled out in bulk forms;
- Fields left blank in Bulk Apply must not overwrite the existing values of each Scenario item;
- P0 Bulk Apply only needs to display the summary of "the following fields that will cover N Scenarios" and does not require item-by-item before/after diff;
- Bulk Apply item-by-item preview diff can be used as a subsequent experience enhancement if necessary, and will not be used as P0 acceptance.
- Bulk Apply example: The user fills in Concurrency / Node = 100, Ramp-up = 60s, and Hold-for is left blank; the system only overwrites Concurrency / Node and Ramp-up in batches, and does not change the existing Hold-for of each Scenario item.
- Single node concurrency needs to provide soft upper limit protection: for low-frequency team usage scenarios, when P0 exceeds 1,000 by default, a strong warning is displayed and the user is required to confirm twice; the threshold should support deployment-level configuration.
- In P1 multi-node mode, the total concurrency also needs to provide soft upper limit protection: when `Node Count × per-node concurrency` exceeds the system configuration threshold, OOM/node unavailability risks will be prompted.
- The backend still needs to do basic hard verification: concurrency, duration, throughput and other values must be within a reasonable non-negative range to avoid extreme inputs from directly bringing down the load testing engine.

##### SLA Rules

Fields:

- Subject
- Condition
- Threshold
- Label
- Timeframe
- Logic
- Action:continue / stop

Rules:

- SLA can be null;
- Required fields must be completed when SLA is not empty;
- P0 minimum acceptance supports at least a single SLA Rule; if multiple rules are implemented, the product wording of this article will not be changed;
- The Subject list exposed by the first version of the front-end drop-down is: `avg-rt`, `p90`, `p95`, `p99`, `fail`, `succ`, `hits`, `bytes`, `rc<CODE>`;
- `rc<CODE>` means matching by response code, such as `rc500`, `rc4??`, `rc*`; the advanced Taurus subject is not exposed in the first version of the UI;
- `Label` is used to limit a single sampler/API; when empty, it represents global aggregation;
- `Timeframe` and `Logic` are used to express continuous windows, such as `for 10s`, `within 1m`;
- `stop` means interrupt execution when triggered;
- `continue` means execution continues but the final report should be marked as failed or not passed.

##### Actions

- Save Configuration;
- Run Now;
- Debug;
- Schedule Run(P2);
- Preview Generated YAML (P1, read-only).

Rules:

- Create a new Test Plan and save it before running;
- Debug uses low-risk default payload;
- Schedule Run is a P2 capability: one-time future time scheduling, does not extend complex periodic tasks.
- After P2 enables Schedule Run, the Test Plan Editor/Detail should display the Scheduled Jobs that have not been triggered by the Test Plan, including at least the trigger time, status, creator, and Cancel operation;
- Preview Generated YAML is a P1 diagnostic capability that displays the read-only configuration that will be submitted to Taurus after the Test Plan is compiled. It is used for pre-execution confirmation and troubleshooting. YAML editing capabilities are not provided.

### 8.8 Runs / Reports

#### 8.8.1 Run List

Function:

- List display execution records;
- Filter by status;
- Filter by validity;
- Filter by trigger source;
- Search by keyword;
- Label display (if any);
- Quick filtering in the last 24 hours;
- Stop Running / Initializing Run;
- mark Valid / Invalid;
- Enter details.

Fields:

- Run ID
- Test Plan / Scenario
- Run Type
- Status
- Validity
- SLA Result
- Triggered By
- Trigger Source
- Start At
- End At
- Duration
- Tags (if displayed, must use Scenario/Test Plan tags from the snapshot)

Fixed caliber: `Run tag display/filter, if present, must use snapshot Scenario/Test Plan tags; Run has no independent mutable tag model.` Run List currently only displays tags and does not add tag filtering UI.

#### 8.8.2 Run Report

First version layout priority:

1. **Verdict Summary**

   - Status
   - Run Type
   - Validity
   - Duration
   - Triggered By
   - SLA Result:Passed / Failed / Not Evaluated
   - Error Message (if any)

2. **KPI Summary**

   - Required: total requests
   - Required: failed requests
   - Required: error rate
   - Required: average response time
   - Required items must be permanently displayed in the Run Report; if the parsing fails or the execution does not generate data, `N/A` and the missing reason should be displayed and cannot be hidden silently.
   - Optional: percentile indicators, such as P90 / P95 / P99, depending on whether finalstats / summary is output
   - Optional: throughput / TPS, depending on whether finalstats / summary is output

3. **Failure Diagnostics**

   - P0 displays security failure reasons, error messages, heartbeat/self-healing prompts and artifact warnings;
   - P0 does not display `failed_requests.csv` preview;
   - failed requests plug-in preview, error type, interface, status code and error message table are defined by P1.

4. **Final Stats Preview**

   - Preview of finalstats.csv or similar statistics file.

5. **Test Plan Snapshot**

   - Env Group;
   - Run Mode;
   - Scenario Orchestration;
   - SLA;
   - Global Settings.

6. **Artifacts**

   - artifacts.zip;
   - Report HTML, if generated by the underlying tool, can be downloaded as a zip file; P0 does not render separately or preview inline;
   - logs;
   - csv / xml / jtl;
   - P0 only supports inline summary preview of finalstats, other products can be downloaded; P1 can be expanded to more single file previews.

7. **Nodes**

   - The node used this time;
   - Node IP;
   - Node operating status.

8. **Live Monitoring(P1)**

   - P0 does not require the display of Live Monitoring and does not affect the core reporting loop of Run Report;
   - P1 displays the "Open Monitoring" entrance after being enabled;
   - After P1 is enabled, it provides a read-only Monitoring entrance, which can jump to or embed Grafana Dashboard;
   - Running / Stopping stage represents real-time observation;
   - P1 supports the historical playback entrance filtered by the current Run ID / runId in Terminal state, subject to InfluxDB retention restrictions;
   - P1 If Grafana Dashboard supports runId variable, priority should be given to filtering by current Run ID;
   - If Monitoring is not configured, you should be prompted to configure the Grafana Dashboard URL or InfluxDB write configuration instead of hiding the entry.

Interaction requirements:

- Automatically refresh during Running / Initializing / Stopping;
- When the Terminal state is in the Terminal state but the summary has not yet been generated, you can retry the refresh in a short period of time;
- Stop is only available for Running / Initializing; after entering Stopping, it can only be Refresh, and the Stop main action will no longer be displayed repeatedly;
- Validity can be switched manually;
- Report button is available when there is an HTML report;
- Show empty state when artifacts is empty.
- P0 relies on automatic refresh, status description and Runner heartbeat to display execution progress in the Running / Initializing / Stopping state.
- P1 After Monitoring is enabled, the Run Report should highlight the Live Monitoring entry in the Running / Initializing / Stopping state to help users observe real-time TPS, response time, error rate and active threads.
- P1 After enabling historical replay, the Monitoring entry is retained in the Finished/Failed/Aborted status; if the InfluxDB data has expired or Grafana has no data, the empty status "Monitoring time series data may have expired" should be displayed instead of deleting the entry.

### 8.9 Load Nodes / Resources

Function:

- node list;
- Search;
- Filter by Pool Type/Status;
- Register node;
- Edit node;
- Delete node;
- Initialize nodes;
- View initialization log;
- SSH key generation, uploading and activation;
- Password authentication.

Management rules:

- Load Node is divided into Public and Private according to Pool Type;
- Public Load Node is a public resource of the platform and can only be created, edited, initialized, deleted or Disabled by Admin/resource administrator;
- Private Load Node belongs to the current Workspace and can be created, edited, initialized, deleted or Disabled by the current Workspace user;
- Private Load Node only appears in the resource selector of the Workspace to which it belongs and can only be used by the Test Plan of the Workspace;
- Admin can view the basic status, health status, last heartbeat and current run of all Load Nodes for platform security and troubleshooting;
- Admin should not view, copy or export sensitive credentials such as SSH passwords and private keys of Private Load Node;
- Credentials such as passwords and private keys are not echoed in text after being saved; if you need to change the credentials when editing a node, you should re-enter or upload them again;
- The Load Node status in the system configuration only indicates whether the pressure generating resources are available, but does not mean that all pressure generating machines must be uniformly configured by Admin.

Fields:

- IP
- SSH Port
- SSH User
- Runner Home
- Auth Type
- Pool Type
- Workspace (Private nodes are required or automatically filled in by the current Workspace; Public nodes are empty or marked Global)
- Maintainer
- Status
- Current Run
- Last Heartbeat
- Runner Version
- Bundle Version
- Remark

Status rules:

| Status | Meaning | Executable Actions |
| ------------- | ---------- | -------------------------------- |
| Uninitialized | Registered but not initialized | Initialize, Edit, Delete |
| Idle | Assignable | Edit, Delete, assigned by execution |
| Busy | Executing | View, cannot be deleted or reassigned |
| Offline | Not available | Initialize / Edit / Delete, subject to implementation limitations |

### 8.10 Monitoring(P1)

Positioning:

Monitoring is the read-only observation entry and write link configuration capability of P1. P0 does not require Monitoring pages, Grafana iframes, InfluxDB write links, or timing indicator filtering by Run ID; P0 Run Report uses offline report summaries, failure previews, logs, and artifacts as the basis for execution result judgment and long-term backtracking.

After P1 enables Monitoring, the platform does not develop real-time charts by itself, but implements it through **JMeter Backend Listener → InfluxDB → Grafana Dashboard → Platform read-only entrance**. P1 does not include Grafana datasource management, Dashboard editing, and InfluxDB management; it only provides write link configuration and read-only entry for JMeter Backend Listener + InfluxDB write config.

P1 function:

- Provides a read-only entrance to the Grafana Dashboard within the platform (can be embedded or jumped);
- Support Open in Grafana, open the complete Grafana in a new window;
- Supports unconfigured state, prompting that Grafana Dashboard URL needs to be configured;
- Support entering Monitoring from Run Report;
- P1 If the Dashboard supports variable filtering, it should support viewing single execution indicators by Run ID / runId;
- Real-time data is displayed in the Running / Stopping stage; P1 allows the Terminal state to continue to be opened as a historical playback entrance;
- Display real-time load testing indicators, including but not limited to:
  - Request throughput/TPS;
  - response time;
  - P50 / P90 / P95 / P99;
  - Error rate;
  - Active threads/concurrency;
  - Sampler/API dimension metrics.

Monitor data link:

1. Visual Scenario generates JMeter/Taurus execution configuration;
2. Taurus/JMeter injects JMeter Backend Listener before running;
3. Backend Listener writes indicators to InfluxDB;
4. Grafana uses the pre-configured InfluxDB datasource to display the dashboard;
5. The front-end Monitoring page obtains the Grafana Dashboard URL through runtime configuration or build configuration;
6. Web Nginx can reverse Grafana to `/grafana/` to support same-origin iframe embedding.

P1 operation and deployment requirements:

- A Compose deployment with Monitoring enabled should include InfluxDB and Grafana services;
- Grafana should allow iframe embedding;
- Grafana can enable anonymous Viewer for read-only access to the platform Monitoring page;
- Grafana datasource should be pre-configured by the deployment as InfluxDB, platform P1 does not manage the datasource;
- Dashboard JSON should be imported by deployment initialization, platform P1 does not edit Dashboard;
- For production deployment, it is strongly recommended to reverse Grafana through the same origin of the Web gateway, such as the `/grafana/` prefix; cross-domain iframe is not a stable solution;
- If embedding from the same source is not possible, the Monitoring page must retain Open in Grafana as an available backend;
- If you use iframe embedding, you must avoid white screen or repeated login problems caused by browser SameSite/Cookie restrictions; Anonymous Viewer read-only access is recommended;
- `PT_INFLUXDB_URL` must be the InfluxDB write address accessible to the pressure-generating node;
- `PT_INFLUXDB_TOKEN`, `PT_INFLUXDB_ORG`, `PT_INFLUXDB_BUCKET` should be consistent with the InfluxDB initialization parameters;
- The front-end should support runtime configuration `grafanaDashboardUrl` to avoid having to rebuild the front-end image when deploying to different machines;
- InfluxDB bucket retention is recommended to default to 30 days and allow deployment-level adjustments; after the retention is exceeded, the Monitoring entry of historical runs can be retained, but Grafana may display empty data, and the offline summary and artifacts of the Run Report are still the basis for long-term backtracking.

Product boundaries:

- P0 does not require the addition of self-developed monitoring charts, Grafana iframes, InfluxDB datasource management, or Run-level real-time indicator filtering.
- P0 Run creation, execution, stop, report summary, and artifacts download must not depend on Monitoring configuration being successful.

P1 does not implement Grafana Dashboard editing, Datasource management, or InfluxDB management within the platform; these capabilities are retained within Grafana/InfluxDB itself.

### 8.11 Help(P2)

The in-product Help page is a P2 capability. Project documents such as README/deployment/operation and maintenance are not restricted.

Function:

- Show Taurus/JMeter usage instructions;
- Show JMeter JSR223 / Groovy Step scripting help;
- Display variable injection, dependency files, and SLA rule descriptions.

### 8.12 Admin

Positioning:

Admin is the entrance to system configuration, initialization inspection and management. In order to avoid over-design of P0, P0 only has read-only Setup Status; editable System Settings, user management and Workspace management are placed in P1, and enterprise-level login and sensitive configuration management are placed in P2.

#### 8.12.1 Setup Status(P0)

Goal: Help Admin determine whether the platform is ready for operation.

Display items:

- Whether there is a default Workspace;
- Whether there is at least one Admin user;
- Whether there is an available Load Node;
  - Whether the Public Load Node is available;
  - Whether there is a Private Load Node available in the current Workspace;
- Whether MinIO/artifacts storage is available;
- Whether local registration is enabled;
- Whether the concurrent soft/hard upper limit is configured;
- Whether the background heartbeat self-healing task is enabled;
- After P1 enables Monitoring, you can add Grafana Dashboard URL and InfluxDB write configuration integrity check;
- P2 can add "whether configured" status check for sensitive configurations such as Runner internal token, MinIO access key/secret, and InfluxDB token;

Rules:

- Setup Status P0 is read-only and does not require online modification of configuration;
- Missing items must give an understandable prompt, such as "MinIO artifacts storage is unavailable, Run artifacts will not be saved";
- The Load Node check in Setup Status is only used to indicate the availability of pressure generating resources, and does not mean that all pressure generating machines should be uniformly configured by Admin;
- P0 does not display sensitive configuration values, nor is it required to implement sensitive configuration desensitization components; sensitive configuration status display enters P2.

#### 8.12.2 System Settings(P1)

P1 provides some non-sensitive configuration editing capabilities in Admin.

Configurable item suggestions:

- Grafana Dashboard URL;
- Concurrency soft and hard caps;
-Default page size;
-Default Workspace name;
- Load Node initializes default parameters;
- Whether to allow local registration;
- InfluxDB retention display value.

Read-only or deployment-level configuration:

- Database connection;
- MinIO endpoint / bucket / access key / secret;
- InfluxDB token;
- Runner internal token;
- Encryption key/session secret.

These sensitive configurations should be provided through environment variables, configuration files, or Secret Manager, and clear text editing in the UI is not recommended.

#### 8.12.3 User Management(P1)

P1 user management capabilities:

- User list;
- Search users;
- Disable/enable users;
- Modify user role Admin / User;
- Admin creates users or resets passwords;
- Check the latest login time;
- View user source: Local; P2 adds OIDC source after enabling OIDC.

P0 does not require user management pages; P0 completes the minimum closed loop by "the first registered user automatically becomes Admin + subsequent registrations become User".

#### 8.12.4 OAuth 2.0 / OIDC(P2)

P2 supports OAuth 2.0 / OIDC enterprise login.

Product rules:

- Priority is given to using OIDC to obtain user identity; OAuth 2.0 is only used as the basis of the authorization protocol and does not solely bear the identity authentication semantics;
-Support Authorization Code + PKCE;
- Supports association of local users based on `sub`/email;
- The first SSO login can automatically create a local User;
- Support the deployer to close local registration and only allow SSO login;
- Support mapping Admin / User based on group / claim;
- P2 is not required to support SAML or LDAP unless subsequently implemented separately.

---

## 9. State machine and business rules

### 9.1 Execution main process (P0)

The main execution process of Run Now/Debug:

1. The user clicks Run Now or Debug.
2. The back-end service is completed within an atomic persistence process:
   - Verify Test Plan/Scenario, Env Group, Dependency File, Load Node permissions and reference validity;
   - Generate Run Snapshot;
   - Lock a single Load Node manually selected by the user;
   - Create Run, the initial state is Initializing;
   -Create active node lease;
   - Generate execution bundle metadata.
3. Persistent submission. SSH/SFTP, remote commands, or long-time file uploads are not allowed within this atomization process to avoid locks and semi-committed states being occupied for a long time.
4. The backend service uploads runner.py, run bundle, Taurus YAML, env files, and dependency files to the target Load Node via SSH/SFTP.
5. The backend service executes `runner.py start --run-id <runId>`.
6. The remote runner.py executes `_spawn_detached()`, writes the pid file, and returns the accepted / started result immediately.
7. The backend service returns to the frontend Run created. At this time, the Run status is usually still Initializing; if the runner accepted / running callback has arrived first, Running can also be displayed.
8. The remote detached runner process continues to callback heartbeat, and callback running after Taurus/JMeter actually starts; after execution, callback finished / failed / aborted, and uploads or registers artifacts at the same time.

Main process boundary:

- Run Snapshot, node lease, and bundle metadata must be completed in the same atomic persistence process that created the Run.
- When the remote execution fails to start, Run must converge to Failed and release the node lease.
- Run Report and Run List use Runner callback and background self-healing tasks to converge the state together, and do not rely on front-end polling to trigger state changes.
- P0 does not require Monitoring to participate in execution determination; execution success, SLA results, Validity and artifacts are still determined by the Run Report offline summary and callback status.

### 9.2 Run status

| Status | Meaning | User visible actions |
| ------------ | --------------------------------------------------- | ---------------------------------- |
| Initializing | Creating Run, allocating resources, preparing execution environment | Stop, Refresh |
| Running | Load testinging in progress | Stop, Refresh |
| Stopping | The Stop request has been accepted and is waiting for the Runner to stop, the node to be released, the artifacts to be uploaded and the status callback to converge | Refresh |
| Finished | Execution completed | View reports, download artifacts, mark Valid/Invalid |
| Failed | Execution failed | View errors, download artifacts, mark Valid/Invalid |
| Aborted | Aborted | View existing artifacts, tags Valid/Invalid |

State transition rules:

- Run Now / Debug Enter Initializing after creating Run; enter Running after the resources and execution environment are prepared.
- Initializing contains three sub-phases: resource locking → file delivery → Runner starts and establishes a heartbeat; if any sub-phase fails, it directly enters Failed and releases the locked node.
- After the user clicks Stop in Initializing / Running, Run enters Stopping; the Stop interface must be idempotent, and repeated requests must not create multiple stop processes.
- Stopping is not the final state; only after the Runner is stopped, the node is released, the uploading/registration of artifacts is completed, or the timeout compensation condition is reached, the final state such as Aborted/Failed will be entered.
- The normal final state of a user-initiated Stop is Aborted; if the Runner loses contact, fails to upload products, or fails to clean up during the stop process, it should enter Aborted and display a warning, or enter Failed when the safe completion of execution cannot be confirmed. The specific reasons must be visible.
- Finished / Failed / Aborted are Terminal states; the execution conclusion cannot be changed after Terminal; in principle, artifacts metadata must be registered before entering the final state. If there is a compensation registration, the update time must be recorded and the user must be prompted.
- Initializing / Running / Stopping When there is no Runner heartbeat for a long time, the background self-healing task should be marked as Failed or Aborted, the error reason is Runner heartbeat timeout, and the occupied nodes should be released.

### 9.3 Run conclusion field relationship

At least three types of conclusions should be clearly distinguished in the Run Report and cannot be mixed:

- Status: Execution life cycle status, the values are Initializing, Running, Stopping, Finished, Failed, and Aborted.
- SLA Result: Quality gate control result, the values are Passed, Failed, and Not Evaluated. Not Evaluated can be displayed when no SLA is configured, the execution does not produce decidable data, or the Debug Run does not require access control.
- Validity: manual analysis caliber, the value is Valid, Invalid, used to decide whether to enter Overview, statistical market and subsequent trend caliber.

Relationship rules:

- Status means "whether the run has been completed and what status the run is in".
- SLA Result means "whether the load test quality gate is passed or not."
- Validity indicates "whether this run should be included in the analysis."
- Finished is not equal to SLA Passed; Finished only means that the execution is completed, and SLA Result may still fail.
- Failed / Aborted can still retain the Validity marking capability by default, making it easier for users to determine whether to include failure analysis.
- Debug Run defaults to Invalid; Standard Run defaults to Valid.

Implementations can use equivalent field names, but products, interfaces, reports, and statistical calibers must keep the above three categories of concepts independent.

### 9.4 Run Validity

Validity indicates whether the execution should count against manual analysis.

- Valid: indicates that this execution is valid;
- Invalid: Manually marked as invalid, such as environmental anomalies, configuration errors, and resource failures.

Default value:

- Standard Run default Valid;
- Debug Run defaults to Invalid to avoid test run data contaminating Overview, statistical market and subsequent trend caliber;
- Users can manually switch Valid / Invalid in the Run Report, but the switching behavior needs to record the operator and time.

Note: Validity does not equal execution success/failure.

### 9.5 Schedule Run Rules (P2)

Schedule Run is a P2 capability. P0/P1 does not implement Schedule Run, and only retains two execution entries: Run Now / Debug.

Schedule Run is a one-time future time schedule, not a periodic task.

Product rules:

- When the user creates a Scheduled Run in the Test Plan Editor, the system creates a Scheduled Job; the actual Run is not created before the trigger time arrives.
- Scheduled Job status enumeration: Scheduled, Triggering, Triggered, Failed, Cancelled.
- The front-end Scheduled Job list only displays four states: Scheduled / Triggered / Failed / Cancelled; Triggering only exists as a back-end internal preemption and cross-instance deduplication state.
- The Scheduled Job enters Triggering after the trigger time arrives, and attempts to create a Standard Run; after the Run is successfully created, the Scheduled Job enters Triggered, and the runId is recorded.
- Scheduled Job can be canceled before triggering, and will enter Canceled after cancellation; Cancelled will not create a Run, nor will it be included in Run statistics.
- Run List only displays created Runs; Scheduled Jobs are not counted as Runs and do not enter the success rate, failure rate and Overview Run statistics. Overview can display the "Upcoming Scheduled Jobs" number alone, but it cannot be mixed with Run statistics.
- If there are insufficient resources when triggering, a Failed Run should be created, Trigger Source = Schedule, and the error reason is `RESOURCE_INSUFFICIENT`, which facilitates the user to trace this scheduling attempt in the Run List; if even the Run record cannot be created, the Scheduled Job will enter Failed and the error details will be retained.
- MVP does not provide scheduling queuing, automatic retry, periodic tasks or calendar scheduling; there is no delay in waiting when resources are insufficient.

### 9.6 Debug Run Rules

Debug Run is a low-risk test run, the goal is to verify whether the Scenario/Test Plan can run through.

Rules:

- Run Type = Debug;
- Prioritize the use of 1 node;
- Use minimum load;
- Should not be mistaken for official load testing results;
- Debug Run should also generate Run and artifacts for easy troubleshooting.

### 9.7 Resource Allocation Rules

- Only Idle nodes can be allocated;
- Busy nodes cannot be allocated repeatedly;
- P0 only supports Manual single node mode, and must strictly verify whether the node selected by the user is available, belongs to the selected Pool Type and the current Workspace;
- After P1 supports Auto mode and multi-node mode, Auto mode should be filtered by pool type and workspace;
- Semi-successful executions are not created when resources are insufficient, or failures must be clearly marked and occupied resources released.

### 9.8 Snapshot Rules

Run must be saved when created:

-Test Plan basic information;
- Env Group reference and necessary variable snapshot; P0 saves variables as ordinary variables;
- After the Secret type is enabled in P2, Secret type variables can enter execution snapshots for recurrence, but must be encrypted and saved; Run Reports, logs, error prompts, and export previews can only display desensitized values;
- List of scenarios and definition of each scenario;
- Load Settings;
- SLA Rules;
- Dependency File reference;
- Resource Request.

Purpose: To ensure that historical runs are traceable and are not affected by subsequent asset modifications.

### 9.9 Asset deletion and reference rules

Assets include Env Group, Dependency File, Scenario, Test Plan, Load Node, etc.; P2 includes API Spec after enabling API Catalog.

P0 product rules:

- P0 does not implement unified Archive/soft delete status.
- Assets referenced by the currently valid Scenario or Test Plan are not allowed to be deleted directly.
- When deletion is blocked, a brief reason should be given, such as "This Env Group is being used by 2 Test Plans".
- A snapshot must be saved when a Run is created; subsequent modification or deletion of assets should not change the execution configuration display of the historical Run Report.
- If the asset only exists in the historical run snapshot, the current asset should not be prevented from being deleted; the historical run relies on the snapshot to continue displaying.

P1 enhancement:

| Assets | Default deletion behavior | Behavior when referenced |
| --------------- | ----------------- | ----------------------------- |
| Env Group | Archive | Prevent hard deletions, allow Archive, retain historical snapshots |
| Dependency File | Archive | Prevent hard deletion, allow Archive, keep files retroactively |
| Scenario | Archive | Prompt for impact when referenced by Test Plan; after archived, it can no longer be re-selected |
| Test Plan | Archive | Does not affect history Run |
| API Spec | Archive | Does not affect the Scenario/Test Plan generated by it |
| Load Node | Archive / Disable | Disable deletion when busy; allow archiving when Idle/Offline |

P1 can be supplemented by a pre-delete/archive presentation of the scope of impact, including the Scenario, Test Plan, and most recent Run that referenced it.

### 9.10 API Spec version and product relationship (P1)

- API Spec is the source asset, not the continuous synchronization source that generates Scenario/Test Plan.
- Scenario/Test Plan becomes an independent asset once generated by Spec.
- Reuploading the Spec will not automatically modify the existing Scenario/Test Plan.
- The P1 basic version does not provide Spec Diff, automatic synchronization, and batch update prompts.
- The generated product should retain source metadata, including at least Spec ID, Spec Version, Operation Method, and Operation Path.

### 9.11 Configure foolproof and capacity protection

- The Test Plan configuration page must display the expected concurrency of P0 single node; in P1 multi-node mode, the expected total concurrency will be displayed.
- For low-frequency team usage scenarios, P0 defaults to a strong warning when the single-node concurrency exceeds 1,000 and requires the user to confirm again; this threshold should be adjustable through system configuration.
- The system should provide global maximum input protection and reject obviously abnormal extreme values, such as negative numbers, non-digits, extremely large concurrency, and extremely long duration.
- The soft upper limit is used to remind users of risks; the hard upper limit is used to protect the stability of the platform and pressure-generating nodes.
- Debug Run is not affected by the user's large concurrency configuration and should always use the low-risk default load.

### 9.12 Runner Protocol(P0)

Runner Protocol defines the minimum interaction boundary between the backend service and runner.py on the remote Load Node.

Start protocol:

- The backend service only starts remote execution after Run creates the relevant persistence commit.
- The backend service uploads the execution bundle via SSH/SFTP, which contains at least runner.py, Taurus YAML, env files, dependency files, and run metadata.
- The remote working directory should be isolated by Run, for example `<runner_home>/runs/<run_id>/`.
- Each Run directory contains at least: `bundle/`, `artifacts/`, `logs/`, `runner.pid`, `run-metadata.json`.
- After the backend service executes `runner.py start --run-id <runId>`, runner.py must start the detached child process through `_spawn_detached()`, write the pid file, and return accepted / started as soon as possible.
- accepted / started only means that the remote runner has received and started the detached child process, which does not mean that the load testing has started; only running callback means that Taurus/JMeter has entered the execution state.

Callback event:

| Event | Meaning | Status Effect |
| --------- | -------------------------- | ---------------------------- |
| accepted | runner.py has received the startup request and written to the pid file | Run can persist Initializing |
| running | Taurus/JMeter has started execution | Run enters Running |
| heartbeat | runner detached process is still alive | update last heartbeat without changing the final state |
| artifact | Upload or register a single artifact | Update artifacts metadata without individually changing the Run conclusion |
| finished | Execution ends normally | Run enters Finished and releases node lease |
| failed | execution failed | Run enters Failed and releases node lease |
| aborted | User Stop or runner actively terminates | Run enters Aborted and releases node lease |

Callback requirements:

- All callbacks must carry run_id, node_id, runner internal token, event type, event time and readable message.
- callback must be idempotent; repeated accepted, running, heartbeat, artifact, finished, failed, aborted must not cause state confusion or repeated release of nodes.
- The Terminal status is Finished / Failed / Aborted; after entering the Terminal, it must not be overwritten by the running / failed / finished callback that arrives later.
- If callbacks arrive out of order, the backend should use the Run state machine to determine whether to accept them; ignored callbacks should record structured logs to facilitate troubleshooting.
- Artifact callback can only register relative paths in the current Run directory, and does not allow absolute paths, `..`, soft link escapes or overwriting other Run files.

Stop protocol:

- When the user Stop Initializing / Running Run, the backend first marks the Run as Stopping and records the stop requested by / at.
- The backend executes `runner.py stop --run-id <runId>` via SSH; runner.py stops the detached child process and its child process tree based on the pid file.
- Both the Stop interface and the remote stop command must be idempotent; repeated Stop must not create multiple stop processes.
- Normal Stop converges to aborted callback; if the runner loses contact or stop times out, the background self-healing task converges to Aborted or Failed, and the node lease is released.

Artifact upload constraints:

- Artifact file name, relative path, size, hash, content type, and creation time should be entered in the artifacts metadata.
- artifacts.zip, runner stdout/stderr, `bzt.log`, `finalstats.csv`, etc. P0 key files should be registered first; `failed_requests.csv` relies on the JMeter plug-in output and is defined by P1.
- Failure to upload or register artifacts must not leave Run permanently stuck in Running / Stopping; the final state must be convergent and a warning must be displayed in the Run Report.
- P0 does not require automatic cleaning of remote files; remote retention policies, cleaning tasks, and finer metrics are available as P1 extensions.

---

## 10. Page and interaction design principles

### 10.1 Product Principles

1. **Let users understand first, then let them configure**

   - Page copy prioritizes explaining what users are doing rather than exposing database fields.

2. **Short creation path and sufficient verification before formal execution**

   - Debug Run should be fast;
   - Scenario, resources, SLA, environment references should be checked before Run Now.

3. **On the results page, answer the conclusion first and then provide details**

   - First check whether it succeeded, whether it passed, and why it failed;
   - Look at artifacts and underlying logs again.

4. **The bottom layer is compatible with Taurus, and the upper layer uses business terms**

   - Ordinary users are not required to understand Taurus YAML;
   - But advanced users can troubleshoot through in-product Help (P2) and artifacts.

5. **All assets must be traceable**

   - Who created it, who updated it, which Workspace it belongs to, and which execution it uses.

### 10.2 Empty state

Each list page must have an explicit empty status:

- Scenarios empty: guides the creation of Scenarios; when P1 is enabled, it can guide the use of cURL import; the API document import entrance must not be displayed.
- Test Plans empty: guides the creation of Test Plan; the API document generation Test Plan entry must not be displayed.
- Runs empty: guide Run Now;
- Env Groups empty: guides the creation of environment variable groups;
- Dependency Files empty: guide to upload files;
- Load Nodes empty: boot registration nodes;
- API Catalog empty (P2): guides the uploading of Spec, which is only managed as a document asset.

### 10.3 Error status

Error copy should contain:

- What the user is doing;
- Reason for failure;
- Possible next steps to take.

Example:

- Deprecated: `Run failed`;
- Recommended: `Run creation failed: the selected Public node is currently unavailable. Select another Idle node or try again later.`

### 10.4 Loading status

- List loading uses skeleton or explicit loading;
- The execution action button must prevent repeated submission;
- Run Report Running status display automatic refresh interval;
- Summary generation should show "Waiting for report summary".

---

## 11. Non-functional requirements

### 11.1 Performance and response time

- The first version is designed for low-frequency use within the team and does not define a formal availability SLA; the basic service should be able to stably support daily intranet trials.
- The MVP target supports low-frequency use by 5-10 internal users; larger user concurrency is not a target for the first version.
- The list page must be loaded in pages; the default page size does not exceed 50.
- At the scale of 1,000 similar asset data, the main list page query P95 should take ≤ 3s.
- P95 for basic information query on the details page should be ≤ 2s; it does not include the time taken for large file preview, external Grafana loading, and product downloading.
- File upload, product download, and small file preview must not block main page interaction, and should display progress, loading status, or asynchronous results.
- The automatic refresh interval of the Run Report in the Initializing / Running / Stopping state shall not be less than 5s to avoid overwhelming the backend.
- P0 The default single Test Plan contains a maximum of 20 Scenario items; the default single Visual Scenario contains a maximum of 30 Steps; both thresholds should support deployment-level configuration.
- P0 only supports binding a single Run to a Load Node; Auto allocation, multi-node execution and cross-node concurrency are summarized into P1 capabilities.
- These performance targets belong to P0 product/NFR expectations and are used for design and regression observations. They do not constitute P0 merge gate, formal performance baseline or load-test hard threshold; the acceptance threshold is subject to `docs/sdd/09-testing-and-acceptance-strategy.md`.

### 11.2 Execution and Resource Stability

- The number of Runs running at the same time is determined by the number of available Load Nodes; each Run in P0 only occupies one manually selected Load Node; the first version does not provide queuing, and will directly fail and prompt if resources are unavailable.
- The platform must prevent the same Load Node from being assigned to multiple Running Runs concurrently.
- Stop Run, finished / failed / aborted callback should be idempotent, and repeated calls must not destroy the final state.
- After Run enters Finished / Failed / Aborted, the allocated Load Node should be released.
- Runner heartbeat interruptions should be able to be identified, and Runs without heartbeats for a long time should not stay in Running / Initializing / Stopping forever.
- The background self-healing task must be able to converge the heartbeat timeout Run to the Failed or Aborted final state and release the Load Node; the error cause and the last heartbeat time must be visible in the Run Report.
- Debug Run must use low-risk default workloads that are not affected by large concurrency configured by the user in the Test Plan.
- The recommended default interval for Runner heartbeat is 10s; the default interval is 90s. Failure to receive a heartbeat is considered a timeout. The specific threshold should support deployment-level configuration.
- Stop grace period is recommended to default to 60s; after the timeout, the background self-healing task converges to the Run final state and releases the node.

### 11.3 Product and Report Availability

- After the Run ends, artifacts metadata should be visible within 2 minutes; if parsing is delayed, "Report Summary Generating" should be displayed in the Run Report.
- The complete artifacts.zip should be downloadable after the Runner upload is complete.
- P0 `finalstats` should support inline preview when the key file exists; display an explicit empty state when it does not exist. failed requests Plugin preview belongs to P1.
- The product path and preview interface must prevent path crossing; after P1 enables compressed package decompression, the decompression process must also prevent path crossing.
- P0 only supports MinIO as object storage for Dependency Files and artifacts; it does not provide local storage mode, nor does it provide AWS S3, Alibaba Cloud OSS or other cloud object storage adaptations.
- The default single file limit for Dependency File is recommended to be 50MB; P0 does not support automatic decompression of compressed packages; the default total limit for single Run artifacts is recommended to be 500MB; these thresholds should support deployment-level configuration.
- File preview is a P1 capability; P1 does not preview single files exceeding 10MB by default and only provides downloading.

### 11.4 Security and Deployment Assumptions

- The first version of the deployment is assumed to be an enterprise intranet or a controlled network, and does not write anonymously to the public network.
- P0 uses the local email password account system; all business APIs require login by default.
- Passwords must be stored in a secure hash, and it is prohibited to store the password or password hash in plain text or return it in the business response.
- The first registered user automatically becomes Admin; subsequent users default to User; the Admin/User permissions judgment must be performed by the backend, and the front-end hidden entrance cannot be used as the only permission control.
- Public Load Node credentials are maintained by the Admin/Resource Administrator; Private Load Node credentials are maintained by the owning Workspace user.
- Sensitive credentials such as the SSH password and private key of the Private Load Node must not be displayed to non-owned Workspace users, nor must they be echoed in clear text to the Admin.
- The Runner callback internal interface must be protected by an internal token or equivalent authentication mechanism.
- Workspace is the product data isolation boundary; all business data queries and writes must carry the Workspace context.
- P0 does not build general log and error message desensitization capabilities; systematic desensitization of sensitive information such as Authorization, Session Token, internal token, sensitive Env Var, InfluxDB token, Grafana admin password, etc. is placed in P2.
- P1 When Monitoring is enabled, Grafana Anonymous Viewer can only be used for read-only dashboards, and it is recommended to be deployed within the same-origin gateway and intranet access range.
- Dependency File and artifacts must undergo path security verification; after P1 enables compressed package decompression, the decompression process must undergo path security verification.

### 11.5 Observability and Operations

- Backend, Runner, Load Node initialization, and Run status changes should output structured logs.
- Readable error messages and downloadable logs must be retained when Run fails.
- Downloadable logs on Run failure include at least Runner stdout/stderr, `bzt.log` (if any), and `artifacts.zip`.
- When Monitoring is enabled in P1, the Monitoring link should be able to troubleshoot independently: InfluxDB writing failure, deployment of pre-configured Grafana datasource unavailable, and Dashboard URL not configured should give different prompts respectively; the platform does not manage Grafana datasource.
- docker compose deployments should contain basic health checks or observable startup status.

---

## 12. Acceptance Criteria

### 12.1 Basic closed-loop acceptance

The following closed loop must be completed:

1. Use the default Workspace;
2. Create Env Group;
3. Create Visual Scenario;
4. Add Step;
5. Debug Run;
6. View Run Report;
7. Create Test Plan;
8. Add Scenario;
9. Configure resources and load parameters;
10. Run Now;
11. View artifacts;
12. Mark Run Valid / Invalid.

### 12.2 Account & Admin Setup Acceptance

- The first registered user automatically becomes Admin;
- Subsequent registered users will become User by default;
- After closing open registration, self-registration after the first Admin will be blocked and a clear prompt will be displayed;
- Users can log in with email + password;
- Jump to Login when users who are not logged in access the business page;
- Business records can display Created By / Updated By / Triggered By;
- Admin can access Setup Status;
- Setup Status can display the basic status of the default Workspace, MinIO/artifacts storage, Public Load Node, current Workspace Private Load Node, local registration, concurrency limit, etc.; P1 adds the Grafana and InfluxDB write configuration status after Monitoring is enabled; P2 adds the "configured or not" status of sensitive configurations such as Runner internal token and MinIO secret;
- P0 Setup Status does not display sensitive configuration values; sensitive configuration status display and desensitization caliber enter P2.

### 12.3 API Catalog Document Asset Acceptance (P2)

1. Upload OpenAPI/Swagger Spec;
2. See the upload record in the Spec list;
3. View Spec details;
4. Delete Spec;
5. API Catalog does not provide API document-based import, create Test Plan action, operation import, coverage analysis or API → Scenario/Test Plan generation.

### 12.4 Resource closed-loop acceptance

1. Admin/resource administrator can register Public Load Node;
2. Current Workspace users can register Private Load Node;
3. Initialize the node;
4. Check the initialization log;
5. The node enters Idle;
6. When selecting Public Pool in Test Plan, you can only manually select one Public Idle node;
7. When selecting Private Pool in Test Plan, you can only manually select a Private Idle node of the current Workspace;
8. Private Load Node credentials are not echoed in text after being saved, and Admin cannot view or export them;
9. After execution, the node is released to Idle.

### 12.5 Monitoring Acceptance (P1)

1. Compose deployment includes InfluxDB and Grafana, or the documentation explains how to connect to external InfluxDB/Grafana;
2. Grafana uses the pre-configured InfluxDB datasource for deployment, and the platform does not manage the datasource;
3. Dashboard JSON is imported by deployment initialization, and the platform does not provide Dashboard editing;
4. The platform provides a read-only entrance to Grafana Dashboard (embedded or jumped);
5. A clear empty state is displayed when the Grafana Dashboard URL or InfluxDB write config is not configured;
6. When Run is executed, JMeter Backend Listener can write indicators to InfluxDB;
7. Grafana Dashboard can see real-time stress measurement indicators;
8. The external pressure generating node can access `PT_INFLUXDB_URL`;
9. Run Report provides the entrance to Monitoring;
10. After P1 enables context jump by Run ID, you can still press runId to open history playback when Run enters the Terminal state; an empty data prompt is displayed when the InfluxDB retention is exceeded;
11. The platform does not implement Grafana datasource management, Dashboard editing or InfluxDB management.

### 12.6 Report Acceptance

Run Report must answer:

- What is the status of this execution?
- Is the SLA Result of this execution Passed, Failed or Not Evaluated?
- Is this execution valid and has it entered the default statistical caliber?
- Is this execution Debug or Standard?
- Which Test Plan/Scenario was used for this execution?
- What are the key indicators?
- Is there a reason for the security failure or a diagnostic tip?
- Is there a reporting document?
- Is it possible to download full artifacts?
- Which nodes are used for this execution?
- (After P1 is enabled) Is it possible to view the read-only Generated YAML/execution configuration for troubleshooting purposes?

### 12.7 Assets and Foolproof Acceptance

- Env Group and Dependency File referenced by Scenario/Test Plan are not allowed to be deleted;
- Run snapshots are not affected by subsequent modification or deletion of assets;
- After P1 enables Archive, asset archives no longer appear in the new selector, but historical runs can be displayed normally;
- After P2 enables API Catalog, re-uploading API Spec will not automatically modify the existing Scenario/Test Plan;
- P2 API Catalog does not write source metadata to Scenario/Test Plan; API Catalog is document asset management only;
- After P2 enables dependent packages, Dependency ZIP / TAR / TGZ will automatically decompress and retain the directory structure within the package when running;
- Only one Idle node can be selected for P0 resource configuration;
- After P1 enables multi-node Manual Resource Mode, Node Count automatically equals the number of Selected Nodes, and inconsistency is not allowed;
- Bulk Apply Leaving a blank field will not overwrite the existing value of the Scenario item;
- When the concurrency of a single node exceeds the soft upper limit, a strong warning is displayed and a second confirmation is required;
- Extremely illegal values will be intercepted by front-end and back-end verification.

### 12.8 Run life cycle acceptance

- After the user Stop Running / Initializing Run, the state first enters Stopping, and then converges to the Aborted / Failed final state;
- The runner accepted callback does not mean that the load testing has started; only the running callback means that it has entered Running;
- runner heartbeat can update the last heartbeat time, but cannot overwrite the Terminal status;
- finished / failed / aborted callback remains idempotent when arriving repeatedly and does not release nodes repeatedly;
- The artifact callback can only register the safe relative path of the current Run;
- During the Stopping period, the page only retains Refresh and does not display the Stop main action repeatedly;
- Repeated Stop requests will not cause repeated stop processes or state confusion;
- After Run enters the final state, the Load Node is released and will not be permanently Busy;
- Runs with a heartbeat timeout of the Runner will be converged to Failed/Aborted by the background self-healing task, and the last heartbeat time and error cause will be displayed in the Run Report;

### 12.9 P2 Schedule Run Acceptance

- Scheduled Job is generated after creating Schedule Run, which can be canceled before triggering;
- Create a Standard Run after the Scheduled Job reaches the point, and display it in the Run List. Trigger Source = Schedule;
- When Scheduled Job is triggered, insufficient resources will generate a Failed Run. The cause of the error is visible and does not enter implicit queuing.

---

## 13. MVP and subsequent priorities

### P0-Core: Must run through first

- Local account registration/login/logout;
- The first registered user automatically becomes Admin;
- Default Workspace context;
- Overview basic overview;
- Visual Scenario create/edit/save;
- Env Group;
- Dependency Files: MinIO-based common file upload, download, reference and deletion protection;
- Test Plan creation/editing;
- Test Plan Run Mode: Parallel / Sequential transparent transmission Taurus;
- Minimum subset of SLA Rules: single rule, 9 Subject enumerations, continue/stop actions;
- Resource Manual single node configuration;
- Public/Private Load Node management boundaries;
- Run Now / Debug;
- Run Validity default value and manual flag;
- Run List;
- Run Report-first;
- MinIO artifacts download/preview;
- Load Node registration, initialization, logging, and deletion;
- Admin Setup Status read-only page;
- Basic error handling and empty status.

### P0-Stability: Must be completed with the core closed loop

- Asset reference protection/Run snapshot;
- Run state machine: Initializing / Running / Stopping / Finished / Failed / Aborted;
- Stop idempotent, Stopping convergence, node release;
- Runner heartbeat timeout recognition and Run self-healing final state;
- Concurrency soft upper limit prompt and basic value hard verification;
- Password secure hashing, login state expiration, and basic blast protection;
- Admin/User backend permission verification;
- Private Load Node credentials are not echoed in text and not shown to Admin;
- Dependency File / artifacts path security;
- Idempotent handling of Runner accepted / running / heartbeat / artifact / finished / failed / aborted callback.

### P1: Improve the experience but do not expand the functional boundaries

- Monitoring: read-only entry + JMeter Backend Listener / InfluxDB write config write link configuration, including Terminal status history playback entry; P1 does not include Grafana datasource management, Dashboard editing or InfluxDB management;
- Resource Auto allocation and multi-node execution;
- Workspace switching and Workspace management UI;
- User Management UI;
- System Settings UI;
- Scenario/Test Plan polish: Clone, Archive, read-only Generated YAML/execution configuration preview, existing lightweight tags;
- Scenario/Test Plan tags are existing lightweight metadata and are not new P1 deliverables; P1 does not add a new front-end list filtering UI by tag, nor does it extend tags to Env Group, Dependency File, Load Node or other assets;
- Dependency Files single file preview;
- Run Report failed_requests plug-in preview, failed_requests/finalstats large file paging and enhanced preview;
- If Run tag display/filter exists, the Scenario/Test Plan tags in the snapshot must be used; Run does not have an independent variable tag model; Run List currently only displays tags and does not add a new filtering UI;
- cURL import Step; P1 Import only refers to cURL import;
- Bulk Apply item-by-item before/after diff preview (optional);
- Admin complete management portal.

P1 no longer contains any generation links for OpenAPI / API Catalog → Scenario / Test Plan; P1 Import only refers to cURL import.

### P2: Security Governance, Enterprise Expansion and Deferred Enhancement

- API Catalog: API document asset management, only upload / list / details / delete;
- `P2 API Catalog is documentation asset management only; it does not create, update, or generate Scenario/Test Plan.`
- P2 API Catalog does not include version diff, operation import, coverage analysis, API → Scenario/Test Plan generation;
- OpenAPI Step automatically generates sinking P2, and cannot be implemented in advance as API Catalog → Scenario/Test Plan generation link;
- Schedule Run one-time scheduling and Scheduled Job status closed loop; together with Overview "upcoming execution" statistics and Test Plan details, the Scheduled Jobs list is not triggered;
- In-product Help page; README/deployment/operation and maintenance and other engineering documents are not restricted;
- Safe decompression of Dependency Files ZIP / TAR / TGZ;
- Desensitization of general sensitive information in logs and error messages;
- Env Group Secret type, sensitive value display/replication restrictions;
- Encrypted saving, key rotation and historical Run decryption boundaries of Secret type Env Var in Run Snapshot;
- OAuth 2.0 / OIDC enterprise login;
- SSO users are automatically created and mapped from SSO group/claim to Admin/User;
- Non-MinIO storage backend adaptation, such as local file system, AWS S3, Alibaba Cloud OSS or other cloud object storage.

### Not doing it yet

See Section 3.2.

---

## 14. Suggested slices for first version development

In order to control risks during AI or R&D team development, it is recommended to implement them in the following order:

Implementation boundaries:

- The first version is initialized with an empty Workspace as the default delivery form;
- P0 only supports creating Visual Scenario within the product;
- P0 only supports MinIO as file and artifact storage;
- P0 only supports manual selection of a single Load Node for execution;
- cURL import, Auto allocation, multi-node execution are placed in P1;
- Import capabilities such as Locust, JMX, and Postman Collection are not within the scope of this version;
- Cross-product data import, batch asset import, and external script compatibility are outside the scope of this version.

### Phase 0: Account and startup configuration

- Local email password registration/login/logout;
- The first registered user automatically becomes Admin;
- The default Workspace is automatically created or initialized;
- Admin Setup Status read-only page;
- Password secure hashing, login state expiration, and basic blast protection;
-Basic login status and Admin/User backend permission verification.

Goal: Allow open source deployment users to complete platform initialization without relying on enterprise SSO.

### Phase 1: Assets and Context

- Default Workspace context;
- Env Groups;
- Dependency Files(MinIO);
- Basic management of Load Nodes.

Goal: First establish management capabilities for all load testing assets.

### Phase 2:Scenario

- Scenario List;
- Visual Designer;
- Scenario Debug Run.

Goal: Allow users to construct and verify "what to test".

### Phase 3:Test Plan

- Test Plan List;
- Test Plan Editor;
- Resource allocation;
- Scenario Orchestration;
- SLA;
- Run Now / Debug.

Goal: Allow users to construct and initiate formal load testings.

### Phase 4:Run & Report

- Run List;
- Run Report;
- Report-first layout;
- Artifacts;
- Validity;
- Stop / Stopping / Aborted status closed loop;
- Runner heartbeat timeout self-healing;
- Node release and status closed loop.

Goal: Allow users to judge load testing results and troubleshoot.

### Phase 5: Experience convergence

- Overview;
- cURL import(P1);
- Resource Auto allocation and multi-node execution (P1);
- Monitoring (P1: read-only entry + write link configuration, including Terminal playback);
- Scenario/TestPlan Polish (P1: clone / Archive / read-only YAML preview / existing lightweight tag);
- Dependency Files single file preview (P1);
- Run Report paging preview of large files (P1);
- Workspace management UI (P1);
- User Management UI(P1);
- System Settings UI(P1);
- Admin;
- API Catalog / Schedule Run / Help / Dependency Files Safe decompression of compressed packages (P2);
- Copy, empty status, error status, permissions and security details.

Goal: Transform the platform from "usable" to "easy to use".

### Phase 6: Security Governance and Enterprise Expansion (P2)

- Desensitization of logs and error messages;
- Env Group Secret type and sensitive value display/copy restrictions;
- Secret Run Snapshot encryption and key rotation;
- OAuth 2.0 / OIDC enterprise login;
- SSO group / claim mapping;
- Non-MinIO storage backend adaptation.

Goal: After the intranet MVP is stabilized, enterprise-level security governance and deployment expansion capabilities will be completed.

---

## 15. Determined product wording for the first version

The following matters are deemed to have been decided in this article:

1. The reusable load testing plan uses **Test Plans** uniformly.
2. All actual executions use **Runs**; the details page of a run is Report.
3. Environment variable groups use **Env Groups** uniformly.
4. Use **Load Nodes** uniformly for load resources.
5. The API module is collectively called **API Catalog**, the priority is P2, and the scope is limited to API document asset upload/list/details/delete; no Scenario/Test Plan is created, updated or generated.
6. The first version does not do resource queuing: when resources are unavailable, it directly blocks the operation and gives an understandable error.
7. The first version only supports Visual Scenario and does not provide independent script scenario mode or multi-executor scenario type.
8. P0 does not provide cURL, Locust, JMX, and Postman Collection import or compatible operation capabilities; cURL import is a P1 capability.
9. P0/P1 does not include Schedule Run; Schedule Run is the one-time scheduling capability of P2 and does not perform periodic tasks, queuing or automatic retry.
10. P0 uses the default Workspace and Workspace context transparent transmission; the Workspace switching and management UI is P1.
11. P0 uses the local email password account system; the first registered user automatically becomes Admin; email verification, email password retrieval and invitation-based registration are not required.
12. OAuth 2.0 / OIDC is P2 enterprise login capability; P0/P1 does not rely on enterprise SSO.
13. P0 Admin only does Setup Status read-only page; System Settings UI and User Management UI are P1; sensitive configuration status display and desensitization caliber enter P2.
14. Public Load Node is managed by Admin/Resource Administrator; Workspace Private Load Node is self-managed by the Workspace user to whom it belongs, without adding complex processes such as approval, quota, Workspace Owner or Resource Manager.
15. P0 only supports Manual single-node execution; Resource Auto allocation, multi-node execution and Node Count are P1 capabilities.
16. P0 only supports MinIO as the storage backend for Dependency File and artifacts; local file system, AWS S3, Alibaba Cloud OSS or other cloud object storage adaptation is a P2 capability.
17. P0 does not provide Env Group Secret type, sensitive value display/copy protection, log and error prompt general desensitization; these capabilities enter P2.
18. Editable Taurus YAML editor is not available in the first release; read-only Generated YAML/execution configuration preview is a P1 diagnostic capability.
19. P1 API Spec updates are not automatically synchronized to the generated Scenario/Test Plan; P1 basic version only retains source metadata.
20. P0 asset deletion only does reference protection and Run snapshot; Archive/soft deletion is a P1 enhancement.
21. P0 does not include Monitoring; P1 Monitoring only includes the write link configuration and read-only entry of JMeter Backend Listener + InfluxDB write config (including Terminal playback), and does not include Grafana datasource management, Dashboard editing or InfluxDB management.
22. The first version does not introduce new product capabilities such as AI generation, trend comparison, and capacity baseline.

---

## 16. Open Questions / TODO

The following issues do not block the P0 product wording, but need to be confirmed during the design or development process and fed back into the corresponding documents:

1. The final default values and deployment configuration names of Runner start accepted timeout, running timeout, heartbeat timeout and stop grace period.
2. The final directory structure, manifest field, and runner.py version compatibility strategy of the execution bundle.
3. Dependency File is the final default value for the total amount of single file and single Run artifacts; confirm the number of compressed package entries and the upper limit of large file preview after P1 is enabled.
4. Whether artifacts retention, remote run directory cleanup, and failed run file retention time are included as P1 operation and maintenance capabilities.
5. Encryption scheme, key rotation strategy and historical Run decryption boundary of P2 Secret type Env Var in Run Snapshot.
6. Grafana dashboard variable naming, runId filtering method, InfluxDB write config, retention and empty data prompt copy of P1 Monitoring.
7. P2 OpenAPI Step automatically generates display copy for single independent items, complex schema warnings, and example generation strategies for oneOf / anyOf / allOf and deeply nested objects.
8. Whether separate interactive design is required for P1 Bulk Apply diff, batch rollback, and conditional coverage of fields.
9. Display copy of Failed Scheduled Job and Failed Run of Schedule Run P2 in the list and statistics.
10. When Run Report offline summary parsing fails, which fields must display `N/A` and which fields allow delayed compensation updates.

---

## 17. Standard Glossary

| Standard terminology | Chinese name | Definition | Notes on naming |
| ----------------- | -------------- | ------------------------------------------------------- | ------------------------ |
| User | User | An account that can log in to the platform and perform operations, P0 uses the local email password system | Mixed use of Operator and Account |
| Admin | Administrator | User role with system initialization, Setup Status, resource management and subsequent management capabilities | Superuser, Owner mixed use |
| Workspace | Workspace | Data isolation and collaboration boundaries | Avoid confusion with concepts such as Tenant and Project |
| API Catalog | API Catalog | P2 OpenAPI/Swagger Spec document asset management portal, only upload / list / details / delete | Avoid calling it P1 import or generation portal |
| Scenario | Scenario | Reusable load testing object, describing "what to stress" | Case, script collection |
| Visual Scenario | Visual Scenario | Interface links consisting of request steps, extractors, assertions, etc. | JMeter configuration page |
| Env Group | Environment Group | A set of runtime environment variables | Avoid understanding it as a list of individual variables |
| Dependency File | Dependency file | File assets that need to be mounted or downloaded to run the load testing | Mixed names of attachments and resource files |
| Test Plan | Test plan | Reusable load testing solution, describing "how to test" | Avoid understanding it as a to-do task or background task |
| Load Settings | Load Settings | Concurrency, duration, throughput and other parameters of each Scenario in Test Plan | Load Profile Template Library |
| SLA Rule | Quality Access Control | Rules for judging whether execution passes | Alarm Rules |
| Scheduled Job | Scheduled task | Future one-time trigger record created by P2 Schedule Run; it was not Run before trigger | Scheduled Run is mixed with Run |
| System Settings | System Settings | Platform-level configuration; P0 read-only Setup Status, P1 supports some non-sensitive configuration UI editing | Config Center |
| Setup Status | Startup configuration status | Admin P0 read-only page to check whether the system key configuration is complete | Health Check page mixed name |
| OIDC | OpenID Connect | P2 enterprise login identity protocol, based on OAuth 2.0 to obtain user identity | Write-only OAuth login |
| Load Node | Load Node | Machine that can be assigned to perform load testing | Avoid abstraction called resource configuration |
| Public Load Node | Public load node | Platform public load resource, maintained by Admin / Resource Administrator, can be used by multiple Workspaces | All load generator machines are maintained by the business team |
| Private Load Node | Private Pressure Node | The Workspace team has its own load resources, which are maintained by the Workspace users themselves. They are only available in this Workspace | All load generator machines are maintained by Admin |
| Run | Execution | An actual run record | Avoid mixing with reusable test plans |
| Run Report | Execution report | Run details page, showing conclusions, indicators, failures and products | Avoid only presenting the product list |

---

## 18. Final product judgment

The focus of the product design of the first version of SurgePilot is not to add more functions, but to form a clear closed loop of core capabilities:

```text
Manual configuration
(P1:cURL / API Spec)
        ↓
Scenario: Define what to test
        ↓
Test Plan: Define how to test, what resources to use, and what counts as passing
        ↓
Run: actually run once
        ↓
Report: Judging results, locating problems, and downloading products
        ↓
Reuse and Iterate Scenario/Test Plan
```

The first phase of development should strictly focus on this main link and not be distracted by advanced capabilities such as AI, trend analysis, and resource queuing.
