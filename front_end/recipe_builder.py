
import tkinter as tk
from tkinter import ttk
import os
import pandas as pd
from datetime import datetime
from pytz import timezone
from front_end.logwindow import *


def get_time():
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time
class process_builder():
    def __int__(self):
        self.recipe_list = [i[0:-5] for i in os.listdir("reagent_sequence_file")]
        self.recipe_list.extend(["imagecycle00", "imagecycle_geneseq", "imagecycle_bcseq", "imagecycle_hyb"])

    def create_window(self,path):
        self.pos_path = path
        self.recipe_popup = tk.Tk()
        self.recipe_popup.geometry("500x500")
        self.recipe_popup.title("Recipe Builder")
        self.dropdown = ttk.Combobox(self.recipe_popup,width=35)
        self.recipe_list = [i[0:-5] for i in os.listdir("reagent_sequence_file") if i not in ["Fluidics_sequence_flush_all.json","Fluidics_sequence_fill_all.json"]]
        self.recipe_list.extend(["imagecycle00", "imagecycle_geneseq", "imagecycle_bcseq", "imagecycle_hyb"])
        self.dropdown['values'] = self.recipe_list
        self.dropdown.current(0)
        self.dropdown.place(x=180, y=10)
        self.label1=tk.Label(self.recipe_popup,text="Choose your process:",width=20)
        self.label1.place(x=30,y=10)
        self.listbox = tk.Listbox(self.recipe_popup, width=50, height=25)
        self.listbox.place(x=80,y=80)
        self.scrollbar = tk.Scrollbar(self.recipe_popup)
        self.scrollbar.place(x=380, y=80, height=405)
        self.listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.listbox.yview)
        self.add_button = tk.Button(self.recipe_popup, text="Add to recipe", command=self.add_option)
        self.add_button.place(x=80, y=40)
        self.withdraw_button = tk.Button(self.recipe_popup, text="Withdraw selection", command=self.withdraw_option)
        self.withdraw_button.place(x=200, y=40)
        self.clear_button = tk.Button(self.recipe_popup, text="Clear all", command=self.clear_option)
        self.clear_button.place(x=400, y=380)
        self.confirm_button = tk.Button(self.recipe_popup, text="Confirm", command=self.confirm_option)
        self.confirm_button.place(x=400, y=420)
    def add_option(self):
        selected_option = self.dropdown.get()
        if selected_option=="Fluidics_sequence_bcseq01" or selected_option=="Fluidics_sequence_geneseq01":
            self.listbox.insert(tk.END, selected_option)
        elif selected_option=="imagecycle00":
            self.listbox.insert(tk.END, selected_option)
        elif selected_option=="Fluidics_sequence_bcseq02+" or selected_option=="Fluidics_sequence_geneseq02+":
            selected_option =selected_option[0:-3]
            ls= self.listbox.get(0, tk.END)
            try:
                n = max([int(i[-2:]) for i in ls if selected_option in i])+1
                selected_option = selected_option + str(n).zfill(2)
            except:
                selected_option=selected_option+str(2).zfill(2)
            self.listbox.insert(tk.END, selected_option)
        else:
            ls = self.listbox.get(0, tk.END)
            n = len([i for i in ls if selected_option in i])
            n=n+1
            selected_option = selected_option + str(n).zfill(2)
            self.listbox.insert(tk.END, selected_option)








    def withdraw_option(self):
        selected_index = self.listbox.curselection()
        if selected_index:
            self.listbox.delete(selected_index)

    def clear_option(self):
        self.listbox.delete(0, tk.END)
    def confirm_option(self):
        self.recipe_final_list=self.listbox.get(0, tk.END)
        df = pd.DataFrame(columns=["process"])
        df["process"] = self.recipe_final_list
        df.to_csv(os.path.join(self.pos_path, "protocol.csv"), index=False)
        txt = get_time() + 'protocol.csv file created!\n'
        add_highlight_mainwindow(txt)
        self.recipe_popup.destroy()