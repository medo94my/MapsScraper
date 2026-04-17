# Take-Home Assessment: Google Maps Business Listing Utility

Build a utility program that takes the name of an input text file as an argument to the program, reads Google Maps search prompts from the input text file, and returns structured business/location listing data for each prompt entry in the file.

This exercise is about extraction from a dynamic public surface, data normalization, duplicate handling, and basic scraper reliability. It does not fully reproduce a heavily defended target, so include a short technical note on how you would harden the approach for a more hostile platform.

## Task

Your implementation should:

- read prompts from a newline-delimited text file
- run those searches on Google Maps
- collect up to 30 unique businesses per prompt
- extract useful structured data for each business
- organize the collected data in a searchable internal data structure that you can return as an object to a user
- write output to `jsonl`

If a prompt returns fewer than 30 businesses, return what you found and document that outcome.

Use any reasonable stack. Browser automation, request-based extraction, or a hybrid approach are all acceptable.

## Driver

The repository includes `task_driver.py`.

We expect to be able to run `task_driver.py` and have it work as part of your submission.

## Prompt Pack

The required prompt set is provided in `prompts.txt` at the repository root.

## Data Model

Choose a schema that is useful to a downstream consumer. The output should be structured, consistent, and traceable back to the originating query and source pages.

Collect as much useful data as you can do reliably. 

Partial records are acceptable if they are represented consistently.

## Constraints

- Do not use the Google Places API, Google Maps API, or paid third-party business data providers.
- Do not manually assemble the dataset.
- Do not spend time solving CAPTCHAs or bypassing login walls for this exercise.
- Keep the implementation scoped. We are evaluating engineering decisions, not scrape volume.

If you encounter blocking, incomplete results, or unstable behavior, document it precisely and explain how you would address it in production.

## Deliverables

Submit:

- source code
- `README.md` with setup and run instructions
- extraction output files
- `DESIGN.md`
- brief notes on your process, tradeoffs, and what you would do next

Your repository should be runnable by another engineer without guessing at missing steps.

## Design Note

In `DESIGN.md`, briefly cover:

1. Extraction strategy and why you chose it
2. Brittle points and likely failure modes
3. Process, tradeoffs, shortcuts, and dead ends
4. Reliability for repeated runs: retries, timeouts, checkpointing, deduplication, logging, partial failure recovery
5. Data quality: validation, drift detection, completeness, confidence
6. How you would adapt the system to a more adversarial target such as a social media surface
7. How you would scale or orchestrate it across many prompts or regions
8. What you would improve with more time

If you have suggestions for improving `task_driver.py` or the exercise contract, include them briefly here.

When discussing that, assume the current driver contract is fixed for the take-home itself.

## Bonus Signals

These are optional, but useful if done for a clear reason and kept proportional:

- resumable runs or checkpointing
- structured logging or simple metrics
- containerized local setup
- CI for tests or linting
- stronger deduplication or entity normalization
- useful enrichment beyond the obvious fields
- a clear orchestration sketch for scaling the collector
- a small fixture-based test strategy for brittle extraction logic
- thoughtful suggestions for improving the provided driver or assessment contract

## Evaluation

We will assess:

- usefulness and consistency of the data model
- correctness and completeness of the extracted data
- quality of the extraction approach
- useful enrichment when justified by the implementation
- code clarity and maintainability
- handling of failure cases, duplicates, and missing fields
- quality of the technical write-up and tradeoff discussion

We are not assessing:

- codebase cosmetics
- unnecessary infrastructure
- large scrape volume
