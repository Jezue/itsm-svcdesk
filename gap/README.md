<!-- ai-generated: 95% - OpenAI Codex designed and interpreted the client-versus-server latency experiment. -->
# Client versus server latency gap

The experiment places a Toxiproxy latency toxic in front of `svcdesk`, configured for 100 ms of latency and zero jitter. The client therefore measures the whole path through the proxy, while `http_server_request_duration_seconds` starts only after the request reaches FastAPI and stops when the server has produced its response. The difference is time experienced by the caller but invisible to server-side request instrumentation.

The declared client p99, server p99 and gap are in seconds. A 100 ms gap is expected because the injected delay lives outside the application's measurement boundary. This is why the latency SLO explicitly names a server-side SLI: it is useful for service accountability, but it is not a complete measure of user experience. A client-side probe should accompany it when network, gateway or queueing delay matters. The checker repeats the same experiment and allows normal load-test variation rather than trusting these recorded values alone.
