# Changelog

## 0.4.0

- Added environment and YAML controls for independent Attention and Activity source polling.
- Added strict source boolean parsing, Attention `sourceKind` allowlists, and Activity event-list overrides.
- Disabled source surfaces are not polled; durable per-source checkpoints are preserved across disable/re-enable cycles.
- Documented inbox-only deployment and updated the Unraid template and Compose example.
