"""Hardware-free dry-run harness for Seq-o-Matic.

Runs the real program (GUI included) with every hardware boundary replaced by a
fake that records what it was told to do, so two versions of the program can be
run through the same scenario and their traces compared.

See dryrun/README.md.
"""
