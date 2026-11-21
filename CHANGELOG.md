# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security
- PyTorch 2.6.0 → 2.15.0 (CPU), which resolves the open PyTorch advisories (among them CVE-2026-24747,
  code execution through crafted checkpoint files).
- Removed `basicsr`, `realesrgan` and `torchvision` (CVE-2024-27763 in `basicsr` has no fixed release).
  The Real-ESRGAN network and tiled inference are now a small module in the backend with the same output;
  23 transitive packages leave the lock file and the image.

## [0.1.0] - 2026-11-20

First public release.

### Added
- Sync any S3-compatible bucket (AWS S3, Cloudflare R2, DigitalOcean Spaces, Backblaze B2, MinIO…) into a review queue.
- Presets: configurable pipelines for background removal (BiRefNet / U²-Net via rembg), autocrop, Real-ESRGAN
  upscaling, canvas placement, resizing and output encoding — four built-in presets.
- Optional AI engines (OpenAI, Google Gemini) per preset or per run.
- Review before/after, publish in place with automatic backup, one-click restore, generated derivatives
  (thumbnails, WebP copies) from name templates.
- Batch jobs with live progress, abort/skip/stop, retry of failed images.
- Import images from URLs, and a Playground to try presets on a single image.
- Users with admin/operator roles, activity log, dashboard.
- Every behavioural option is editable at runtime on the Settings page (grouping, sync, concurrency, limits,
  session length, login throttling, prefixes, object ACL, publish derivatives, source filters, AI models);
  `.env` holds only secrets and boot-time infrastructure.
- Docker Compose setup for development and production; multi-arch images on GHCR.

### Security and data safety
- Publishing can never replace a backup: each image records its backup location before its source is
  overwritten, one image is published or restored by one request at a time, and restore works from the
  recorded location even after the backup prefix changes.
- Login attempts are counted before the password is checked, so parallel guesses cannot exceed the limit;
  the admin step-up password is throttled too. Password hashing runs off the event loop.
- Only JPEG, PNG and WebP are ever decoded. Real-ESRGAN runs in tiles with an input-size cap, URL imports
  are stored one by one, so memory use no longer grows with image size or request size.
- API responses carry fixed error messages instead of raw exception text.
- Unsafe environment values (empty or nested prefixes, short `ADMIN_PASSWORD` / `API_KEY`) stop the
  backend at startup. `API_DOCS_ENABLED` is off by default.

[0.1.0]: https://github.com/derar-sattouf-dev/bucket-studio/releases/tag/v0.1.0
