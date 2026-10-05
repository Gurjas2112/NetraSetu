# NetraSetu — Explainable DR Screening for Rural India

### Engineering, product and experience specification

**SIH PS 26038 · MathWorks · MedTech / HealthTech** — v3.2, final

Scale target: 100,000 screenings per district per year

> This is the repository edition of `NetraSetu_Engineering_Specification.html` v3.2 — the same specification, section for section. Its ten diagrams are Mermaid, which GitHub renders natively. It also carries three things the HTML only summarises: the full screen specifications, the design tokens as code, and the complete repository layout.

## How to read this document

This is a **single recommended path**, not a menu. Every tool is the one pick for its layer, with the reason it beat the alternatives. Parts I–II say what to build and why; Part III covers the platform around the model; Part IV is the build and the pitch; Part V takes the build from an empty laptop to a deployed showcase. When the platform and the algorithm compete for hours, the algorithm wins.

**On MATLAB releases.** System requirements in this document were verified against R2026a. Everything applies equally to R2026b, the release installed on the team laptop, with one exception: the Python engine package must match your exact release (Section 21).

## Contents

**Part I — Position**

- [1. Scope and scoring logic](#1-scope-and-scoring-logic)
- [2. What is already solved, and what is not](#2-what-is-already-solved-and-what-is-not)
- [3. Users and scenarios](#3-users-and-scenarios)

**Part II — System**

- [4. System architecture](#4-system-architecture)
- [5. End-to-end screening flow](#5-end-to-end-screening-flow)
- [6. Algorithm pipeline](#6-algorithm-pipeline)
- [7. Capacity model](#7-capacity-model)

**Part III — Platform**

- [8. Deployment and scaling](#8-deployment-and-scaling)
- [9. Identity and access](#9-identity-and-access)
- [10. Data architecture](#10-data-architecture)
- [11. Verification and validation](#11-verification-and-validation)
- [12. Regulatory parameters](#12-regulatory-parameters)

**Part IV — Build**

- [13. Tool register](#13-tool-register)
- [14. Interface design](#14-interface-design)
- [15. Prototype build plan](#15-prototype-build-plan)
- [16. Demo script](#16-demo-script)
- [17. Risk register](#17-risk-register)

**Part V — Setup and operations**

- [18. Setup roadmap](#18-setup-roadmap)
- [19. Your machine — compatibility verdict](#19-your-machine--compatibility-verdict)
- [20. Compute — is a Colab T4 needed?](#20-compute--is-a-colab-t4-needed)
- [21. Installation](#21-installation)
- [22. Configuration](#22-configuration)
- [23. Integration](#23-integration)
- [24. Testing](#24-testing)
- [25. Deployment](#25-deployment)
- [26. Caching strategy](#26-caching-strategy)

---

## 1. Scope and scoring logic

PS 26038 grades an algorithm, not a platform. Everything in this document earns its place by one of two tests, and anything failing both was cut.

The problem statement asks for five modules: image quality assessment, retinal structure segmentation, severity grading, explainability, and a Simulink workflow simulation. It names its own acceptance criteria — sensitivity above 90% and specificity above 85% for referable DR, Grad-CAM outputs rated clinically useful, a resource-allocation model, and validation showing the integrated pipeline beats any single technique.

That last clause is an instruction to build an ablation table. Design the architecture backwards from it.

### The two tests

Every element outside the five graded modules must be either a **regulatory precondition** for touching Indian health data, or must **feed a graded module**. Applying those tests:

| Element                                   | Verdict        | Reason                                                                                                                                                                                                                                                  |
|-------------------------------------------|----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Audit chain, consent ledger               | ✅ **build**   | Regulatory precondition. No lawful path to production without them.                                                                                                                                                                                     |
| Role-based access for clinical users      | ✅ **build**   | Which ophthalmologist signed a grade is a medico-legal fact. A human-in-the-loop with anonymous humans is not a loop.                                                                                                                                   |
| Admin dashboard                           | ⚠️ **reframe** | Not as observability. As *Programme & Model Health*, where measured throughput meets the SimEvents prediction — which makes it Module 5 content.                                                                                                        |
| Database and object storage               | ✅ **build**   | Required, but scoped: pixels never enter the relational store.                                                                                                                                                                                          |
| Duplicate and integrity checks            | ✅ **build**   | The same eye screened twice at one camp silently inflates throughput and wastes grader time. A real field failure, cheap to prevent.                                                                                                                    |
| Patient signup and login                  | ❌ **cut**     | Patients must not have accounts. Every account makes you a data fiduciary for it, adds a phishing surface aimed at first-time app users, and blocks the people you are trying to reach. Signed single-use links are the correct design, not a shortcut. |
| Distributed tracing, APM, log aggregation | ❌ **cut**     | Zero judge value, one day of cost.                                                                                                                                                                                                                      |

> **The governing trade.** When the platform track and the algorithm track compete for hours, the algorithm wins. A polished platform wrapped around a 78%-sensitivity model loses to a plain one wrapped around 92%.

---

## 2. What is already solved, and what is not

Detection is commodity in both the US and India. The unsolved layer is precisely what this problem statement asks for.

### Solved elsewhere

Three autonomous DR systems hold FDA clearance — LumineticsCore (formerly IDx-DR), EyeArt, and AEYE-DS. The first cleared in 2018 on a prospective primary-care trial reporting 87.2% sensitivity and 90.7% specificity for more-than-mild DR. Reimbursement is settled too: CPT 92229 was the first CPT code for autonomous AI in any specialty, paying roughly \$40 per screening against \$29 for physician-interpreted remote imaging.

India is not a blank slate either. Remidio's Medios AI runs fully offline on a smartphone fundus camera and returns a referable-DR result to a rural operator within about 20 seconds of capture, validated at scale in Indian populations.

### Not solved anywhere

| Gap                                    | Evidence                                                                                                                                                 | Our module                                                                   |
|----------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| Adoption                               | Autonomous DR AI reaches under 0.1% of US screenings, eight years post-clearance, despite reimbursement and quality-measure incentives.                  | The whole product. A solved algorithm attached to an unsolved product.       |
| Image quality in the field             | Across real US adopters, average nonmydriatic gradability ran 49–75% and specificity fell as low as 60%, against 90.7% in the pivotal trial.             | **Module 1.** Not preprocessing — the open problem.                          |
| Quality assessment as a research topic | In the DeepDRiD challenge, grading kappa reached 0.93 while image-quality accuracy topped out at 0.70. The field solved grading and left quality behind. | Module 1, validated against real quality labels.                             |
| Explanation                            | Cleared devices are binary referable/not-referable triage. No five-level grade, no lesion-level evidence.                                                | **Module 4.** Evidence Strip, ICDR criterion matching, calibrated posterior. |
| Scope safety                           | These models are not trained to detect other ocular pathology that a human tele-grader would catch and report.                                           | Human-in-the-loop by design, not as a fallback.                              |
| Referral completion                    | Referral adherence, not detection, is the documented bottleneck in Indian DR programmes.                                                                 | Patient View ends in a held appointment slot.                                |

> **Use this as your opening rebuttal.** "This is solved in America" is the first objection a judge raises. Answering with the 0.1% adoption figure and the 49–75% gradability range converts their objection into your thesis.

---

## 3. Users and scenarios

Four people. Every screen in this system exists because one of them needs it. Demo them in this order.

### A — Sunita, ASHA worker, mobile camp, no signal

Ambegaon block, Pune district. Tuesday NCD camp. 61 registered diabetics, one Android phone with a clip-on fundus lens, 4G that dies by noon. Sunita has never heard the word "microaneurysm." She scans an ABHA QR, and the app talks her through capture in Marathi. Her third image is rejected — but not as "ungradeable." The app says *"Too dark on the nose side. Move the light slightly right and take it again."* She retakes. Nine seconds later: **REFER — see an eye doctor within 4 weeks**, spoken aloud, with a printed QR slip. The phone is offline throughout. At 6 p.m. on sub-centre Wi-Fi, 61 cases sync at once.

*Forces:* rejection with actionable guidance, on-device inference, voice output, a queue that survives a dead network, a decision readable at arm's length in sunlight.

### B — Dr. Anjali Rao, retina specialist, 90 cases, one lunch hour

Cases sorted by decision value, not ID. One case per viewport, keyboard-driven. Left: the fundus at full resolution, deep-zoomable, overlays on number keys. Right: the Evidence Strip — six native-resolution crops, each captioned with the ICDR criterion it satisfies. Below: the calibrated posterior with the referral threshold drawn as a line. She agrees with 78, overturns 9 with a reason chip, marks 3 ungradeable. Median 21 seconds.

*Forces:* keyboard-first review, native-resolution crops, calibration, a disagreement-capture loop.

### C — Ramesh, 54, at home

An SMS link, no login, signed single-use token. He sees his own retina with two soft markers. *"Early damage found. Your eyes can still be saved."* Three cards: what we found, what happens next, where to go — ending in a held slot with a date, not a phone number. A toggle expands the full clinical report for when he hands the phone to a doctor.

*Forces:* two registers of one report, tokenised access without accounts, a referral that terminates in an appointment.

### D — Dr. Patil, District Programme Officer

One question: how many graders and how much bandwidth for 100,000 screenings a year? Two sliders, a contour of 95th-percentile turnaround, one exportable memo.

*Forces:* the SimEvents model, operable by a non-engineer.

---

## 4. System architecture

One MATLAB algorithm, compiled once, served statelessly to every channel. Nothing is reimplemented per surface.

```mermaid
flowchart TB
  subgraph CH["Channel layer — React 19 · Vite · TypeScript · offline-first PWA"]
    FA["Field App<br/>ASHA / technician · offline"]
    RC["Reviewer Console<br/>ophthalmologist · keyboard"]
    PV["Patient View<br/>token link · no account"]
    AD["Admin + District Twin<br/>Grafana · Simulink web app"]
  end
  GW["API Gateway<br/>OIDC · consent · audit · rate limit · schema validation"]
  subgraph SV["Serving layer — MATLAB Production Server on Kubernetes"]
    IN["Ingress / load balancer"]
    P1["MPS pod"]
    P2["MPS pod"]
    P3["MPS pod (autoscaled)"]
    CTF[["netrasetu.ctf — compiled once, mounted in every pod"]]
  end
  subgraph AC["Algorithm core — MATLAB"]
    direction LR
    Q["Quality gate"] --> E["Enhancement"] --> S["Segmentation"] --> F["Fusion grading"] --> C["Calibration"] --> X["Explanation"]
  end
  subgraph PS["Platform services"]
    direction LR
    KC["Keycloak<br/>OIDC · 4 roles · TOTP"]
    PG[("PostgreSQL 17<br/>metadata · FHIR · audit")]
    OS[("Object store<br/>Garage · S3 Object Lock in prod")]
    OB["Prometheus + Grafana"]
    AB["ABDM / ABHA"]
  end
  EDGE["Edge: GPU Coder → Jetson Orin<br/>second compile target · results sync"]
  FA --> GW
  RC --> GW
  PV --> GW
  AD --> GW
  GW --> IN
  IN --> P1
  IN --> P2
  IN --> P3
  CTF -.-> P1
  CTF -.-> P2
  CTF -.-> P3
  SV --> AC
  AC --> PS
  AC -. same source .-> EDGE
  classDef key fill:#E6F1F2,stroke:#0E7C86,stroke-width:1.5px;
  class GW,CTF,X key;
```

*Figure 1 — System architecture. Five layers plus an edge branch. The teal elements are the load-bearing ones: the gateway owns everything that is not mathematics, the CTF archive is compiled once and mounted identically in every pod, and the explanation stage is the product's differentiator. Note the edge path shares source with the cloud path — one algorithm, two compilation targets.*

### Why the core stays in MATLAB

This is a MathWorks problem statement. Reimplementing the model in PyTorch and wrapping MATLAB around it is the fastest available way to lose. Every algorithmic decision lives inside MATLAB; the web layer is a thin, well-made client.

### Why the gateway exists

MPS should do exactly one thing: evaluate the algorithm. ABHA authentication, the consent ledger, the audit chain, tokenised patient links and rate limiting all sit in the gateway, because none of them belong in MATLAB and all of them need to change faster than the model does.

---

## 5. End-to-end screening flow

Five lanes, two loops. The retake loop is what makes the system work in a field camp; the override loop is what makes it improve.

```mermaid
flowchart TB
  subgraph L1["Screener — ASHA / technician"]
    A1["Scan ABHA QR"] --> A2["Record consent"] --> A3["Capture image"]
    A9["Hand slip + speak decision"]
  end
  subgraph L2["Device — PWA + camera"]
    B1["Quality gate<br/>focus · illumination · FOV"] --> B2{"Gradable?"}
    B3["Retake guidance<br/>max 3 attempts"]
    B4["Queue offline<br/>Dexie + Workbox"]
  end
  subgraph L3["Cloud — gateway + MATLAB"]
    C1["Gateway<br/>authN · consent · audit"] --> C2["Validate + store<br/>pHash · SHA-256"] --> C3["Inference<br/>grade · evidence · report"] --> C4{"Triage router"}
    C5["Auto-discharge<br/>grade 0–1, confident · about 71%"]
  end
  subgraph L4["Ophthalmologist — district hub"]
    D1["Reviewer Console<br/>21 s median"]
    D2["Overturn + reason chip"]
    D3["Sign report<br/>HPR ID → audit chain"]
  end
  subgraph L5["Patient — home"]
    E1["SMS link<br/>signed · single-use · 72 h"] --> E2["Held appointment slot"] --> E3["Attendance recorded"]
  end
  A3 --> B1
  B2 -- no --> B3
  B3 -. retake loop .-> A3
  B2 -- yes --> B4 --> C1
  C4 -- routine --> C5
  C4 -- "referable or low confidence" --> D1
  C5 -. decision returned .-> A9
  D1 --> D2
  D1 --> D3
  D2 -. active-learning loop .-> C3
  D3 --> E1
  classDef refer fill:#FBECEB,stroke:#B3261E;
  classDef routine fill:#EAF4EE,stroke:#1B7F4C;
  classDef retake fill:#FBF3E6,stroke:#B26B00;
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class C5 routine;
  class B3 retake;
  class C3,D1,E2 key;
```

*Figure 2 — End-to-end screening flow. The amber dashed paths are the two loops that most implementations omit: the retake loop, which recovers images that would otherwise be discarded, and the active-learning loop, which turns grader disagreement into training data. The green path is the auto-discharge branch that produces the 71% ophthalmologist-hour saving. The flow does not end at "referred" — it ends at "attended."*

### Decision logic for one screening

The swimlane shows who does what. This flowchart shows what the system decides, in order, for a single eye. Every terminal state is one of the three decision states from Section 14, or a human decision — there is no path that ends in "uncertain."

```mermaid
flowchart TD
  S(["Start screening"]) --> D1{"Consent given?"}
  D1 -- no --> X1(["Stop — record refusal"])
  D1 -- yes --> C["Capture image<br/>live quality ring"]
  C --> D2{"Gradable?"}
  D2 -- no --> D3{"Attempt 1 or 2?"}
  D3 -- yes --> R["Speak retake guidance"] --> C
  D3 -- "no, 3rd failure" --> X2(["Refer for dilated exam"])
  D2 -- yes --> D4{"Seen in last 30 days?"}
  D4 -- yes --> F["Flag repeat screening<br/>link prior study"] --> RV
  D4 -- no --> G["Grade and calibrate<br/>evidence crops + ICDR match"]
  G --> D5{"p(referable) ≥ threshold?"}
  D5 -- yes --> RF["REFER<br/>eye doctor within 4 weeks"] --> RV
  D5 -- no --> D6{"Grade ≤ 1 and confident?"}
  D6 -- yes --> RT(["ROUTINE<br/>rescreen in 12 months"])
  D6 -- no --> RV["Reviewer decides<br/>agree · overturn · ungradeable"]
  RV --> END(["Signed report → patient link"])
  RT -- report still sent --> END
  classDef refer fill:#FBECEB,stroke:#B3261E;
  classDef routine fill:#EAF4EE,stroke:#1B7F4C;
  classDef retake fill:#FBF3E6,stroke:#B26B00;
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class RF refer;
  class RT routine;
  class R,X2 retake;
  class RV key;
```

*Figure 2b — Decision logic flowchart. Two design choices are visible here. A repeat screening is never silently dropped or silently re-graded — it is routed to a human with the prior study attached. And the threshold diamond comes before the confidence diamond: an eye above the referral threshold is referred regardless of confidence, because a missed referable case costs more than a reviewer's 21 seconds.*

---

## 6. Algorithm pipeline

Two streams into one fusion model. The architecture generates the required ablation table by construction.

```mermaid
flowchart LR
  I[/"Fundus image<br/>4288 × 2848"/] --> Q{"1 · Quality gate<br/>Laplacian · illumination · FOV · pHash"}
  Q -- reject --> RG["Retake guidance<br/>failure mode → localised instruction"]
  Q -- accept --> E["2 · Enhancement<br/>FOV crop → Ben Graham → CLAHE"]
  E --> S["3 · Structures and lesions<br/>optic disc · fovea · vessel U-Net<br/>MA: rotating top-hat → CNN → Gaussian fit<br/>haemorrhage · exudate · NV proxy"]
  S --> A["Stream A — CNN<br/>ordinal regression head"]
  S --> B["Stream B — lesion features<br/>~24-dim, ICDR-aligned"]
  Q --> QC["Stream C — quality<br/>score + FOV metrics"]
  A --> F["4 · Fusion<br/>fitcensemble → grade 0–4"]
  B --> F
  QC --> F
  F --> K["5 · Calibration<br/>temperature scaling · ECE"]
  K --> X["6 · Explanation and artefacts<br/>Evidence Strip · ICDR match<br/>Grad-CAM + LLP · PDF + FHIR R4"]
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  classDef retake fill:#FBF3E6,stroke:#B26B00;
  class F,X key;
  class RG retake;
```

*Figure 3 — Algorithm pipeline. Three streams converge on a small gradient-boosted fusion model, which is what makes the required "beats any single technique" ablation fall out of the architecture rather than needing to be constructed afterwards. The amber branch is the reject path — the only part of the pipeline that talks back to the person holding the camera.*

### Three decisions that carry most of the performance

**Ordinal regression, not 5-class softmax.** DR severity is ordered; misgrading 0→4 is not the same error as 3→4. Train a regression head with MSE loss, then optimise four cut-points on validation to maximise quadratic weighted kappa. Two lines different from the naive approach, and the single highest-return modelling choice available.

**Grad-CAM from an intermediate layer.** At ResNet-50's final conv layer the map is 7×7. Upsampled over a 4288-pixel image, one cell spans roughly 600 pixels — about 40× the diameter of a microaneurysm. Say this arithmetic out loud in the pitch; it is why the Evidence Strip exists.

**Quantified explanation.** IDRiD ships pixel-level lesion masks. Use them to compute the fraction of Grad-CAM activation mass falling inside true lesion masks, and the pointing-game score. "Clinically useful explanation" becomes a number with a confidence interval instead of a claim. Almost no competing team will do this.

---

## 7. Capacity model

The screening pipeline is a queueing problem, not a signal-flow problem. Model it in SimEvents, and give the output to someone who controls a budget.

```mermaid
flowchart LR
  G(["Arrivals<br/>Poisson λ per PHC"]) --> Q1[["Queue · FIFO"]] --> S1["Capture + quality server"]
  S1 -. "rework 10–15%, measured" .-> Q1
  S1 --> T["Transmission<br/>delay = size ÷ bandwidth"] --> CH{"Cache hit?"}
  CH -- "yes · measured ratio" --> R{"Triage router"}
  CH -- no --> INF["Inference server<br/>service time measured with Locust"] --> R
  R -- "grade 0–1, confident" --> AD(["Auto-discharge"])
  R -- "referable or uncertain" --> RQ[["Review queue<br/>sorted by decision value"]] --> GS["Grader server · 30 s"] --> SK(["Sink"])
  RP[("Resource pool<br/>N ophthalmologists")] -.- GS
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class INF,GS key;
```

*Figure 4 — SimEvents capacity model. Entity Queue, Entity Server and Resource Pool blocks map directly onto the vocabulary of a district programme. Two parameters are measured rather than guessed: the rework rate comes from your quality gate's own rejection statistics, and inference service time comes from the real pipeline. That is what separates this from a plausible-looking simulation.*

Lead your final slide with the ophthalmologist-hours figure, not the turnaround time. It is the entire policy case for the project.

---

## 8. Deployment and scaling

MATLAB Production Server on Kubernetes. One compiled archive, many channels.

MPS is the multi-channel answer because client libraries exist for Python, C/C++, .NET, Java and a range of enterprise applications including web apps and Excel add-ins, enabling integration across desktop, web, mobile and enterprise systems. Your field PWA, reviewer console, patient link, an eSanjeevani hook and a WhatsApp bot all call the same endpoint. You compile `netrasetu_analyze` once and never port it.

It scales because the server is stateless: vertically by adding cores and memory, or horizontally by adding servers behind a load balancer. MathWorks ships a supported Kubernetes reference architecture with Docker images and Helm charts for EKS, AKS, GKE, OpenShift or on-premises, where the Ingress controller doubles as the load balancer and is the preferred way to expose the service in production. Containers beat VMs here because screening load is spiky — camp days, not steady state.

| Concern                 | Decision                                                                                                                                                                                                                                                                                                                         |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Long-running requests   | Full inference plus Grad-CAM plus report generation is not a 200 ms call. Use MPS asynchronous execution; the client must carry the `Set-Cookie` value on subsequent requests to land on the same server. This also gives the field app the POST-then-poll behaviour it needs when a phone drops off 4G mid-upload.              |
| Sizing                  | Each MPS container needs at least 1 CPU core and 2 GiB RAM, on Kubernetes 1.24 or later. Feed those numbers into the SimEvents model rather than guessing service capacity.                                                                                                                                                      |
| Licensing               | Requires a *concurrent* licence tied to a network licence manager that must be reachable from the cluster but must not be installed inside it, plus access to the MathWorks container registry. State this as a known procurement dependency — knowing where the licence manager sits signals you have read the deployment docs. |
| Prototype substitute    | MATLAB Engine API for Python behind FastAPI. Ships with MATLAB, no extra licence, runs on one laptop, gives live inference during a demo instead of cached JSON.                                                                                                                                                                 |
| Not for public channels | MATLAB Web App Server hosts App Designer apps and is built for a trusted intranet. Keep it for the District Twin, which genuinely is an internal NHM tool. Everything public goes through MPS behind the gateway.                                                                                                                |

---

## 9. Identity and access

Three authenticated roles, one unauthenticated path, and a hard separation between grading and administering.

```mermaid
sequenceDiagram
  participant D as Field device
  participant K as Keycloak
  participant G as Gateway
  participant S as Object store
  participant M as MATLAB / MPS
  participant P as PostgreSQL
  participant Pt as Patient
  D->>K: device credential + PIN
  K-->>D: JWT · role=screener · facility · 15 min
  rect rgb(251, 243, 230)
    Note over D,P: per screening
    D->>G: POST /study — image + consent artefact
    G->>P: consent row + audit entry (hash chain)
    G->>S: store raw image + SHA-256
    G->>M: netrasetu_analyze (async)
    M-->>G: grade · posterior · evidence · report · FHIR
    G->>P: persist result with model_ver
  end
  rect rgb(230, 241, 242)
    Note over G,P: grader review — separate session, TOTP, HPR ID
    G->>P: decision + reason chip → review + audit
    G->>S: presigned tile URLs
  end
  G->>Pt: SMS — signed single-use token, 72 h
  Pt->>G: GET /r/token — no account, no session persisted
```

*Figure 5 — Authentication and consent sequence. Note what is absent: the patient never authenticates. The amber regions mark the two places where a hash-chained audit entry is mandatory. Large images never transit the API layer — the console fetches tiles directly from object storage via presigned URLs.*

| Role            | Authentication                                                                                                              | Authorisation boundary                                                                             |
|-----------------|-----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Screener        | Facility-issued credential bound to a registered device, plus a 6-digit PIN. Enrolled by the PHC admin — never self-signup. | Capture, own queue, print slips. Cannot see other facilities' grades or export images.             |
| Grader          | Keycloak with mandatory TOTP second factor. Identity linked to their Health Professional Registry ID.                       | Reviewer Console for their district. Every decision written to the audit chain under their HPR ID. |
| Programme admin | Keycloak with TOTP, plus a named approver for destructive actions.                                                          | Admin Console, audit search, operator enrolment. **Cannot grade.**                                 |
| Patient         | No account. Signed, single-use, 72-hour link by SMS.                                                                        | Their own report only. Token bound to one study ID and one phone-number hash.                      |

Two rules worth saying out loud in the pitch: a second factor is mandatory for anyone who can change a clinical grade, and no role can both grade and administer. Separation of duties is what makes an audit trail meaningful rather than decorative.

Keycloak is the pick because MPS supports certificate- and token-based authentication with OAuth 2.0 access control, and MATLAB Web App Server supports OIDC and LDAP. One realm secures the API layer and the District Twin with the same tokens, and self-hosting keeps identity data in-country.

---

## 10. Data architecture

Pixels never enter the relational store. At 15–30 MB per image and 100,000 screenings a year, that is roughly 3 TB annually.

```mermaid
erDiagram
  PATIENT ||--o{ STUDY : has
  PATIENT ||--o{ CONSENT : grants
  STUDY ||--o| RESULT : produces
  STUDY ||--o{ REVIEW : receives
  STUDY ||--o| FHIR_BUNDLE : exports
  STUDY ||--o| JOB : "queued as (Tier 1)"
  PATIENT {
    uuid id PK
    bytea abha_hash "pgcrypto"
    uuid facility_id "RLS key"
    bytea phone_hash
  }
  STUDY {
    uuid id PK
    uuid patient_id FK
    text laterality "OD or OS"
    bytea sha256
    bigint phash "dedupe"
    uuid client_key "idempotency, unique"
    uuid device_id FK
  }
  RESULT {
    uuid study_id FK
    int grade "0 to 4"
    real_array posterior "5 values"
    real p_referable
    real llp
    text model_ver "required"
  }
  REVIEW {
    uuid study_id FK
    text grader_hpr
    text decision
    text reason_chip
    int elapsed_ms
  }
  CONSENT {
    uuid patient_id FK
    text purpose
    bytea notice_hash
    text language
    timestamptz granted_at
    timestamptz withdrawn_at
  }
  AUDIT {
    bigint seq PK
    text actor
    text action
    bytea prev_hash
    bytea hash "SHA-256 chain"
  }
  FHIR_BUNDLE {
    uuid study_id FK
    jsonb bundle "NRCeS R4"
  }
  INFERENCE_CACHE {
    bytea img_sha256 PK
    text model_ver PK
    text cfg_hash PK
    jsonb payload
    int hit_count
  }
  JOB {
    uuid id PK
    uuid study_id FK
    text object_key
    text status
    text worker
  }
```

*Figure 6 — Data model and storage layout. Teal-outlined tables are the ones with regulatory weight. model_ver on every result is not a nicety: when you retrain, you must be able to answer "which model graded this patient in March" without archaeology.*

Two further tables support caching and are specified in Section 26: `inference_cache`, keyed by image hash, model version and configuration hash, and a unique `client_key` column on `study` for idempotent retries.

Row-level security binds only a role that does not own the tables. Section 25 specifies the separate `gateway` and `worker` roles, with the policy forced, that make the facility isolation above actually enforceable.

---

## 11. Verification and validation

Two distinct disciplines that teams routinely conflate. Say both words separately in your pitch.

### Data validation — is this input trustworthy?

| Check                                             | Where                      | On failure                                                                 |
|---------------------------------------------------|----------------------------|----------------------------------------------------------------------------|
| Schema conformance                                | Gateway (OpenAPI/Pydantic) | 400 before MATLAB is ever invoked                                          |
| SHA-256 of original bytes                         | Ingest → audit chain       | Detects post-hoc tampering                                                 |
| Perceptual hash vs. last 30 days at that facility | `nx_quality`               | Flags a repeat screening — prevents double-counting and wasted grader time |
| Device fingerprint vs. registered cameras         | Ingest                     | Quarantine, not silent acceptance                                          |
| Laterality sanity via disc–fovea vector           | `nx_structures`            | Catches mislabelled eyes, a common and dangerous field error               |
| FHIR bundle against NRCeS R4 profile              | Egress                     | Never emit a malformed clinical record                                     |

### Clinical validation — is this output trustworthy?

- **Split at patient level, before anything else.** APTOS contains near-duplicate fellow-eye pairs from the same patient. Splitting at image level leaks and inflates every number you report. Commit `splits.json` in hour one.
- **Pre-specify the threshold on validation.** Choose the operating point that achieves sensitivity ≥ 0.90 on the validation ROC, freeze it, then report test performance at that fixed point. Picking it on the test set is the commonest form of accidental fraud in this competition.
- **Bootstrap for uncertainty.** 2,000 resamples, 95% CIs on both sensitivity and specificity.
- **Hold Messidor-2 out entirely.** Train on APTOS and IDRiD; test on data you never touched. "Our model generalises across acquisition sites" is a claim almost no hackathon team can make.
- **Report the full 5×5 confusion matrix and per-grade recall.** APTOS is about 49% grade 0; accuracy alone hides everything that matters.

### Continuous validation — the Admin Console

Validation does not end at submission. The dashboard is the continuous form of the same discipline, and it is deliberately framed as *Programme & Model Health* rather than observability, because the first panel is Module 5 content.

| Panel                                 | What it shows, and the intervention attached                                                                                                                                                                                                                                                                                               |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 · Simulated vs. measured throughput | Your SimEvents prediction overlaid on what the district actually did. Divergence triggers re-parameterisation. This converts the Simulink module from slideware into a live operational instrument.                                                                                                                                        |
| 2 · Gradability by site               | Rejection rate by failure mode, sliced by device, operator and facility. A site at 58% gradability does not need a better model — it needs two hours of operator retraining or a cleaned lens coupling. Given that US adopters ran 49–75% gradability, a panel that surfaces and fixes this addresses the field's actual unsolved problem. |
| 3 · Model drift                       | Grade distribution against the training prior, mean calibrated confidence, and the **grader override rate** — which moves weeks before any accuracy metric does. Alert at baseline + 2σ over a 7-day window.                                                                                                                               |
| 4 · Referral funnel                   | Screened → referred → booked → **attended**. Only the last number matters. A dashboard that stops at "referred" is measuring the wrong thing.                                                                                                                                                                                              |

Instrument it from MATLAB directly. Because MPS supports custom Prometheus metrics defined inside your MATLAB code, `nx_quality` can increment `netrasetu_quality_reject_total{reason="underexposed"}` as it rejects an image — no separate telemetry layer, and no risk of the dashboard and the algorithm disagreeing about what happened.

---

## 12. Regulatory parameters

Four regimes apply. Know which one governs which part of the system.

### CDSCO and the Medical Devices Rules 2017 — governs whether you can sell it

CDSCO issued draft guidance on Medical Device Software on 21 October 2025 and has since finalised it. The definition explicitly covers software as a medical device and medical software enabled by AI, subject to the four-tier Class A–D risk classification under MDR 2017. Software performing disease diagnosis or screening sits at the moderate-to-high end, so plan for **Class C**, filed on Form MD-15 through the Sugam portal.

> **CE Mark and FDA clearance do not substitute for CDSCO licensing.** India's framework operates independently; foreign dossiers can support the clinical performance evaluation but the Indian application must be filed and approved separately. This kills the "we would follow the US pathway" answer, so have it ready as a backup slide.

The guidance does not create new law — it clarifies how MDR 2017 applies across the software lifecycle, with quality-management expectations aligned to ISO 13485, plus IEC 62304 for software lifecycle and ISO 14971 for risk management.

The clause that matters most to you: India lacks AI/ML-specific rules today, but the emphasis on technical documentation and risk-based classification means developers of AI-enabled systems must be prepared to explain **datasets, validation methods, and algorithmic logic** as part of their submission. That is a regulator asking for exactly what your explainability module produces. It reframes Module 4 from "helpful for clinicians" to "required for market access."

### DPDP Act 2023 and DPDP Rules 2025 — governs the data

Rules were notified on 13 November 2025 with phased compliance. Consent-manager registration opens 13 November 2026; the substantive consent, notice and security provisions take effect 13 May 2027. Consent must be specific, revocable, and recorded through interoperable platforms maintained by board-registered consent managers. Note that DPDP applies uniformly to all personal data without carving out a separate "sensitive" category as the earlier SPDI Rules did — so health data receives the same statutory baseline, and you should exceed it voluntarily.

### ABDM — governs interoperability

FHIR R4 on NRCeS India profiles, ABHA identity, HIE-CM consent artefacts. Sandbox exit requires a functional testing report *and* a Web Application Security Assessment from a CERT-In empanelled agency before production credentials are issued. Budget for it; it is not a formality.

### Clinical governance — governs the humans

Your system is a screening triage aid with mandatory human review, not an autonomous diagnostic. Say this consistently. It keeps you in a lower risk tier, it is what the problem statement actually asks for, and it is honest.

### What to build in the hackathon

You will not achieve ABDM certification or a CDSCO licence in 36 hours and nobody expects you to. Build the *seams* — four hours of work, disproportionate credibility. A consent row visible in the demo. A real FHIR R4 bundle you can show as JSON. A hash-chained audit entry. The ABHA sandbox registration page on a slide with your integration plan.

---

## 13. Tool register

One pick per layer. Each chosen because it is the native fit for something already in the stack, not because it is popular.

### Algorithm and simulation

| Layer                    | Pick                                                                                | Reason                                                                                     |
|--------------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| Numerical core           | MATLAB R2026a                                                                       | Current release; Deep Learning Toolbox training improvements and MATLAB Copilot land here. |
| Transfer learning        | `imagePretrainedNetwork`                                                            | Unified entry point for pretrained backbones with class adaptation.                        |
| Explainability           | `gradCAM`                                                                           | Native, accepts a `FeatureLayer` so you can pull lesion-scale maps instead of 7×7 mush.    |
| Reference implementation | [ogemarques/xai-matlab](https://github.com/ogemarques/xai-matlab)                   | Working MATLAB Grad-CAM and imageLIME on a medical task. Read it before writing yours.     |
| Annotation               | Medical Image Labeler                                                               | Correct IDRiD masks and label hard cases without leaving MATLAB.                           |
| Reporting                | MATLAB Report Generator                                                             | Programmatic PDF from the same session as the inference.                                   |
| Throughput               | [SimEvents](https://www.mathworks.com/products/simevents.html)                      | Entity Queue, Entity Server, Resource Pool — the vocabulary of a district programme.       |
| Starting point           | [awesome-matlab-hackathons](https://github.com/mathworks/awesome-matlab-hackathons) | MathWorks' own curated resource list.                                                      |

### Bridge, platform and front end

| Layer                  | Pick                                                                                                                                                                                       | Reason                                                                                                                                                                                                                                                                                                                                 |
|------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Demo bridge            | [MATLAB Engine API for Python](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html) + FastAPI                                                                              | Ships with MATLAB, no extra licence, live inference on one laptop.                                                                                                                                                                                                                                                                     |
| Production serving     | [MATLAB Production Server](https://www.mathworks.com/products/matlab-production-server.html) on [Kubernetes](https://github.com/mathworks-ref-arch/matlab-production-server-on-kubernetes) | Stateless, horizontally scalable, client libraries for every channel.                                                                                                                                                                                                                                                                  |
| Simulink as a web page | Simulink Compiler → MATLAB Web App Server                                                                                                                                                  | Gives the District Officer a URL. Intranet only, by design.                                                                                                                                                                                                                                                                            |
| Edge                   | GPU Coder → NVIDIA Jetson Orin                                                                                                                                                             | Generates CUDA for the whole algorithm including classical pre/post-processing, not just the network.                                                                                                                                                                                                                                  |
| Identity               | [Keycloak](https://www.keycloak.org)                                                                                                                                                       | MPS supports OAuth 2.0 providers; Web App Server supports OIDC. One realm covers both.                                                                                                                                                                                                                                                 |
| Metrics                | [Prometheus](https://prometheus.io) + [Grafana](https://grafana.com)                                                                                                                       | MPS already returns diagnostics in Prometheus format and supports custom metrics written in your MATLAB code. Nothing else has a first-party hook.                                                                                                                                                                                     |
| Relational store       | [PostgreSQL 17](https://www.postgresql.org)                                                                                                                                                | JSONB for FHIR, pgcrypto for identifiers, row-level security for facility partitioning enforced in the database rather than in application code.                                                                                                                                                                                       |
| Showcase data (Tier 1) | [Supabase](https://supabase.com), Mumbai region                                                                                                                                            | Postgres and S3-compatible Storage in `ap-south-1`, where Railway has no India region. Used for data only — not its Auth or browser-facing API. Section 25 covers the five settings that make it safe.                                                                                                                                 |
| Image store            | [Garage](https://garagehq.deuxfleurs.fr/) (prototype) · Amazon S3, ap-south-1 (production)                                                                                                 | MinIO stopped publishing community Docker images in October 2025 and its repository is archived, so it is no longer a safe pick. Garage is a single-binary S3-compatible store that runs in one container on your laptop. It lacks S3 Object Lock, so production moves to a managed in-country S3 with Object Lock in compliance mode. |
| Framework              | React 19 + Vite + TypeScript                                                                                                                                                               | Fastest path to a running PWA.                                                                                                                                                                                                                                                                                                         |
| Fundus viewer          | [OpenSeadragon](https://openseadragon.github.io)                                                                                                                                           | The most important front-end pick. An `<img>` tag destroys exactly the sub-pixel detail the problem statement asks you to detect.                                                                                                                                                                                                      |
| Offline                | [Dexie](https://dexie.org) + [Workbox](https://developer.chrome.com/docs/workbox)                                                                                                          | What makes "offline camp" real rather than claimed.                                                                                                                                                                                                                                                                                    |
| Typography             | IBM Plex Sans / Devanagari / Mono via [Fontsource](https://fontsource.org)                                                                                                                 | One superfamily with a real Devanagari companion, plus tabular figures for the grader console. Self-hostable, works offline.                                                                                                                                                                                                           |
| Voice                  | Web Speech API                                                                                                                                                                             | Offline TTS using Android's installed hi-IN and mr-IN voices. Zero cost, high impact for low-literacy operators.                                                                                                                                                                                                                       |

### Health-systems integration

| Layer | The pick | Why | Link |
|---|---|---|---|
| Patient identity | **ABHA** via the ABDM Sandbox | The 14-digit ABHA is India's health identity layer; ABDM integration is already effectively required for government hospital empanelment and PM-JAY-linked facilities | [ABDM Sandbox](https://sandbox.abdm.gov.in) · [ABDM](https://abdm.gov.in) |
| Record format | **FHIR R4 with NRCeS India profiles** | ABDM prescribes FHIR R4 customised to the Indian context. Emit your report as a `DiagnosticReport` + `Observation` + `Media` bundle | [NRCeS FHIR R4 India](https://nrces.in/ndhm/fhir/r4/index.html) |
| Consent | **HIE-CM consent artefact**, mirrored in a local consent ledger | ABDM's architecture is consent-first and federated | [ABDM architecture](https://sandbox.abdm.gov.in/docs/architecture) |
| Privacy law | **DPDP Act 2023 + DPDP Rules 2025** | Rules were notified 13 Nov 2025 with phased compliance; consent-manager registration opens Nov 2026 and the substantive consent/notice/security provisions bite 13 May 2027. Build for it now | [MeitY / DPDP overview](https://www.dlapiperdataprotection.com/?t=law&c=IN) · [EY compliance guide](https://www.ey.com/en_in/insights/cybersecurity/decoding-the-digital-personal-data-protection-act-2023) |
| Teleconsult pathway | **eSanjeevani** as the referral destination | India's national telemedicine platform, hub-and-spoke, >163 million consultations by Sept 2023 and heavily used for diabetes follow-up. Your "book my appointment" button should terminate here, not in a mock modal | [Adoption study](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12558045/) |

### Datasets

| Dataset                                                                                        | Role                                                                                                                                                |
|------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| [APTOS 2019](https://www.kaggle.com/c/aptos2019-blindness-detection)                           | Primary grading training set, 3,662 labelled images.                                                                                                |
| [IDRiD](https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid) | Lesion segmentation and the ground truth for your Grad-CAM localisation metric. Indian population — say so on the slide.                            |
| [Refined IDRiD (Zenodo)](https://zenodo.org/records/17615903)                                  | 81 images re-annotated at 1024×1024 with unified masks covering 7 lesion types and 4 anatomical structures in 12 classes. A free multi-task target. |
| [DRIVE](https://drive.grand-challenge.org/)                                                    | Vessel U-Net and the published Dice/AUC benchmark you report against.                                                                               |
| [Messidor-2](https://www.adcis.net/en/third-party/messidor2/)                                  | **Hold out entirely.** External validation across acquisition sites.                                                                                |
| [FGADR](https://arxiv.org/pdf/2008.09772)                                                      | 1,842 pixel-level lesion-annotated images if you need segmentation volume beyond IDRiD's 81.                                                        |
| DeepDRiD                                                                                       | The only public set with real image-quality labels rather than synthetic degradations. Use it to validate Module 1.                                 |

---

## 14. Interface design

### The design thesis

The interface is achromatic so the retina is the only saturated thing on screen.

Every UI colour is a cool neutral. Every saturated colour is either the fundus image or a lesion marker. This is a clinical safety rule, not an aesthetic preference: if your buttons are orange and your hard-exudate markers are yellow, a tired grader at case 74 will conflate chrome with pathology.

#### Colour tokens

**Chrome — cool neutrals only**
```css
--nx-void      #0B0F14   /* reviewer console background — camera dark   */
--nx-slate-900 #141A21
--nx-slate-700 #263038
--nx-slate-400 #7C8B98
--nx-slate-200 #C4CED6
--nx-paper     #F4F6F7   /* field app light theme — outdoor legibility  */
--nx-signal    #0E7C86   /* the ONLY interactive accent: deep teal.
                            Chosen as the optical complement of retinal
                            orange, so it can never be mistaken for tissue */
```

**Lesion semantics — derived from what the lesion actually looks like**
```css
--lx-exudate    #E8C33A   /* hard exudate — waxy yellow                */
--lx-cottonwool #B9D6C6   /* soft exudate — pale mint                  */
--lx-haem       #8E1F2B   /* intraretinal haemorrhage — deep crimson   */
--lx-microan    #C2185B   /* microaneurysm — magenta-rose, deliberately
                             NOT red, so 20px dots stay findable       */
--lx-vessel     #5A1A14   /* vessel tree — oxblood                     */
--lx-neovasc    #7B2FF7   /* NV proxy — violet, the one non-natural hue,
                             flagged as a proxy not a detection        */
```

**Decision states — three, and only three**
```css
--dx-refer     #B3261E   /* Refer                                     */
--dx-routine   #1B7F4C   /* Routine rescreen                          */
--dx-retake    #B26B00   /* Retake image                              */
```
No fourth state. If your system can output "possibly", an ASHA worker cannot act on it.

#### Type scale

One superfamily, three roles, chosen for script coverage and tabular figures:

| Role | Face | Usage |
|---|---|---|
| Display | **IBM Plex Sans** 600, tightened tracking | Decisions, headings |
| Devanagari | **IBM Plex Sans Devanagari** 400/600 | Hindi & Marathi at exact weight parity — no visual second-class localisation |
| Data | **IBM Plex Mono** 400/500, `font-variant-numeric: tabular-nums` | Lesion counts, confidences, ABHA IDs, timestamps — anything that appears in a column and must not jitter between cases |

```css
--t-decision  clamp(2.0rem, 6vw, 2.75rem)/1.05   600
--t-h1        1.5rem/1.2      600
--t-body      1.0625rem/1.55  400     /* 17px floor: outdoor + presbyopia */
--t-data      0.9375rem/1.4   500     mono, tabular
--t-caption   0.8125rem/1.35  400
```

Minimum body size is 17px, not 14px. Your users are diabetics over 50 reading a phone in sunlight.

### The signature element: the Evidence Strip

A horizontal filmstrip of native-resolution lesion crops — not a heatmap. Each tile is a 200×200 window cut from the original image at a detected lesion centroid, with a thin marker ring and a caption naming the ICDR criterion it satisfies.

``` text
┌──────────────────────────────────────────────────────────────┐
│ EVIDENCE                                    6 findings  ›    │
├────────┬────────┬────────┬────────┬────────┬────────┬────────┤
│  [MA]  │  [MA]  │  [HE]  │  [HE]  │  [EX]  │  [EX]  │        │
│ ◦      │   ◦    │  ●●    │   ●    │  ▓▓    │  ▓     │  + 0   │
│ super- │ infero-│ supero-│ nasal  │ 1.4 DD │ 0.8 DD │        │
│ temporal│nasal  │ nasal  │        │ from   │ from   │        │
│        │        │        │        │ fovea  │ fovea  │        │
├────────┴────────┴────────┴────────┴────────┴────────┴────────┤
│ 14 intraretinal haemorrhages across 3 quadrants               │
│ → ICDR Level 2, Moderate NPDR · REFERABLE                     │
└──────────────────────────────────────────────────────────────┘
```

Ship Grad-CAM too — the problem statement asks for it — but ship it as context, in a collapsible panel, with your measured Lesion Localisation Precision printed beside it. Showing the number turns a decorative overlay into evidence.

### The second invention: confidence as a band

Never print "Confidence: 87.3%." It is false precision and clinicians distrust it correctly. Print the calibrated posterior across all five grades as a stacked band with the referral threshold drawn as a rule.

``` text
 Grade   0        1        2        3        4
        ├────────┼────────┼────────┼────────┼────────┤
        ▓▓▓▓░░░░░░░░░░░░████████████████░░░░░░░░
                        │
                  referral threshold (frozen on validation)

 Referable DR: 0.91   ·   ECE after temperature scaling: 0.031
```

This communicates two things a single number cannot: where the probability mass sits, and how close the case is to the line. A case at 0.51 and one at 0.98 both round to "refer" but deserve very different amounts of the grader's attention — and the review queue should sort on exactly this.

### Reviewer Console rules that produce the 30 seconds

- **Keyboard first.** `J`/`K` navigate, `A` agrees, `O` overturns, `U` marks ungradeable, `1–5` toggle overlays, `G` toggles Grad-CAM, `Z` snaps to 1:1. A mouse-driven console cannot reach a 21-second median.
- **No scrolling.** One case, one viewport. If it does not fit, cut content.
- **Sort by decision value.** Order by severity × proximity to threshold, so borderline high-grade cases surface first.
- **Overturns are data.** Every overturn requires a one-tap reason chip — image artefact, lesion miscount, disc-region confusion, DME missed. That chip is your active-learning label and your error-taxonomy slide.
- **Show the median timer.** It quantifies the sub-30-second requirement live, in front of the judges.

### Rejection is a feature, with words

Every other team's quality module outputs a binary. Yours outputs a directive. Build a lookup from failure mode — defocus, underexposure, partial field, media opacity — to a localised instruction, in three languages. Two hours of work, and the most field-credible thing in your demo.

``` text
   RETAKE
   The nose side of this image is too dark.
   Move the light slightly to the right.
   [ Retake ]              attempt 2 of 3
```

After three failures: *"Cannot screen here — refer for a dilated exam."* A clean escalation, not a loop. Log every failure reason; that distribution is what parameterises the rework loop in Figure 4, making it an empirical value rather than a guess.

### Screen specifications

The four surfaces from Section 3, specified screen by screen. The Admin Console is specified in Section 11.

#### Field App — five screens, thumb-reachable, one decision

**S1 · Identify.** ABHA QR scan fills the screen; a "no ABHA" path collects name + age + phone only. One-tap consent with a plain-language DPDP notice in the local language, recorded with timestamp and version hash.

**S2 · Capture.** Live camera preview with an alignment reticle. A **live quality ring** around the shutter runs the cheap half of the quality gate (Laplacian variance in the arcade region, illumination CV) at ~5 fps and turns from `--nx-slate-400` to `--dx-routine` when the frame is gradable. Sunita learns to hold steady from the ring, not from training.

**S3 · Assess.** Full-screen progress with honest stage labels — *Checking image quality → Finding the optic disc → Looking for lesions → Grading* — because a nine-second blank spinner in a field camp reads as a crash.

**S4 · Decide.** The whole screen is the decision.

```text
╔══════════════════════════════════════╗
║                                      ║
║   REFER                              ║   ← --t-decision, --dx-refer
║   रेफर करा                            ║
║                                      ║
║   See an eye doctor within 4 weeks   ║
║                                      ║
║   ┌────────────────────────────┐     ║
║   │  [fundus thumbnail, 2 dots]│     ║
║   └────────────────────────────┘     ║
║                                      ║
║   ▸ Why?      (2 findings)           ║   ← optional, collapsed
║                                      ║
║   [ Print slip ]  [ Send SMS ]       ║
║   [ Next patient ]                   ║
╚══════════════════════════════════════╝
```
Spoken aloud in the selected language on arrival. The "Why?" drawer is collapsed by default — Sunita does not need it, but a visiting medical officer does, and its presence is what makes the tool trustworthy rather than oracular.

**S4-alt · Retake.** The rejection path is where you win credibility. Never say "ungradeable". Say what to change:

```text
   RETAKE
   The nose side of this image is too dark.
   Move the light slightly to the right.
   [ Retake ]              attempt 2 of 3
```
After three failures: `Cannot screen here — refer for a dilated exam.` A clean escalation, not a loop. Log every failure reason; that distribution is what feeds the rework loop in your SimEvents model, and it is a real empirical parameter rather than a guessed one.

**S5 · Queue.** A persistent strip: `47 screened · 12 waiting to sync · last sync 09:14`. Tapping shows the queue with retry state. Nothing is ever lost, and Sunita can see that.

#### Reviewer Console — the 30-second screen

Dark theme (`--nx-void`), because graders work in dim rooms and the fundus should be the brightest object on screen.

```text
┌────────────────────────────────────────────────────────────────────────┐
│ NetraSetu Review    Case 12 / 90    ▓▓▓░░░░░░░  median 21s   Dr A. Rao │
├──────────────────────────────────────┬─────────────────────────────────┤
│                                      │ AI GRADE                        │
│                                      │   2 · Moderate NPDR             │
│      [ OpenSeadragon deep-zoom       │   REFERABLE                     │
│        fundus, overlays toggled      │                                 │
│        by number keys 1–5 ]          │ ░▓▓▓████████░░░  0.91           │
│                                      │        │threshold              │
│                                      │                                 │
│                                      │ EVIDENCE                        │
│                                      │ [strip of 6 native crops]       │
│                                      │                                 │
│                                      │ 14 haemorrhages / 3 quadrants   │
│                                      │ → ICDR L2                       │
│  ⌨ 1 MA  2 HE  3 EX  4 SE  5 vessels │ 6 hard exudates, nearest        │
│    G Grad-CAM   Z 1:1 zoom           │   0.8 DD from fovea → DME risk  │
├──────────────────────────────────────┴─────────────────────────────────┤
│  [A] Agree      [O] Overturn → grade _      [U] Cannot grade    [J] ▸   │
└────────────────────────────────────────────────────────────────────────┘
```

Design rules that produce the 30 seconds:
- **Keyboard first.** `J`/`K` navigate, `A` agrees, `O` opens a grade picker, `U` marks ungradeable, `1–5` toggle overlays, `G` toggles Grad-CAM, `Z` snaps to 1:1. A mouse-driven console cannot hit 21 seconds median.
- **No scrolling.** One case, one viewport. If it does not fit, cut content.
- **Sort by decision value, not by ID.** Order by `severity × (1 − |p − threshold|)` so borderline high-grade cases surface first.
- **Overturns are data.** Every `O` requires a one-tap reason chip (*image artefact / lesion miscount / disc-region confusion / DME missed*). That chip is your active-learning label and your error taxonomy slide.
- **Show the median timer.** It quantifies the "<30 seconds" requirement live, in front of the judges.

#### Patient View — the same finding, a different register

Token-authenticated link, no account, works on a 2018 Android with 300 kB of budget.

Three cards, in this order:

1. **What we found.** The patient's own retina with two soft pulsing markers. Plain sentence: *"We found early damage in the small blood vessels of your right eye."* No grade number. A `Show clinical details` toggle reveals the full report for when they hand the phone to a doctor.
2. **What happens next.** A three-step visual timeline: *Today → See the eye doctor (within 4 weeks) → Treatment keeps your sight.* Framed around preservation, not loss. Fear suppresses attendance.
3. **Where to go.** Nearest facility with eye OPD, days and hours, a one-tap call, walking/bus context, and — this is the part that matters — **a held appointment slot with a date**. A referral that ends in a phone number is a referral that will be ignored. A referral that ends in "Tuesday 14th, 10:30, Dr. Rao, District Hospital, Slot #A-42" gets attended.

Every string is available in Hindi, Marathi and English, and the whole card set can be read aloud with one tap.

#### District Twin — SimEvents made operable

An App Designer front-end over the compiled SimEvents model, packaged with Simulink Compiler and hosted on MATLAB Web App Server.

Three inputs the officer actually controls: **number of remote graders**, **uplink bandwidth per PHC**, **number of PHCs**. Two derived outputs he actually cares about:

- A contour of **95th-percentile turnaround time** over graders × bandwidth, with the 4-hour and 24-hour isolines drawn.
- A single headline: **"Ophthalmologist-hours saved per year by AI auto-discharge: 71%."**

Underneath, the model is honest: Poisson arrivals, a quality gate with a rework loop parameterised from your *measured* retake rate, transmission delay as filesize ÷ bandwidth with a rural-4G variability distribution, inference service time from your *measured* runtime, and a triage router that auto-discharges high-confidence grade 0–1 while sending everything else to a finite grader Resource Pool with 30-second service time.

Do the arithmetic on the slide: 100,000 patients ÷ ~250 working days ≈ **400 patients/day**. Then show what configuration sustains it.

---

---

## 15. Prototype build plan

One laptop, campus MATLAB licence, no reliable internet, ten minutes on stage, a projector that will misrepresent your colours.

### Demo topology

``` text
  ONE LAPTOP
  ┌───────────────────────────────────────────────────┐
  │ MATLAB R2026a                                     │
  │   netrasetu_analyze.m  ← the whole pipeline       │
  └────────────────┬──────────────────────────────────┘
                   │ matlab.engine (in-process, kept warm)
  ┌────────────────▼──────────────────────────────────┐
  │ FastAPI  :8000                                    │
  │   POST /analyze         multipart image → JSON    │
  │   GET  /study/{id}/tile OpenSeadragon DZI         │
  │   GET  /report/{id}.pdf                           │
  └────────────────┬──────────────────────────────────┘
  ┌────────────────▼──────────────────────────────────┐
  │ Vite dev server :5173                             │
  │   /field   /review   /patient/{token}   /admin    │
  └───────────────────────────────────────────────────┘
  Phone joins laptop hotspot → http://<laptop-ip>:5173/field
```

The phone-on-hotspot detail matters. Handing a judge a *phone* running your field app while the reviewer console is live on the projector is worth more than any slide.

### The MATLAB contract

Write one entry point and freeze its signature on day one. Everything negotiates around it.

``` matlab
function out = netrasetu_analyze(imgPath)
%NETRASETU_ANALYZE  Full DR screening pipeline for one fundus image.
%   Returns a struct that jsonencode() can serialise directly.

    out = struct();
    out.studyId = char(matlab.lang.internal.uuid);

    % 1 ── quality gate ------------------------------------------------
    q = nx_quality(imgPath);          % .score .verdict .failureMode .phash
    out.quality = q;
    if q.verdict == "reject"
        out.decision       = "RETAKE";
        out.retakeGuidance = nx_guidance(q.failureMode);   % localised key
        return
    end

    % 2 ── enhance -----------------------------------------------------
    I = nx_enhance(imgPath);          % FOV crop → Ben Graham → CLAHE

    % 3 ── structures & lesions ---------------------------------------
    s = nx_structures(I);             % optic disc, fovea, vessel mask
    L = nx_lesions(I, s);             % MA / HE / EX / SE + centroids

    % 4 ── two-stream grading + calibration ---------------------------
    g = nx_grade(I, L, q);            % .posterior(1x5) .grade .pReferable
    out.grade      = g.grade;
    out.posterior  = g.posterior;
    out.pReferable = g.pReferable;
    out.decision   = string(g.pReferable >= NX_THRESHOLD) ...
                     .replace("true","REFER").replace("false","ROUTINE");

    % 5 ── explanation -------------------------------------------------
    out.gradcamPng = nx_gradcam(I, g);           % file path
    out.evidence   = nx_evidence_crops(I, L);    % .type .png .location
    out.criteria   = nx_icdr_criteria(L, s);     % matched ICDR text keys
    out.llp        = g.lesionLocalisationPrecision;

    % 6 ── artefacts ---------------------------------------------------
    out.reportPdf  = nx_report(out);             % Report Generator
    out.fhirBundle = nx_fhir(out);               % FHIR R4 JSON
end
```

Two rules that save you: return a struct `jsonencode` can eat — no objects, no function handles, no `categorical` — and write PNGs to a served static folder, returning paths rather than base64 blobs over the wire.

### Nine-hour build order — two front end, three MATLAB, one integrator

| Hours | MATLAB                                                                                       | Front end                                                     | Integrator                                                                                                                                                                 |
|-------|----------------------------------------------------------------------------------------------|---------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0–1   | Freeze the `netrasetu_analyze` signature; stub it with canned JSON                           | Scaffold Vite, Tailwind, Plex; build four routes on mock data | `docker-compose up` for Postgres, Garage, Keycloak, Prometheus, Grafana; run migrations; seed four facilities; FastAPI against the stub. **End-to-end green in hour one.** |
| 1–4   | Quality gate, enhancement, lesion detectors                                                  | Reviewer Console, OpenSeadragon, Evidence Strip               | Tile pipeline, static serving                                                                                                                                              |
| 4–7   | Grading head, calibration, Grad-CAM, LLP metric                                              | Field App, quality ring, retake guidance, TTS                 | Swap stub for the real engine call; latency budget                                                                                                                         |
| 7–8   | Report Generator, FHIR bundle, SimEvents sweep, custom Prometheus counters from `nx_quality` | Patient View, i18n, District Twin embed, Admin shell          | Seed 30 days of synthetic programme data; wire Grafana; test on venue Wi-Fi                                                                                                |
| 8–9   | **Freeze the checkpoint.** No retraining after this hour.                                    | Projector colour check; dark-room check                       | Three full dry runs, including the failure path                                                                                                                            |

> **Two non-negotiables.** Build the stub-to-UI path in the first hour so integration is never a cliff at hour eight. And nominate one person who owns the demo laptop and the frozen checkpoint from hour eight — nothing kills a finale like a last-minute retrain that breaks the app.

### The demo pack

Curate six images and rehearse them in this order. Never let the demo depend on a random draw.

| \#  | Image                           | What it proves                                        |
|-----|---------------------------------|-------------------------------------------------------|
| 1   | Clean grade 0                   | Speed, and that you do not over-refer                 |
| 2   | Grade 2, countable haemorrhages | Evidence Strip and ICDR criterion match               |
| 3   | Grade 4 with NV near disc       | Severity handling and your honesty about the NV proxy |
| 4   | Deliberately underexposed       | Retake guidance — your credibility moment             |
| 5   | Dense cataract, ungradeable     | Clean escalation after three attempts                 |
| 6   | Unseen Messidor-2 image         | External validation, live                             |

### Offline insurance

- Everything on `localhost`. No CDN fonts, no CDN JavaScript.
- A pre-warmed cache: run all six demo images through the pipeline beforehand so their results sit in the inference cache. If the engine fails or exceeds 15 seconds, the gateway serves them from the cache through the same code path, so the UI is identical (Section 26). Rehearse in this mode once so you can fall into it without a stutter.
- The PDF report already open in a second tab.
- One A3 poster of the Reviewer Console. If both laptop and projector fail, you still present.

### Repository layout

Every file this specification names, in one tree. MATLAB helpers live in a plain `nx/` folder on the path — not a `+nx` package, which would change every call from `nx_quality` to `nx.quality`.

```text
netrasetu/
├── .env.example                  every key, no values — .env and .env.tier1 are gitignored
├── docker-compose.yml            postgres · keycloak · garage · prometheus · grafana
├── requirements.txt              pinned, incl. the matlabengine version matching your MATLAB
├── start-demo.ps1                Tier 0 runbook (Section 25)
├── matlab/
│   ├── netrasetu_analyze.m       ← the frozen contract
│   ├── netrasetu_analyze_json.m  engine-facing wrapper, returns JSON text only
│   ├── nx/                       nx_config · nx_version · nx_model · nx_warmup
│   │                             nx_quality · nx_enhance · nx_structures · nx_lesions
│   │                             nx_grade · nx_gradcam · nx_evidence_crops · nx_icdr_criteria
│   │                             nx_report · nx_fhir · nx_guidance · nx_build_cache
│   ├── config/threshold.json     written by eval/, never by hand
│   ├── models/                   weights — gitignored; modelVer lives in nx_config
│   ├── train/                    ordinal head, fusion, calibration
│   ├── tests/                    unit tests + golden/ (the six demo images)
│   ├── simevents/district_twin.slx
│   └── app/DistrictTwin.mlapp
├── eval/
│   ├── run_validation.m          sens/spec + bootstrap CIs, QWK, LLP, ECE, ablation
│   └── check_threshold_hash.py   CI gate: threshold.json must match validation output
├── service/
│   ├── main.py                   FastAPI gateway, Pattern A (in-process engine)
│   ├── cache.py                  idempotency, cross-patient check, inference cache
│   ├── worker.py                 Pattern B pull worker (Tier 1)
│   ├── auth.py                   OIDC token verification, role guards
│   ├── schemas.py                Pydantic request contracts → OpenAPI
│   ├── tiles.py                  Deep Zoom tiles via pyvips
│   ├── tests/                    pytest: auth, schema, audit chain, caching
│   ├── Dockerfile.gateway        Tier 1 image — no MATLAB, deliberately
│   └── requirements-gateway.txt  excludes matlabengine
├── scripts/migrate.py            same migrations for every tier; sets role passwords
├── platform/
│   ├── migrations/               schema · RLS · audit triggers · inference_cache · 040_roles.sql
│   ├── garage/garage.toml.example
│   ├── keycloak/realm-export.json   4 roles, TOTP policy, secrets masked
│   ├── prometheus/prometheus.yml
│   └── grafana/{provisioning,dashboards}/   programme-health.json
├── web/
│   ├── vercel.json · vite.config.ts      PWA + Workbox runtime caching
│   ├── public/locales/{en,hi,mr}.json
│   └── src/
│       ├── routes/{field,review,patient,admin}
│       ├── api/schema.d.ts       generated from OpenAPI — never edited by hand
│       └── design/tokens.css     the tokens in Section 14
├── tests/
│   ├── fixtures/                 grade0_clean.jpg · grade2_haem.jpg · …
│   └── load/locustfile.py        measured service time → SimEvents
├── .github/workflows/
│   ├── ci.yml                    MATLAB tests · pytest · Vitest + Playwright · threshold hash
│   └── keepalive.yml             daily query so the Supabase showcase never pauses
├── data/                         gitignored — except splits.json, which is committed
│   └── cache/enh_v1_512/         preprocessing cache; version in the folder name
├── results/                      gitignored — load-test CSVs, figures
└── docs/
    ├── VALIDATION.md             metrics, CIs, ablation, splits protocol
    └── LIMITATIONS.md            the honest slide, in prose
```

Commit `splits.json` — patient-level, not image-level. APTOS contains near-duplicate fellow-eye pairs from the same patient; splitting at image level leaks and inflates every number you report. A judge who checks this and finds you got it right will trust everything else you say.

---

## 16. Demo script

| Time | Beat                                                                                                                                                                                                                |
|------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0:00 | **The number.** 77 million Indian diabetics. One ophthalmologist per 100,000 rural people. 90% of vision loss is preventable — if someone looks.                                                                    |
| 0:30 | **Sunita.** Hand a judge the phone. They capture. The retake prompt fires. They fix it. Nine seconds to REFER. Let them do it; do not narrate it.                                                                   |
| 2:00 | **Dr. Rao.** Reviewer Console on the projector. Three cases on the keyboard. Overturn one with a reason chip. Point at the live median: 21 seconds.                                                                 |
| 3:30 | **The evidence.** Zoom to 1:1 on a microaneurysm. Say the 7×7 arithmetic. Show LLP = 84% beside the Grad-CAM.                                                                                                       |
| 4:30 | **Ramesh.** Patient View in Marathi, read aloud. End on the held appointment slot.                                                                                                                                  |
| 5:15 | **The twin.** Two slider drags. "Two graders and 2 Mbps sustain 400 patients a day; auto-discharge cuts ophthalmologist-hours by 71%."                                                                              |
| 5:45 | **The loop closes.** Admin Panel 1: simulated versus measured throughput on one axis. Then Panel 2: a site at 58% gradability, flagged for lens cleaning. "The model isn't the intervention here. The operator is." |
| 6:15 | **The numbers.** Sensitivity and specificity with bootstrap CIs at a frozen threshold. The four-row ablation. Messidor-2 as external validation.                                                                    |
| 6:45 | **What this doesn't do yet.** Four honest bullets. Stop talking.                                                                                                                                                    |

### The closing pitch

"We built a quality-gated, two-stream pipeline that reaches 92% sensitivity and 87% specificity for referable DR on external validation — and our explanations land inside annotated lesions 84% of the time, so an ophthalmologist confirms the referral in 22 seconds. Our SimEvents model shows that lets two remote graders cover a district of 100,000 patients."

Four numbers, all defensible, all measured. That is what beats a prettier heatmap.

### What this doesn't do yet

- Neovascularisation is a vessel-morphology proxy, not a detector.
- No prospective clinical validation.
- Single-field imaging only.
- In the prototype, offline capture queues for grading on sync; fully on-device grading is the Jetson edge path.
- Prototype object storage is tamper-evident, not tamper-proof; write-once Object Lock arrives with the production tier.
- No CDSCO pathway completed.

Every judge has sat through teams claiming clinical readiness. The one team that states its limits precisely reads as the only one that understands the domain.

---

## 17. Risk register

| Risk                                                            | Mitigation                                                                                                                                                                             |
|-----------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Patient-level leakage in APTOS splits                           | Split by patient before anything else; commit `splits.json` in hour one                                                                                                                |
| Grad-CAM too coarse to be clinically useful                     | Intermediate feature layer; ship the Evidence Strip as the primary explanation and Grad-CAM as context                                                                                 |
| Threshold chosen on the test set                                | Pre-specify on validation, freeze, report bootstrap CIs at that fixed point — and say so on the slide                                                                                  |
| No public quality-labelled data                                 | Synthesise degradations for training; validate against DeepDRiD's real quality labels                                                                                                  |
| NV detector overclaimed                                         | Label it a proxy in the UI, with a distinct violet hue, and in the pitch                                                                                                               |
| Demo network failure                                            | Everything on localhost; pre-warmed inference cache as fallback; A3 poster                                                                                                             |
| MATLAB engine cold start                                        | Start the engine at FastAPI boot, keep it warm, warm up on one image before the demo                                                                                                   |
| Projector colour shift kills lesion semantics                   | Check on the actual projector; if greens shift, raise the routine-state luminance and re-export tokens                                                                                 |
| Toolbox coverage looks thin to MathWorks judges                 | Visibly touch Image Processing, Computer Vision, Deep Learning, Statistics & ML, Medical Imaging, and Simulink/SimEvents; name them on the architecture slide                          |
| Platform layer eats the algorithm budget                        | `docker-compose up` for all five services, seeded, in hour zero. If it is not running by hour two, ship with a stub auth guard and a JSON audit file — the algorithm is what is graded |
| Empty admin dashboard at demo time                              | Seed 30 days of synthetic programme data across four facilities beforehand. A Grafana panel with three data points is worse than no panel                                              |
| Judge asks whether this is a medical device                     | Answer immediately: yes, MDSW under MDR 2017, planning Class C via Form MD-15, and FDA or CE clearance would not substitute for CDSCO licensing. Keep it on a backup slide             |
| GPU out of memory on 6 GB VRAM                                  | Halve the mini-batch, then drop to 384 px; `reset(gpuDevice)` before each run; checkpoint every epoch                                                                                  |
| Two MATLAB processes exhaust 16 GB RAM                          | Shared engine: `shareEngine` in the desktop, `connect_matlab` from Python. Never train while the Docker stack runs                                                                     |
| Laptop GPU throttles mid-training                               | AC power, Best performance mode, checkpoints so a thermal stop costs one epoch                                                                                                         |
| npm 12 leaves native packages unbuilt                           | Approve the listed package and reinstall; install the Railway CLI via Scoop                                                                                                            |
| Space in the Windows user path breaks tooling                   | Everything under `C:\dev\netrasetu` from the first command                                                                                                                             |
| Phone camera and offline mode fail over plain HTTP              | Chrome insecure-origin flag on the demo phone for Tier 0; Tier 1 uses Vercel's real HTTPS                                                                                              |
| Object-storage dependency abandoned upstream                    | Already happened to MinIO. Garage for the prototype, managed S3 with Object Lock for production, and pinned image tags throughout                                                      |
| A cached result reaches the wrong patient                       | Cache stores computation only; every request creates its own study; identical pixels on a different patient are flagged for review, never auto-served. Covered by a dedicated test     |
| Training silently mixes old and new preprocessing               | Preprocessing version in the cache folder name; changing `nx_enhance` means a new folder                                                                                               |
| Supabase project paused when a judge opens the link             | Daily keep-alive job; restore and load the site yourself before sharing the link                                                                                                       |
| Gateway connects as table owner and bypasses row-level security | Dedicated `gateway` and `worker` roles without BYPASSRLS; `FORCE ROW LEVEL SECURITY` on clinical tables                                                                                |
| Supabase project created outside India                          | Pick "South Asia (Mumbai)" explicitly at creation — region cannot be changed afterwards                                                                                                |
| Stale model served after retraining                             | Model version is part of every cache key; restart the engine on deploy so the persistent model reloads                                                                                 |

### Turning this into a portfolio artifact

1.  **A public repo with `docs/VALIDATION.md`.** Metrics with confidence intervals, a documented splits protocol, the ablation table, external validation. This one file is a stronger hiring signal than the entire application, because almost nobody writes it.
2.  **A MATLAB File Exchange submission.** Package the quality-assessment module or the Grad-CAM-versus-lesion-mask localisation metric as a documented standalone function with a live script demo. MathWorks engineers read File Exchange.
3.  **A four-minute recorded walkthrough of the engineering**, not the pitch. Why ordinal regression beats 5-class softmax for QWK, why Grad-CAM came from an intermediate layer, why the threshold was frozen on validation.

---

## 18. Setup roadmap

Six phases, four gates. Do not start a phase until the gate before it passes — every gate here exists because skipping it produces a failure that surfaces hours later and looks like a different problem.

```mermaid
flowchart LR
  P1["1 · Prepare machine<br/>no-space project path · NVIDIA driver<br/>WSL2 + Docker · .wslconfig · AC power"] --> G1{"GPU ok?<br/>validateGPU"}
  G1 -- fail --> P1
  G1 -- pass --> P2["2 · Install<br/>MATLAB + 8 add-ons · pretrained add-on<br/>Python venv + engine · Vite app · datasets"] --> G2{"Stack up?<br/>engine + compose"}
  G2 -- fail --> P2
  G2 -- pass --> P3["3 · Configure<br/>.env · compose · Garage layout<br/>Keycloak realm · nx_config + threshold.json"] --> P4["4 · Integrate<br/>stub contract · FastAPI ↔ engine<br/>OpenAPI → TS types · tiles · pull worker"] --> G3{"Contract green?<br/>hour-one check"}
  G3 -- fail --> P4
  G3 -- pass --> P5["5 · Test<br/>MATLAB unit + golden · pytest<br/>Playwright offline · Locust · validation gate"] --> G4{"All gates pass?"}
  G4 -- fail --> P5
  G4 -- pass --> P6["6 · Deploy<br/>freeze checkpoint · tag · smoke test<br/>rehearse fallback"]
  P6 --> T0(["Tier 0 — Classroom<br/>the demo"])
  P6 --> T1(["Tier 1 — Vercel · Railway · Supabase · laptop<br/>a link for judges and recruiters"])
  P6 -.-> T2(["Tier 2 — MPS on Kubernetes<br/>the pitch, not the build"])
  classDef gate fill:#FBF3E6,stroke:#B26B00;
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class G1,G2,G3,G4 gate;
  class P6,T0 key;
```

*Figure 7 — Setup-to-deployment flowchart. Read row one left to right, row two right to left. Amber dashed paths are failure loops; each returns to the phase where the fix actually lives. Tier 0 is teal because it is the one you must ship; Tier 2 is dashed because you describe it, you do not build it.*

---

## 19. Your machine — compatibility verdict

Every component clears its requirement. Memory and VRAM are tight, not insufficient — they need a plan, not an upgrade.

| Component | Yours                                | Requirement                                                                                      | Verdict                            |
|-----------|--------------------------------------|--------------------------------------------------------------------------------------------------|------------------------------------|
| OS        | Windows 11 Home 26H2, build 26300    | MATLAB R2026a: Windows 11 23H2 or higher                                                         | ✅ **pass**                        |
| CPU       | i7-11800H, 8 cores / 16 threads      | Recommended: four logical cores with AVX2 — and a future MATLAB release will make AVX2 mandatory | ✅ **pass** Tiger Lake has AVX2    |
| RAM       | 16 GB (15.7 usable)                  | Minimum 8 GB, recommended 16 GB                                                                  | ⚠️ **tight** see memory plan       |
| GPU       | RTX 3060 Laptop, 6 GB, Ampere cc 8.6 | MATLAB supports NVIDIA compute capability 5.0 to 9.x                                             | ✅ **pass** VRAM is the constraint |
| Storage   | ~303 GB free                         | MATLAB with these toolboxes ~15–20 GB; datasets ~25 GB; containers ~6 GB                         | ✅ **pass**                        |
| Python    | 3.12.0                               | R2026a engine supports 3.9, 3.10, 3.11, 3.12 and 3.13                                            | ✅ **pass** but upgrade the patch  |
| npm       | 12.0.1                               | Vite 7 requires Node 20.19+ or 22.12+                                                            | ⚠️ **check** run `node --version`  |
| Docker    | not yet installed                    | Docker Desktop on Windows Home uses the WSL2 backend                                             | ⚠️ **install**                     |
| User path | `C:\Users\Gurjas Gandhi`             | —                                                                                                | ❌ **move** the space breaks tools |

### Four things specific to this machine

**The space in your user path will bite you.** Compiler toolchains, some CUDA builds, Docker bind mounts and shell scripts mishandle `C:\Users\Gurjas Gandhi`. Put the entire project at `C:\dev\netrasetu` and keep datasets under `C:\dev\netrasetu\data`. This costs nothing now and an afternoon later.

**Python 3.12.0 is the first 3.12 release.** It is supported, but install the latest 3.12 patch release for bug and security fixes. Same minor version, so engine compatibility is unchanged. Do not jump to 3.14 — it is outside R2026a's qualified range.

**npm 12 blocks dependency install scripts by default.** Packages that build or download a native binary during install can be left unbuilt. If `npm run dev` fails with an esbuild or missing-binary error, that is the cause: approve the listed package using the instruction npm prints at the end of `npm install`, then reinstall. For the same reason, install the Railway CLI through Scoop rather than npm (Section 21).

**This is a hybrid-graphics laptop.** The Intel UHD drives the display; the RTX 3060 does compute. MATLAB's GPU functions find the NVIDIA device regardless. What matters is power: laptop GPUs throttle heavily on battery. Train plugged in, with Windows power mode set to Best performance.

### Memory plan — three operating modes

16 GB holds the whole stack, but not the whole stack *and* a training run. Choose one mode at a time. Figures are estimates; confirm in Task Manager on your own machine.

| Mode        | Running                                                                              | Stopped                             | Approx. RAM   |
|-------------|--------------------------------------------------------------------------------------|-------------------------------------|---------------|
| **Train**   | MATLAB desktop running `trainnet`, one terminal                                      | Docker, FastAPI, Vite, browser tabs | MATLAB 6–8 GB |
| **Develop** | MATLAB desktop as a shared engine, FastAPI, Vite, Docker capped at 4 GB, one browser | —                                   | 13–14 GB      |
| **Demo**    | As Develop, MATLAB minimised                                                         | IDE, chat apps, extra tabs          | ~12 GB        |

> **The single biggest saving: one MATLAB process, not two.** `matlab.engine.start_matlab()` launches a *second* MATLAB alongside your desktop session — roughly 2–3 GB you do not have. Instead, run `matlab.engine.shareEngine("netrasetu")` in your open MATLAB and have FastAPI call `connect_matlab("netrasetu")`. One process, and you can watch the pipeline execute in the desktop while the demo runs.

---

## 20. Compute — is a Colab T4 needed?

No. And using it would actively weaken your submission.

### Three reasons

**Colab does not run your stack.** Colab is a Python notebook service. Training there means rewriting the model in PyTorch or TensorFlow, which moves your core algorithm out of MATLAB on a MathWorks problem statement. Section 4 explains why that is the fastest available way to lose.

**Your GPU is not the bottleneck.** The RTX 3060 Laptop offers FP32 throughput in the same class as a T4. The T4's real advantage is memory — 16 GB against your 6 GB — and that is solved with batch size and resolution, not with a different machine.

**The datasets are small.** APTOS is 3,662 images. IDRiD's segmentation set is 81. DRIVE is 40. These train on a laptop GPU in hours, not days. Colab's free-tier session limits would interrupt runs that your own machine completes uninterrupted.

### Fitting into 6 GB of VRAM

| Model                            | Input           | Starting batch | If out of memory |
|----------------------------------|-----------------|----------------|------------------|
| EfficientNet-b0 grading backbone | 512 × 512       | 16             | 8, then 384 px   |
| ResNet-50 (ablation only)        | 512 × 512       | 8              | 4, then 384 px   |
| Vessel U-Net                     | 48 × 48 patches | 64             | 32               |
| Microaneurysm candidate CNN      | 32 × 32 patches | 128            | 64               |

These are starting points to tune, not guarantees. Two habits prevent most failures: call `reset(gpuDevice)` before every run, and set a `CheckpointPath` so a thermal shutdown or out-of-memory error at epoch 22 costs you one epoch, not twenty-two.

``` matlab
reset(gpuDevice);
opts = trainingOptions("adam", ...
    MiniBatchSize        = 16, ...        % halve on "out of memory on device"
    MaxEpochs            = 30, ...
    InitialLearnRate     = 1e-4, ...
    ExecutionEnvironment = "gpu", ...
    Shuffle              = "every-epoch", ...
    ValidationData       = dsVal, ...
    ValidationFrequency  = 50, ...
    CheckpointPath       = "checkpoints", ...
    Plots                = "training-progress", ...
    Verbose              = false);
net = trainnet(dsTrain, net, "mse", opts);   % ordinal regression head
```

> **When you would genuinely need more compute.** Only if you scale segmentation training to FGADR or DDR at full resolution. The MATLAB-native answer then is MATLAB on a cloud GPU VM — not Colab — so the code does not change. For this hackathon, you will not reach that point.

---

## 21. Installation

In this order. Each step's verification is the gate for the next.

### 1 · Machine preparation

``` powershell
# PowerShell as Administrator (all blocks in this section are PowerShell)
mkdir C:\dev\netrasetu
wsl --install            # skip if WSL is already present
wsl --update
nvidia-smi               # must list the RTX 3060 and a driver version
```

Install the latest NVIDIA driver for the RTX 3060 from NVIDIA's site before anything else. Then install Docker Desktop and leave the WSL2 backend selected (it is the only option on Windows Home). You do *not* need the CUDA Toolkit for training — the driver is sufficient. The CUDA Toolkit is only needed for the GPU Coder edge path, which is roadmap, not build.

### 2 · MATLAB R2026a and toolboxes

Sign in to the MathWorks installer with your campus licence and select exactly these:

| Product                                           | Why                                                                                                          |
|---------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| MATLAB, Simulink                                  | Core                                                                                                         |
| Image Processing Toolbox, Computer Vision Toolbox | Quality gate, enhancement, lesion detection                                                                  |
| Deep Learning Toolbox                             | Backbone, U-Net, `gradCAM`                                                                                   |
| **Parallel Computing Toolbox**                    | Required for GPU training. The one most teams forget, then discover when `ExecutionEnvironment="gpu"` errors |
| Statistics and Machine Learning Toolbox           | `fitcensemble` fusion, bootstrap CIs                                                                         |
| Medical Imaging Toolbox                           | Medical Image Labeler                                                                                        |
| SimEvents                                         | Capacity model                                                                                               |
| MATLAB Report Generator                           | Clinical PDF report                                                                                          |

Then verify the GPU from the MATLAB command window — this is gate G1:

``` matlab
validateGPU                                  % full diagnostic, since R2024b
g = gpuDevice;
fprintf("%s  cc %s  %.1f GB free\n", g.Name, g.ComputeCapability, g.AvailableMemory/2^30);

net = imagePretrainedNetwork("efficientnetb0");   % prompts for the add-on if missing
```

### 3 · Python environment

``` powershell
cd C:\dev\netrasetu
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
# if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

python -m pip install --upgrade pip
pip install matlabengine `
            fastapi "uvicorn[standard]" pydantic python-multipart `
            "pyjwt[crypto]" "psycopg[binary]" boto3 "pyvips[binary]" `
            prometheus-client kaggle pytest httpx locust

python -c "import matlab.engine; print('engine ok')"
```

The engine package must match your MATLAB release exactly: each version works only with the release it was built for. On a fresh install the latest package matches the latest MATLAB, so install it unpinned, then record the exact version with `pip show matlabengine` and pin that in `requirements.txt` so every teammate gets the same one. If anyone stays on an older release, they need that release's engine version from the PyPI release history.

### 4 · Front end

``` powershell
node --version          # needs 20.19+ or 22.12+
cd C:\dev\netrasetu
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install openseadragon dexie i18next react-i18next recharts lucide-react `
            @fontsource/ibm-plex-sans @fontsource/ibm-plex-sans-devanagari @fontsource/ibm-plex-mono
npm install -D vite-plugin-pwa tailwindcss @tailwindcss/vite vitest `
               @playwright/test @axe-core/playwright openapi-typescript
npx playwright install chromium
npm run dev             # if esbuild fails here, see the npm 12 note in Section 19
```

`vite-plugin-pwa` is the single pick for wiring Workbox into Vite — it generates the service worker and manifest from config instead of hand-written files.

### 5 · Datasets

``` powershell
# place kaggle.json in %USERPROFILE%\.kaggle\ and accept the competition rules on Kaggle first
kaggle competitions download -c aptos2019-blindness-detection -p data\aptos
# IDRiD — IEEE DataPort (free account)      → data\idrid
# DRIVE — grand-challenge.org (registration) → data\drive
# Messidor-2 — ADCIS request form            → data\messidor2   (never opened until test day)
```

### 6 · Showcase CLIs — Tier 1 only

``` powershell
npm install -g vercel
# Railway: install via Scoop to avoid npm 12's install-script blocking
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression   # run as a normal user, not Administrator
scoop install railway
vercel --version
railway --version
```

Skip this step entirely if you are only building Tier 0. Neither CLI is needed for the classroom demo.

---

## 22. Configuration

One `.env` as the single source of truth. Everything else reads from it, and it is never committed.

### WSL2 memory cap

Without this, WSL2 can take up to half your RAM and Docker will starve MATLAB. Create `%USERPROFILE%\.wslconfig`, then run `wsl --shutdown` to apply.

``` ini
[wsl2]
memory=4GB
processors=4
swap=2GB
```

### .env — repository root

``` bash
# ── generate secrets with:  python -c "import secrets; print(secrets.token_hex(32))"

# identity
KEYCLOAK_TAG=latest                 # pin to the exact tag after first pull
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=replace-me
OIDC_ISSUER=http://localhost:8080/realms/netrasetu
OIDC_AUDIENCE=netrasetu-gateway

# database
POSTGRES_USER=netrasetu
POSTGRES_PASSWORD=replace-me
POSTGRES_DB=netrasetu
DATABASE_URL=postgresql://netrasetu:replace-me@localhost:5432/netrasetu

# object storage — Garage
S3_ENDPOINT=http://localhost:3900
S3_REGION=garage
S3_BUCKET=netrasetu
S3_ACCESS_KEY=                      # filled from `garage key create`
S3_SECRET_KEY=

# observability
PROMETHEUS_TAG=latest
GRAFANA_TAG=latest

# gateway
GATEWAY_MODE=inprocess              # inprocess (Tier 0) | queue (Tier 1)
MATLAB_SHARED_ENGINE=netrasetu
NX_ROOT=C:/dev/netrasetu/matlab
CORS_ORIGINS=http://localhost:5173,http://192.168.137.1:5173
NX_CACHED_MODE=false                # true = serve from inference cache only, never call MATLAB

# caching (Section 26)
CACHE_ENABLED=true
IDEMPOTENCY_TTL_DAYS=7
PRESIGN_TTL_SECONDS=3600            # reuse each URL for its lifetime so browser caching works
JWKS_CACHE_SECONDS=3600
```

Commit a `.env.example` with every key and no values. Then `git check-ignore .env` should print `.env` — if it prints nothing, stop and fix `.gitignore` before your first commit.

### docker-compose.yml

``` yaml
name: netrasetu
services:
  postgres:
    image: postgres:17
    env_file: .env
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./platform/migrations:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 5s
      retries: 10
    mem_limit: 512m

  keycloak:
    image: quay.io/keycloak/keycloak:${KEYCLOAK_TAG}
    command: ["start-dev", "--import-realm"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: ${KEYCLOAK_ADMIN}
      KC_BOOTSTRAP_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    ports: ["8080:8080"]
    volumes: ["./platform/keycloak:/opt/keycloak/data/import:ro"]
    mem_limit: 1g

  garage:
    image: dxflrs/garage:v2.3.0
    ports: ["3900:3900", "3903:3903"]
    volumes:
      - ./platform/garage/garage.toml:/etc/garage.toml:ro
      - garage-meta:/var/lib/garage/meta
      - garage-data:/var/lib/garage/data
    mem_limit: 256m

  prometheus:
    image: prom/prometheus:${PROMETHEUS_TAG}
    volumes: ["./platform/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
    ports: ["9090:9090"]
    extra_hosts: ["host.docker.internal:host-gateway"]
    mem_limit: 256m

  grafana:
    image: grafana/grafana-oss:${GRAFANA_TAG}
    ports: ["3000:3000"]
    volumes:
      - ./platform/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./platform/grafana/dashboards:/var/lib/grafana/dashboards:ro
    mem_limit: 256m

volumes: { pgdata: {}, garage-meta: {}, garage-data: {} }
```

The memory limits sum to about 2.3 GB, inside the 4 GB WSL cap with headroom. Once all five images pull successfully, run `docker compose images` and replace every `latest` in `.env` with the exact tag shown. Unpinned images are how a working demo breaks the night before.

### platform/garage/garage.toml

Garage reads secrets from this file directly, so commit only `garage.toml.example` and gitignore the real one.

``` toml
metadata_dir       = "/var/lib/garage/meta"
data_dir           = "/var/lib/garage/data"
db_engine          = "sqlite"
replication_factor = 1

rpc_bind_addr   = "[::]:3901"
rpc_public_addr = "127.0.0.1:3901"
rpc_secret      = "PASTE_64_HEX_CHARS"

[s3_api]
s3_region     = "garage"
api_bind_addr = "[::]:3900"
root_domain   = ".s3.garage.localhost"

[admin]
api_bind_addr = "[::]:3903"
admin_token   = "PASTE_TOKEN"
metrics_token = "PASTE_TOKEN"
```

Initialise the single-node layout once. The Garage image ships without a shell, so every command goes through the binary directly:

``` powershell
docker compose up -d
docker compose exec garage /garage status                 # copy the node ID
docker compose exec garage /garage layout assign -z dc1 -c 20G <NODE_ID>
docker compose exec garage /garage layout apply --version 1
docker compose exec garage /garage bucket create netrasetu
docker compose exec garage /garage key create netrasetu-app   # → S3_ACCESS_KEY / S3_SECRET_KEY
docker compose exec garage /garage bucket allow --read --write --owner netrasetu --key netrasetu-app
```

### platform/prometheus/prometheus.yml

``` yaml
global: { scrape_interval: 15s }
scrape_configs:
  - job_name: gateway
    metrics_path: /metrics
    static_configs: [{ targets: ["host.docker.internal:8000"] }]
```

An honest note on where metrics come from. In production, MPS emits custom Prometheus metrics straight from MATLAB code. In the prototype there is no MPS, so the gateway translates each MATLAB result into counters — `netrasetu_quality_reject_total{reason=…}` is incremented in Python from the `failureMode` field MATLAB returns. Same metric names, so Grafana dashboards carry over unchanged when you move to Tier 2.

### Keycloak realm

Create the realm once in the admin console at `localhost:8080`: realm `netrasetu`; roles `screener`, `grader`, `admin`; client `netrasetu-web` as a public client with PKCE; client `netrasetu-gateway` as the token audience; OTP as a required action for grader and admin. Then use Realm settings → Action → Partial export and save it as `platform/keycloak/realm-export.json`. Partial export masks client secrets, so the file is safe to commit, and `--import-realm` recreates the realm on any teammate's machine.

### MATLAB — nx_config.m

``` matlab
function cfg = nx_config()
%NX_CONFIG  Single source of pipeline configuration. Read once, then cached.
    persistent c
    if isempty(c)
        root = fileparts(fileparts(mfilename("fullpath")));
        t = jsondecode(fileread(fullfile(root, "config", "threshold.json")));
        c.threshold     = t.pReferable;    % written by eval/ — never edited by hand
        c.thresholdHash = t.sha256;        % CI checks this against validation output
        c.inputSize     = [512 512];
        c.modelFile     = fullfile(root, "models", "netrasetu_v1.mat");
        c.modelVer      = "netrasetu_v1";   % part of every cache key — bump on retrain
        c.maxRetakes    = 3;
        c.dupWindowDays = 30;
        c.useGPU        = canUseGPU();
    end
    cfg = c;
end
```

`threshold.json` is written by the validation script, never by a person. It records the operating point, the split it was chosen on, and a hash. That file is your evidence that the threshold was frozen on validation rather than tuned on test.

### web/vercel.json — Tier 1 only

``` json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    { "source": "/sw.js",
      "headers": [{ "key": "Cache-Control", "value": "no-cache" }] },
    { "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000" },
        { "key": "X-Content-Type-Options",    "value": "nosniff" },
        { "key": "Referrer-Policy",           "value": "no-referrer" },
        { "key": "Permissions-Policy",        "value": "camera=(self), microphone=()" }
      ] }
  ]
}
```

Two of these headers are product decisions, not boilerplate. `Referrer-Policy: no-referrer` stops a patient's single-use token from leaking to any third-party site via the Referer header. `no-cache` on the service worker means a fixed bug reaches field devices on next load instead of being pinned in cache for days.

---

## 23. Integration

One rule governs everything here: MATLAB returns JSON text, never a struct.

### The contract, refined

The MATLAB Engine for Python converts MATLAB structs into Python dictionaries and numeric arrays into its own array type. Nested structs, empty fields and string arrays convert in ways that differ subtly from what you expect, and every one of those differences becomes a front-end bug. So wrap the frozen entry point once:

``` matlab
function txt = netrasetu_analyze_json(imgPath, outDir)
%NETRASETU_ANALYZE_JSON  Engine-facing wrapper. Returns JSON text only.
    out = netrasetu_analyze(imgPath, outDir);
    txt = jsonencode(out, PrettyPrint=false);
end
```

Python calls `json.loads()` on the result. MATLAB owns serialisation, so there is exactly one place where types are decided.

### Pattern A — in-process, Tier 0

``` python
# service/main.py  (essential parts)
import json, os, threading, tempfile
from contextlib import asynccontextmanager
import matlab.engine
from fastapi import FastAPI, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app
from .auth import require_role

REJECTS = Counter("netrasetu_quality_reject_total", "Quality rejections", ["reason"])
GRADES  = Counter("netrasetu_grade_total", "Grades issued", ["grade", "decision"])
LATENCY = Histogram("netrasetu_analyze_seconds", "MATLAB pipeline time")

eng, lock = None, threading.Lock()      # one engine executes one call at a time

@asynccontextmanager
async def lifespan(app):
    global eng
    name = os.getenv("MATLAB_SHARED_ENGINE")
    eng = matlab.engine.connect_matlab(name) if name else matlab.engine.start_matlab("-nodesktop")
    eng.addpath(eng.genpath(os.environ["NX_ROOT"]), nargout=0)
    eng.nx_warmup(nargout=0)            # first call pays model load — not the judge
    yield
    if not name:
        eng.quit()

app = FastAPI(title="NetraSetu gateway", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
app.mount("/metrics", make_asgi_app())

@app.post("/analyze")
def analyze(file: UploadFile, user=Depends(require_role("screener"))):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "in.jpg")
        with open(path, "wb") as f:
            f.write(file.file.read())
        with lock, LATENCY.time():
            out = json.loads(eng.netrasetu_analyze_json(path, d, nargout=1))
    if out["decision"] == "RETAKE":
        REJECTS.labels(out["quality"]["failureMode"]).inc()
    else:
        GRADES.labels(str(out["grade"]), out["decision"]).inc()
    return out
```

Note `def`, not `async def`. FastAPI runs sync endpoints in a thread pool, so a ten-second MATLAB call does not freeze every other request. The lock serialises calls into the single engine, which is exactly the single-server behaviour your SimEvents model assumes.

In the build, the endpoint does not call the engine directly. It calls `analyze_cached` from Section 26, which handles retries, the cross-patient check and the inference cache before MATLAB is ever reached.

### Pattern B — pull worker, Tier 1

When the gateway is in the cloud and MATLAB is on your laptop, the obvious design is a tunnel from the internet into your laptop. Don't. Invert it: the laptop *pulls* work over an outbound connection. No open port, no tunnel, and when your laptop sleeps, jobs wait in the queue instead of failing.

``` python
# service/worker.py
import json, os, tempfile, time, psycopg, boto3
from botocore.config import Config
import matlab.engine

CLAIM = """
UPDATE job SET status = 'running', claimed_at = now(), worker = %(w)s
WHERE id = (SELECT id FROM job WHERE status = 'queued'
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
RETURNING id, object_key;
"""
s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"],
                  config=Config(s3={"addressing_style": "path"}))
eng = matlab.engine.connect_matlab(os.environ["MATLAB_SHARED_ENGINE"])

with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as db:
    while True:
        row = db.execute(CLAIM, {"w": os.environ["WORKER_ID"]}).fetchone()
        if not row:
            time.sleep(2); continue
        job_id, key = row
        try:
            with tempfile.TemporaryDirectory() as d:
                src = os.path.join(d, "in.jpg")
                s3.download_file(os.environ["S3_BUCKET"], key, src)
                out = json.loads(eng.netrasetu_analyze_json(src, d, nargout=1))
                # upload evidence crops, tiles and report from d, then:
                db.execute("UPDATE job SET status='done', result=%s WHERE id=%s",
                           (json.dumps(out), job_id))
        except Exception as e:
            db.execute("UPDATE job SET status='failed', error=%s WHERE id=%s",
                       (str(e)[:500], job_id))
```

`FOR UPDATE SKIP LOCKED` makes the claim atomic, so two teammates can each run a worker and never grade the same image twice. Add a reaper that resets jobs stuck in `running` for more than ten minutes. Path-style addressing is set explicitly because virtual-host bucket addressing needs DNS you will not have configured.

Look at what this pattern is: a node that works offline, syncs results not images, and reconnects when it can. It is the edge architecture from Section 4, running on your laptop. Say so in the pitch.

### Shared types — contract drift becomes a compile error

``` powershell
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
```

FastAPI publishes an OpenAPI document automatically. Generating TypeScript types from it means that when a MATLAB field is renamed and the Pydantic model updated, the front end fails to compile rather than failing in front of a judge. Regenerate on every contract change.

### Deep-zoom tiles

Generate tiles with `pyvips` — `image.dzsave()` writes the Deep Zoom format OpenSeadragon reads natively. The console then requests tiles from the object store using presigned URLs, so 25 MB fundus images never pass through FastAPI.

### Integration checkpoints

| Hour | Checkpoint                                                              | Proves                                                     |
|------|-------------------------------------------------------------------------|------------------------------------------------------------|
| 1    | Stubbed MATLAB returns canned JSON through FastAPI into all four routes | Every interface exists. Integration is never a cliff later |
| 4    | Real quality gate; retake guidance appears on the phone                 | MATLAB → phone round trip                                  |
| 7    | Real grading, evidence crops, tiles in OpenSeadragon                    | Full pipeline end to end                                   |
| 8    | Reject counters visible in Grafana after five test uploads              | Observability is wired, not mocked                         |

---

## 24. Testing

Nine layers. Each answers a different question, and the clinical validation gate outranks all the others.

| Layer                   | Tool                        | Proves                                                                                                                                     | Runs         |
|-------------------------|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| MATLAB unit             | `matlab.unittest`           | Quality gate rejects known degradations; contract is JSON-safe                                                                             | Laptop, CI   |
| Golden regression       | `matlab.unittest`           | The six demo images still produce their frozen outputs                                                                                     | Laptop       |
| **Clinical validation** | `eval/run_validation.m`     | Sensitivity, specificity with CIs, QWK, LLP, ECE at the frozen threshold                                                                   | Laptop (GPU) |
| Gateway                 | pytest + FastAPI TestClient | Role boundaries, schema rejection, single-use tokens, audit-chain integrity                                                                | Laptop, CI   |
| Front-end unit          | Vitest                      | Posterior band, Evidence Strip, every i18n key present in all three languages                                                              | Laptop, CI   |
| End to end              | Playwright + axe            | Offline capture then sync; keyboard review flow; accessibility                                                                             | Laptop, CI   |
| Load                    | Locust                      | Measured service time — which becomes a SimEvents parameter                                                                                | Laptop       |
| Security                | OWASP ZAP baseline          | Headers, cookies, common injection — a rehearsal for the CERT-In assessment                                                                | Laptop       |
| Caching                 | pytest                      | Retries are idempotent; hits still create a per-patient study; same pixels on another patient are flagged; clinical routes send `no-store` | Laptop, CI   |

### MATLAB — the quality gate must reject what it claims to reject

``` matlab
classdef tQualityGate < matlab.unittest.TestCase
    properties (TestParameter)
        sigma = {4, 8, 12};
    end
    methods (Test)
        function rejectsDefocus(tc, sigma)
            I = imread("fixtures/grade0_clean.jpg");
            p = fullfile(tempdir, "blur.jpg");
            imwrite(imgaussfilt(I, sigma), p);
            q = nx_quality(p);
            tc.verifyEqual(q.verdict, "reject");
            tc.verifyEqual(q.failureMode, "defocus");
        end
        function contractIsJsonSafe(tc)
            txt = netrasetu_analyze_json("fixtures/grade2_haem.jpg", tempdir);
            out = jsondecode(txt);
            tc.verifyTrue(all(isfield(out, ["studyId" "decision" "quality"])));
        end
    end
end
```

``` matlab
results = runtests("tests");
assertSuccess(results);
```

The defocus test reuses the synthetic-degradation idea from Module 1: the same transforms you used to generate training data become the test fixtures. If the gate stops rejecting σ = 8 blur, you know before a judge does.

### Gateway — the security boundaries are tests, not intentions

``` python
def test_screener_cannot_read_other_facility(client, token_for):
    t = token_for(role="screener", facility="ambegaon")
    r = client.get("/study/khed-0001", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 404     # not 403: never confirm the record exists

def test_patient_link_is_single_use(client, patient_link):
    assert client.get(patient_link).status_code == 200
    assert client.get(patient_link).status_code == 410

def test_audit_chain_detects_tampering(db, audit_rows):
    db.execute("UPDATE audit SET action = 'edited' WHERE seq = 3")
    assert verify_chain(db) == 3    # first broken link is reported
```

The 404 rather than 403 is deliberate. A 403 tells an attacker the Khed record exists; a 404 tells them nothing. The audit test is your proof that the hash chain is real — run it live if a judge asks how the audit trail resists tampering.

### End to end — the offline claim is tested, not asserted

``` typescript
test('capture survives a dead network and syncs later', async ({ page, context }) => {
  await page.goto('/field');
  await context.setOffline(true);
  await page.setInputFiles('input[type=file]', 'fixtures/grade2_haem.jpg');
  await expect(page.getByText('1 waiting to sync')).toBeVisible();
  await context.setOffline(false);
  await expect(page.getByText('0 waiting to sync')).toBeVisible({ timeout: 30_000 });
});
```

> **Be precise about what "offline" means in the prototype.** The field app captures and queues offline; grading happens when the queue syncs to the laptop. Fully on-device grading is the Jetson edge path. Say this exactly — Scenario A describes the product, and a judge who asks "does it grade with no network?" deserves the accurate answer. It is in the limitations list in Section 16 for that reason.

### Load — the test that feeds the simulation

``` python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class Screener(HttpUser):
    wait_time = between(1, 3)
    @task
    def analyze(self):
        with open("fixtures/grade2_haem.jpg", "rb") as f:
            self.client.post("/analyze", files={"file": f}, headers=AUTH)
```

``` powershell
locust -f tests/load/locustfile.py --headless -u 4 -r 1 -t 5m --csv results/load
```

Because the engine serialises calls, this measures single-server service time — p50 and p95 — which is precisely the Entity Server parameter in Figure 4. Your capacity model now runs on a measured number. This is the sentence that makes the Simulink module credible.

### Caching — the safety properties are tests

``` python
def test_retry_returns_same_study(client, screener, image):
    h = {"Idempotency-Key": str(uuid.uuid4()), **screener}
    a = client.post("/analyze", files={"file": image}, headers=h).json()
    b = client.post("/analyze", files={"file": image}, headers=h).json()
    assert a["studyId"] == b["studyId"]

def test_cache_hit_still_creates_new_study(client, screener, image, db):
    a = client.post("/analyze", files={"file": image}, headers=screener).json()
    b = client.post("/analyze", files={"file": image}, headers=screener).json()
    assert a["studyId"] != b["studyId"]
    assert audit_source(db, b["studyId"]) == "cache"

def test_same_pixels_other_patient_is_flagged(client, token_for, image):
    client.post("/analyze", files={"file": image}, headers=token_for(patient="P1"))
    r = client.post("/analyze", files={"file": image}, headers=token_for(patient="P2")).json()
    assert r["flag"] == "same_image_other_patient" and r.get("grade") is None

def test_clinical_routes_are_never_cached(client, screener, image):
    r = client.post("/analyze", files={"file": image}, headers=screener)
    assert r.headers["Cache-Control"] == "no-store"

def test_new_model_version_misses_cache(db, image, version):
    analyze_cached(db, image, "P1", None, fake_matlab, version)
    assert analyze_cached(db, image, "P1", None, fake_matlab,
                          {**version, "modelVer": "v2"})["source"] == "matlab"
```

The third test is the one to show a judge. It proves that a cache built for speed cannot hand one patient's result to another.

### Security rehearsal

``` powershell
docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t http://host.docker.internal:8000
```

### Continuous integration

``` yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  matlab:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: matlab-actions/setup-matlab@v2      # use the current major version
        with:
          release: R2026a
          products: Image_Processing_Toolbox Computer_Vision_Toolbox Deep_Learning_Toolbox Statistics_and_Machine_Learning_Toolbox
      - uses: matlab-actions/run-tests@v2
        with: { select-by-folder: matlab/tests }
  gateway:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r service/requirements-gateway.txt pytest httpx
      - run: pytest service/tests
      - run: python eval/check_threshold_hash.py   # threshold.json must match validation.json
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: cd web && npm ci && npx vitest run && npx playwright install --with-deps chromium && npx playwright test
```

MathWorks offers MATLAB on GitHub Actions for public repositories, which makes your repo's green badge a credible signal. Clinical validation stays on your laptop — it needs the GPU and the data — but CI enforces its integrity: `check_threshold_hash.py` fails the build if anyone edits `threshold.json` without regenerating validation results. That one check is your answer to "how do I know you didn't tune on test?"

---

## 25. Deployment

Three tiers. You ship Tier 0, you share Tier 1, you pitch Tier 2.

```mermaid
flowchart TB
  subgraph T0["Tier 0 — Classroom · fully offline · the demo"]
    PH["Phone on laptop hotspot<br/>192.168.137.1:5173"] --> V["Vite dev server :5173"] --> FA["FastAPI gateway :8000<br/>auth · schema · Prometheus counters"] --> ML["MATLAB — shared engine<br/>RTX 3060 · one process"]
    FA --> DK[("Docker · WSL2 · 4 GB cap<br/>Postgres 17 · Keycloak · Garage v2.3<br/>Prometheus · Grafana")]
  end
  subgraph T1["Tier 1 — Public showcase · public datasets only"]
    VC["Vercel — static PWA<br/>global CDN · real HTTPS"] --> RW["Railway — containers<br/>gateway (queue mode) · Keycloak · Grafana"]
    RW --> SB[("Supabase · ap-south-1 Mumbai<br/>Postgres: jobs · cache · studies<br/>Storage: S3 protocol")]
    WK["Your laptop — grading worker<br/>MATLAB + RTX 3060 · outbound only"] <-- "claim job · get image · write result" --> SB
  end
  subgraph T2["Tier 2 — Production · real patient data"]
    CHN["All channels<br/>PWA · console · patient · eSanjeevani"] --> AG["API gateway<br/>authN · consent · audit"] --> ING["Ingress / load balancer"] --> MPS["MATLAB Production Server pods"]
    MPS --> PL[("In-country ap-south-1<br/>managed Postgres · S3 Object Lock<br/>Keycloak · Prometheus + Grafana")]
    EJ["Edge: GPU Coder → Jetson Orin<br/>PHCs with no usable uplink"] -.-> PL
  end
  T0 ~~~ T1
  T1 ~~~ T2
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class ML,WK,MPS,AG key;
```

*Figure 8 — Deployment tiers. The same MATLAB code runs in all three. What changes is where the grader lives: in-process on the laptop, pulling work from a cloud queue, or in autoscaled pods. Tier 1's two-way teal arrows are outbound connections from the laptop — the inversion that removes the need for any tunnel. Tier 1's data sits in Supabase's Mumbai region, so even the showcase keeps images in-country.*

### Can Vercel, Railway and Supabase be used?

Yes — all three, for Tier 1 only, each for a narrow job. None of them can host the part of this system that matters most.

|             | Vercel                                                                                                                       | Railway                                                                                               | Supabase                                                                              |
|-------------|------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Verdict     | ✅ **use** front end only                                                                                                    | ✅ **use** containers only                                                                            | ✅ **use** data only                                                                  |
| Hosts       | The static PWA build, from a global CDN with real HTTPS — which also fixes the phone camera and service-worker problem below | Gateway in queue mode, Keycloak, Grafana                                                              | Postgres (job queue, inference cache, study records) and Storage for images and tiles |
| Cannot host | MATLAB. Short-lived serverless functions with a 300-second ceiling on Hobby                                                  | MATLAB. No documented GPU offering, and your campus licence normally only works on the campus network | MATLAB, or the Python gateway — its functions are not long-running Python processes   |
| Region      | Global CDN                                                                                                                   | US, EU and Singapore — no India region                                                                | **Mumbai, `ap-south-1`**, chosen at project creation                                  |
| Not used    | Functions                                                                                                                    | Postgres and Bucket — moved to Supabase                                                               | Auth, the browser-facing Data API, Edge Functions                                     |

**Why the data moved to Supabase.** Railway has no India region; Supabase has Mumbai. For a showcase holding only public datasets, either is legally acceptable — but putting the database and images in-country even when it is not yet required means your Tier 1 already follows the data-residency rule Tier 2 must obey. And because the code is written against the Postgres and S3 protocols rather than any vendor's SDK, the switch is configuration only: no code changes at all.

**Why Supabase Auth is not used.** Keycloak issues the same tokens to the gateway, MATLAB Production Server and MATLAB Web App Server across all three tiers. Adding a second identity system for one tier would break the claim that Tiers 0, 1 and 2 share one realm configuration.

### Tier 0 — classroom runbook

``` powershell
# start-demo.ps1 — run from C:\dev\netrasetu
docker compose up -d
docker compose ps                         # all five must show healthy or running

# In the open MATLAB command window, once:
#   matlab.engine.shareEngine("netrasetu")

.\.venv\Scripts\Activate.ps1
Start-Process powershell -ArgumentList '-NoExit','-Command',
  '.\.venv\Scripts\uvicorn.exe service.main:app --host 0.0.0.0 --port 8000'
Start-Process powershell -ArgumentList '-NoExit','-Command',
  'cd web; npm run dev -- --host'
```

Turn on Windows Mobile hotspot and join it from the demo phone. The laptop is normally reachable at `192.168.137.1` on that network. Allow Python and Node through Windows Firewall for private networks when prompted — a blocked firewall prompt is the most common reason a phone cannot reach a laptop.

> **The phone will not get camera access or offline mode over plain HTTP.** Browsers only enable the camera API and service workers in a secure context, and `http://192.168.137.1:5173` is not one. Without a fix, the live quality ring and the offline queue both silently fail on stage. On the one Android phone you will demo with, open `chrome://flags`, enable "Insecure origins treated as secure," add `http://192.168.137.1:5173`, and relaunch Chrome. This is a development setting on a device you control — never a deployment answer. Tier 1 does not need it, because Vercel serves real HTTPS.

### Tier 1 — showcase deployment

``` powershell
# Supabase — in the dashboard at https://supabase.com/dashboard
#   New project → Region: choose "South Asia (Mumbai)" explicitly.
#   Do NOT pick a general "APAC" region — it may place the project in Singapore,
#   and a project's region cannot be changed after creation.
#   Then: Storage → create bucket "netrasetu" (private) → S3 access keys → generate
python scripts\migrate.py          # needs ADMIN_DATABASE_URL, GATEWAY_DB_PASSWORD, WORKER_DB_PASSWORD

# Railway — from the repository root (no database here any more)
railway login
railway init                                  # project: netrasetu-showcase
railway up                                    # builds service/Dockerfile.gateway
railway variables --set "GATEWAY_MODE=queue" `
                  --set "CORS_ORIGINS=https://netrasetu.vercel.app" `
                  --set "DATABASE_URL=<Supabase session-pooler URL, gateway role>" `
                  --set "S3_ENDPOINT=<Supabase Storage S3 endpoint>"
railway domain                                # prints the public gateway URL
# add Keycloak and Grafana from the Railway dashboard templates

# Vercel — from web\
vercel login
vercel link
vercel env add VITE_API_BASE production       # paste the Railway gateway URL
vercel                                        # preview URL for teammates
vercel --prod                                 # production URL for the submission

# Laptop worker — reads .env.tier1
python -m service.worker
```

``` dockerfile
# service/Dockerfile.gateway — no MATLAB, deliberately
FROM python:3.12-slim
WORKDIR /app
COPY service/requirements-gateway.txt .
RUN pip install --no-cache-dir -r requirements-gateway.txt
COPY service/ ./service/
ENV GATEWAY_MODE=queue
CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

Three traps. `VITE_` variables are baked in at build time, so changing `VITE_API_BASE` needs a redeploy, not a restart. Add the Vercel domain to the Keycloak client's redirect URIs or login will fail with a redirect mismatch. And the `requirements-gateway.txt` must exclude `matlabengine`, which cannot install without MATLAB present.

### Supabase — five settings that decide whether it is safe

#### 1 · Connect through the session pooler

Supabase's direct connection string is IPv6-only; for IPv4 you use Supavisor session mode or a paid IPv4 add-on. Many Indian home and college networks lack working IPv6, and so may Railway's outbound network, so use the **session pooler (port 5432 on the pooler host)** for both the gateway and the laptop worker. Avoid transaction mode (port 6543): it does not support prepared statements, and psycopg starts preparing repeated queries automatically — the worker's polling query would begin failing after a few iterations, which is a confusing bug to meet on demo day.

``` bash
# .env.tier1 — never committed
DATABASE_URL=postgresql://worker.<project-ref>:<password>@<pooler-host>:5432/postgres
S3_ENDPOINT=https://<project-ref>.supabase.co/storage/v1/s3
S3_REGION=ap-south-1
S3_BUCKET=netrasetu
S3_ACCESS_KEY=                    # Storage → S3 access keys
S3_SECRET_KEY=
GATEWAY_MODE=queue
MATLAB_SHARED_ENGINE=netrasetu
WORKER_ID=laptop-gurjas
```

Copy the pooler host and the exact username format from the project's **Connect** panel rather than typing them; they encode the project reference and region.

#### 2 · Keep clinical tables out of the browser API

Supabase automatically exposes tables in the `public` schema through a REST API that anyone holding the project's public key can call, guarded only by row-level security. This system never uses that API — the browser talks only to your gateway. So create every table in a `clinical` schema that is not in the exposed-schemas list, and the API has nothing to serve.

#### 3 · Make row-level security actually bind

This corrects a gap in Section 10 that applies to local Postgres too. Row-level security does not constrain a table's owner, and the default `postgres` connection is an administrative role. A gateway connecting as `postgres` would silently bypass every facility policy — so the claim "a screener at Ambegaon cannot read Khed's rows even if the application is compromised" would be false. Give each service its own role, and force the policy:

``` sql
-- platform/migrations/040_roles.sql — runs on Tier 0 and Tier 1 alike
CREATE SCHEMA IF NOT EXISTS clinical;

CREATE ROLE gateway LOGIN NOBYPASSRLS;     -- passwords are set by migrate.py
CREATE ROLE worker  LOGIN NOBYPASSRLS;     -- from environment variables, never here

GRANT USAGE ON SCHEMA clinical TO gateway, worker;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical TO gateway;
GRANT SELECT, UPDATE ON clinical.job TO worker;              -- worker sees jobs and
GRANT SELECT, INSERT, UPDATE ON clinical.inference_cache TO worker;  -- the cache, nothing else

ALTER TABLE clinical.study ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.study FORCE  ROW LEVEL SECURITY;        -- binds even the owner
CREATE POLICY facility_isolation ON clinical.study
  USING (facility_id = current_setting('app.facility_id')::uuid);
```

``` python
# scripts/migrate.py — the same migrations for every tier
import os, pathlib, psycopg
from psycopg import sql

with psycopg.connect(os.environ["ADMIN_DATABASE_URL"], autocommit=True) as db:
    for f in sorted(pathlib.Path("platform/migrations").glob("*.sql")):
        db.execute(f.read_text())
        print("applied", f.name)
    for role in ("gateway", "worker"):
        db.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(role),
            sql.Literal(os.environ[f"{role.upper()}_DB_PASSWORD"])))
```

The admin connection string is used only by this script and is never given to a running service. The gateway runs `SET LOCAL app.facility_id = …` at the start of each transaction, taken from the verified token. The worker never touches patient rows at all: it reads a job, fetches pixels by object key, and writes a result. Separating the two roles is what makes the earlier security test meaningful rather than decorative.

#### 4 · The free tier pauses after a week

Free projects pause after 7 days of inactivity. Data survives a pause; a judge clicking your link to a paused project sees an error. Two habits cover it: restore the project from the dashboard and load the site yourself before sharing the link, and add a scheduled job that touches the database daily. Confirm on the dashboard that the project stays active — inactivity rules are Supabase's to define and have changed before.

``` yaml
# .github/workflows/keepalive.yml
name: keepalive
on: { schedule: [{ cron: "30 3 * * *" }], workflow_dispatch: {} }
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: psql "$DB" -c "select 1"
        env: { DB: "${{ secrets.SUPABASE_KEEPALIVE_URL }}" }
```

#### 5 · Budget the storage

The free tier includes 500 MB of database and 1 GB of file storage. Metadata, the job queue and the inference cache fit easily. Images and their deep-zoom tiles do not fit indefinitely: curate about thirty showcase images, upload them with their tiles, and check the Storage usage page before adding more. That limit is a reason to keep Tier 1 a curated showcase, which is what it should be anyway.

> **And for Tier 2?** Supabase on a paid plan in Mumbai is a legitimate candidate for the managed Postgres in production — it removes the pause and raises the limits to 8 GB of database and 100 GB of storage. Production still needs Object Lock for write-once raw images and a compliance review, so this spec keeps Tier 2's store generic and leaves that choice to procurement. Supabase is the right pick for the showcase; it is a possible pick for production.

### Tier 2 — production

Section 8 specifies it: MATLAB Production Server on Kubernetes, in an in-country region, with the gateway in front and managed Postgres and S3 Object Lock behind. You describe this tier; you do not build it. Its credibility comes from the fact that Tiers 0 and 1 already run the same CTF contract, the same metric names and the same realm configuration.

### Go-live checklist — the night before

| Check                                                         | How                                                                                   |
|---------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Model checkpoint frozen and tagged                            | `git tag demo-v1`; no training after this                                             |
| Threshold hash matches validation output                      | `python eval/check_threshold_hash.py`                                                 |
| Six golden demo images pass                                   | `runtests("tests/golden")`                                                            |
| Cache pre-warmed with the six demo images; fallback rehearsed | Run each image once, then `NX_CACHED_MODE=true` and run the full script               |
| Supabase project active, in Mumbai, under storage limits      | Dashboard shows region `ap-south-1`; open the Vercel link from a phone on mobile data |
| Image tags pinned                                             | No `latest` left in `.env`                                                            |
| Phone flag set, hotspot tested in the venue                   | Capture one image on site, not at home                                                |
| Grafana seeded with 30 days across four facilities            | Panel 1 shows both lines                                                              |
| No secrets committed                                          | `git log -p | findstr /i "password secret token"` returns nothing                     |
| Projector colour check                                        | Refer, routine and retake states distinguishable at the back of the room              |

---

## 26. Caching strategy

Cache computation, never authority. Every key is content-addressed, so nothing can go stale and there is no invalidation logic to get wrong.

### Where caching pays, and where it does not

Caching passes the scope test from Section 1 because it feeds three graded concerns: training speed on a single laptop, the sub-30-second review target, and the correctness of offline sync. But the value is unevenly distributed, and the spec should say so plainly.

| Cache                            | Value           | Why                                                                                                                                                                                                           |
|----------------------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Training preprocessing           | ✅ **highest**  | Without it, FOV crop, Ben Graham normalisation and CLAHE re-run on every image in every epoch of every experiment. On one laptop that is hours lost per day of iteration.                                     |
| Reviewer prefetch                | ✅ **high**     | The next case is already loaded when the grader presses `J`. Network wait is the one part of the 21-second median the grader cannot shorten by being faster.                                                  |
| Idempotent retries               | ✅ **required** | A correctness fix, not a speed-up. A phone whose upload drops and retries must not create two studies for one eye.                                                                                            |
| Inference results                | ⚠️ **modest**   | Most eyes are graded exactly once, so production hit rates will be low. Real value is in retries, report regeneration, and demo reliability. Do not claim it improves production throughput — it barely does. |
| A dedicated cache server (Redis) | ❌ **cut**      | At about 400 screenings a day, a Postgres primary-key lookup is fast enough. On 16 GB of RAM, another service costs memory and adds a failure point for no measurable gain.                                   |

### Three rules

**Content-addressed keys.** An inference result is keyed by the SHA-256 of the image bytes, the model version and the configuration hash. Retrain the model and the version changes, so every old entry simply stops matching. Nothing is ever invalidated because nothing can ever be stale.

**Cache computation, not decisions.** A grade is a pure function of pixels and model, so it is safe to reuse. A study record, a consent, and a reviewer's decision are facts about a specific patient at a specific time, and are always read from the database of record. A cache hit still creates a new study bound to the current patient, with its own audit entry.

**Clinical data never enters a shared cache.** Every clinical API response carries `Cache-Control: no-store`. Image tiles are cached only in the reviewer's own browser, only for the working session, and are cleared at logout.

```mermaid
flowchart TD
  U(["Upload arrives — POST /analyze"]) --> I{"Idempotency key seen?"}
  I -- yes --> E["Return the existing study<br/>retry after a dropped upload"]
  I -- no --> H["SHA-256 of image bytes"] --> O{"Same pixels,<br/>other patient?"}
  O -- yes --> F["Integrity flag → reviewer<br/>likely a mislabelled patient"]
  O -- no --> C{"Cache hit?<br/>sha · model · cfg"}
  C -- yes --> R["Reuse cached payload<br/>no MATLAB call"]
  C -- no --> M["Run MATLAB pipeline<br/>then write cache entry"]
  R --> N["New study bound to this patient + audit entry<br/>Cache-Control: no-store"]
  M --> N
  classDef routine fill:#EAF4EE,stroke:#1B7F4C;
  classDef retake fill:#FBF3E6,stroke:#B26B00;
  classDef key fill:#E6F1F2,stroke:#0E7C86;
  class R routine;
  class F retake;
  class M key;
```

*Figure 9 — Request path through the caches. The order of the diamonds matters. Idempotency is checked first because a retry must return the same study, not merely the same grade. The cross-patient check comes before the cache lookup so that a mislabelled image is caught even when a cached answer is available.*

### What is cached, where, for how long

| Layer                   | Key                                           | Lifetime                    | Invalidated by                                      |
|-------------------------|-----------------------------------------------|-----------------------------|-----------------------------------------------------|
| Inference results       | SHA-256 · model version · config hash         | Until the model is retired  | Nothing — a new model version simply stops matching |
| Idempotency keys        | Client-generated UUID per capture             | 7 days                      | Expiry                                              |
| MATLAB model and config | Process lifetime                              | Until engine restart        | Restart after deploying a new model                 |
| Training images         | Folder name carries the preprocessing version | Until preprocessing changes | Bump the version; a new folder is built             |
| Lesion features         | Image ID · detector version                   | Until a detector changes    | Bump the detector version                           |
| Image tiles (browser)   | Content-addressed URL                         | One working session, capped | Logout clears the cache                             |
| App shell (browser)     | Build hash in each filename                   | Until the next deploy       | New build, new filenames                            |
| Keycloak signing keys   | Key ID                                        | 1 hour                      | Unknown key ID forces a refetch                     |

### Gateway — the inference cache

One table in the Postgres you already run. No new service.

``` sql
CREATE TABLE inference_cache (
  img_sha256   bytea       NOT NULL,
  model_ver    text        NOT NULL,
  cfg_hash     text        NOT NULL,
  payload      jsonb       NOT NULL,      -- grade, posterior, evidence keys, criteria
  created_at   timestamptz NOT NULL DEFAULT now(),
  hit_count    integer     NOT NULL DEFAULT 0,
  PRIMARY KEY (img_sha256, model_ver, cfg_hash)
);

ALTER TABLE study ADD COLUMN client_key uuid UNIQUE;   -- idempotency
```

``` python
# service/cache.py — wraps the MATLAB call from Section 23
import hashlib, json
from prometheus_client import Counter

CACHE = Counter("netrasetu_cache_requests_total", "Cache lookups", ["layer", "result"])

def analyze_cached(db, raw: bytes, patient_id, client_key, run_matlab, version):
    # 1 · idempotency: a retry returns the same study, not a new one
    if client_key:
        row = db.execute("SELECT id FROM study WHERE client_key = %s", (client_key,)).fetchone()
        if row:
            CACHE.labels("idempotency", "hit").inc()
            return load_study(db, row[0])

    sha = hashlib.sha256(raw).digest()

    # 2 · same pixels already belong to a different patient → never auto-serve
    other = db.execute(
        "SELECT 1 FROM study WHERE sha256 = %s AND patient_id <> %s LIMIT 1",
        (sha, patient_id)).fetchone()
    if other:
        return create_study(db, patient_id, client_key, sha, payload=None,
                            flag="same_image_other_patient")

    # 3 · computation cache, keyed by content + model + config
    key = (sha, version["modelVer"], version["cfgHash"])
    row = db.execute("""UPDATE inference_cache SET hit_count = hit_count + 1
                        WHERE img_sha256 = %s AND model_ver = %s AND cfg_hash = %s
                        RETURNING payload""", key).fetchone()
    if row:
        CACHE.labels("inference", "hit").inc()
        payload, source = row[0], "cache"
    else:
        CACHE.labels("inference", "miss").inc()
        payload, source = run_matlab(raw), "matlab"
        db.execute("""INSERT INTO inference_cache (img_sha256, model_ver, cfg_hash, payload)
                      VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                   (*key, json.dumps(payload)))

    # 4 · always a fresh study for this patient, with the source in the audit trail
    return create_study(db, patient_id, client_key, sha, payload, source=source)
```

Get the version from MATLAB itself at engine startup, so the cache key cannot drift from the model actually loaded:

``` matlab
function txt = nx_version()
%NX_VERSION  Identity of the loaded model and configuration, for cache keys.
    cfg = nx_config();
    s.modelVer = string(cfg.modelVer);
    s.cfgHash  = string(cfg.thresholdHash);
    txt = jsonencode(s);
end
```

`modelVer` is already defined in `nx_config` (Section 22). Bump it whenever the weights change.

### MATLAB — load the model once

``` matlab
function net = nx_model()
%NX_MODEL  Trained network, loaded on first call and kept for the engine's lifetime.
    persistent m
    if isempty(m)
        cfg = nx_config();
        s = load(cfg.modelFile, "net");
        m = s.net;
    end
    net = m;
end
```

This is what `nx_warmup` from Section 23 actually pays for: the first call loads the weights, every later call reuses them. Restart the engine after deploying a new model, or the old one stays in memory.

### Training — preprocess once, train many times

``` matlab
function nx_build_cache(srcDir, cacheDir)
%NX_BUILD_CACHE  Enhance every image once. Resumable: finished files are skipped.
%   Put the preprocessing version in cacheDir, e.g. data/cache/enh_v1_512.
    imds = imageDatastore(srcDir, IncludeSubfolders=true);
    if ~isfolder(cacheDir), mkdir(cacheDir); end
    files = imds.Files;
    parfor i = 1:numel(files)
        [~, name] = fileparts(files{i});
        out = fullfile(cacheDir, name + ".png");
        if isfile(out), continue; end
        I = nx_enhance(files{i});
        imwrite(imresize(I, [512 512]), out);
    end
end
```

``` matlab
parpool("Processes", 4);     % 4, not 8 — each worker costs RAM on a 16 GB machine
nx_build_cache("data/aptos/train_images", "data/cache/enh_v1_512");
dsTrain = imageDatastore("data/cache/enh_v1_512");   % every epoch reads from here
```

Three details make this safe. PNG, not JPEG, so caching adds no compression artefacts to images whose microaneurysms are a few pixels wide. The version in the folder name means changing `nx_enhance` produces a new folder rather than silently mixing old and new preprocessing in one training run. And the `isfile` check makes an interrupted build resume where it stopped.

Apply the same pattern to Stream B: save the ~24 lesion features per image to `data/cache/features_v1.mat`, so retraining the fusion model takes seconds instead of re-running every detector.

### Browser — service worker and prefetch

``` typescript
// web/vite.config.ts — inside VitePWA({ ... })
workbox: {
  globPatterns: ['**/*.{js,css,html,woff2,svg}'],          // app shell, precached
  runtimeCaching: [
    { urlPattern: ({ url }) => url.pathname.startsWith('/locales/'),
      handler: 'StaleWhileRevalidate',
      options: { cacheName: 'i18n' } },
    { urlPattern: ({ url }) => url.pathname.includes('/dzi/'),
      handler: 'CacheFirst',
      options: { cacheName: 'tiles',
                 expiration: { maxEntries: 2000, maxAgeSeconds: 8 * 3600 } } },
  ],
  // deliberately no rule for /analyze, /study or /review — those are never cached
}
```

``` typescript
// Reviewer Console — prefetch the next two cases while the current one is open
useEffect(() => {
  queue.slice(index + 1, index + 3).forEach(c => {
    fetch(c.dzi.level0Url);                       // lands in the 'tiles' cache
    c.evidence.forEach(e => fetch(e.cropUrl));
  });
}, [index]);

// On logout
await caches.delete('tiles');
```

One trap breaks this silently. Presigned URLs carry a signature in the query string, and the browser caches by full URL. If the gateway issues a fresh signature on every request, every tile looks new and nothing is ever reused. Have the gateway reuse each study's presigned URLs for the length of their validity, so the cache key stays stable across a session.

### HTTP policy

| Resource                            | Cache-Control                          | Reason                                                                                 |
|-------------------------------------|----------------------------------------|----------------------------------------------------------------------------------------|
| Built assets (`/assets/*`)          | `public, max-age=31536000, immutable`  | Vite puts a content hash in every filename                                             |
| `index.html`, `sw.js`               | `no-cache`                             | Must pick up new asset names and fixes immediately                                     |
| Image tiles                         | `private, max-age=31536000, immutable` | Pixels never change, but `private` keeps patient images out of any shared cache or CDN |
| `/analyze`, `/study/*`, `/review/*` | `no-store`                             | Clinical data                                                                          |
| Patient link `/r/{token}`           | `no-store`                             | Single-use token; a cached copy would outlive it                                       |

### The demo fallback becomes the cache

The cached-results mode from Section 15 no longer needs separate machinery. Before the demo, run the six demo images through the pipeline once; their results are now in `inference_cache`. If MATLAB fails on stage, the gateway serves those six from the cache and answers anything else with a clear *"grading node unavailable — queued"*. The UI is identical either way, because it is the same code path. `NX_CACHED_MODE=true` now means one thing: serve from the cache, never call MATLAB.

### Observability and the capacity model

Add a hit-ratio panel to the Admin Console from `netrasetu_cache_requests_total`. In SimEvents, a cache hit bypasses the inference server entirely, so add it as a routing branch before that server — and parameterise it with your *measured* hit ratio, which in production will be small. Modelling an optimistic hit rate would flatter your throughput numbers in exactly the way Section 11 warns against.

All colour tokens, type decisions, diagrams and screen specifications in this document are original to this brief. External tools, datasets and standards are linked to primary sources in Section 13. Performance figures quoted for the closing pitch are targets, not measured results — replace them with your own bootstrap intervals before presenting.

NetraSetu — engineering specification v3.2 · SIH PS 26038 · MathWorks

---

*All colour tokens, type decisions, diagrams and screen specifications in this document are original to this brief. External tools, datasets and standards are linked to primary sources in Section 13. Performance figures in the closing pitch are targets, not measured results — replace them with your own bootstrap intervals before presenting.*
