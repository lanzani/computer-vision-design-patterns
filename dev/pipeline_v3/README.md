# pipeline_v3 dev scripts

Progressive examples of the v3 pipeline architecture. Run them in order.

| Script | What it teaches | Needs camera |
|--------|-----------------|--------------|
| `dev_01_minimal.py` | Smallest pipeline: source → sink, `chain()`, `stats()` | No |
| `dev_02_apartments.py` | The reference topology: 4 streams × (pose → fall) into 2 apartment aggregators; hot add/remove streams; `on_event` | No |
| `dev_03_process_stages.py` | Heavy stage in a child process; shared-memory frame transport; cross-process metrics | No |
| `dev_04_webcam.py` | Real `CameraSource` with reconnect; `VideoSink` with graceful quit | Yes |

```bash
uv run python dev/pipeline_v3/dev_01_minimal.py
```

Key rules of thumb:

- Stages are pure logic: `setup()` / `process()` / `teardown()`. Never sleep in
  `process()` — the runner handles pacing, backoff, and shutdown.
- Use `ExecutorType.PROCESS` for CPU-heavy stages (models); keep sources,
  sinks, and aggregators as THREAD.
- Fan-in stages that must accept streams at runtime (aggregators) must be
  THREAD — you cannot hot-attach to a running child process.
- Video edges default to `LATEST_ONLY` (newest frame wins); use `BLOCK` or
  `DROP_OLDEST` with a larger `maxsize` for event streams that must not drop.
