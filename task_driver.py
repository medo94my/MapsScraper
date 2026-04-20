# -*- coding: utf-8 -*-
import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.resolve()
INPUT_DIR = ROOT_DIR / "inputs"


from task.main import *


def fail_test(message):
    print("Test Failed: " + message)
    sys.exit(-1)


def test_missing_file():
    task = MapsScraper()
    try:
        task.read_prompt_file(str(INPUT_DIR / "i_do_not_exist.txt"))
        fail_test("missing file test failed")
    except MissingPromptFile:
        pass


def test_wrong_prompt_file():
    task = MapsScraper()
    try:
        task.read_prompt_file(str(INPUT_DIR / "prompts.invalid.txt"))
        fail_test("wrong prompt file test failed")
    except WrongPromptFile:
        pass


def test_read_prompt_file():
    scraper = MapsScraper()
    prompts = scraper.read_prompt_file(str(ROOT_DIR / "prompts.txt"))

    if not len(prompts) > 0:
        fail_test("prompt file should return prompts")

    if not isinstance(prompts[0], Prompt):
        fail_test("read_prompt_file should return Prompt objects")


def test_run():
    scraper = MapsScraper()
    prompts = [Prompt("bookstores in Cairo")]
    listings = scraper.run(prompts, limit=5)

    if not isinstance(listings, list):
        fail_test("run should return a list")

    if not len(listings) > 0:
        fail_test("run should return listings")

    listing = listings[0]

    if not isinstance(listing, Listing):
        fail_test("run should return Listing objects")

    if not hasattr(listing, "name"):
        fail_test("Listing should include name")

    if not hasattr(listing, "lat"):
        fail_test("Listing should include lat")

    if not hasattr(listing, "lon"):
        fail_test("Listing should include lon")

    if not hasattr(listing, "url"):
        fail_test("Listing should include url")


def tests():
    test_missing_file()
    test_wrong_prompt_file()
    test_read_prompt_file()
    test_run()


def main():
    tests()
    scraper = MapsScraper()
    prompts = scraper.read_prompt_file(str(ROOT_DIR / "prompts.txt"))
    
    # Enable resumable runs with progress reporting
    checkpoint = Checkpoint(str(ROOT_DIR / "output.jsonl"))
    listings = scraper.run(prompts, limit=30, checkpoint=checkpoint, show_progress=True)


if __name__ == "__main__":
    main()
