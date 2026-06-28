"""Standalone, GUI-free AWS upload worker for Seq-o-matics.

This module performs the tar + zstd compression and ``aws s3 cp`` upload of a
max-projection experiment folder.  It is intentionally free of any tkinter /
GUI dependency so it can be launched as a *detached* OS process that outlives
the GUI (see ``window_widgets._launch_aws_upload`` in front_end/Widgets.py).

It can be invoked either:
  * from the command line / a detached subprocess::

        python aws_upload_worker.py \
            --base-dir   "<*_maxprojection folder>" \
            --folder     "<S3 key prefix>" \
            --protocol-src "<folder for json/txt/csv, or empty to skip>" \
            --bucket     barseq-acquisition \
            --log-file   "<path to this job's log>"

  * or in-process via ``run_upload(...)`` (used for unit/sanity checks).

Every step is logged with a timestamp to ``--log-file`` (and stdout).  The job
finishes with a single ``STATUS: SUCCESS|PARTIAL|FAILED`` line so the log is
easy to grep for completion state.
"""

import argparse
import logging
import os
import subprocess
import sys
import tarfile

import zstandard


DEFAULT_BUCKET = "barseq-acquisition"
MAX_RETRIES = 3


def _make_logger(log_file):
    """Build a logger that writes to *log_file* (if given) and stdout."""
    logger = logging.getLogger("aws_upload_worker")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def _compress_and_upload(archive_path, sub_path, arcname, s3_uri, logger):
    """Tar+zstd *sub_path* into *archive_path*, upload to *s3_uri*, retrying.

    Returns True on a successful upload (and removes the local archive), else
    False (keeping the local archive for a later manual retry).
    """
    logger.info(f"Creating {archive_path}")
    cctx = zstandard.ZstdCompressor(level=3, threads=-1)
    with open(archive_path, "wb") as f_out:
        with cctx.stream_writer(f_out) as compressor:
            with tarfile.open(fileobj=compressor, mode="w|") as tar:
                if isinstance(arcname, list):
                    # arcname is a list of (src_path, name) protocol files
                    for src, name in arcname:
                        tar.add(src, arcname=name)
                else:
                    tar.add(sub_path, arcname=arcname)

    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Attempt {attempt}/{MAX_RETRIES}: uploading to {s3_uri}")
        upload = subprocess.run([
            "aws", "s3", "cp", archive_path, s3_uri,
            "--storage-class", "INTELLIGENT_TIERING",
            "--checksum-algorithm", "SHA256",
        ])
        if upload.returncode == 0:
            success = True
            break
        logger.info(f"  Upload failed (exit {upload.returncode}), retrying...")

    if success:
        os.remove(archive_path)
        logger.info(f"Deleted {archive_path}.")
    else:
        logger.info(
            f"FAILED to upload {archive_path} after {MAX_RETRIES} attempts. "
            f"Keeping local file."
        )
    return success


def run_upload(base_dir, folder, protocol_src=None, bucket=DEFAULT_BUCKET,
               log_file=None):
    """Upload every per-cycle subfolder of *base_dir* to S3, plus a protocol bundle.

    Parameters
    ----------
    base_dir : str
        The ``*_maxprojection`` folder containing per-cycle subfolders.
    folder : str
        The S3 key prefix (typically ``os.path.basename(base_dir)``).
    protocol_src : str or None
        Folder to gather ``.json``/``.txt``/``.csv`` files from for the protocol
        bundle.  If None or empty, the protocol bundle is skipped.
    bucket : str
        Target S3 bucket.
    log_file : str or None
        Path to write the job log to (in addition to stdout).

    Returns
    -------
    str : "SUCCESS", "PARTIAL", or "FAILED".
    """
    logger = _make_logger(log_file)
    logger.info(f"=== AWS upload job start: base_dir={base_dir} folder={folder} ===")

    if not os.path.isdir(base_dir):
        logger.info(f"ERROR: base_dir does not exist: {base_dir}")
        logger.info("STATUS: FAILED")
        return "FAILED"

    results = []

    # ----- Per-cycle maxprojection subfolders -----
    subdirs = [n for n in os.listdir(base_dir)
               if os.path.isdir(os.path.join(base_dir, n))]
    if not subdirs:
        logger.info(f"ERROR: no subfolders found in {base_dir}; nothing to upload.")
        logger.info("STATUS: FAILED")
        return "FAILED"

    for name in subdirs:
        sub_path = os.path.join(base_dir, name)
        archive_path = os.path.join(base_dir, f"{name}.tar.zst")
        s3_uri = f"s3://{bucket}/{folder}/{name}.tar.zst"
        ok = _compress_and_upload(archive_path, sub_path, name, s3_uri, logger)
        results.append(ok)
        if ok:
            logger.info("Moving to next folder.")

    # ----- Protocol bundle: json/txt/csv files from protocol_src -----
    if protocol_src and os.path.isdir(protocol_src):
        protocol_files = [
            fname for fname in os.listdir(protocol_src)
            if (".json" in fname or ".txt" in fname or ".csv" in fname)
            and os.path.isfile(os.path.join(protocol_src, fname))
        ]
        if protocol_files:
            protocol_archive = os.path.join(base_dir, "protocol.tar.zst")
            protocol_s3_uri = f"s3://{bucket}/{folder}/protocol.tar.zst"
            members = [(os.path.join(protocol_src, f), f) for f in protocol_files]
            ok = _compress_and_upload(
                protocol_archive, None, members, protocol_s3_uri, logger)
            results.append(ok)
        else:
            logger.info("No protocol files found; skipping protocol bundle.")
    else:
        logger.info("No protocol source folder; skipping protocol bundle.")

    if all(results):
        status = "SUCCESS"
    elif any(results):
        status = "PARTIAL"
    else:
        status = "FAILED"
    logger.info(f"Finished all folders. STATUS: {status}")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detached AWS upload worker.")
    parser.add_argument("--base-dir", required=True,
                        help="The *_maxprojection folder to upload.")
    parser.add_argument("--folder", required=True,
                        help="S3 key prefix (usually basename of base-dir).")
    parser.add_argument("--protocol-src", default="",
                        help="Folder to gather json/txt/csv from; empty to skip.")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--log-file", default="")
    args = parser.parse_args(argv)

    status = run_upload(
        base_dir=args.base_dir,
        folder=args.folder,
        protocol_src=args.protocol_src or None,
        bucket=args.bucket,
        log_file=args.log_file or None,
    )
    # Non-zero exit on failure so callers/CI can detect it.
    return 0 if status == "SUCCESS" else (2 if status == "FAILED" else 1)


if __name__ == "__main__":
    sys.exit(main())
