---
lab3_genai_diff:
  instrumentation: "opentelemetry-sdk 1.38.0 JSON SpanExporter capture"
  spec_ref: "semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d"
  attributes:
    - name: gen_ai.operation.name
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.provider.name
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.request.model
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.response.model
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.response.finish_reasons
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.usage.input_tokens
      emitted: true
      in_spec: true
      stability: development
    - name: gen_ai.usage.output_tokens
      emitted: true
      in_spec: true
      stability: development
---
<!-- ai-generated: 95% - OpenAI Codex compared the emitted span attributes with the pinned GenAI registry. -->
# OpenTelemetry GenAI semantic-convention diff

The JSON capture represents one client span around a local, deterministic stand-in for an LLM chat call; it requires no external network or credentials. The emitted set contains the operation, provider, requested and returned model, finish reasons, and token usage. Every emitted `gen_ai.*` key is listed above exactly once.

Against the pinned semantic-conventions GenAI model revision, all seven names are present and all remain at development stability. This matters operationally: dashboards may use the fields, but an upgrade must review semantic-convention changes rather than assuming a stable schema. Content-bearing prompt and response attributes were intentionally not emitted, reducing accidental disclosure and telemetry volume.
