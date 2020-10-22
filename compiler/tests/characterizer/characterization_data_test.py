#!/usr/bin/env python3
import os

from char_test_base import CharTestBase


class CharacterizationDataTest(CharTestBase):

    def setUp(self):
        super().setUp()
        self.remove_test_files()

    def cleanup(self):
        super().cleanup()
        self.remove_test_files()

    @staticmethod
    def remove_test_files():
        from characterizer.characterization_data import get_data_file
        sample_file = get_data_file("test", [])
        directory = os.path.dirname(sample_file)
        for f in os.listdir(directory):
            if f.startswith("test") and f.endswith(".json"):
                os.remove(os.path.join(directory, f))

    def test_module_with_no_extra_config(self):
        from characterizer.characterization_data import save_data, load_data
        save_data("test", "A", 0.1e-15, clear_existing=True)
        save_data("test", "B", 0.2e-15)

        self.isclose(load_data("test", "A"), 0.1e-15)
        self.isclose(load_data("test", "A", size=10), 0.1e-15)
        self.isclose(load_data("test", "B"), 0.2e-15)
        self.assertIsNone(load_data("test", "C"))

    def test_size_interpolation(self):
        from characterizer.characterization_data import save_data, load_data
        save_data("test", "A", 0.1e-15, size=1, clear_existing=True)
        save_data("test", "A", 0.2e-15, size=3)
        save_data("test", "A", 0.25e-15, size=5)

        self.isclose(load_data("test", "A", size=0.5), 0.1e-15)
        self.isclose(load_data("test", "A", size=1), 0.1e-15)

        self.isclose(load_data("test", "A", size=5), 0.25e-15)
        self.isclose(load_data("test", "A", size=10), 0.25e-15)

        self.isclose(load_data("test", "A", size=2), 0.15e-15)
        self.isclose(load_data("test", "A", size=4), 0.225e-15)

    def test_file_suffixes(self):
        from characterizer.characterization_data import save_data, load_data

        values = [1e-15, 2e-15, 2.5e-15, 3e-15]
        heights = [0.9, 1, 2]

        # add one without height
        save_data("test", "A", values[3], size=1, clear_existing=True)

        for i in range(len(heights)):
            file_suffixes = [("height", heights[i])]
            save_data("test", "A", values[i], size=1, clear_existing=True,
                      file_suffixes=file_suffixes)

        mean_value = sum(values) / len(values)
        # if height not specified, get the mean
        self.isclose(load_data("test", "A", size=2), mean_value)

        # exact height specified
        self.isclose(load_data("test", "A", size=2,
                               file_suffixes=[("height", 1)]), 2e-15)

    def test_suffixes_filter(self):
        from characterizer.characterization_data import filter_suffixes, get_size_key

        candidates = []
        for size in [1, 2, 4]:
            for h in [1, 1.25, 1.8]:
                for nf in [1, 3, 8]:
                    size_key = get_size_key(size, [("height", h), ("nf", nf)])
                    candidates.append(size_key)

        # specify all 2 criteria
        match_results = filter_suffixes([("height", 1.5), ("nf", 4)], candidates=candidates)
        self.assertEqual(len(match_results), 3, "Three matches with only sizes changing")
        for result in match_results:
            self.assertTrue(result.endswith("height_1.25_nf_3"))

        # specify only nf criteria
        match_results = filter_suffixes([("nf", 4)], candidates=candidates)
        self.assertEqual(len(match_results), 9, "Nine matches")
        for result in match_results:
            self.assertTrue(result.endswith("_nf_3"))

        # specify only height criteria
        match_results = filter_suffixes([("height", 1.1)], candidates=candidates)
        self.assertEqual(len(match_results), 9, "Nine matches")
        for result in match_results:
            self.assertTrue("_height_1" in result)

        # specify no criteria
        match_results = filter_suffixes([], candidates=candidates)
        self.assertEqual(len(match_results), 27, "27 matches")


CharacterizationDataTest.run_tests(__name__)
