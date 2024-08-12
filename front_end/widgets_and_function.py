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

system_path=os.getcwd()

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


def get_position(pos):
    position_name = pos['Device']['scalar']
    position_value = pos['Position_um']['array']
    if position_name == 'ZDrive':
        return {'z': position_value[0]}
    elif position_name == 'XYStage':
        return {'x': position_value[0], 'y': position_value[1]}
    else:
        return None


def get_position_piezo(pos):
    position_name = pos['Device']['scalar']
    position_value = pos['Position_um']['array']
    if position_name == 'ZDrive':
        return {'z': position_value[0]}
    elif position_name == 'XYStage':
        return {'x': position_value[0], 'y': position_value[1]}
    elif position_name == 'DA Z Stage':
        return {'piezo': position_value[0]}
    else:
        pass
def get_position(pos):
    position_name = pos['Device']['scalar']
    position_value = pos['Position_um']['array']
    if position_name == 'ZDrive':
        return {'z': position_value[0]}
    elif position_name == 'XYStage':
        return {'x': position_value[0], 'y': position_value[1]}
    else:
        pass
def get_pos_data(item):
    positions = item['DevicePositions']['array']
    pos_data = {}
    for pos in positions:
        pos_data.update(get_position_piezo(pos)) #change to get_position_piezo(pos) if have piezo, get_position(pos) if you don't use piezo
    pos_data.update({'position': item['Label']['scalar']})
    return pos_data

def create_folder_file(pos_path,name):
    if not os.path.exists(os.path.join(pos_path,name)):
        os.makedirs(os.path.join(pos_path,name))

def copy_dic(pos_path,cycle):
    directory = os.listdir(os.path.join(pos_path,cycle))

class widge_attr:
    normal_edge=3
    disable_edge = 0.9
    normal_color = '#0f0201'
    disable_color = '#bab8b8'
    warning_color='#871010'
    black_color='#0a0000'
    yellow_color="#e0c80b"

filterSize =(10, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT,  filterSize)
color_array=np.array([[0,4,4],[1.5,1.5,0],[1,0,1],[0,0,1.5]])

def hattop_convert(x):
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)
def denoise(x):
    x[x<np.percentile(x, 85)]=0
    return x
class window_widgets:
    def __init__(self, mainwindow=None):
        self.check_file = 0
        self.process_index=0
        self.cancel=0
        #lableframe
        self.section1_lbf=tk.LabelFrame(mainwindow, text="Section 1",width=300, height=100)
        self.section1_lbf.pack_propagate(False)
        #Button group
        self.parent_window=mainwindow
        self.recipe_btn = Button(mainwindow, text="Recipe Builder", command=self.recipe_btn_handler,
                               bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.recipe_btn["state"] = "disable"
        self.info_btn=Button(mainwindow, text="Step 1 Create Your Experiment", command=self.info_btn_handler,
               bd=widge_attr.normal_edge, fg="#1473cc")
        self.focus_btn=Button(mainwindow, text="Step 2 Focus", command=self.focus_btn,
               bd=widge_attr.normal_edge, fg="#1473cc")
        self.focus_btn["state"] = "disable"
        self.align_btn=Button(mainwindow, text="Step 3 Align", command=self.align_btn_handler,
            bd=widge_attr.normal_edge, fg="#1473cc")
        self.align_btn["state"] = "disable"
        self.tile_btn=Button(mainwindow, text="Step 4 Creat Tiles", command=self.tile_btn_handler,
            bd=widge_attr.normal_edge, fg="#1473cc")
        self.tile_btn["state"] = "disable"
        self.max_btn=Button(mainwindow, text="Step 5 Image and Maxproject", command=self.max_btn_handler,
            bd=widge_attr.normal_edge, fg="#1473cc")
        self.max_btn["state"] = "disable"
        self.wash_btn=Button(mainwindow, text="wash tubes", command=self.wash_btn_handler,
            bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.wash_btn["state"] = "disable"
        self.prime_btn=Button(mainwindow, text="Prime tubes", command=self.prime_btn_handler,
            bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.prime_btn["state"]="disable"
        self.cancel_sequence_btn=Button(mainwindow, text="Cancel Automation process", command=self.cancel_btn_handler,
            bd=widge_attr.normal_edge, fg=widge_attr.warning_color)
        self.cancel_sequence_btn["state"]="disable"
        self.start_sequence_btn=Button(mainwindow, text="Start Automation process", command=self.start_btn_handler,
            bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.start_sequence_btn["state"]="disable"
        self.browse_btn=Button(mainwindow, text="Browse", command=self.browse_handler,
            bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        self.cancle_image_btn = Button(mainwindow, text="Cancel image process", command=self.cancel_manual_process,
                                 bd=widge_attr.normal_edge, fg=widge_attr.warning_color)
        self.cancle_image_btn["state"] = "disable"

        self.fill_single_btn = Button(mainwindow, text="Fill single reagent", command=self.fill_single_reagent,
                                       bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.fill_single_btn["state"] = "disable"

        self.device_btn = Button(mainwindow, text="Devices configuration", command=self.config_device,
                                      bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.device_btn["state"] = "disable"

        self.brain_btn = Button(mainwindow, text="Tissue Scanner", command=self.scan_tissue,
                                 bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.brain_btn["state"] = "disable"
        self.savenote_btn = Button(mainwindow, text="Save to note", command=self.save_to_note,
                                bd=widge_attr.normal_edge, fg=widge_attr.normal_color)
        self.savenote_btn["state"] = "disable"
        self.exp_btn = Button(mainwindow, text="Fill experiment detail", command=self.exp_btn_handler, width=18,
                              bd=widge_attr.normal_edge, fg=widge_attr.normal_color)

        ##Lable group
        self.OR_lb = Label(mainwindow, text="OR", bd=1, relief="flat", width=3,
                                   fg=widge_attr.black_color, font=("Arial", 10))
        self.warning_lb = Label(mainwindow, text="System warning", bd=1, relief="groove", width=15,
                           fg=widge_attr.warning_color, font=("Arial", 10))
        self.note_lb = Label(mainwindow, text="Note to log", bd=1, relief="groove", width=15,
                                fg=widge_attr.black_color, font=("Arial", 10))
        self.notification_lb = Label(mainwindow, text="System Notification", bd=1, relief="groove", width=15,
                                fg=widge_attr.black_color, font=("Arial", 10))
        self.live_lb = Label(mainwindow, text="Live View", bd=1, relief="groove", width=15, fg=widge_attr.black_color,
                           font=("Arial", 10))
        self.auto_label_area = Label(mainwindow, text="AUTOMATION FUNCTIONS:", bd=1, relief="flat", width=25,
                                fg="#f0850c", font=("Arial", 10))
        self.manual_label_area = Label(mainwindow, text="Manual Functions:", bd=1, relief="flat", width=13,
                                  fg=widge_attr.yellow_color, font=("Arial", 10))
        self.work_path_lb=Label(mainwindow, text="Select your work directory:", bd=1, relief="flat", width=20,
                           fg=widge_attr.black_color, font=("Arial", 10))

        self.current_cycle_lb=Label(mainwindow, text="Current cycle and number:", bd=1, relief="flat", width=19,
                                    fg=widge_attr.black_color, font=("Arial", 10))
        self.cycle_num_lb=Label(mainwindow, text="Current cycle number:", bd=1, relief="flat", width=18,
                                fg=widge_attr.black_color, font=("Arial", 10))

        self.aws_account_lb=Label(mainwindow, text="AWS account:", bd=1, relief="flat", width=12,
                                     fg=widge_attr.disable_color, font=("Arial", 10))
        self.aws_password_lb = Label(mainwindow, text="AWS password:", bd=1, relief="flat", width=15,
                               fg=widge_attr.disable_color, font=("Arial", 10))

        self.slice_per_slide_lb = Label(mainwindow, text="Slice per slide:", bd=1, relief="flat", width=15,
                                   fg=widge_attr.black_color, font=("Arial", 10))
        self.server_account_lb=Label(mainwindow, text="server account:", bd=1, relief="flat", width=15,
                                     fg=widge_attr.disable_color, font=("Arial", 10))
        self.server_lb=Label(mainwindow, text="server name:", bd=1, relief="flat", width=15,
                             fg=widge_attr.disable_color, font=("Arial", 10))

        ## checkbox group
        self.change_pixel_value=IntVar()
        self.change_pixel_value.set(0)
        self.change_pixel = Checkbutton(mainwindow, text="change pixel size", command=self.change_pixel_handler,
                           fg=widge_attr.normal_color, variable=self.change_pixel_value,onvalue=1,offvalue=0)

        self.upload_aws_value = IntVar()
        self.upload_aws_value.set(0)
        self.upload_aws = Checkbutton(mainwindow, text="upload to AWS", command=self.upload_aws,
                                 fg=widge_attr.normal_color, variable=self.upload_aws_value, onvalue=1, offvalue=0)
        self.change_server_value = IntVar()
        self.change_server_value.set(0)
        self.change_server = Checkbutton(mainwindow, text="change storage server", command=self.change_server,
                                    fg=widge_attr.normal_color, variable=self.change_server_value, onvalue=1, offvalue=0)

        self.build_own_cycle_sequence_value = IntVar()
        self.build_own_cycle_sequence_value.set(0)
        self.build_own_cycle_sequence = Checkbutton(mainwindow, text="Use user designed recipe",command=self.build_own,
                                            fg=widge_attr.normal_color, variable=self.build_own_cycle_sequence_value,
                                            onvalue=1,
                                            offvalue=0)

        self.build_own_cycle_sequence["state"] = "disable"
        self.mock_alignment= IntVar()
        self.mock_alignment.set(0)
        self.mock_alignment_cbox = Checkbutton(mainwindow, text="Skip Alignment",
                                      fg=widge_attr.normal_color, variable=self.mock_alignment, onvalue=1, offvalue=0)

        ## radio button group
        self.mychioce = StringVar()
        self.mychioce.set("manual")
        self.auto_image = PhotoImage(file=os.path.join(system_path, "logo", "auto_logo.png"))
        self.manual_image = PhotoImage(file=os.path.join(system_path, "logo", "hand.png"))
        self.Auto_rbtn = Radiobutton(mainwindow, text="Barseq Automation System", value="BAS", command=self.BAS_check_handler,
                                variable=self.mychioce, width=200, height=50, bd=3, image=self.auto_image, compound="left")
        self.mannual_rbtn = Radiobutton(mainwindow, text="Barseq Manual Aid System", value="manual",
                                   command=self.manual_check_handler, variable=self.mychioce, width=300, height=50, bd=3,
                                   image=self.manual_image, compound="left")
        ## Field
        self.path = tk.StringVar()
        self.work_path_field = Entry(mainwindow, relief="groove", width=35)
        self.pixel_size = tk.StringVar()
        self.pixel_size.set("0.33")
        self.pixel_size_field = Entry(mainwindow, relief="groove", width=6, textvariable=self.pixel_size)
        self.pixel_size_field.config(state=DISABLED)

        self.account = tk.StringVar()
        self.account.set("imagestorage")
        self.account_field = Entry(mainwindow, relief="groove", width=15, textvariable=self.account)
        self.account_field.config(state=DISABLED)

        self.slice_number_field=Entry(mainwindow, relief="groove", width=10)

        self.server = tk.StringVar()
        self.server.set("barseqstorage3-ux1")
        self.server_field = Entry(mainwindow, relief="groove", width=20, textvariable=self.server)
        self.server_field.config(state=DISABLED)

        self.aws = tk.StringVar()
        self.aws.set("aixin.zhang@alleninstitute.org")
        self.aws_account_field = Entry(mainwindow, relief="groove", width=20, textvariable=self.aws)
        self.aws_account_field.config(state=DISABLED)

        self.aws_pwd = tk.StringVar()
        self.aws_pwd.set("pSQ-bitP!43_Y2i")
        self.aws_pwd_field = Entry(mainwindow, relief="groove", width=20, textvariable=self.aws_pwd)
        self.aws_pwd_field.config(state=DISABLED)
        ## txt filed
        self.note_stw = scrolledtext.ScrolledText(
            master=mainwindow,
            wrap=tk.WORD,
            width=106,
            height=2,
        )
        ##combo box


        self.reagent = StringVar()
        self.reagent_list_cbox = ttk.Combobox(mainwindow, textvariable=self.reagent, width=15)
        self.reagent_ls,self.reagent_dict=self.create_reagent_list()
        self.reagent_list_cbox['value'] = self.reagent_ls
        self.reagent_list_cbox['state'] = "readonly"


        self.current_c = StringVar()
        self.current_cbox = ttk.Combobox(mainwindow, textvariable=self.current_c, width=8)
        self.current_cbox['value'] = ['geneseq', 'hyb', 'bcseq']
        self.current_cbox['state'] = "readonly"

        ## spin box
        self.sb1_cycle_number = Spinbox(mainwindow, from_=0, to=50, state="readonly", width=5)
        self.reagent_amount = Spinbox(mainwindow, from_=0.5, to=10, state="readonly", increment=0.5,width=5)



        # canvas
        self.focusfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_focus = FigureCanvasTkAgg(self.focusfigure, master=mainwindow)
        self.alignfigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_align = FigureCanvasTkAgg(self.alignfigure, master=mainwindow)
        self.tilefigure = plt.Figure(figsize=(2.5, 2.5), dpi=100)
        self.canvas_tile = FigureCanvasTkAgg(self.tilefigure, master=mainwindow)
        self.livefigure = plt.Figure(figsize=(5, 5), dpi=100)
        self.livefigure.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.99, wspace=0, hspace=0)
        self.canvas_live = FigureCanvasTkAgg(self.livefigure, master=mainwindow)

        self.device_status = {
            "pump_group": 0,
            "selector_group": 0,
            "relay_group": 0,
            "heater_group": 0}
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


    def config_device(self):
        self.device_popup = tk.Tk()
        self.device_popup.geometry("500x170")
        self.device_popup.title("Device config")
        self.device_dropdown = ttk.Combobox(self.device_popup, width=35)
        self.device_dropdown['values'] = ["pump group","relay group","heater group","selector group"]
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
        print(device_group)
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

    def exp_btn_handler(self):
        if self.work_path_field.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        work_path = self.work_path_field.get()
        Exp_profile(work_path)
    def build_own(self):
        if self.build_own_cycle_sequence_value.get() == 1:
            self.recipe_btn["state"]="disable"
        else:
            self.recipe_btn["state"] = "normal"

    def create_reagent_list(self):
        with open(os.path.join(system_path, "config_file", 'Fluidics_Reagent_Components.json'), 'r') as r:
            reagent = json.load(r)
        reagent_ls=[]
        reagent_hardwareID=[]
        for i in reagent:
            reagent_ls.append(i['solution'])
            reagent_hardwareID.append(i['name'])
        reagent_dict = dict(zip(reagent_ls, reagent_hardwareID))

        return reagent_ls,reagent_dict

    def slice_per_slide_reformat(self):
        try:
            a=self.slice_number_field.get()
            listOfChars = list()
            listOfChars.extend(a)
            num = [int(x) for x in listOfChars if x.isdigit()]
            self.slice_per_slide = num
        except:
            self.log_update=0
            messagebox.showinfo(title="Wrong Input", message="Slice per slide is wrong!")

    def auto_button_disable(self):
        self.device_btn["state"] = "disable"
        self.info_btn["state"] = "disable"
        self.wash_btn["state"] = "disable"
        self.prime_btn["state"] = "disable"
        self.start_sequence_btn["state"] = "disable"
        self.fill_single_btn["state"] = "disable"
        self.build_own_cycle_sequence["state"] = "disable"
        #self.device_config_button["state"] = "disable"
    def auto_button_able(self):
        self.info_btn["state"] = "normal"
        self.device_btn["state"]="normal"
        self.wash_btn["state"] = "normal"
        self.prime_btn["state"] = "normal"
        self.start_sequence_btn["state"] = "normal"
        self.fill_single_btn["state"] = "normal"
        self.cancel_sequence_btn["state"] = "normal"

    def manual_button_disable(self):
        self.info_btn["state"] = "disable"
        self.focus_btn["state"] = "disable"
        self.align_btn["state"] = "disable"
        self.tile_btn["state"] = "disable"
        self.max_btn["state"] = "disable"

    def manual_button_able(self):
        self.info_btn["state"] = "normal"
        self.focus_btn["state"] = "normal"
        self.align_btn["state"] = "normal"
        self.tile_btn["state"] = "normal"
        self.max_btn["state"] = "normal"
    def info_btn_handler(self):
        self.slice_per_slide_reformat()
        if self.mychioce.get() == "manual":
            clear_error()
            self.focus_btn["state"] = "normal"
            self.align_btn["state"] = "normal"
            self.tile_btn["state"] = "normal"
            self.max_btn["state"] = "normal"
            self.cancle_image_btn['state']="normal"
            self.savenote_btn['state']="normal"
            self.recipe_btn["state"] = "disable"
            self.auto_button_disable()
            self.build_own_cycle_sequence["state"] = "disable"
            #self.device_config_button["state"] = "disable"
            self.cycle_number = self.sb1_cycle_number.get()
            self.current_cycle = self.current_c.get()+self.sb1_cycle_number.get().zfill(2)
            self.pos_path=self.work_path_field.get()
            self.protocol_list_index=0
            self.skip_alignment=self.mock_alignment.get()
            self.server = self.account_field.get() + "@" + self.server_field.get()
            if self.work_path_field.get()=="":
                messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
                return
            self.brain_btn["state"] = "normal"
            if self.current_c.get() == "":
                messagebox.showinfo(title="Wrong Input", message="current cycle type can't be empty")
                return
            if self.slice_number_field.get() == "":
                messagebox.showinfo(title="Wrong Input", message="slice per slide can't be empty")
                return
            self.protocol_list=[self.current_cycle]
            if "00" in self.current_cycle:
                self.align_btn["state"] = "disable"
                self.tile_btn["state"] = "disable"
                self.max_btn["state"] = "disable"
            if not os.path.exists(os.path.join(self.pos_path,"log.txt")):
                open(os.path.join(self.pos_path, "log.txt"), 'a').close()
            print(self.slice_per_slide)
            self.scope=scope(self.pos_path,self.slice_per_slide,self.server,self.skip_alignment)
            txt=get_time()+"\n"+"work directory: "+self.pos_path+"\n"+"Current cycle: "+self.protocol_list[self.protocol_list_index]+"\n"
            print(txt)
            self.write_log(txt)
            add_highlight_mainwindow(txt)
            if not os.path.exists(os.path.join(self.pos_path, "manual_process_record.csv")):
                df = pd.DataFrame(columns=["protocol"])
                df["protocol"] = "imagecycle_"+self.current_cycle
                df.to_csv(os.path.join(self.pos_path, "manual_process_record.csv"), index=False)
            else:
                df = pd.read_csv(os.path.join(self.pos_path, "manual_process_record.csv"))
                df.loc[len(df.index)] = ["imagecycle_"+self.current_cycle]
                df.to_csv(os.path.join(self.pos_path, "manual_process_record.csv"), index=False)
            self.scope.move_to_image()
        else:
            self.cancel = 0
            self.skip_alignment = self.mock_alignment.get()
            Log_window.warning_stw.delete('1.0', END)
            if self.work_path_field.get() == "":
                messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
                return
            self.brain_btn["state"] = "normal"
            self.pos_path = self.work_path_field.get()
            if not os.path.exists(os.path.join(self.pos_path, "temp.txt")):
                open(os.path.join(self.pos_path, "temp.txt"), 'w')
            if not os.path.exists(os.path.join(self.pos_path, "log.txt")):
                open(os.path.join(self.pos_path, "log.txt"), 'w')
            self.assign_cycle_detail()
            try:
                self.scope = scope(self.pos_path, self.slice_per_slide,self.server,self.skip_alignment)
            except:
                messagebox.showinfo(title="Config failure ",
                                    message="Please run micromanager first!")
                update_error("Please run micromanager first!")
                return
            self.fluidics=FluidicSystem(self.pos_path)
            self.savenote_btn['state']='normal'
            self.auto_button_able()
            self.cancel_sequence_btn['state']='normal'
            self.skip_alignment = self.mock_alignment.get()
            self.server=self.account_field.get()+"@"+self.server_field.get()



    def assign_cycle_detail(self):
        if not os.path.exists(os.path.join(self.pos_path,"recipe.csv")):
            txt=get_time()+"couldn't find recipe.csv file, please create recipe if choose using user defined recipe!"
            update_error(txt)
            return
        df=pd.read_csv(os.path.join(self.pos_path,"recipe.csv"))
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
        add_highlight_mainwindow("recipe has beed assigned!"+"\n")
        self.write_log("recipe has beed assigned!")




    def check_imagecycle00(self):
        if "imagecycle00" in self.process_ls:
            if not os.path.exists(os.path.join(self.pos_path, "cycle00.pos")):
                messagebox.showinfo(title="Config failure ",
                                    message="Please create cycle00 coordinates first!")
                update_error("Please create cycle00 coordinates first!")
                return
            with open(os.path.join(self.pos_path, "cycle00.pos")) as f:
                d = json.load(f)
            try:
                focus_poslist = pd.DataFrame([get_pos_data(item) for item in d['map']['StagePositions']['array']])[
                    ['position', 'x', 'y', 'z', 'piezo']] # add "piezo" ino column ['position', 'x', 'y', 'z', 'piezo'] if we have piezo, remove 'piezo' if no piezo
            except:
                messagebox.showinfo(title="Load position failure ",
                                    message="Current position missing coordinates from piezo!")
                return
            if len(focus_poslist) != sum(self.slice_per_slide) * 4:
                messagebox.showinfo(title="Config failure ",
                                    message="Slice per slide is not consistent with number of FOV!")
                update_error("Slice per slide is not consistent with number of FOV!")
                return
            self.check_file=1
        else:
            check = [1 for i in self.process_ls if "imagecycle" in i]
            if sum(check) == 0:
                self.check_file = 1
                return
            else:
                if not os.path.exists(os.path.join(self.pos_path, "pre_adjusted_pos.pos")):
                    messagebox.showinfo(title="Config failure ",
                                        message="Missing pre_adjusted_pos.pos!")
                    update_error("Missing pre_adjusted_pos.pos!")
                    return
                else:
                    self.check_file = 1



    def check_files(self):
        if  sum([1 for i in self.process_ls if "user_defined" in i])!=0:
            if not os.path.exists(os.path.join(system_path,"reagent_sequence_file", "Fluidics_sequence_user_defined.json")):
                messagebox.showinfo(title="Config failure ",
                                    message="Please create userdefined fluidics sequence file first!")
                update_error("Please create userdefined fluidics sequence file first!")
            else:
               self.check_imagecycle00()
        else:
            self.check_imagecycle00()



    def write_log(self,txt):
        f = open(os.path.join(self.pos_path,"log.txt"), "a")
        f.write(txt)
        f.close()

    def focus_btn(self):
        self.scope.cancel_process = 0
        clear_error()
        t = Thread(target=self.do_focus_thread)
        t.start()



    def align_and_draw_thread(self):
        if "00" in self.current_cycle:
            add_highlight_mainwindow("Cycle 00 doesn't need to run alignment!")
        else:
            self.manual_button_disable()
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
                self.manual_button_able()
            except:
                txt=get_time()+"Aligmen is wrong or cancelled"
                update_error(txt)



    def check_file(self,path,file,warning):
        if not os.path.exists(os.path.join(path, file)):
            txt = get_time() + warning
            update_error(txt)
            self.write_log(txt)
            status=0
        else:
            status=1
        return status

    def focus_check(self,path,file,message):
        if not os.path.exists(os.path.join(path,file)):
            txt=get_time()+message
            self.write_log(txt)
            update_error(txt)



    def do_focus_thread(self):
        if "Hyb" in self.current_cycle:
            focus_channel=["DIC"]
            target_channel="DIC"
        else:
            focus_channel = ["DIC"] #change here if focus on different channel
            target_channel = "DIC"
        if "00" in self.current_cycle:
            status=self.focus_check(self.pos_path,"cycle00.pos"," Abort, no archor coordinates found!")
            if status==0:
                return
            else:
                create_folder_file(self.pos_path, "dicfocuscycle00")
                create_folder_file(self.pos_path, "focuscycle00")
                self.focus_poslist=self.scope.pos_to_csv(self.current_cycle)
                diff=self.scope.focus_image("cycle00",self.focus_poslist,target_channel,focus_channel)
        else:
            status = self.focus_check(self.pos_path,"dicfocuscycle00" , " Abort, no archor coordinates folder found!")

            if status==0:
                return
            else:
                status = self.focus_check(self.pos_path, "pre_adjusted_pos.pos"," Abort, no pre adjusted coordinate for current cycle!")
                if status ==0:
                    return
                else:
                    create_folder_file(self.pos_path, "dicfocus"+self.current_cycle)
                    create_folder_file(self.pos_path, "focus"+self.current_cycle)
                    with open(os.path.join(self.pos_path, "pre_adjusted_pos.pos")) as f:
                        d = json.load(f)
                    shutil.copy(os.path.join(self.pos_path, "pre_adjusted_pos.pos"), os.path.join(self.pos_path, self.current_cycle+".pos"))
                    self.focus_poslist =pd.DataFrame([get_pos_data(item) for item in d['map']['StagePositions']['array']])[
                    ['position', 'x', 'y', 'z','piezo']] # add "piezo" ino column ['position', 'x', 'y', 'z', 'piezo'] if we have piezo, remove 'piezo' if no piezo

                    self.focus_poslist.to_csv(os.path.join(self.pos_path, self.current_cycle+".csv"), index=False)
                    self.FOV_num = len(self.focus_poslist)
                    diff = self.scope.focus_image(self.current_cycle, self.focus_poslist, target_channel, focus_channel)
        try:
            plot1 = self.focusfigure.add_subplot(111)
            plot1.plot(diff)
            plot1.axhline(y=20, color='r')
            plot1.axhline(y=-20, color='r')
            plot1.get_xaxis().set_visible(False)
            plot1.get_yaxis().set_visible(False)
            self.canvas_focus.draw()
            update_focuse_process_bar(0)
            self.manual_button_able()
            os.chdir(system_path)
        except:
            self.manual_button_able()
            os.chdir(system_path)
            txt=get_time()+"focus is wrong or cancelled"
            update_error(txt)

    def align_btn_handler(self):
        self.scope.cancel_process = 0
        self.scope.focus_status=1
        clear_error()
        t = Thread(target=self.align_and_draw_thread)
        t.start()


    def tile_btn_handler(self):
        self.scope.cancel_process = 0
        self.scope.alignment_status = 1
        clear_error()
        t = Thread(target=self.tile_and_draw_thread)
        t.start()

    def tile_and_draw_thread(self):
        self.scope.make_tile(self.current_cycle)
        txt = get_time() + "created tiles for " + self.current_cycle + "\n"
        add_highlight_mainwindow(txt)
        df = pd.read_csv(os.path.join(self.pos_path, 'tiledregoffset' + self.current_cycle + '.csv'))
        plot3 = self.tilefigure.add_subplot(111)
        plot3.scatter(df['X'],df['Y'],c='hotpink',s=4)
        plot3.get_xaxis().set_visible(False)
        plot3.get_yaxis().set_visible(False)
        self.canvas_tile.draw()


    def max_btn_handler(self):
        self.scope.cancel_process = 0
        self.scope.maketiles_status = 1
        clear_error()
        df = pd.read_csv(os.path.join(self.pos_path, 'tiledregoffset' + self.current_cycle + '.csv'))
        self.max_name_ls = df['switched_Posinfo']
        self.min_x = df['X'].min() - 50
        self.max_x = df['X'].max() + 50
        self.min_y = df['Y'].min() - 50
        self.max_y = df['Y'].max() + 50
        t1 = Thread(target=self.maxprojection_thread)
        t1.start()
        t2 = Thread(target=self.plot_live_view_thread)
        t2.start()

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
        self.manual_button_disable()
        df = pd.read_csv(os.path.join(self.pos_path, 'tiledregoffset' + self.current_cycle + '.csv'))
        self.max_name_ls = df['switched_Posinfo']
        self.scope.image_and_maxprojection(self.current_cycle)
        self.manual_button_able()
        os.chdir(system_path)

    def plot_live_view_thread(self):
        print("I was called!")
        time.sleep(3)
        name=self.scope.maxprojection_name
        print(name)
        while name!='end'  and self.cancel!=1:
            if name !='':
                self.plot_maxprojection_liveview(name)
            time.sleep(2)
            name = self.scope.maxprojection_name
        if self.scope.max_projection_status ==1:
            txt=get_time()+"max_projection_finished!!!!!"
            add_highlight_mainwindow(txt)
            self.info_btn['state']='normal'


    def plot_maxprojection_liveview(self, name):
        disk = "D://"
        server_name = self.current_cycle + '.tif'
        plot1 = self.livefigure.add_subplot(111)
        img = tif.imread(os.path.join(disk, self.pos_path[3:]+"_maxprojection", name, server_name))
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
        self.canvas_live.draw()


    def change_server(self):
       if self.change_server_value.get() == 1:
            self.server_account_lb.config(fg=widge_attr.normal_color)
            self.server_lb.config(fg=widge_attr.normal_color)
            self.server_field["state"]="normal"
            self.account_field["state"]="normal"
       else:
           self.server_account_lb.config(fg=widge_attr.disable_color)
           self.server_lb.config(fg=widge_attr.disable_color)
           self.server_field["state"] = "disable"
           self.account_field["state"] = "disable"


    def sensor_fluidics_process(self):
        self.auto_button_disable()
        check=self.fluidics.cycle_done
        while check!=1:
            time.sleep(2)
            check = self.fluidics.cycle_done
        txt = get_time() + "Start in chamber line"
        add_highlight_mainwindow(txt)
        self.fluidics.select_chamber( FluidicsConstants.SELECT_CHAMBER_STATE)
        self.fluidics.setSource(self.reagent_dict["PBST"])
        self.fluidics.pumpVol(4, 1.5)
        time.sleep((float(4) / 1.5) * 60 + 5)
        txt = get_time() + "Finish in chamber line! Wash/Prime line Done!!"
        add_highlight_mainwindow(txt)
        self.fluidics.disconnect_pump()
        self.fluidics.disconnect_relay()
        self.fluidics.disconnect_selector()
        self.fluidics.disconnect_heater()
        self.auto_button_able()

    def fill_single_reagent(self):
        t1 = Thread(target=self.pump_reagent)
        t1.start()

    def pump_reagent(self):
        reagent = self.reagent.get()
        vol=self.reagent_amount.get()
        if reagent=="":
            add_highlight_mainwindow("Please select reagent!")
        else:
            self.auto_button_disable()
            self.fluidics.connect_pump()
            self.fluidics.connect_relay()
            self.fluidics.connect_selector()
            self.fluidics.connect_heater()
            self.fluidics.select_chamber( FluidicsConstants.SELECT_CHAMBER_STATE)
            self.fluidics.setSource(self.reagent_dict[reagent])
            txt = get_time() + "fill chamber with " + reagent + "\n"
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            self.fluidics.pumpVol(vol,1.5)
            time.sleep((float(vol)/1.5)*60 +5)
            txt = get_time() + "fill chamber with " + reagent + " is done!\n"
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            self.fluidics.disconnect_pump()
            self.fluidics.disconnect_relay()
            self.fluidics.disconnect_selector()
            self.fluidics.disconnect_heater()
            self.auto_button_able()


    def wash_btn_handler(self):
        self.fluidics.sequenceStatus=0
        self.fluidics.connect_pump()
        self.fluidics.connect_relay()
        self.fluidics.connect_selector()
        self.fluidics.connect_heater()
        self.fluidics.select_chamber( not FluidicsConstants.SELECT_CHAMBER_STATE)
        self.fluidics.loadSequence(self.fluidics.FLUSH_ALL_SEQUENCE)
        t1 = Thread(target=self.fluidics.startSequence)
        t1.start()
        txt = get_time() + "Wash with pbs\n"
        add_highlight_mainwindow(txt)
        self.write_log(txt)
        t2=Thread(target=self.sensor_fluidics_process)
        t2.start()


    def prime_btn_handler(self):
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



    def cancel_btn_handler(self):
        self.cancel=1
        self.fluidics.Heatingdevice.cancel==1
        if "fluidics" in self.process_ls[self.process_index]:
            self.fluidics.cancelSequence()
        self.scope.cancel_process = 1
        txt=get_time()+"Canceled current process\n"
        add_highlight_mainwindow(txt)
        self.write_log(txt)
        self.info_btn['state']="normal"
        self.auto_button_able()


    def change_pixel_handler(self):
        if self.change_pixel_value.get() == 1:
            self.pixel_size_field.config(state=NORMAL)
        else:
            t = self.pixel_size_field.get()
            self.pixel_size.set(t)
            self.pixel_size_field.config(state=DISABLED)


    def upload_aws_handler(self):
        pass
    def BAS_check_handler(self):
        # self.wash_btn["state"] = "normal"
        # self.device_btn["state"] = "normal"
        # self.fill_single_btn["state"] = "normal"
        # self.prime_btn["state"] = "normal"
        # self.start_sequence_btn["state"] = "normal"
        # self.cancel_sequence_btn["state"] = "normal"
        # self.reagent_amount["state"] = "normal"
        self.build_own_cycle_sequence["state"]="normal"
        #self.init_cycle_lb.config(fg=widge_attr.disable_color)
        self.current_cycle_lb.config(fg=widge_attr.disable_color)
        self.cycle_num_lb.config(fg=widge_attr.disable_color)
        self.recipe_btn["state"]="normal"
        self.focus_btn["state"]="disable"
        self.align_btn["state"]="disable"
        self.tile_btn["state"]="disable"
        self.max_btn["state"]="disable"
        self.cancle_image_btn['state']="disable"
        #self.init_cbox.config(state=DISABLED)
        self.current_cbox.config(state=DISABLED)
        self.sb1_cycle_number.config(state=DISABLED)

    def manual_check_handler(self):
        self.recipe_btn["state"] = "disable"
        self.recipe_btn["state"] = "disable"
        self.device_btn["state"] = "disable"
        self.fill_single_btn["state"] = "disable"
        self.start_sequence_btn["state"]="disable"
        self.cancel_sequence_btn["state"]="disable"
        self.wash_btn["state"]="disable"
        self.prime_btn["state"] = "disable"
        self.build_own_cycle_sequence["state"] = "disable"
        #self.init_cycle_lb.config(fg=widge_attr.black_color)
        self.current_cycle_lb.config(fg=widge_attr.black_color)
        self.cycle_num_lb.config(fg=widge_attr.black_color)
        self.focus_btn["state"]="normal"
        self.align_btn["state"]="normal"
        self.tile_btn["state"]="normal"
        self.max_btn["state"]="normal"
        self.sb1_cycle_number.config(state=NORMAL)
        #self.init_cbox.config(state=NORMAL)
        self.current_cbox.config(state=NORMAL)

    def recipe_btn_handler(self):
        self.pb=process_builder()
        self.pb.create_window(self.work_path_field.get())

    def search_for_file_path(self):
        self.currdir = os.getcwd()
        self.tempdir = filedialog.askdirectory(parent=self.parent_window, initialdir=self.currdir, title='Please select a directory')
        if len(self.tempdir) > 0:
            print("You chose: %s" % self.tempdir)
        return self.tempdir


    def browse_handler(self):
        self.tempdir = self.search_for_file_path()
        self.path.set(self.tempdir)
        self.work_path_field.config(textvariable=self.path)


    # def init_cbox_handler(self):
    #     self.init_cycle = self.init_c.get()


    def current_cbox_handler(self):
        self.current_cycle = self.current_c.get()


    # def auto_cycle_cbox_handler(self):
    #     self.auto_cycle = self.auto_cycle_c.get()


    def align_pre_cycle_handler(self):
        pass

    def run_fluidics_cycle(self,sequence):
        self.fluidics.loadSequence(sequence)
        self.fluidics.startSequence()

    def run_image_cycle(self):
        pass
    def run_first_image_cycle(self):
        pass
    def find_protocol(self,type):
        if "geneseq" in type and "01" in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_geneseq01.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_geneseq01.json protocol!\n"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_geneseq01.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_geneseq01.json"), os.path.join(self.pos_path, "Fluidics_sequence_geneseq01.json"))
        elif "bcseq" in type and "01" in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_bcseq01.json"), 'r') as r:
                protocol = json.load(r)
            txt=get_time()+"load Fluidics_sequence_bcseq01.json protocol!\n"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_bcseq01.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_bcseq01.json"), os.path.join(self.pos_path, "Fluidics_sequence_bcseq01.json"))
        elif "geneseq" in type  and "01" not in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_geneseq02+.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_geneseq02+.json protocol!\n"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_geneseq02+.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_geneseq02+.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_geneseq02+.json"))
        elif "bcseq" in type and "01" not in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_bcseq02+.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_bcseq02+.json protocol!\n"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_bcseq02+.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_bcseq02+.json"), os.path.join(self.pos_path, "Fluidics_sequence_bcseq02+.json"))
        elif "user_defined" in type:
            with open(os.path.join(system_path,"reagent_sequence_file","Fluidics_sequence_user_defined.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_user_defined protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path,"Fluidics_sequence_user_defined.json")):
                shutil.copyfile(os.path.join(system_path,  "reagent_sequence_file","Fluidics_sequence_user_defined.json"), os.path.join(self.pos_path, "Fluidics_sequence_user_defined.json"))

        elif "HYB" in type and "rehyb" not in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_HYB.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_HYB protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_HYB.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_HYB.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_HYB.json"))
        elif "add_gene_primer" in type and "rehyb" not in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_gene_primer.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_gene_primer protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_gene_primer.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer.json"))
        elif "add_bc_primer" in type and "rehyb" not in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_bc_primer.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_bc_primer protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_bc_primer.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer.json"))


        elif "HYB" in type and "rehyb" in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_HYB_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_HYB_rehyb protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_HYB_rehyb.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_HYB_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_HYB_rehyb.json"))
        elif "add_gene_primer" in type and "rehyb"  in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_gene_primer_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_gene_primer_rehyb protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer_rehyb.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_gene_primer_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer_rehyb.json"))
        elif "add_bc_primer" in type and "rehyb"  in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_bc_primer_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_bc_primer_rehyb protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer_rehyb.json")):
                shutil.copyfile(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_add_bc_primer_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer_rehyb.json"))
        elif "strip" in type:
            with open(os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_strip.json"),
                      'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_strip protocol\n!"
            print(txt)
            add_highlight_mainwindow(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_strip.json")):
                shutil.copyfile(
                    os.path.join(system_path, "reagent_sequence_file", "Fluidics_sequence_strip.json"),
                    os.path.join(self.pos_path, "Fluidics_sequence_strip.json"))

        return protocol

    def start_sequence(self):
        if self.process_index>self.process_index_limite:
            txt=get_time()+"All rounds finished!\n"
            self.write_log(txt)
            add_highlight_mainwindow(txt)
            self.fluidics.disconnect_pump()
            self.fluidics.disconnect_selector()
            self.fluidics.disconnect_relay()
            self.fluidics.disconnect_heater()
            self.auto_button_able()
            return
        self.process_cycle = self.process_ls[self.process_index]
        txt=get_time()+"start "+self.process_cycle+"\n"
        self.write_log(txt)
        add_highlight_mainwindow(txt)
        self.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
        if "Fluidics_sequence" in self.process_cycle:
            self.scope=scope(self.pos_path,self.slice_per_slide,self.server,self.skip_alignment)
            self.scope.move_to_fluidics()

            try:
                self.protocol=self.find_protocol(self.process_cycle)
            except:
                self.fluidics.disconnect_pump()
                self.fluidics.disconnect_selector()
                self.fluidics.disconnect_relay()
                self.fluidics.disconnect_heater()
                self.auto_button_able()
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
            self.scope=scope(self.pos_path,self.slice_per_slide,self.server,self.skip_alignment)
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
            self.scope=scope(self.pos_path,self.slice_per_slide,self.server,self.skip_alignment)
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


    def start_btn_handler(self):
        if sum(self.device_status.values())!=4:
            messagebox.showinfo(title="config", message="Please config all devis!")
            return

        self.process_index=0
        self.process_index_limite=len(self.process_ls)-1
        self.process_cycle=self.process_ls[self.process_index]
        self.cancel=0
        self.fluidics.sequenceStatus=0
        self.auto_button_disable()
        self.check_files()
        if self.check_file==1:
            self.fluidics.connect_pump()
            self.fluidics.connect_relay()
            self.fluidics.connect_selector()
            self.fluidics.connect_heater()
            tt=Thread(target=self.start_sequence)
            tt.start()
        else:
            print("Missing files!")



    def cancel_manual_process(self):
        self.scope.cancel_process=1
        self.manual_button_able()

