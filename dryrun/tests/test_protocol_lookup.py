"""The branch's protocol lookup must pick the same file as the reference's if/elif chain (P18)."""

import itertools
import os
import sys
import types
import unittest

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "code")


def reference_find_protocol(name):
    """Matching order of REF system/fluidics_exchange_system.py find_protocol (2026-10-05)."""
    if "geneseq" in name and "01" in name:
        return "geneseq01"
    elif "bcseq" in name and "01" in name:
        return "bcseq01"
    elif "geneseq" in name and "01" not in name:
        return "geneseq02+"
    elif "bcseq" in name and "01" not in name:
        return "bcseq02+"
    elif "user_defined" in name:
        return name
    elif "HYB" in name and "rehyb" not in name:
        return "HYB"
    elif "add_gene_primer" in name and "rehyb" not in name:
        return "add_gene_primer"
    elif "add_bc_primer" in name and "rehyb" not in name:
        return "add_bc_primer"
    elif "HYB" in name and "rehyb" in name:
        return "HYB_rehyb"
    elif "add_gene_primer" in name and "rehyb" in name:
        return "add_gene_primer_rehyb"
    elif "add_bc_primer" in name and "rehyb" in name:
        return "add_bc_primer_rehyb"
    elif "strip" in name:
        return "strip"
    return None


class TestProtocolLookup(unittest.TestCase):
    def test_same_file_as_reference_for_combined_names(self):
        saved = {k: sys.modules.get(k) for k in ("front_end", "front_end.logwindow")}
        sys.modules["front_end"] = types.ModuleType("front_end")
        sys.modules["front_end.logwindow"] = types.SimpleNamespace(add_fluidics_reagent=lambda t: None)
        sys.path.insert(0, CODE)
        try:
            from system.fluidics.protocol_loader import PROTOCOL_MAP
        finally:
            sys.path.remove(CODE)
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

        def branch(name):
            for cond, fname in PROTOCOL_MAP:
                if cond(name):
                    return name if fname is None else fname[len("Fluidics_sequence_"):-len(".json")]
            return None

        words = ["geneseq", "bcseq", "HYB", "add_gene_primer", "add_bc_primer", "rehyb", "strip", "user_defined",
                 "01", "02"]
        for k in (1, 2, 3):
            for combo in itertools.permutations(words, k):
                name = "Fluidics_sequence_" + "_".join(combo)
                self.assertEqual(branch(name), reference_find_protocol(name), name)


if __name__ == "__main__":
    unittest.main()
