# Module reference overview

This section is the single source of truth for class and function API
reference. Each page documents one focused module area so maintainers can update
behavior and docs in one place.

## Source-of-truth rules

Use these rules to keep documentation consistent.

- Put API signatures and behavior details only in module pages.
- Keep [docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md) focused on
  architecture and operations.
- Keep [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md) focused on
  setup and first contributions.

## Module pages

Use these pages based on what you are changing.

- [docs/modules/models-and-errors.md](docs/modules/models-and-errors.md)
- [docs/modules/logger-and-exports.md](docs/modules/logger-and-exports.md)
- [docs/modules/base-scraper.md](docs/modules/base-scraper.md)
- [docs/modules/checkpoint.md](docs/modules/checkpoint.md)
- [docs/modules/progress-reporter.md](docs/modules/progress-reporter.md)
- [docs/modules/retries.md](docs/modules/retries.md)
- [docs/modules/listing-normalizer.md](docs/modules/listing-normalizer.md)
- [docs/modules/maps-scraper.md](docs/modules/maps-scraper.md)

## Update workflow

Use this sequence when implementation changes.

1. Update code in the target module.
2. Update only the corresponding module reference page.
3. Update maintainer or onboarding docs only when architecture or process
   changes.
4. Validate with tests and an end-to-end driver run.

## Next steps

After you update a module page, verify links from
[docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md) and
[README.md](README.md) still point to the correct entry pages.
