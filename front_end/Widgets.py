import time
import json
import shutil
from front_end.logwindow import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import *
from datetime import datetime
from pytz import timezone
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import tifffile as tif
import cv2
from system.fluidics_exchange_system import FluidicSystem,FluidicsConstants
from system.image_acquisition_and_analysis_system import scope
from front_end.recipe_builder import process_builder
from tkinter import ttk, StringVar,filedialog,messagebox,scrolledtext,Button
from front_end.tissue_scanner import tissue_scan
from front_end.experiment_profile import Exp_profile


def clear_canvas(canvas):
    for item in canvas.get_tk_widget().find_all():
       canvas.get_tk_widget().delete(item)
def get_time():
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time
def get_date():
    time_now = timezone('US/Pacific')
    date = str(datetime.now(time_now))[0:10]
    return date
def create_folder_file(pos_path,name):
    if not os.path.exists(os.path.join(pos_path,name)):
        os.makedirs(os.path.join(pos_path,name))

filterSize =(10, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT,  filterSize)
color_array=np.array([[0,4,4],[1.5,1.5,0],[1,0,1],[0,0,1.5]])

def hattop_convert(x):
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)
def denoise(x):
    x[x<np.percentile(x, 85)]=0
    return x
class widge_attr:
    normal_edge=3
    disable_edge = 0.9
    normal_color = '#0f0201'
    disable_color = '#bab8b8'
    warning_color='#871010'
    black_color='#0a0000'
    yellow_color="#e0c80b"


class window_widgets:
    def __init__(self,mainwindow,path):
        self.device_status = {
            "pump_group": 0,
            "selector_group": 0,
            "relay_group": 0,
            "heater_group": 0}
        self.system_path=path
        self.main=mainwindow
        self.parent_window = mainwindow
        self.auto_image = PhotoImage(file=os.path.join( self.system_path,"logo", "auto_logo.png"))
        self.manual_image = PhotoImage(file=os.path.join(self.system_path,"logo", "hand.png"))
        self.frame0 = tk.Frame(self.main, bg=self.main.cget('bg'))
        self.frame0.grid(row=0, column=0, sticky="nsew")
        self.notebook = ttk.Notebook(self.frame0)
        self.notebook.grid(row=0, column=0)


        self.auto_tab = ttk.Frame(self.notebook)
        self.manual_tab= ttk.Frame(self.notebook)
        self.notebook.add(self.auto_tab, text='Automation System',image=self.auto_image, compound=tk.LEFT)
        self.notebook.add(self.manual_tab, text='Manual System', image=self.manual_image, compound=tk.LEFT)
        ## section
        self.section1_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 1 Choose work directory",width=600)
        self.section1_lbf_auto.pack_propagate(False)
        self.section1_lbf_auto.grid(row=0, column=0, padx=3, pady=3,sticky="n")

        self.section1_lbf_manual = tk.LabelFrame(self.manual_tab, text="Section 1 Choose work directory")
        self.section1_lbf_manual.pack_propagate(False)
        self.section1_lbf_manual.grid(row=0, column=0, padx=3, pady=3, sticky="n")

        self.section2_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 2 Fill process details",width=600)
        self.section2_lbf_auto.pack_propagate(False)
        self.section2_lbf_auto.grid(row=1, column=0, padx=3, pady=3,sticky="n")

        # self.section2_lbf_manual = tk.LabelFrame(self.manual_tab, text="Section 2 Fill process details", width=600)
        # self.section2_lbf_manual.pack_propagate(False)
        # self.section2_lbf_manual.grid(row=1, column=0, padx=3, pady=3, sticky="n")

        self.section3_lbf_auto = tk.LabelFrame(self.auto_tab, text="Section 3 Automation functions", width=600)
        self.section3_lbf_auto.pack_propagate(False)
        self.section3_lbf_auto.grid(row=3, column=0, padx=3, pady=3, sticky="n")

        # self.section3_lbf_manual = tk.LabelFrame(self.manual_tab, text="Section 3 Manual functions", width=600)
        # self.section3_lbf_manual.pack_propagate(False)
        # self.section3_lbf_manual.grid(row=3, column=0, padx=3, pady=3, sticky="n")


        self.section4_addtion_note = tk.LabelFrame(self.frame0, text="Section 4 Addition notes", width=600)
        self.section4_addtion_note.pack_propagate(False)
        self.section4_addtion_note.grid(row=5, column=0, padx=3, pady=3, sticky="n")

        ##Frame

        self.frame1 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'),width=500)
        self.frame1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        # self.frame1_1 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'), width=500)
        # self.frame1_1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.frame2 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame2.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        # self.frame2_2 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'), width=500)
        # self.frame2_2.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)


        self.frame3 = tk.Frame(self.section2_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame3.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        # self.frame3_3 = tk.Frame(self.section2_lbf_manual, bg=self.main.cget('bg'), width=500)
        # self.frame3_3.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self.frame5 = tk.Frame(self.section3_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame5.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.frame6 = tk.Frame(self.section3_lbf_auto, bg=self.main.cget('bg'), width=500)
        self.frame6.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame7 = tk.Frame(self.frame0, bg=self.main.cget('bg'), width=500)
        self.frame7.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)

        ##label group
        self.work_path_lb_auto = Label(self.section1_lbf_auto, text="Select your work directory:", bd=1, relief="flat", width=20,
                                  fg=widge_attr.black_color, font=("Arial", 10))
        self.work_path_lb_manual = Label(self.section1_lbf_manual, text="Select your work directory:", bd=1, relief="flat",
                                       width=20,fg=widge_attr.black_color, font=("Arial", 10))

        self.slice_per_slide_lb_auto = Label(self.frame1, text="Slice per slide:", bd=1, relief="flat", width=15,
                                        fg=widge_attr.black_color, font=("Arial", 10))

        # self.slice_per_slide_lb_manual = Label(self.frame1_1, text="Slice per slide:", bd=1, relief="flat", width=15,
        #                                      fg=widge_attr.black_color, font=("Arial", 10))

        self.OR_lb = Label(self.frame1, text="OR", bd=1, relief="flat", width=3,
                           fg=widge_attr.black_color, font=("Arial", 10))

        self.server_account_lb_auto = Label(self.frame2, text="server account:", bd=1, relief="flat", width=10,
                                       fg=widge_attr.disable_color, font=("Arial", 10))

        self.server_lb_auto = Label(self.frame2, text="server name:", bd=1, relief="flat", width=10,
                               fg=widge_attr.disable_color, font=("Arial", 10))

        # self.server_account_lb_manual = Label(self.frame2_2, text="server account:", bd=1, relief="flat", width=10,
        #                                     fg=widge_attr.disable_color, font=("Arial", 10))
        #
        # self.server_lb_manual = Label(self.frame2_2, text="server name:", bd=1, relief="flat", width=10,
        #                             fg=widge_attr.disable_color, font=("Arial", 10))
        #
        #


        self.aws_account_lb_auto = Label(self.frame3, text="AWS account:", bd=1, relief="flat", width=12,
                                    fg=widge_attr.disable_color, font=("Arial", 10))
        self.aws_password_lb_auto = Label(self.frame3, text="AWS password:", bd=1, relief="flat", width=15,
                                     fg=widge_attr.disable_color, font=("Arial", 10))

        # self.aws_account_lb_manual = Label(self.frame3_3, text="AWS account:", bd=1, relief="flat", width=12,
        #                                  fg=widge_attr.disable_color, font=("Arial", 10))
        # self.aws_password_lb_manual = Label(self.frame3_3, text="AWS password:", bd=1, relief="flat", width=15,
        #                                   fg=widge_attr.disable_color, font=("Arial", 10))
        #
        #



        self.fill_lb=Label(self.frame5, text="Reagent:", bd=1, relief="flat", width=6,
                                     fg=widge_attr.black_color, font=("Arial", 10))

        self.focus_lb = Label(self.frame7, text="Focus shift", bd=1, relief="flat", width=15,
                             fg=widge_attr.black_color, font=("Arial", 10))
        self.align_lb = Label(self.frame7, text="XY-plane shift", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))
        self.tile_lb = Label(self.frame7, text="Tiles", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))
        self.note_lb = Label(self.section4_addtion_note, text="Notes", bd=1, relief="flat", width=15,
                              fg=widge_attr.black_color, font=("Arial", 10))

        # self.current_cycle_lb=Label(self.frame1_1, text="Current Cycle:", bd=1, relief="flat", width=15,
        #                       fg=widge_attr.black_color, font=("Arial", 10))

        #button group
        self.browse_btn_auto = Button(self.section1_lbf_auto, text="Browse", command=self.browse_handler_auto,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.exp_btn_auto = Button(self.section1_lbf_auto, text="Fill experiment detail", command=self.exp_btn_handler, width=18,
                              bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.browse_btn_manual = Button(self.section1_lbf_manual, text="Browse", command=self.browse_handler_manual,
                                      bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.exp_btn_manual = Button(self.section1_lbf_manual, text="Fill experiment detail", command=self.exp_btn_handler,
                                   width=18,bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.recipe_btn = Button(self.frame1, text="Create Protocol", command=self.recipe_btn_handler,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.info_btn_auto = Button(self.auto_tab, text="Create Your Experiment",command=self.create_exp_auto,
                               bd=widge_attr.normal_edge, fg="#1473cc")

        self.device_btn = Button(self.frame5, text="Devices configuration", command=self.config_device,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.brain_btn = Button(self.frame5, text="Tissue Scanner (optional)", command=self.scan_tissue,
                                bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.prime_btn = Button(self.frame5, text="Prime lines", command=self.prime_btn_handler,
                                bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.fill_single_btn = Button(self.frame5, text="Fill", command=self.fill_single_reagent,
                                      bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.start_sequence_btn = Button(self.frame6, text="Start Automation process",command=self.start_btn_handler,
                                         bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.cancel_sequence_btn = Button(self.frame6, text="Cancel Automation process", command=self.cancel_btn_handler,
                                          bd=widge_attr.normal_edge, fg=widge_attr.warning_color)
        self.cancel_sequence_btn['state'] = "disable"
        self.wash_btn = Button(self.frame6, text="wash tubes", command=self.wash_btn_handler,
                               bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.note_btn = Button(self.section4_addtion_note, text="Send note to server", command=self.save_to_note,
                               bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        ## Field
        self.path = tk.StringVar()
        self.work_path_field_auto = Entry(self.section1_lbf_auto, relief="groove", width=43)
        self.work_path_field_manual = Entry(self.section1_lbf_manual, relief="groove", width=35)

        self.pixel_size = tk.StringVar()
        self.pixel_size.set("0.33")
        self.pixel_size_field_auto = Entry(self.frame2, relief="groove", width=6, textvariable=self.pixel_size)
        self.pixel_size_field_auto.config(state=DISABLED)
        # self.pixel_size_field_amanual = Entry(self.frame2_2, relief="groove", width=6, textvariable=self.pixel_size)
        # self.pixel_size_field_amanual.config(state=DISABLED)

        self.slice_number_field_auto = Entry(self.frame1, relief="groove", width=10)
        #self.slice_number_field_manual = Entry(self.frame1_1, relief="groove", width=10)

        self.account = tk.StringVar()
        self.account.set("imagestorage")
        self.account_field_auto = Entry(self.frame2, relief="groove", width=15, textvariable=self.account)
        self.account_field_auto.config(state=DISABLED)
        # self.account_field_manual = Entry(self.frame2_2, relief="groove", width=15, textvariable=self.account)
        # self.account_field_manual.config(state=DISABLED)

        self.server = tk.StringVar()
        self.server.set("10.128.30.152")
        self.server_field_auto = Entry(self.frame2, relief="groove", width=20, textvariable=self.server)
        self.server_field_auto.config(state=DISABLED)
        # self.server_field_manual = Entry(self.frame2_2, relief="groove", width=20, textvariable=self.server)
        # self.server_field_manual.config(state=DISABLED)

        self.aws = tk.StringVar()
        self.aws.set("aixin.zhang@alleninstitute.org")
        self.aws_account_field_auto = Entry(self.frame3, relief="groove", width=20, textvariable=self.aws)
        self.aws_account_field_auto.config(state=DISABLED)
        # self.aws_account_field_manual = Entry(self.frame3_3, relief="groove", width=20, textvariable=self.aws)
        # self.aws_account_field_manual.config(state=DISABLED)

        self.aws_pwd = tk.StringVar()
        self.aws_pwd.set("pSQ-bitP!43_Y2i")
        self.aws_pwd_field_auto = Entry(self.frame3, relief="groove", width=20, textvariable=self.aws_pwd)
        self.aws_pwd_field_auto.config(state=DISABLED)
        # self.aws_pwd_field_manual = Entry(self.frame3_3, relief="groove", width=20, textvariable=self.aws_pwd)
        # self.aws_pwd_field_manual.config(state=DISABLED)
        ##check box
        self.mock_alignment = IntVar()
        self.mock_alignment.set(0)
        self.mock_alignment_cbox = Checkbutton(self.frame1, text="Skip Alignment",
                                               fg=widge_attr.normal_color, variable=self.mock_alignment, onvalue=1,
                                               offvalue=0)
        # self.mock_alignment_cbox_manual = Checkbutton(self.frame1_1, text="Skip Alignment",
        #                                        fg=widge_attr.normal_color, variable=self.mock_alignment, onvalue=1,
        #                                        offvalue=0)

        self.build_own_cycle_sequence_value = IntVar()
        self.build_own_cycle_sequence_value.set(0)
        self.build_own_cycle_sequence = Checkbutton(self.frame1, text="Use protocol in work directory",
                                                    fg=widge_attr.normal_color,
                                                    variable=self.build_own_cycle_sequence_value,
                                                    onvalue=1,
                                                    offvalue=0)
        self.change_pixel_value = IntVar()
        self.change_pixel_value.set(0)
        self.change_pixel_auto = Checkbutton(self.frame2, text="change pixel size", command=self.change_pixel_handler_auto,
                                        fg=widge_attr.normal_color, variable=self.change_pixel_value, onvalue=1,
                                        offvalue=0)
        # self.change_pixel_manual = Checkbutton(self.frame2_2, text="change pixel size",
        #                                      command=self.change_pixel_handler_manual,
        #                                      fg=widge_attr.normal_color, variable=self.change_pixel_value, onvalue=1,
        #                                      offvalue=0)


        self.change_server_value = IntVar()
        self.change_server_value.set(0)
        self.change_server_auto = Checkbutton(self.frame2, text="change storage server",
                                              command=self.change_server_auto,
                                              fg=widge_attr.normal_color, variable=self.change_server_value, onvalue=1,
                                              offvalue=0)
        # self.change_server_manual = Checkbutton(self.frame2_2, text="change storage server",
        #                                       command=self.change_server_manual,
        #                                       fg=widge_attr.normal_color, variable=self.change_server_value, onvalue=1,
        #                                       offvalue=0)


        self.upload_aws_value = IntVar()
        self.upload_aws_value.set(0)
        self.upload_aws_auto = Checkbutton(self.frame3, text="upload to AWS", command=self.upload_to_aws_auto,
                                      fg=widge_attr.normal_color, variable=self.upload_aws_value, onvalue=1, offvalue=0)

        self.inchamber_path = IntVar()
        self.inchamber_path.set(1)
        self.inchamber_path_cbox = Checkbutton(self.frame5, text="To chamber",
                                               fg=widge_attr.normal_color, variable=self.inchamber_path, onvalue=1,
                                               offvalue=0)

        ## Dropdown list
        self.reagent = StringVar()
        self.reagent_list_cbox = ttk.Combobox(self.frame5, textvariable=self.reagent, width=8)
        self.reagent_ls, self.reagent_dict = self.create_reagent_list()
        self.reagent_list_cbox['value'] = self.reagent_ls
        self.reagent_list_cbox['state'] = "readonly"

        # self.current_c = StringVar()
        # self.current_cbox = ttk.Combobox(self.frame1_1, textvariable=self.current_c, width=8)
        # self.current_cbox['value'] = ['geneseq', 'hyb', 'bcseq']
        # self.current_cbox['state'] = "readonly"

        ## spinner
        self.reagent_amount = Spinbox(self.frame5, from_=0.5, to=10, state="readonly", increment=0.5, width=5)
        # self.sb1_cycle_number = Spinbox(self.frame1_1, from_=0, to=50, state="readonly", width=5)
        # canvas
        self.focusfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_focus = FigureCanvasTkAgg(self.focusfigure, master=self.frame7)
        self.alignfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_align = FigureCanvasTkAgg(self.alignfigure, master=self.frame7)
        self.tilefigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_tile = FigureCanvasTkAgg(self.tilefigure, master=self.frame7)

        ## text field
        self.note_stw = scrolledtext.ScrolledText(
            master=self.section4_addtion_note,
            wrap=tk.WORD,
            width=60,
            height=2,
        )



    def browse_handler_auto(self):
        self.tempdir = self.search_for_file_path()
        self.path.set(self.tempdir)
        self.work_path_field_auto.config(textvariable=self.path)

    def browse_handler_manual(self):
        self.tempdir = self.search_for_file_path()
        self.path.set(self.tempdir)
        self.work_path_field_manual.config(textvariable=self.path)
    def search_for_file_path(self):
        self.currdir = os.getcwd()
        self.tempdir = filedialog.askdirectory(parent=self.parent_window, initialdir=self.currdir, title='Please select a directory')
        if len(self.tempdir) > 0:
            print("You chose: %s" % self.tempdir)
        return self.tempdir
    def exp_btn_handler(self):
        if self.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        else:
            work_path = self.work_path_field_auto.get()
            Exp_profile(work_path)
    def recipe_btn_handler(self):
        self.pb=process_builder()
        self.pb.create_window(self.work_path_field_auto.get())

    def change_pixel_handler_auto(self):
        if self.change_pixel_value.get() == 1:
            self.pixel_size_field_auto.config(state=NORMAL)
        else:
            t = self.pixel_size_field_auto.get()
            self.pixel_size.set(t)
            self.pixel_size_field_auto.config(state=DISABLED)

    def change_pixel_handler_manual(self):
        if self.change_pixel_value.get() == 1:
            self.pixel_size_field_manual.config(state=NORMAL)
        else:
            t = self.pixel_size_field_manual.get()
            self.pixel_size.set(t)
            self.pixel_size_field_manual.config(state=DISABLED)
    def change_server_auto(self):
       if self.change_server_value.get() == 1:
            self.server_account_lb_auto.config(fg=widge_attr.normal_color)
            self.server_lb_auto.config(fg=widge_attr.normal_color)
            self.server_field_auto["state"]="normal"
            self.account_field_auto["state"]="normal"
       else:
           self.server_account_lb_auto.config(fg=widge_attr.disable_color)
           self.server_lb_auto.config(fg=widge_attr.disable_color)
           self.server_field_auto["state"] = "disable"
           self.account_field_auto["state"] = "disable"

    def change_server_manual(self):
       if self.change_server_value.get() == 1:
            self.server_account_lb_manual.config(fg=widge_attr.normal_color)
            self.server_lb_manual.config(fg=widge_attr.normal_color)
            self.server_field_manual["state"]="normal"
            self.account_field_manual["state"]="normal"
       else:
           self.server_account_lb_manual.config(fg=widge_attr.disable_color)
           self.server_lb_manual.config(fg=widge_attr.disable_color)
           self.server_field_manual["state"] = "disable"
           self.account_field_manual["state"] = "disable"

    def upload_to_aws_auto(self):
        if self.upload_aws_value.get() == 1:
            self.aws_account_lb_auto.config(fg=widge_attr.normal_color)
            self.aws_password_lb_auto.config(fg=widge_attr.normal_color)
            self.aws_account_field_auto["state"] = "normal"
            self.aws_pwd_field_auto["state"] = "normal"
        else:
            self.aws_account_lb_auto.config(fg=widge_attr.disable_color)
            self.aws_password_lb_auto.config(fg=widge_attr.disable_color)
            self.aws_account_field_auto["state"] = "disable"
            self.aws_pwd_field_auto["state"] = "disable"
    def slice_per_slide_reformat(self):
        try:
            a = self.slice_number_field_auto.get()
            print(a)
            listOfChars = list()
            listOfChars.extend(a)
            num = [int(x) for x in listOfChars if x.isdigit()]
            self.slice_per_slide = num
        except:
            self.log_update=0
            messagebox.showinfo(title="Wrong Input", message="Slice per slide is wrong!")
            self.slice_per_slide=None


    def create_exp_auto(self):
        self.slice_per_slide_reformat()
        self.cancel = 0
        self.skip_alignment = self.mock_alignment.get()
        Log_window.warning_stw.delete('1.0', END)
        if self.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
            return
        self.pos_path = self.work_path_field_auto.get()
        if not os.path.exists(os.path.join(self.pos_path, "temp.txt")):
            open(os.path.join(self.pos_path, "temp.txt"), 'w')
        if not os.path.exists(os.path.join(self.pos_path, "log.txt")):
            open(os.path.join(self.pos_path, "log.txt"), 'w')
        self.server = self.account_field_auto.get() + "@" + self.server_field_auto.get()
        self.assign_cycle_detail()
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.scope_cfg=json.load(r)
        #try:
        self.scope = scope(self.scope_cfg,self.pos_path, self.slice_per_slide, self.server, self.skip_alignment,0,system_path=self.system_path)
        # except:
        #     messagebox.showinfo(title="Config failure ",
        #                         message="Please run micromanager first!")
        #     update_error("Please run micromanager first!")
        #     return
        self.fluidics = FluidicSystem(system_path=self.system_path,pos_path=self.pos_path)




    def assign_cycle_detail(self):
        if not os.path.exists(os.path.join(self.pos_path,"protocol.csv")):
            txt=get_time()+"couldn't find protocol.csv file, please create protocol if choose using user defined protocol!"
            update_error(txt)
            return
        df=pd.read_csv(os.path.join(self.pos_path,"protocol.csv"))
        self.process_ls=df['process'].tolist()
        check=[1 for i in self.process_ls if "imagecycle" in i]
        if sum(check)>=1:
            if not "imagecycle00" in self.process_ls:
                if not os.path.exists(os.path.join(self.pos_path,"dicfocuscycle00")):
                    for i in range(len(self.process_ls)):
                        cycle=self.process_ls[i]
                        if "imagecycle" in cycle:
                            self.process_ls.insert(i, 'imagecycle00')
                            break
        add_highlight_mainwindow("protocol has beed assigned!"+"\n")
        self.write_log("protocol has beed assigned!")

    def write_log(self, txt):
        f = open(os.path.join(self.pos_path, "log.txt"), "a")
        f.write(txt)
        f.close()

    def config_device(self):
        self.device_popup = tk.Tk()
        self.device_popup.geometry("500x170")
        self.device_popup.title("Device config")
        self.device_dropdown = ttk.Combobox(self.device_popup, width=35)
        self.device_dropdown['values'] = ["selector group","relay group","heater group","pump group"]
        self.device_dropdown.place(x=170,y=10)
        self.device_label=tk.Label(self.device_popup,text="Choose system devices:",width=20)
        self.device_label.place(x=15, y=10)
        self.device_config_button=tk.Button(self.device_popup, text="Config", command=self.config_dev)
        self.device_config_button.place(x=250,y=50)
        self.warning_dev = scrolledtext.ScrolledText(
            master=self.device_popup,
            wrap=tk.WORD,
            width=60,
            height=3,
        )
        self.warning_dev.place(x=15,y=80)
        self.warning_dev.tag_config('warning', foreground="red")
        self.warning_dev.tag_config('normal', foreground="black")

    def config_dev(self):
        device_group=self.device_dropdown.get()
        self.pos_path = self.work_path_field_auto.get()
        if self.pos_path == "":
            self.pos_path = "C://"
            self.fluidics = FluidicSystem(system_path=self.system_path,pos_path=self.pos_path)
            if not os.path.exists(os.path.join(self.pos_path, "temp.txt")):
                open(os.path.join(self.pos_path, "temp.txt"), 'w')
            if not os.path.exists(os.path.join(self.pos_path, "log.txt")):
                open(os.path.join(self.pos_path, "log.txt"), 'w')
        if "pump" in device_group:
            try:
                self.fluidics.config_pump()
                self.device_status["pump_group"]=1
                self.warning_dev.insert(END, "Pump groups works well!\n", 'normal')
                return
            except:
                self.warning_dev.insert(END, "Please, reconnect Pump groups!\n", 'warning')
                return
        if "relay" in device_group:
            try:
                self.fluidics.config_relay()
                self.device_status["relay_group"] = 1
                self.warning_dev.insert(END, "Solenoid groups works well!\n", 'normal')
            except:
                self.warning_dev.insert(END, "Please, reconnect relay groups!\n", 'warning')
                return
        if "heater" in device_group:
            try:
                self.fluidics.config_heater()
                self.device_status["heater_group"] = 1
                self.warning_dev.insert(END, "Heater groups works well!\n", 'normal')
            except:
                self.warning_dev.insert(END, "Please, reconnect heater groups!\n", 'warning')
                return
        if "selector" in device_group:
            try:
                self.fluidics.config_selector()
                self.device_status["selector_group"] = 1
                self.warning_dev.insert(END, "Selector groups works well!\n", 'normal')
            except:
                self.warning_dev.insert(END, "Please, reconnect selector groups!\n", 'warning')
                return

    def scan_tissue(self):
        scanner = tissue_scan(self.pos_path)

    def prime_btn_handler(self):
        if sum(self.device_status.values())!=len(self.device_status):
            messagebox.showinfo(title="Config device", message="Please config the device first!")
        else:
            self.all_autobtn_disable()
            self.cancel_sequence_btn['state'] = "normal"
            self.fluidics.sequenceStatus = 0
            self.fluidics.connect_pump()
            self.fluidics.connect_relay()
            self.fluidics.connect_selector()
            self.fluidics.connect_heater()
            self.fluidics.select_chamber( not FluidicsConstants.SELECT_CHAMBER_STATE)
            self.fluidics.loadSequence(self.fluidics.Fill_ALL_SEQUENCE)
            t1 = Thread(target=self.fluidics.startSequence)
            t1.start()
            txt = get_time() + "Fill reagents into tubes!\n"
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            t2 = Thread(target=self.sensor_fluidics_process)
            t2.start()
    def sensor_fluidics_process(self):
        check=self.fluidics.cycle_done
        while check!=1:
            time.sleep(2)
            check = self.fluidics.cycle_done
        txt = get_time() + "Now starting in chamber line\n"
        add_fluidics_status(txt)
        self.fluidics.select_chamber( FluidicsConstants.SELECT_CHAMBER_STATE)
        self.fluidics.setSource(self.reagent_dict["PBST"])
        self.fluidics.pumpVol(4, 1.5)
        time.sleep((float(4) / 1.5) * 60 + 5)
        txt = get_time() + "Finish in chamber line! Wash/Prime line Done!\n"
        add_highlight_mainwindow(txt)
        self.fluidics.disconnect_pump()
        self.fluidics.disconnect_relay()
        self.fluidics.disconnect_selector()
        self.fluidics.disconnect_heater()
        self.all_autobtn_normal()
        self.cancel_sequence_btn['state'] = "disable"

    def create_reagent_list(self):
        with open(os.path.join( "config_file", 'Fluidics_Reagent_Components.json'), 'r') as r:
            reagent = json.load(r)
        reagent_ls=[]
        reagent_hardwareID=[]
        for i in reagent:
            reagent_ls.append(i['solution'])
            reagent_hardwareID.append(i['name'])
        reagent_dict = dict(zip(reagent_ls, reagent_hardwareID))

        return reagent_ls,reagent_dict

    def fill_single_reagent(self):
        if sum(self.device_status.values())!=len(self.device_status):
            messagebox.showinfo(title="Config device", message="Please config the device first!\n")
        else:
            t1 = Thread(target=self.pump_reagent)
            t1.start()

    def pump_reagent(self):
        reagent = self.reagent.get()
        vol=self.reagent_amount.get()
        if reagent=="":
            add_highlight_mainwindow("Please select reagent!\n")
        else:
            self.fluidics.connect_pump()
            self.fluidics.connect_relay()
            self.fluidics.connect_selector()
            self.fluidics.connect_heater()
            self.fluidics.setSource(self.reagent_dict[reagent])
            if self.inchamber_path.get()==1:
                self.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
            else:
                self.fluidics.select_bypass(FluidicsConstants.SELECT_BYPASS_STATE)
            txt = get_time() + "fill with " + reagent + "\n"
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            self.fluidics.pumpVol(vol,1.5)
            time.sleep((float(vol)/1.5)*60 +5)
            txt = get_time() + "fill with " + reagent + " is done!\n"
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            self.fluidics.disconnect_pump()
            self.fluidics.disconnect_relay()
            self.fluidics.disconnect_selector()
            self.fluidics.disconnect_heater()

    def start_btn_handler(self):
        if sum(self.device_status.values())!=len(self.device_status):
            messagebox.showinfo(title="config", message="Please config all devis!")
        else:
            self.process_index=0
            self.process_index_limite=len(self.process_ls)-1
            self.process_cycle=self.process_ls[self.process_index]
            self.cancel=0
            self.fluidics.sequenceStatus=0
            self.check_files()
            if self.check_file==1:
                self.fluidics.connect_pump()
                self.fluidics.connect_relay()
                self.fluidics.connect_selector()
                self.fluidics.connect_heater()
                self.all_autobtn_disable()
                self.cancel_sequence_btn['state'] = 'normal'
                tt=Thread(target=self.start_sequence)
                tt.start()
            else:
                print("Missing files!")
    def cancel_btn_handler(self):
        self.cancel=1
        self.fluidics.Heatingdevice.cancel==1
        if "fluidics" in self.process_ls[self.process_index]:
            self.fluidics.cancelSequence()
        self.scope.cancel_process = 1
        txt=get_time()+"Canceled current process\n"
        add_highlight_mainwindow(txt)
        self.write_log(txt)
        self.all_autobtn_normal()
        self.cancel_sequence_btn['state'] = "disable"


    def wash_btn_handler(self):
        if sum(self.device_status.values())!=len(self.device_status):
            messagebox.showinfo(title="Config device", message="Please config the device first!")
        else:
            self.fluidics.sequenceStatus=0
            self.fluidics.connect_pump()
            self.fluidics.connect_relay()
            self.fluidics.connect_selector()
            self.fluidics.connect_heater()
            self.fluidics.select_chamber( not FluidicsConstants.SELECT_CHAMBER_STATE)
            self.fluidics.loadSequence(self.fluidics.FLUSH_ALL_SEQUENCE)
            t1 = Thread(target=self.fluidics.startSequence)
            t1.start()
            txt = get_time() + "Wash with water\n"
            add_fluidics_status(txt)
            self.write_log(txt)
            t2=Thread(target=self.sensor_fluidics_process)
            t2.start()
    def all_autobtn_disable(self):
        self.browse_btn_auto['state']="disable"
        self.browse_btn_manual['state']="disable"
        self.exp_btn_manual['state']="disable"
        self.exp_btn_auto['state']="disable"
        self.recipe_btn['state']="disable"
        self.info_btn_auto['state']="disable"
        self.device_btn['state']="disable"
        self.brain_btn['state']="disable"
        self.prime_btn['state']="disable"
        self.start_sequence_btn['state']="disable"
        self.fill_single_btn['state']="disable"

    def all_autobtn_normal(self):
        self.browse_btn_auto['state'] = "normal"
        self.browse_btn_manual['state'] = "normal"
        self.exp_btn_manual['state'] = "normal"
        self.exp_btn_auto['state'] = "normal"
        self.recipe_btn['state'] = "normal"
        self.info_btn_auto['state'] = "normal"
        self.device_btn['state'] = "normal"
        self.brain_btn['state'] = "normal"
        self.prime_btn['state'] = "normal"
        self.start_sequence_btn['state'] = "normal"
        self.fill_single_btn['state'] = "normal"
        self.cancel_sequence_btn['state'] = "normal"

    def check_files(self):
        user_define=[1 for i in self.process_ls if "user_defined" in i]
        print(user_define)
        if  sum(user_define)!=0:
            if not os.path.exists(os.path.join("reagent_sequence_file", "Fluidics_sequence_user_defined.json")):
                messagebox.showinfo(title="Config failure ",
                                    message="Please create userdefined fluidics sequence file first!")
                update_error("Please create userdefined fluidics sequence file first!")
            else:
               self.check_imagecycle00()
        else:
            self.check_imagecycle00()
    def check_imagecycle00(self):
        if "imagecycle00" in self.process_ls:
            if not os.path.exists(os.path.join(self.pos_path, "cycle00.pos")):
                messagebox.showinfo(title="Config failure ",
                                    message="Please create cycle00 coordinates first!")
                update_error("Please create cycle00 coordinates first!")
                return
            else:
                self.check_file=self.scope.check_cycle00()
        else:
            check = [1 for i in self.process_ls if "imagecycle" in i]
            if sum(check) == 0:
                self.check_file = 1
                return
            else:
                if not os.path.exists(os.path.join(self.pos_path, "dicfocuscycle00")):
                    update_error("Missing dicfocuscycle00")
                    return
                if not os.path.exists(os.path.join(self.pos_path, "pre_adjusted_pos.pos")):
                    update_error("Missing pre_adjusted_pos.pos")
                    return
                else:
                    self.check_file = 1

    def start_sequence(self):
        if self.process_index>self.process_index_limite:
            txt=get_time()+"All rounds finished!\n"
            self.write_log(txt)
            add_highlight_mainwindow(txt)
            self.fluidics.disconnect_pump()
            self.fluidics.disconnect_selector()
            self.fluidics.disconnect_relay()
            self.fluidics.disconnect_heater()
            self.all_autobtn_normal()
            self.cancel_sequence_btn['state']="disable"
            return
        self.process_cycle = self.process_ls[self.process_index]
        txt=get_time()+"start "+self.process_cycle+"\n"
        self.write_log(txt)
        add_highlight_mainwindow(txt)
        self.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
        if "Fluidics_sequence" in self.process_cycle:
            self.scope = scope(self.scope_cfg,self.pos_path, self.slice_per_slide, self.server, self.skip_alignment,0,system_path=self.system_path)
            self.scope.move_to_fluidics()
            try:
                self.protocol=self.fluidics.find_protocol(self.process_cycle)
            except:
                self.fluidics.disconnect_pump()
                self.fluidics.disconnect_selector()
                self.fluidics.disconnect_relay()
                self.fluidics.disconnect_heater()
                self.all_autobtn_normal()
                self.cancel_sequence_btn['state'] = "disable"
                messagebox.showinfo(title="Protocol issue", message="check protocol file, the format is wrong")
                return
            t = Thread(target=self.run_fluidics_cycle(self.protocol))
            t.start()
            check = self.fluidics.start_image
            while check != 1:
                if self.cancel==1:
                    break
                time.sleep(2)
                check = self.fluidics.start_image
            self.process_index = self.process_index + 1
            if self.cancel!=1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        elif "imagecycle00" in self.process_cycle:
            self.scope=scope(self.scope_cfg,self.pos_path, self.slice_per_slide, self.server, self.skip_alignment,0,system_path=self.system_path)
            self.scope.move_to_image()
            self.scope.cancel_process = 0
            self.current_cycle = "imagecycle00"
            t = Thread(target=self.do_focus_thread)
            t.start()
            check=self.scope.focus_status
            while check != 1 :
                if self.cancel == 1:
                    break
                time.sleep(2)
                check = self.scope.focus_status
            self.process_index = self.process_index + 1
            if self.cancel!=1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        else:
            self.scope=scope(self.scope_cfg,self.pos_path, self.slice_per_slide, self.server, self.skip_alignment,0,system_path=self.system_path)
            self.scope.move_to_image()
            self.scope.cancel_process = 0
            self.current_cycle = self.process_cycle[11:]
            self.image_auto()
            check = self.scope.max_projection_status
            while check != 1 :
                if self.cancel == 1:
                    break
                time.sleep(2)
                check = self.scope.max_projection_status
            self.process_index = self.process_index + 1
            if self.cancel!=1:
                time.sleep(10)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
    def check_focus_file(self,path,file,msg):
        if not os.path.exists(os.path.join(path,file)):
            txt=get_time()+msg
            self.write_log(txt)
            update_error(txt)
            Pass=0
        else:
            Pass=1
        print(Pass)
        return Pass


    def do_focus_thread(self):
        if "00" in self.current_cycle:
            create_folder_file(self.pos_path, "dicfocuscycle00")
            create_folder_file(self.pos_path, "focuscycle00")
            check=self.check_focus_file(self.pos_path,"cycle00.pos","Missing cycle00.pos")
            if check==0:
                return
            else:
                self.focus_poslist = self.scope.pos_to_csv(self.current_cycle)
                diff = self.scope.focus_image("cycle00", self.focus_poslist)
        else:
            check = self.check_focus_file(self.pos_path, "dicfocuscycle00", " Abort, no archor coordinates folder found!")
            if check == 0:
                return
            else:
                status = self.check_focus_file(self.pos_path, "pre_adjusted_pos.pos"," Abort, no pre adjusted coordinate for current cycle!")
                if status ==0:
                    return
                else:
                    create_folder_file(self.pos_path, "dicfocus"+self.current_cycle)
                    create_folder_file(self.pos_path, "focus"+self.current_cycle)
                    with open(os.path.join(self.pos_path, "pre_adjusted_pos.pos")) as f:
                        d = json.load(f)
                    shutil.copy(os.path.join(self.pos_path, "pre_adjusted_pos.pos"), os.path.join(self.pos_path, self.current_cycle+".pos"))
                    self.focus_poslist = self.scope.pos_to_csv(self.current_cycle)
                    diff = self.scope.focus_image(self.current_cycle, self.focus_poslist)
        try:
            plot1 = self.focusfigure.add_subplot(111)
            plot1.plot(diff)
            plot1.axhline(y=20, color='r')
            plot1.axhline(y=-20, color='r')
            plot1.get_xaxis().set_visible(False)
            plot1.get_yaxis().set_visible(False)
            self.canvas_focus.draw()
            update_process_bar(0)
            update_process_label("Process")
            os.chdir(self.system_path)
        except:
            os.chdir(self.system_path)
            txt=get_time()+"focus is wrong or cancelled"
            update_error(txt)
    def image_auto(self):
        if self.cancel==1:
            pass
        else:
            self.do_focus_thread()
            self.align_and_draw_thread()
            self.tile_and_draw_thread()
        if self.cancel == 1:
            pass
        else:
            t1 = Thread(target=self.maxprojection_thread)
            t1.start()
            t2 = Thread(target=self.plot_live_view_thread)
            t2.start()

    def align_and_draw_thread(self):
        if "00" in self.current_cycle:
            add_highlight_mainwindow("Cycle 00 doesn't need to run alignment!")
        else:
            self.scope.do_alignment(self.current_cycle)
            try:
                uniqslidenum = np.unique(self.scope.slidenum)
                data=pd.DataFrame(columns=['x', 'y', 'slidenum'])
                for i in uniqslidenum:
                    data1 = pd.DataFrame(columns=['x', 'y', 'slidenum'])
                    data1['x'] = np.round((self.scope.x_offset[np.where(self.scope.slidenum == i)]))
                    data1['y'] = np.round((self.scope.y_offset[np.where(self.scope.slidenum == i)]))
                    data1['slidenum'] = str(i)
                    data = pd.concat([data, data1], ignore_index=True)
                groups = data.groupby('slidenum')
                plot2 = self.alignfigure.add_subplot(111)
                for name, group in groups:
                    plot2.scatter(group.x, group.y, marker='o')
                plot2.set(ylim=(-200, 200))
                plot2.set(xlim=(-200, 200))
                self.canvas_align.draw()
            except:
                txt=get_time()+"Aligmen is wrong or cancelled"
                update_error(txt)

    def tile_and_draw_thread(self):
        self.scope.make_tile(self.current_cycle)
        txt = get_time() + "created tiles for " + self.current_cycle + "\n"
        add_highlight_mainwindow(txt)
        df = pd.read_csv(os.path.join(self.pos_path, 'tiledregoffset' + self.current_cycle + '.csv'))
        plot3 = self.tilefigure.add_subplot(111)
        plot3.scatter(df['X'],df['Y'],c='hotpink',s=4)
        plot3.axis('scaled')
        plot3.get_xaxis().set_visible(False)
        plot3.get_yaxis().set_visible(False)
        self.canvas_tile.draw()


    def upload_aws(self):
        if self.upload_aws_value.get() == 1:
            self.aws_account_lb.config(fg=widge_attr.normal_color)
            self.aws_password_lb.config(fg=widge_attr.normal_color)
            self.aws_account_field["state"] = "normal"
            self.aws_pwd_field["state"] = "normal"
        else:
            self.aws_account_lb.config(fg=widge_attr.disable_color)
            self.aws_password_lb.config(fg=widge_attr.disable_color)
            self.aws_account_field["state"] = "disable"
            self.aws_pwd_field["state"] = "disable"

    def maxprojection_thread(self):
        df = pd.read_csv(os.path.join(self.pos_path, 'tiledregoffset' + self.current_cycle + '.csv'))
        self.max_name_ls = df['switched_Posinfo']
        self.scope.image_and_maxprojection(self.current_cycle)
        os.chdir(self.system_path)

    def plot_live_view_thread(self):
        name = self.scope.maxprojection_name
        while name != 'end' and self.cancel != 1:
            if name != '':
                self.plot_maxprojection_liveview(name)
            time.sleep(20)
            name = self.scope.maxprojection_name
        txt = get_time() + "max_projection_finished!"
        add_highlight_mainwindow(txt)

    def plot_maxprojection_liveview(self, name):
        disk = self.scope.maxprojection_drive
        server_name = self.current_cycle + '.tif'
        plot1 = Log_window.livefigure.add_subplot(111)
        img = tif.imread(os.path.join(disk, self.pos_path[3:] + "_maxprojection", name, server_name))
        img_converted = np.array(list(map(hattop_convert, img)))
        img_converted_denoise = np.array(list(map(denoise, img_converted)))
        img_1 = np.stack((img_converted_denoise[0, :, :], img_converted_denoise[1, :, :],
                          img_converted_denoise[2, :, :], img_converted_denoise[3, :, :]), axis=-1)
        img_2 = np.reshape(img_1, (2048 * 2048, 4))
        img_3 = np.dot(img_2, color_array)
        img_4 = np.reshape(img_3, (2048, 2048, 3))
        img_4 = np.where(img_4 > 255, 255, img_4).astype('uint8')
        plot1.imshow(img_4[500:1200, 500:1200, :])
        plot1.get_xaxis().set_visible(False)
        plot1.get_yaxis().set_visible(False)
        Log_window.canvas_live.draw()

    def upload_aws_handler(self):
        pass
    def run_fluidics_cycle(self,sequence):
        self.fluidics.loadSequence(sequence)
        self.fluidics.startSequence()

    def save_to_note(self):
        if not os.path.exists(os.path.join(self.pos_path, "experiment_detail.txt")):
            open(os.path.join(self.pos_path, "experiment_detail.txt"), 'a').close()
        txt=get_time()+self.note_stw.get("1.0", "end-1c")+"\n"
        f = open(os.path.join(self.pos_path, "experiment_detail.txt"), "a")
        f.write(txt)
        f.close()
        server_path = '/mnt/imagestorage/' + self.pos_path[3:]
        self.linux_server=self.server
        try:
            cmd = "scp " + os.path.join(self.pos_path, "experiment_detail.txt") + " " + self.linux_server + ":" + server_path
            os.system(cmd)
            txt = get_time() + "local note saved to experiment_detail.txt, and uploaded to server!"+"\n"
            add_highlight_mainwindow(txt)

        except:
            txt=get_time()+"local note saved to experiment_detail.txt, upload to server is failed!"
            add_highlight_mainwindow(txt)




