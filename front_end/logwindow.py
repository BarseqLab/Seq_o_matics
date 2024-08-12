
import tkinter as tk
from tkinter import *
from tkinter import ttk,scrolledtext
import os
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import cv2

class widge_attr:
    normal_edge=3
    disable_edge = 0.9
    normal_color = '#0f0201'
    disable_color = '#bab8b8'
    warning_color='#871010'
    black_color='#0a0000'
    yellow_color="#e0c80b"


def hattop_convert(x):
    filterSize = (10, 10)
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT, filterSize)
    return cv2.morphologyEx(x, cv2.MORPH_TOPHAT, kernel)


def denoise(x):
    x[x < np.percentile(x, 85)] = 0
    return x

class Log_window:
        filterSize = (10, 10)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, filterSize)
        color_array = np.array([[0, 4, 4], [1.5, 1.5, 0], [1, 0, 1], [0, 0, 1.5]])

        mainwindow = tk.Tk()
        mainwindow.title("Seq-o-Matic")
        mainwindow.geometry("1250x780")
        frame=tk.Frame(mainwindow, bg=mainwindow.cget('bg'))
        frame.grid(row=0, column=1, sticky="nsew")
        img = PhotoImage(file=os.path.join('LOGO.png'))
        mainwindow.iconphoto(False, img)
        warning_stw = scrolledtext.ScrolledText(
            master=frame,
            wrap=tk.WORD,
            width=45,
            height=4,
        )
        warning_stw.tag_config('warning', foreground="red")

        notification_stw = scrolledtext.ScrolledText(
            master=frame,
            wrap=tk.WORD,
            width=45,
            height=10,
        )
        notification_lb = Label(frame, text="System Notification", bd=1, relief="groove", width=15,
                                     fg=widge_attr.black_color, font=("Arial", 10))
        notification_lb.grid(row=2, column=0)

        warning_lb = Label(frame, text="System warning", bd=1, relief="groove", width=15,
                                fg=widge_attr.black_color, font=("Arial", 10))
        warning_lb.grid(row=0, column=0,pady=3,padx=3)
        liveview_lb = Label(frame, text="Live view of Barcodes", bd=1, relief="groove", width=15,
                           fg=widge_attr.black_color, font=("Arial", 10))
        liveview_lb.grid(row=5, column=0,pady=3,padx=3)

        frame1 = tk.Frame(frame, bg=mainwindow.cget('bg'))
        frame1.grid(row=3, column=0, sticky="nsew")

        process="Process"
        process_lable = Label(frame1, text=process, bd=1, relief="flat", width=18,
                                             fg=widge_attr.black_color, font=("Arial", 10))
        process_lable.grid(row=0, column=0,pady=3)
        progressbar1 = ttk.Progressbar( frame1,mode = 'indeterminate',length=250)
        progressbar1.grid(row=0, column=1,pady=3)


        notification_stw.tag_config('highlight_from_scope', foreground='#3f51b5')  # <-- Change colors of texts tagged `name`
        notification_stw.tag_config('highlight_from_mainwindow', foreground='blue')
        notification_stw.tag_config('reagent_highlight_from_fluidics', foreground='#8a0788')
        notification_stw.tag_config('status_highlight_from_fluidics', foreground='#fcb900') # <-- Change colors of texts tagged `name`
        notification_stw.tag_config('device_highlight_from_device', foreground='black')
        warning_stw.tag_config('warning', foreground="red")

        livefigure = plt.Figure(figsize=(4, 4), dpi=100)
        livefigure.subplots_adjust(left=0.01, bottom=0.01, right=0.99, top=0.99, wspace=0, hspace=0)
        canvas_live = FigureCanvasTkAgg(livefigure, master=frame)
        canvas_live.get_tk_widget().grid(row=6, column=0,padx=3,pady=3, sticky="w")

        notification_stw.grid(row=4, column=0)
        warning_stw.grid(row=1, column=0)




def update_error(txt):
    Log_window.warning_stw.insert(END, txt,'warning')
def clear_error():
    Log_window.warning_stw.delete('1.0', tk.END)
def add_highlight_from_scope(txt):
    Log_window.notification_stw.insert(END, txt, 'highlight_from_scope')
def add_device_information(txt):
    Log_window.notification_stw.insert(END, txt, 'device_highlight_from_device')
def add_fluidics_status(txt):
    Log_window.notification_stw.insert(END, txt, 'status_highlight_from_fluidics')
def add_fluidics_reagent(txt):
    Log_window.notification_stw.insert(END, txt, 'reagent_highlight_from_fluidics')
def add_highlight_mainwindow(txt):
    Log_window.notification_stw.insert(END, txt, 'highlight_from_mainwindow')

def update_process_bar(i):
    Log_window.progressbar1['value']=i
def update_process_label(txt):
    Log_window.process_lable['text']=txt








