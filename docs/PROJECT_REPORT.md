# Agentic 3D Asset Factory

## A Human-in-the-Loop Workflow for Modular Character Asset Creation

**Course:** DASC7606C — Track 2: Agentic Framework Design  
**Status:** Working prototype; comparative evaluation pending  
**Draft date:** 4 October 2026  
**Team members:** [To be completed]

> Draft conventions: **Implemented** describes current software behavior. **Observed** describes a preliminary case or reported measurement. **Planned** describes work that has not yet produced experimental results. Placeholders must be completed before submission. This document is a report draft, not a claim that all evaluation has been completed. Condense and format the final report to the course's 5–8-page limit, excluding references.

## Abstract

Commercial image-to-3D models can generate character assets, but obtaining an editable result involves more than a single generation request. Reference preparation, occluded clothing, inconsistent views, unwanted connections between hair and clothing, repeated revisions, and file handoff can create substantial workflow friction. We develop Agentic 3D Asset Factory, a local web application that organizes character creation into overall design, full-character views, parallel component references, visual review, component geometry, optional texturing, and Blender export. A character is represented as one persistent project, with separate head, body-and-outfit, and hair assets.

The system combines image generation, a vision-language reviewer, and Tripo's 3D generation API. AI review findings inform subsequent revisions, while users retain authority over paid execution and subjective acceptance. Our contribution is the workflow and its feedback and asset-management mechanisms, rather than a new generative model. A preliminary Jinx case demonstrates application integration and editable asset handoff. A separate historical anime-character case demonstrates downstream assembly, rigging and a dance demo after external Blender/Codex-assisted processing. User-reported API expenditure for the initial application-flow test was 595 Tripo credits and USD 0.43 for OpenAI usage, equivalent to USD 6.38 at the published Tripo API credit rate; this excludes the historical dance project's development expenditure. Comparative quality, editing effort, and time advantages remain hypotheses to be evaluated against direct whole-character generation and a component workflow without AI review.

## 1. Problem and Intended Users

### 1.1 Target users

The initial target users are independent creators, students, and small game or animation teams who want a customized character asset starting point and have basic Blender skills. They may already use AI generation tools but do not want to repeatedly transfer reference images, track versions, and repair unrelated parts after a local change.

This is currently a target-user hypothesis informed by the project member's own use. We have not conducted a representative user study. Before submission, obtain a small amount of independent feedback and distinguish it from team observations.

### 1.2 Workflow problem

A whole-character generation request can introduce several problems:

- Long hair may conceal back clothing in the reference, leaving the intended garment design unspecified.
- Hair, clothing, and anatomy can acquire unwanted connections that complicate independent editing.
- Small facial features compete with the full body for reference-image space and geometric detail.
- A satisfactory body may need to be regenerated because the head or hair is unsatisfactory.
- Reference revisions and generated assets can become mismatched during manual file transfer.

These are failure modes to investigate, not claims that every whole-character result has them. Modular generation also introduces its own problems, especially alignment, scale mismatch, and neck joins.

### 1.3 Scope and useful output

Our intended output is a **modular, editable character asset starting point**, not a fully rigged production character. The exported Blender scene contains separately addressable components and available textures, accompanied by their selected reference images. Position, scale, joins, and intersections may require subsequent adjustment. Successful file export does not establish deformation quality or suitability for production animation.

## 2. Tool Design and User Workflow

### 2.1 End-to-end workflow

1. **Overall design:** Start with a text description or an existing image. The character brief is optional when an adequate image is supplied.
2. **Full-character views:** Confirm the design and generate a four-view reference sheet. Requirements include consistent identity, scale and pose, an initial standing pose, and separated legs.
3. **Component references:** Confirm the full views and generate head, body-and-outfit, and hair sheets in parallel, using the confirmed full-character sheet as shared visual authority.
4. **Visual review and revision:** Inspect the component images. AI structure findings, user text, uploaded change references, and optional brush annotations guide revision of the current sheet.
5. **Geometry generation:** After all component references are confirmed, upload four separate views per component and generate the three untextured meshes in parallel.
6. **Optional texturing:** Generate textures using a copy of a chosen white mesh and its recorded component references. Preserve the original mesh and previous candidates.
7. **Handoff:** Select component candidates and export a project ZIP with a native Blender scene and corresponding references. Continue assembly or refinement in Blender, optionally using the user's own Codex.

Human confirmation is a checkpoint for subjective quality and expenditure. In the current UI, some approvals trigger the next paid stage automatically, including the component-reference batch and the geometry batch. These transitions must be communicated clearly; users do not necessarily approve each individual API request separately.

### 2.2 Why three components?

The head, body-and-outfit, and hair divide concentrates on parts with distinct reference and editing requirements while keeping assembly manageable. The head needs facial consistency and a controlled neck termination. The body retains shoulders and a short neck allowance. Hair must exclude facial anatomy and ears while preserving natural strand direction.

This is a design hypothesis, not a proven optimal decomposition. Finer decomposition might help some outfits but increases calls, interface boundaries, and assembly work. Combining body and outfit also means the current system does not provide an independently editable garment layer.

### 2.3 State, memory, and version control

Each character is one project. Project context stores the design brief, current selected references, approvals, revision dependencies, feedback, and generated candidates. Model submissions retain their reference input snapshots. Upstream changes invalidate dependent downstream results without deleting their history.

This is explicit application state supplied to model requests, rather than an assumption that an API model remembers earlier calls. Component revisions use the current component sheet together with authoritative character references and relevant feedback.

### 2.4 Deterministic automation

Four-view splitting uses local Python/Pillow processing, not a Codex session or paid model call. It searches for light background gutters near the sheet center, crops the four regions, and pads them to consistent square outputs. Direction labels follow the required layout: top-left front, top-right left, bottom-left back, bottom-right right.

The splitter does not semantically recognize directions. Misordered views may therefore receive incorrect labels; uncertain or blank crops need review. Component isolation is performed by the image-generation model, not by this crop algorithm.

### 2.5 Export and external editing

The backend uses Blender to create a real `.blend` scene and pack textures. The project ZIP includes five selected reference sheets and, for a complete set, sixteen individual view images. It excludes historical messages and unrelated reference versions. Component view images correspond to the selected model's recorded inputs.

The user opens the extracted `.blend` directly. Objects remain separate and are named using the project name and component. The backend requires Blender for native export; a recipient can download the package before installing Blender and open it after installation.

We deliberately do not embed a replica of Codex's Blender operation capabilities. Open-ended refinement can be performed using Blender or a user's existing assistant. This limits engineering scope and avoids introducing an additional internal agent bill; any external assistance used during evaluation must still be recorded.

## 3. Deep Learning Approach and Agentic Role

### 3.1 Models, inputs, and outputs

| Module | Current configuration | Inputs | Outputs |
|---|---|---|---|
| Image generation/editing | OpenAI image API; development default `gpt-image-2.5-sunburst` | Stage rules, character brief, selected images, user feedback and annotations | Design or four-view component sheet |
| Visual reviewer | Vision-language model; default `gpt-5-mini` | Component sheet and authoritative full-character reference | Structured findings and a review verdict |
| Component geometry | Tripo P2.0, `P2-20260801` | Four separately uploaded images ordered front, left, back, right | Untextured model files and task metadata |
| Texture generation | Separate Tripo texture engine, `v3.5-20260815`, detailed PBR | Copy of the selected geometry and its four-view references | Textured model files |

These are development configurations, not a claim that they are the globally best available models. Exact configuration and prompt snapshots should accompany experimental runs. Account availability may differ.

Geometry requests always specify `quad=true`. Head requests target 5,000 faces; body and hair target 20,000 each. Requested settings do not prove actual output counts or topology quality. Inspect authoritative source meshes; browser rendering and GLB previews may triangulate geometry.

### 3.2 Why an agentic workflow?

The execution stages are deliberately constrained. However, visual defects are not identical across generations: a hair sheet may retain ears, a head sheet may change expression between views, or a neck may flare into shoulders. A vision-language model interprets these differences and produces findings that guide a targeted revision. The revision request combines those findings with the current image and user instructions.

We describe this as a **human-in-the-loop agentic workflow**. AI participates in diagnosis and revision guidance; the user controls expenditure and acceptance. Requiring approval before paid action does not require removing model-based judgment. Subjective tolerance also matters: a user may accept a minor defect that another user wants corrected.

The current implementation is not an autonomous planner. Review is advisory, and there is no automatic unlimited repair loop, model-driven API selection, or autonomous Blender assembly. The fixed scheduler, cropper, and packager are engineering automation. This boundary should remain explicit, especially because stricter definitions reserve “agent” for model-directed actions [2].

### 3.3 Technical contribution

Our contribution consists of:

1. A component-specific reference strategy with expression, anatomy isolation, hair-flow, and neck-interface constraints.
2. Persistent visual authority and version dependencies across generation stages.
3. A review-to-revision mechanism that incorporates image-specific AI findings and user changes.
4. Parallel independent generation, candidate preservation, geometry-before-texture processing, and guarded paid-task handling.
5. A usable bilingual interface and a traceable Blender handoff package.

Geometry and texture synthesis remain capabilities of external models. We do not claim to improve their learned weights. The workflow contribution must be evaluated through input quality, editing convenience, effort, and delivery reliability.

### 3.4 Data sources

Runtime data consists of user-supplied character images or descriptions, generated references, review outputs, and model artifacts. No custom training dataset or model training is currently used. Evaluation characters should have documented provenance and permission to use and redistribute necessary sample inputs. A Jinx example is useful as an internal demonstration but does not itself establish redistribution or commercial-use rights.

## 4. Implemented Prototype and Preliminary Evidence

### 4.1 Evidence available now

| Evidence | Status and observation | What it establishes | What it does not establish |
|---|---|---|---|
| Jinx end-to-end case | **Observed:** references, three components, textures, preview and native Blender export have been exercised | Integration feasibility for one case | General success rate or superiority |
| Historical anime-character dance case | **Recorded and visually inspected:** assembled character, external rigging/motion work, front/side dance contact sheets, and a historical 906-frame numerical scan | Downstream animation feasibility for a second character after additional processing | Automatic binding by the app, a clean repeatable current-app run, or animation-ready quality without repairs |
| Assembly/refinement | **User-reported:** separate parts were assembled with basic Blender operations; estimated assembly time is about 10 minutes for an experienced Blender user, or 10–15 minutes with Codex assistance and user adjustments | The result can support further editing in that case; preliminary effort estimates | Formally timed performance, a universal completion-time guarantee, or proof that Codex is faster |
| Blender verification | **Previously recorded:** backend Blender 5.2.2 reopened the export with three meshes and twelve embedded 4096×4096 textures | Concrete export and texture packaging behavior | Future outputs always have 4K textures or correct materials |
| Automated tests | **Re-run on 4 October 2026:** 45 tests passed in 7.14 seconds | Tested application and mocked-provider contracts behave as expected | Real-provider visual quality or statistical effectiveness |
| Pipeline expenditure | **User-reported:** 595 Tripo credits plus USD 0.43 OpenAI usage | A preliminary run-level cost observation | Stable per-character production cost or a matched-baseline comparison |

The prior Blender verification is carried forward from the existing project record; it was not re-executed when drafting this report. Test execution for this draft used the local Python environment and did not request paid generations.

### 4.1.1 Historical downstream animation case

The parent workspace contains a separate anime character project, `v2_soft_anime_trial.blend`, dance inspection images, VMD motion inputs, and rigging/repair records. The inspected contact sheet shows the assembled character in multiple dance poses from front and side views. The handoff describes separate body and hair rigs, VMD adaptation, and subsequent pose, weighting, foot-contact, expression and material adjustments. Hair movement is described as driven animation, not a validated collision-physics system.

The historical report `mmd_rebuild/validation_final.json` records 906 checked frames (0–905), no non-finite bone-matrix values, and no unweighted vertices in the checked head (4,823 vertices) and body (26,446 vertices). The motion notes identify dance frames 6–905, preceded by a neutral interval. The report also records substantial adjacent-frame rotation changes, including approximately 60 degrees at one hand. These diagnostics establish specific checks, not uniformly natural movement or collision-free playback. Key-frame visual inspection is not an exhaustive visual review of every frame.

This case materially extends the evidence beyond static display: assets of this type can be assembled, bound and adapted to a dance demo. It involved external Blender/Codex-assisted and user processing and predates the current application's complete workflow. It therefore should be presented as **downstream feasibility evidence**, separately from Jinx's application integration test. Traceable proof that this exact historical asset was generated by the current application is not established. Do not assign the USD 6.38 application-flow cost to this longer historical project.

For presentation, show the current application workflow followed by a short recording of this downstream dance result. Record the actual final scene version, motion source attribution, manual interventions and unresolved defects. This report inspected existing records and contact-sheet images; it did not reopen or replay the current `.blend`, change the scene, or rerun the historical animation scan.

### 4.1.2 Functional editing observations and preliminary assembly effort

The project member supplied the following additional observations on 4 October 2026. These are recorded for later organization and verification; they are not new controlled experiments executed while updating this document.

| Task | Reported behavior | Supported use and evidence boundary |
|---|---|---|
| Blinking | A newly generated closed-eye head is alternated with the open-eye head to produce a blink action | Basic expression animation has been demonstrated using two head models. This is model switching, not a complete facial rig, smooth blendshape system, or validation of all expressions. |
| Hair recoloring | Hair is independently generated and selectable, allowing its color to be edited separately | Separate objects enable local appearance editing. The member considers this operation straightforward; preserve an explicit before/after example and verify that face and clothing remain unaffected before claiming a measured editing result. |
| Manual assembly | Opening the exported scene, basic alignment and presentation are estimated to take roughly 10 minutes for an experienced Blender user | A practitioner estimate of assembly effort, not a formal timing result or novice-user benchmark. Record the required adjustments and accepted final quality. |
| Codex-assisted assembly | The member estimates roughly 10–15 minutes including Codex reasoning/tool time, with some user fine adjustments to fit hair closely to the face | An estimate for an assisted workflow, not autonomous zero-intervention assembly. Do not infer that Codex is faster than a skilled Blender user or that its cost/time applies to every character. |

These observations support the scoped use case of editable character prototypes and animation demonstrations. They do not establish game-engine performance, production animation quality, or a complete facial-animation system. The downstream work and any newly generated closed-eye head must be accounted for separately from the initial application-flow bill unless billing records confirm their inclusion.

Next evidence to collect: record one full assembly session per approach with the same starting assets and acceptance criteria; distinguish active human effort, assistant execution/waiting and elapsed time. Capture the blink transition and independent hair-color edit, including any artifacts or remaining fit problems. Generalizing assistance to inexperienced users requires a separate user test.

### 4.2 Engineering tests

The test suite covers project context, dependencies, four-view splitting, input order, quad request enforcement, parallel batches, review feedback integration, preservation of existing results, interrupted/unknown task behavior, texture-copy submission, and export selection. Many provider tests use mocks. They are valuable for catching workflow regressions, but must not be presented as forty-five character-quality experiments.

### 4.3 Formative observations and prompt changes

Development surfaced concrete issues: hair references containing ears or facial silhouettes, implausible side-view fringe flow, different mouth expressions across head views, and head references extending into shoulder flares. Stage prompts and review criteria were adjusted in response. Body references retain a short upward neck allowance for joining.

These observations motivate the design. They are not controlled evidence that each prompt change improved outcomes. A stronger report should include paired before/after images, the exact change, generation configuration, and remaining defects, without selecting only favorable examples.

### 4.4 Preliminary cost accounting

Tripo's published API exchange rate is USD 0.01 per credit [3]. Assuming the reported 595 credits are API credits and the OpenAI figure is USD:

`595 × USD 0.01 + USD 0.43 = USD 6.38`

External Codex assistance is a separate subscription allocation, not a pipeline API fee. For an illustrative monthly payment of AUD 145, the 2 October 2026 RBA rate of USD 0.6933 per AUD gives approximately USD 100.53 [4].

| Assumed monthly allocation | 5% of one full allowance | Conservative 25% allowance allocation | USD 6.38 API cost plus 25% allocation |
|---|---:|---:|---:|
| Four full allowances | USD 1.26 | USD 6.28 | USD 12.66 |
| Five full allowances | USD 1.01 | USD 5.03 | USD 11.41 |
| Six full allowances | USD 0.84 | USD 4.19 | USD 10.57 |

Four allowances follows the team's four-week-month convention. Five or six assume additional resets are actually available and used; they are not guaranteed plan entitlements. The 25% scenario is five times the assumed 5% use, not a measured charge. These are proportional subscription allocations, not official dollar values of quota percentages or additional amounts deducted. Subscription and API pricing are distinct [5].

For the final experiment, separate initial generation, revisions, review, geometry candidates, texture calls, and external assembly assistance. Confirm the ledger against account records. Exclude software-development expenditure from recurring character-production cost, and include recurring editing effort. USD 3.50 was an early estimate, not the measured total for this run.

## 5. Planned Baseline and Evaluation

**No completed baseline or ablation results are reported in this draft.** The experiment below is the highest-priority remaining work.

### 5.1 Questions and hypotheses

- **RQ1:** Does component reference preparation reduce unwanted hair/anatomy/clothing mixing compared with whole-character generation?
- **RQ2:** Does the modular output reduce effort for localized edits, after accounting for assembly?
- **RQ3:** Does AI structure feedback improve revisions compared with user feedback alone?
- **RQ4:** What extra generation expense and waiting time are required, and are they offset by less manual work?

The expected benefits are hypotheses. More requested faces do not by themselves prove better geometry; extra components do not guarantee easier rigging; generated hidden clothing details may be plausible but still differ from the intended design.

### 5.2 Comparison arms

| Arm | Procedure | Purpose |
|---|---|---|
| B0: Direct whole character | Use the same approved full-character four views as separate images in Tripo; generate geometry and comparable textures | Evaluate direct use of the underlying generator |
| W1: Component workflow without AI review | Generate component references; retain user feedback and approvals; do not provide AI review findings | Isolate the workflow's modularization and organization benefits |
| W2: Current full workflow | Same component workflow, with visual review findings supplied to subsequent revisions | Estimate the incremental benefit and cost of AI review |

Use B0 versus W2 for the overall workflow comparison, and W1 versus W2 for review-specific claims. Optional later comparison: existing service generation followed by its native segmentation tools. Do not imply that commercial alternatives lack multiview, segmentation, or editing features [6].

### 5.3 Sample and controls

Start with 3–5 characters covering simple hair, long hair obscuring clothing, and complex outfits or accessories. This sample is a preliminary feasibility study, not proof of industry-wide superiority. Add repeated independent generations where budget permits and report the attempt count per arm.

Fix the character design, approved full-character references, geometry engine, view order, quad requirement, and comparable texturing settings. Agree the acceptance rubric before inspecting results. Do not handicap B0 by uploading an unsplit four-view collage where the endpoint expects separate views.

The component workflow requests a total of 45,000 faces, whereas a whole-character request is subject to its single-model limit. Report requested and actual counts and actual costs. This resource difference is part of the practical comparison, but prevents attributing every visual improvement to decomposition. If supported, add a lower-budget component condition or matched-cost candidate budget. Otherwise state the unmatched budget clearly.

Evaluate raw outputs and outcomes after a fixed manual editing time. Include component alignment time. If external Codex is used, record the same allowance/time policy for both arms and distinguish its changes from the generated output. Log provider seeds when available; otherwise record independent task identifiers and configurations.

### 5.4 Metrics and acceptance criteria

| Dimension | Proposed measurement |
|---|---|
| Reference fidelity | Predefined 1–5 ratings for face, hairstyle, clothing and color, using consistent rendered viewpoints |
| Structural defects | Checklist counts for missing parts, unintended connections, anatomy retained in hair, intersections, and view inconsistency |
| Hidden clothing | With hair hidden where possible, rate exposed back clothing against a specified intended reference; score plausibility separately if no ground truth exists |
| Editability | Time and operation count for changing hair color, replacing/hiding hair, and adjusting a selected head; record spillover onto unrelated parts |
| Assembly burden | Active time to align components, adjust scale and handle neck joins |
| Delivery | ZIP integrity, successful Blender open, embedded textures, separate objects, and correct selected-reference mapping |
| Efficiency | End-to-end elapsed time, active human time, model waiting time, successful/failed attempts, and total billable cost |
| Review quality | Human verification of each AI finding, precision among reported findings, and missed defects against a human checklist |

Define “usable” at the prototype's scope: the scene opens, the intended parts exist and remain editable, and the prescribed modification can be completed within the chosen effort budget. Add a predeclared visual acceptance rubric. Do not silently include rigging or production animation readiness in this definition.

Use identical lighting, camera views and display settings. Blind visual ratings to arm labels where practical. Editing evaluators will see object structure, so full blinding is not feasible; disclose this. With a small sample, report individual cases and descriptive summaries rather than unsupported statistical significance claims.

### 5.5 Results template — pending execution

| Character | Arm | Actual faces / quad proportion | Fidelity | Defects | Assembly min | Edit min | Elapsed min | API USD | External assistance |
|---|---|---|---|---|---|---|---|---|---|
| [Character] | B0 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| [Character] | W1 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| [Character] | W2 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

For each case, retain the input, configuration and prompt versions, operation records, selected and rejected candidates, consistent screenshots, timing log, and reason for acceptance or rejection. Keep artifacts out of the source repository; provide authorized sample inputs and evaluation evidence separately.

## 6. Limitations and Risks

- **Cross-view consistency:** Image generation can change expressions, scale or anatomy between views. Cropping preserves these errors rather than correcting them.
- **Occlusion and invented detail:** Removing hair from a reference exposes a need to infer unseen clothing. User review makes that inference inspectable; it does not recover missing ground truth.
- **Component interfaces:** Separate generation may cause proportion mismatch, gaps and intersections. More parts may increase rather than decrease total effort.
- **Topology and animation:** Quad requests and visible wireframes do not establish deformation-friendly edge flow. A historical anime case includes rigging and motion checks, but the application does not automatically rig assets; there is no cross-character controlled animation evaluation or current-app rigging guarantee.
- **Review reliability:** AI findings can be incorrect or incomplete. Current findings are advisory and require user judgment.
- **Dependence on services:** Availability, model changes, output formats, latency and pricing depend on vendors. Interrupted or unknown requests require reconciliation before another paid submission.
- **Expense authorization:** Current automatic transitions can submit a batch after approval. A more explicit estimated-cost and batch-consent UI is planned. Development mode has no call-count limit.
- **Privacy and rights:** Selected user images are transmitted to external providers. Deployment needs consent, storage/retention rules, access control, and reference licensing checks.
- **Evidence limits:** One current-app integration case, a separate historical downstream dance case, a user-reported bill and mocked-provider tests support different aspects of feasibility, but not comparative superiority or robust generalization.

## 7. Remaining Modules and Development Priorities

| Priority | Module or task | Current gap | Completion criterion |
|---|---|---|---|
| P0 — submission | Baseline runner and timing/cost ledger | No controlled asset-quality comparison | Reproducible B0/W1/W2 records and case-level results |
| P0 — submission | Evidence package | Historical observations not yet organized as experiment evidence | Authorized inputs, before/after figures, failure cases and demonstration recording |
| P0 — submission | Reproduction and contribution statement | Clean-clone sample delivery and team details need completion | Setup verified by another member; responsibilities and LLM assistance disclosed |
| P1 | Review and revision instrumentation | No measurement of finding accuracy or repair success | Trace each finding to revision and human outcome |
| P1 | Budget and paid-action controls | Approval-triggered batches need clearer cost communication | Estimated spend, explicit batch scope, and per-project budget policy |
| P1 | Reference/interface validation | Prompt constraints do not guarantee consistent necks, expressions or views | Measurable checks and clear human-review warnings |
| P1 | Service modularization | Generation, memory and orchestration logic need cleaner boundaries | Documented interfaces and regression tests for dependency behavior |
| P2 | Multi-candidate quality selection | Manual candidate inspection; automated ranking not validated | Ranking compared with human preferences, with disagreement handling |
| P2 | Optional bounded repair loop | No autonomous review–repair iteration | Opt-in budget, iteration limit, consent boundaries and repair-gain evidence |
| P2 | Lightweight assembly assistance | Alignment and neck joins require external editing | Demonstrated reduction in assembly effort without damaging geometry |
| P3 | Deployment and batch creation | Local prototype, not a multi-user asset factory | Isolation, authentication, queues, storage quotas and retention controls |

Near-term work should prioritize evidence and reliability rather than expanding to a general-purpose Blender agent.

## 8. Future Extensions

The modular representation could support hairstyle replacement, outfit variants, reusable component libraries, and larger character batches. If visual review is reliable, a bounded agent could choose which component to repair, form a targeted instruction, recheck the result, and escalate uncertainty. Paid execution would follow the user's chosen budget and authorization policy.

The historical dance case supplies initial rigging and motion evidence. Future work should make this validation repeatable on exports from the current application: hand scenes to Blender tools or an external assistant for binding, then inspect neck, shoulder and hair deformation and record intervention time. Reusing an existing motion is animation adaptation, not motion generation. These tests would extend downstream utility evidence, not constitute automatic rigging already implemented by this application.

Broader decomposition should follow measured needs: separate accessories or garments only when the reduction in editing effort outweighs extra calls and interface complexity. Embedding Codex-like computer operation remains outside the present scope.

## 9. Conclusion

The prototype demonstrates a complete workflow from character input to modular assets and a native Blender handoff. Its contribution lies in organizing references, revisions, visual feedback, generation stages and selected outputs into a coherent tool. A preliminary case and engineering tests support feasibility. Baseline and review-ablation experiments remain necessary to establish whether this organization delivers better editing outcomes and justified cost/time trade-offs than direct whole-character generation.

## Submission Checklist

- [ ] Run B0/W1/W2 on representative characters and replace pending results.
- [ ] Reconcile the reported USD 6.38 with billing records and classify retries versus development calls.
- [ ] Record elapsed and active editing time; include assembly and external assistance.
- [ ] Verify the reported 10-minute manual / 10–15-minute Codex-assisted assembly estimates with timed sessions; capture blink and hair-recolor examples.
- [ ] Inspect actual topology and face counts from authoritative models.
- [ ] Add reproducible screenshots, failure cases and reference provenance.
- [ ] Verify setup using a clean environment with an authorized sample input.
- [ ] Prepare a 10-minute presentation including the complete demo, plus a backup recording.
- [ ] Complete member contributions and the course-required LLM-use disclosure.
- [ ] Convert this draft to a 5–8-page report excluding references; retain only supported conclusions.

## Team Contributions and LLM-Use Disclosure — To Complete

| Member | Actual contribution | Supporting artifacts |
|---|---|---|
| [Name] | [Implementation / prompt design / evaluation / documentation] | [Files, logs, experiment records] |

Suggested disclosure to customize: OpenAI Codex assisted with software implementation, debugging, documentation and report drafting. Runtime image generation and visual review use OpenAI APIs; geometry and texturing use Tripo APIs. External Codex assistance for Blender editing, where used, must be distinguished from the application's own behavior. Team members are responsible for verifying implementation, sources, results and submitted claims. Follow the course's full LLM policy; this paragraph alone does not establish compliance.

## References

1. Course team. *DASC7606C Group Project*, supplied assignment document, Track 2 requirements, pp. 5–7.
2. Anthropic. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents). Used for the distinction between predefined workflows and model-directed agents.
3. Tripo. [API Pricing](https://developers.tripo3d.com/en/pricing). API credit conversion checked on 4 October 2026.
4. Reserve Bank of Australia. [Exchange Rates](https://www.rba.gov.au/statistics/frequency/exchange-rates.html). Rate used: 2 October 2026, USD 0.6933 per AUD.
5. OpenAI. [Pricing](https://learn.chatgpt.com/docs/pricing). Subscription allowances and API prices are distinct; our quota allocations are assumptions, not official conversion rates.
6. Meshy. [How to Use Multi-View Image to 3D](https://www.meshy.ai/tutorials/multi-view-image-to-3d). Example of existing multiview, texture and downstream editing capabilities; no independent comparative performance claim is inferred.

## Internal Traceability Notes

- Current behavior and previously recorded Blender checks: `README.md`.
- Crop implementation: `src/asset_factory/views.py`.
- Project state, generation and AI review integration: `src/asset_factory/studio.py`.
- Advisory visual review: `src/asset_factory/review.py`.
- Tripo request contracts: `src/asset_factory/tripo.py`.
- Geometry and texture orchestration: `src/asset_factory/geometry.py`.
- Native scene export: `src/asset_factory/blender_export.py` and `scripts/export_blend.py`.
- Engineering checks: `tests/test_studio.py` and `tests/test_blender_import.py`.
- Historical dance evidence under the parent workspace `/Users/shangyishen/Desktop/model_v2`: `dance_audit/sheet_01.jpg`, `mmd_rebuild/validation_final.json`, `MMD重建说明.txt`, and `docs/BLENDER_HANDOFF.md`. These are external experimental artifacts, not assets to commit with this software repository. The report describes the inspected records; provenance and final scene playback must be verified for presentation.

These notes support team verification and can be removed from the submitted report.
