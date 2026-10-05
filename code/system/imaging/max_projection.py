"""
Max-intensity projection and image transfer for the imaging pipeline.

Handles multi-channel z-stack acquisition at tile positions, max-projection
computation, and data transfer to remote servers.
"""
import os
import shutil
import threading
import time

import numpy as np
import pandas as pd
import tifffile
from pycromanager import Acquisition, Core

from front_end.logwindow import (
    update_error, add_highlight_from_scope,
    update_process_bar, update_process_label, draw_liveview,
)
from system.imaging.ndtiff_stack import NDTiffStack
from system.imaging.position_utils import (
    get_time, color_array, hattop_convert, denoise, image_channels_for_cycle,
)


class MaxProjectionManager:
    """Manages max-intensity projection acquisition, computation, and data transfer.

    Handles the full imaging loop: acquiring multi-channel z-stacks at each tile
    position, computing max-intensity projections, and transferring results to
    remote servers.
    """

    def __init__(self, parent):
        """Initialize the MaxProjectionManager with a reference to the parent ImagingSystem.

        Args:
            parent: The parent ImagingSystem instance providing core, config, and path state.
        """
        self._parent = parent

    def image_and_maxprojection(self, cycle):
        """Acquire multi-channel z-stacks for all tiles and compute max-intensity projections.

        Waits for tile generation to complete, then images each tile position and
        produces max-projection TIFF files for downstream analysis.

        Args:
            cycle: Cycle name string (e.g., 'geneseq01', 'hyb01').
        """
        p = self._parent
        p.live_plot=1
        check = p.maketiles_status
        while check == 0:
            if p.cancel_process == 1:
                print("maxprojection thread! Cancelled while waiting for tiles.")
                p.maxprojection_name = 'end'
                return
            time.sleep(5)
            check = p.maketiles_status
            print("maxprojection thread! I am waiting make tile finished!")
        p.cycle = cycle
        self.create_max_projection_folder()
        print(p.cycle )
        self.Assign_image_channel()
        self.start_max_imgage_cycle()
        print("maxprojection thread! I am finished! Thread closed!")
        txt=get_time()+""+p.cycle+" image and maxprojection finished!"+"\n"
        print(txt)
        p.write_log(txt)
        add_highlight_from_scope(txt)

    def create_max_projection_folder(self):
        """Create local and max-projection output directories for the current cycle.

        Loads the tiled position list and creates the necessary folder structure
        on both the local pos_path and the max-projection drive.
        """
        p = self._parent
        if os.path.isfile(os.path.join(p.pos_path, 'tiledregoffset' + p.cycle + '.csv')):
            p.tilepos_new = pd.read_csv(os.path.join(p.pos_path, 'tiledregoffset' + p.cycle + '.csv'))
            p.maxproject_list =p.tilepos_new
        else:
            txt = get_time() + p.cycle + "Can't find tiledregoff" + p.cycle + " datafile! \n"
            update_error(txt)
            p.max_projection_status = 0
            return

        image_path = os.path.join(p.pos_path, p.cycle)
        if not os.path.exists(image_path):
            os.mkdir(image_path)
            txt = get_time() + p.cycle + ' maxprojection Folder is created!\n'
            add_highlight_from_scope(txt)
            p.write_log(txt)
            print(txt)
        if not os.path.exists(os.path.join(p.maxprojection_drive, p.pos_path[3:]+"_maxprojection")):
            os.mkdir(os.path.join(p.maxprojection_drive, p.pos_path[3:]+"_maxprojection"))
        # create folder on server

    def Assign_image_channel(self):
        """Set the imaging channel list based on the current cycle type.

        Gene/barcode sequencing cycles use G/T/A/C channels (plus DAPI for cycle 01),
        while hybridization cycles use GFP/YFP/TxRed/Cy5/DAPI/DIC channels.
        Also calculates the total z-stack size for max-projection.
        """
        p = self._parent
        p.channel_list = image_channels_for_cycle(p.cycle)
        p.maxprojection_stack = p.stack_num_maxpro * len(p.channel_list)
        p.timer=5*len(p.channel_list)
        return

    def start_max_imgage_cycle(self):
        """Start the max-projection imaging cycle if channels are assigned, otherwise log an error."""
        p = self._parent
        if p.channel_list != ['']:
            start_time = time.time()
            p._cycle_dir = os.path.join(p.pos_path, p.cycle)
            self.maxprojection_image_cycle()
            add_highlight_from_scope("--- %s seconds ---" % (time.time() - start_time))
            p.maxprojection_name='end'
            p.max_projection_status = 1
            p.fluidics = 1
        else:
            txt = get_time() + p.cycle + "Can not load image channel!"
            update_error(txt)
            p.maxprojection_name = 'end'
            p.write_log(txt)
            print("Can not load image channel!")
            p.max_projection_status = 0

    def maxprojection_image_cycle(self):
        """Execute the full imaging loop: acquire z-stacks at each tile and compute max-projections.

        Iterates over all tile positions, moves the stage/piezo, acquires multi-channel
        z-stacks, and spawns threads to compute max-intensity projections. Includes
        retry logic for acquisition failures.
        """
        p = self._parent
        if os.path.isfile(os.path.join(p.pos_path, 'tiledregoffset' + p.cycle + '.csv')):
            p.tilepos_new = pd.read_csv(os.path.join(p.pos_path, 'tiledregoffset' + p.cycle + '.csv'))
            p.maxproject_list =p.tilepos_new
        update_process_bar(0)
        update_process_label("maxprojection")
        threads=[]
        df = pd.read_csv(os.path.join(p.pos_path, 'cycle00.csv'))  # this pary is used when we have piezo
        p.piezo_init = df.iloc[0]['piezo']
        p.i = 100 / len(p.maxproject_list)
        p.write_log('Start maxprojection')
        p.piezo_middle_pos = p.piezo #This is used when we have piezo
        p.piezo_event = p._focus_mgr.create_piezo_event(p.channel_list, p.zstack.imaging_planes)
        if p.zstack.split_enabled:
            self.write_substack_table()
        p.core.set_shutter_open(False)
        for index, row in p.maxproject_list.iterrows():
            update_process_bar(p.i)
            pos = row['switched_Posinfo']
            txt=get_time()+"prepare "+pos+" in "+p.cycle+"\n"
            print(index)
            p.write_log(txt)
            add_highlight_from_scope(txt)
            if p.cancel_process ==1:
                txt=get_time()+"process canceled!"
                print(txt)
                p.write_log(txt)
                add_highlight_from_scope(txt)
                update_process_bar(0)
                update_process_label("process")
                p.core.stop_stage_sequence('DA Z Stage')
                p.core.set_position("DA Z Stage", p.piezo_middle_pos) # This is used when we have piezo
                break
        #     #This part is used when we have piezo
            try:
                p.core.stop_stage_sequence('DA Z Stage')
                x = row['X']
                y = row['Y']
                p.core.set_xy_position(x, y)
                p.core.wait_for_device("XYStage")
                print("XYStage ready")
                txt = get_time() + "XYStage ready" + "\n"
                p.write_log(txt)
                z = row['Z']
                p.core.set_position("ZDrive", z)
                p.core.wait_for_device("ZDrive")
                print("ZDrive ready")
                txt = get_time() + "ZDrive ready" + "\n"
                p.write_log(txt)
                piezo_z =  p.piezo_init
                p.core.set_position("DA Z Stage", piezo_z)
                p.core.wait_for_device("DA Z Stage")
                txt = get_time() + "DA Z Stage" + "\n"
                p.write_log(txt)
                print("DA Z Stage")
                with Acquisition(directory=os.path.join(p.pos_path, p.cycle), name=pos, show_display=False) as acq:
                    acq.acquire(p.piezo_event)
                    acq.mark_finished()
                p.core.stop_stage_sequence('DA Z Stage')
                p.core.wait_for_device("DA Z Stage")
            except Exception as e:
                time.sleep(2)
                p.core.stop_stage_sequence('DA Z Stage')
                txt = get_time() + p.cycle +" "+pos + ' Acq.acquire failed' +  "\n"
                p.write_log(txt)
                error_message = "An error occurred: " + str(e)+ "\n"
                p.write_log(error_message)
                update_error(txt)
                txt = get_time() + p.cycle + ' System try to reimage!' + "\n"
                p.write_log(txt)
                update_error(txt)
                try:
                    p.core=Core()
                    p.core.stop_stage_sequence('DA Z Stage')
                    p.x = row['X']
                    p.y = row['Y']
                    p.core.set_xy_position(x, y)
                    p.core.wait_for_device("XYStage")
                    print("XYStage ready")
                    txt = get_time() + "XYStage ready" + "\n"
                    p.write_log(txt)
                    z = row['Z']
                    p.core.set_position("ZDrive", z)
                    p.core.wait_for_device("ZDrive")
                    print("ZDrive ready")
                    txt = get_time() + "ZDrive ready" + "\n"
                    p.write_log(txt)
                    piezo_z =  p.piezo_init
                    p.core.set_position("DA Z Stage", piezo_z)
                    p.core.wait_for_device("DA Z Stage")
                    print("DA Z Stage")
                    txt = get_time() + "DA Z Stage" + "\n"
                    p.write_log(txt)
                    with Acquisition(directory=os.path.join(p.pos_path, p.cycle), name=pos, show_display=False) as acq:
                        acq.acquire(p.piezo_event)
                        acq.mark_finished()
                    p.core.stop_stage_sequence('DA Z Stage')
                    p.core.wait_for_device("DA Z Stage")

                    txt = get_time() + "Second Acquisition passed!"+ "\n"
                    p.write_log(txt)
                    update_error(txt)
                except Exception as e:
                    txt = get_time() + p.cycle + ' Second time Acq.acquire failed' + "\n"
                    p.write_log(txt)
                    error_message = "An error occurred: " + str(e) + "\n"
                    p.write_log(error_message)
                    p.core.set_position("DA Z Stage", p.piezo_event_pos[0])
                    p.core.wait_for_device("DA Z Stage")
                    txt = get_time() + "Piezo reset!"+ "\n"
                    p.write_log(txt)
                    raise ValueError("The tile can't be imaged!")
            p.thread_limiter.acquire()  # released by process_scope_image
            try:
                t = threading.Thread(target=self.process_scope_image, args=(row['switched_Posinfo'],))
                t.start()
                threads.append(t)
            except Exception as e:
                p.thread_limiter.release()
                update_error(f"Missing maxprojection: {e}")
            p.i = p.i + 100 / len(p.maxproject_list)
        for t in threads:
            t.join()
        p.core.set_position("DA Z Stage", p.piezo_middle_pos)

        p.maxprojection_name = 'end'
        txt=get_time()+" !"+"\n"
        print(txt)
        p.write_log(txt)
        add_highlight_from_scope(txt)
        time.sleep(3)
        p.max_projection_status=self.check_transfer_complete(p.maxprojection_drive)
        return

    def process_scope_image(self, pos):
        """Process a single acquired tile: compute max-projection and update live view name.

        Args:
            pos: Position name string for the tile to process.
        """
        p = self._parent
        try:
            self.maxprojection(pos)
            names = self.output_names(pos)
            p.maxprojection_name = names[len(names) // 2]  # live view shows the middle group
            txt = get_time() + "Maxprojection finish " + pos + " in "+p.cycle +"\n"
            print(txt)
            p.write_log(txt)
            add_highlight_from_scope(txt)
        finally:
            p.thread_limiter.release()

    def output_names(self, pos):
        """Projection file names of a tile: MAX_<pos>.tif, or MAX_<pos>_z00.tif ... with several groups."""
        groups = self._parent.zstack.substack_groups()
        if len(groups) == 1:
            return ['MAX_' + pos + '.tif']
        return ['MAX_%s_z%02d.tif' % (pos, g.index) for g in groups]

    def _cycle_output_dir(self):
        p = self._parent
        out_dir = os.path.join(p.maxprojection_drive, p.pos_path[3:] + "_maxprojection", p.cycle)
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def write_substack_table(self):
        """Write <cycle>_substacks.csv: the planes and piezo range behind each _zNN file."""
        p = self._parent
        planes = p.piezo_event_pos
        rows = [{"group": g.index, "file_suffix": "_z%02d" % g.index, "first_plane": g.first,
                 "last_plane": g.last, "n_planes": g.n_planes,
                 "piezo_start_um": planes[g.first], "piezo_end_um": planes[g.last]}
                for g in p.zstack.substack_groups()]
        pd.DataFrame(rows).to_csv(os.path.join(self._cycle_output_dir(), p.cycle + "_substacks.csv"), index=False)

    def maxprojection(self, pos):
        """Compute the max-intensity projections of one tile and save one multi-channel TIFF per group.

        Planes are streamed from the raw stack one at a time. For non-DIC channels each
        group is the maximum over its planes; for DIC it is the group's middle plane
        (plane 9 of 20 at the defaults).

        Args:
            pos: Position name string identifying the acquired tile.
        """
        p = self._parent
        out_dir = self._cycle_output_dir()
        groups = p.zstack.substack_groups()
        with NDTiffStack(os.path.join(p.pos_path, p.cycle, pos + '_1')) as stack:
            for group, name in zip(groups, self.output_names(pos)):
                img_max = []
                for c in p.channel_list:
                    if c != 'DIC':
                        acc = stack.read(channel=c, z=group.first)
                        for z in range(group.first + 1, group.last + 1):
                            np.maximum(acc, stack.read(channel=c, z=z), out=acc)
                    else:
                        acc = stack.read(channel=c, z=group.dic_plane)
                    img_max.append(acc)
                tifffile.imwrite(os.path.join(out_dir, name), np.array(img_max), photometric='minisblack')

    def send_protocol(self, pos_path):
        """Transfer protocol files (JSON, TXT, CSV) from the local position path to the remote server via SCP.

        Args:
            pos_path: Local directory containing the protocol files to transfer.
        """
        p = self._parent
        files = os.listdir(pos_path)
        f = [f for f in files if ".json" in f or ".txt" in f or ".csv" in f]
        server_path = '/mnt/imagestorage/' + pos_path[3:]+ "_maxprojection"
        for i in f:
            cmd = "scp " + os.path.join(pos_path, i) + " " + p.linux_server + ":" + server_path
            os.system(cmd)

    def send_to_server(self, pos_path):
        """Transfer the max-projection image directory to the remote Linux server via SCP.

        Creates the destination directory on the server via SSH, then copies the
        entire max-projection folder recursively.

        Args:
            pos_path: Local base path; the max-projection subfolder is derived from this.
        """
        p = self._parent
        image_local_path = os.path.join(p.maxprojection_drive,pos_path[3:] + "_maxprojection")
        server_path='/mnt/imagestorage/'+pos_path[3:] + "_maxprojection"
        cmd1 = 'ssh '+p.linux_server+ ' -vvv mkdir -p ' + server_path
        p.write_log("transfer data: "+cmd1)
        os.system(cmd1)
        cmd2 = "scp -r " + image_local_path + " " + p.linux_server + ":" + server_path
        p.write_log("transfer data: "+cmd2)
        os.system(cmd2)

    def live_view(self, img):
        """Generate a false-color composite image from 4 fluorescence channels for live display.

        Applies top-hat filtering, percentile-based denoising, and a 4-to-3 channel
        color matrix transform to produce an RGB preview image.

        Args:
            img: 4-channel image array of shape (4, H, W).
        """
        img_converted = np.array(list(map(hattop_convert, img)))
        img_converted_denoise = np.array(list(map(denoise, img_converted)))
        img_1 = np.stack((img_converted_denoise[0, :, :], img_converted_denoise[1, :, :],
                          img_converted_denoise[2, :, :], img_converted_denoise[3, :, :]), axis=-1)
        img_2 = np.reshape(img_1, (2048 * 2048, 4))
        img_3 = np.dot(img_2, color_array)
        img_4 = np.reshape(img_3, (2048, 2048, 3))
        img_4 = np.where(img_4 > 255, 255, img_4).astype('uint8')
        draw_liveview(img_4)

    def check_transfer_complete(self, disk):
        """Verify that all expected max-projection TIFF files were written to disk.

        Compares the number of .tif files in the output directory against the expected
        tile count. If complete, removes the raw acquisition folder to free space.

        Args:
            disk: Drive letter / path where max-projection files are stored.

        Returns:
            1 if all files are present, 0 otherwise.
        """
        p = self._parent
        print("check the transfer")
        file_number=len(p.maxproject_list) * len(p.zstack.substack_groups())
        disk_directory=os.path.join(disk, p.pos_path[3:]+"_maxprojection",p.cycle)
        name_pattern=".tif"
        matched_files_disk  =[1 for j in os.listdir(disk_directory) if name_pattern in j]
        if len(matched_files_disk)!=file_number:
            txt = get_time() + "maxprojection folder doesn't have enough FOV"
            print(txt)
            update_error(txt)
            p.write_log(txt)
            check = 0
        else:
             shutil.rmtree(os.path.join(p.pos_path, p.cycle), ignore_errors=True) # JON COMMENTED OUT ON 04/01 WHEN I AM GOING TO DELET THE FILES IN THE OTHER FUNCTIONS
             check = 1

        return check
