"""Status display panel for the Seq-o-Matic GUI.

Handles canvas clearing, note saving, and AWS upload UI toggling.
"""

import os
import subprocess
import tarfile

import zstandard

from front_end.logwindow import add_highlight_mainwindow, widge_attr


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


class StatusPanel:
    """Manages status display elements: canvas clearing, notes, and AWS upload controls.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def clear_focus_canvas(self):
        """Clear the focus canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_focus.draw()

    def clear_align_canvas(self):
        """Clear the alignment canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_align.draw()

    def clear_tile_canvas(self):
        """Clear the tile canvas by resetting its subplot with hidden axes."""
        plot1 = self.app.alignfigure.add_subplot(111)
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        self.app.canvas_tile.draw()

    def save_to_note(self):
        """Append the notes text widget content to experiment_detail.txt locally and attempt to upload it to the server."""
        if not os.path.exists(os.path.join(self.app.pos_path, "experiment_detail.txt")):
            open(os.path.join(self.app.pos_path, "experiment_detail.txt"), 'a').close()
        txt = _get_time() + self.app.note_stw.get("1.0", "end-1c") + "\n"
        f = open(os.path.join(self.app.pos_path, "experiment_detail.txt"), "a")
        f.write(txt)
        f.close()
        server_path = '/mnt/imagestorage/' + self.app.pos_path[3:]
        self.app.linux_server = self.app.server
        try:
            cmd = ("scp " + os.path.join(self.app.pos_path, "experiment_detail.txt")
                   + " " + self.app.linux_server + ":" + server_path)
            os.system(cmd)
            txt = _get_time() + "local note saved to experiment_detail.txt, and uploaded to server!" + "\n"
            add_highlight_mainwindow(txt)
        except OSError as e:
            txt = _get_time() + "local note saved to experiment_detail.txt, upload to server is failed!"
            add_highlight_mainwindow(txt)

    def upload_aws(self):
        """Toggle the AWS upload credential fields between editable and disabled."""
        if self.app.upload_aws_value.get() == 1:
            self.app.aws_account_lb.config(fg=widge_attr.normal_color)
            self.app.aws_password_lb.config(fg=widge_attr.normal_color)
            self.app.aws_account_field["state"] = "normal"
            self.app.aws_pwd_field["state"] = "normal"
        else:
            self.app.aws_account_lb.config(fg=widge_attr.disable_color)
            self.app.aws_password_lb.config(fg=widge_attr.disable_color)
            self.app.aws_account_field["state"] = "disable"
            self.app.aws_pwd_field["state"] = "disable"

    def upload_aws_handler(self):
        """Upload every per-cycle max-projection folder of this experiment to S3.

        Each <maxprojection drive>/<experiment>_maxprojection/<cycle> folder is packed
        into <cycle>.tar.zst (zstd level 3, streaming) and copied with
        `aws s3 cp ... --storage-class INTELLIGENT_TIERING --checksum-algorithm SHA256`
        (up to 3 attempts, using the AWS CLI's own credentials). The local archive is
        deleted only after a successful upload. Runs in the calling thread, as in the
        reference.
        """
        folder = self.app.pos_path[3:] + "_maxprojection"
        base_dir = os.path.join(self.app.scope.maxprojection_drive, folder)
        bucket = "barseq-acquisition"
        max_retries = 3
        if not os.path.isdir(base_dir):
            txt = _get_time() + f"AWS upload skipped: {base_dir} does not exist\n"
            print(txt)
            add_highlight_mainwindow(txt)
            return
        for name in os.listdir(base_dir):
            sub_path = os.path.join(base_dir, name)
            if not os.path.isdir(sub_path):
                continue
            archive_path = os.path.join(base_dir, f"{name}.tar.zst")
            s3_uri = f"s3://{bucket}/{folder}/{name}.tar.zst"
            # 1. Tar + zstd-compress the folder (streaming, no intermediate uncompressed tar)
            print(f"Creating {archive_path}")
            cctx = zstandard.ZstdCompressor(level=3, threads=-1)
            with open(archive_path, "wb") as f_out:
                with cctx.stream_writer(f_out) as compressor:
                    with tarfile.open(fileobj=compressor, mode="w|") as tar:
                        tar.add(sub_path, arcname=name)
            # 2. Upload, retrying only on CLI failure
            success = False
            for attempt in range(1, max_retries + 1):
                print(f"Attempt {attempt}/{max_retries}: uploading to {s3_uri}")
                upload = subprocess.run([
                    "aws", "s3", "cp", archive_path, s3_uri,
                    "--storage-class", "INTELLIGENT_TIERING",
                    "--checksum-algorithm", "SHA256",
                ])
                if upload.returncode == 0:
                    success = True
                    break
                print(f"  Upload failed (exit {upload.returncode}), retrying...")
            # 3. Delete local archive only after successful upload
            if success:
                os.remove(archive_path)
                print(f"Deleted {archive_path}. Moving to next folder.\n")
            else:
                print(f"FAILED to upload {archive_path} after {max_retries} attempts. Keeping local file.\n")
        print("Finished all folders\n")
