# Limitations

NetraSetu is a research prototype. It is not a medical device and has not been cleared by any
regulator. What it does not do yet:

- Neovascularisation is a vessel-morphology proxy, not a detector. Findings of type `NV_PROXY`
  are labelled as a proxy everywhere they are shown.
- No prospective clinical validation. Every reported number comes from retrospective evaluation
  on public datasets (see [`VALIDATION.md`](VALIDATION.md)).
- Single-field imaging only.
- In the prototype, offline capture queues for grading on sync; fully on-device grading is the
  Jetson edge path and is not built.
- Prototype object storage is tamper-evident, not tamper-proof; write-once Object Lock arrives with
  the production tier.
- No CDSCO pathway completed.
