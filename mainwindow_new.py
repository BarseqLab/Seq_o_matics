from front_end.Widgets import *
from front_end.logwindow import *
import os


mainwindow = Log_window.mainwindow
my_widges = window_widgets(mainwindow=mainwindow,path=os.getcwd())

##automatiob tab area
my_widges.work_path_lb_auto.grid(row=3, column=0, padx=15,sticky="w")
my_widges.work_path_field_auto.grid(row=3, column=3, padx=15, sticky="w")
my_widges.browse_btn_auto.grid(row=3, column=4, padx=15, sticky="w")
my_widges.exp_btn_auto.grid(row=3, column=7, padx=15, sticky="w")


my_widges.slice_per_slide_lb_auto.grid(row=0, column=0, padx=5,sticky="w")
#my_widges.slice_per_slide_lb_manual.grid(row=0, column=0, padx=5,sticky="w")
my_widges.slice_number_field_auto.grid(row=0, column=1, padx=1,sticky="w")
# my_widges.slice_number_field_manual.grid(row=0, column=1, padx=1,sticky="w")
my_widges.mock_alignment_cbox.grid(row=0, column=2, padx=5, sticky="w")
#my_widges.mock_alignment_cbox_manual.grid(row=0, column=2, padx=5, sticky="w")
#my_widges.current_cycle_lb.grid(row=0, column=3, padx=5, sticky="w")
# my_widges.current_cbox.grid(row=0, column=4, padx=5, sticky="w")
#my_widges.sb1_cycle_number.grid(row=0, column=5, padx=5, sticky="w")

my_widges.build_own_cycle_sequence.grid(row=0, column=3, padx=5, sticky="w")
my_widges.OR_lb.grid(row=0, column=4, padx=5, sticky="w")
my_widges.recipe_btn.grid(row=0, column=5, padx=5, sticky="w")


my_widges.change_pixel_auto.grid(row=1, column=0, padx=5, sticky="w")
#my_widges.change_pixel_manual.grid(row=1, column=0, padx=5, sticky="w")
my_widges.pixel_size_field_auto.grid(row=1, column=1, padx=5, sticky="w")
my_widges.change_server_auto.grid(row=1, column=2, padx=5, sticky="w")
#my_widges.change_server_manual.grid(row=1, column=2, padx=5, sticky="w")
my_widges.server_account_lb_auto.grid(row=1, column=3, padx=5, sticky="w")
my_widges.account_field_auto.grid(row=1, column=4, padx=5, sticky="w")
my_widges.server_lb_auto.grid(row=1, column=5, padx=5, sticky="w")
my_widges.server_field_auto.grid(row=1, column=6, padx=5, sticky="w")
#my_widges.server_account_lb_manual.grid(row=1, column=3, padx=5, sticky="w")
#my_widges.account_field_manual.grid(row=1, column=4, padx=5, sticky="w")
#my_widges.server_lb_manual.grid(row=1, column=5, padx=5, sticky="w")
#my_widges.server_field_manual.grid(row=1, column=6, padx=5, sticky="w")



my_widges.upload_aws_auto.grid(row=0, column=0, padx=5, sticky="w")
my_widges.aws_account_lb_auto.grid(row=0, column=1, padx=5, sticky="w")
my_widges.aws_account_field_auto.grid(row=0, column=2, padx=5,sticky="w")
my_widges.aws_password_lb_auto.grid(row=0, column=3, padx=5, sticky="w")
my_widges.aws_pwd_field_auto.grid(row=0, column=4, padx=5, sticky="w")

#my_widges.upload_aws_manual.grid(row=0, column=0, padx=5, sticky="w")
# my_widges.aws_account_lb_manual.grid(row=0, column=1, padx=5, sticky="w")
# my_widges.aws_account_field_manual.grid(row=0, column=2, padx=5,sticky="w")
# my_widges.aws_password_lb_manual.grid(row=0, column=3, padx=5, sticky="w")
# my_widges.aws_pwd_field_manual.grid(row=0, column=4, padx=5, sticky="w")

my_widges.info_btn_auto.grid(row=2, column=0, padx=10, pady=5)

my_widges.device_btn.grid(row=0, column=0, padx=10,sticky="w")
my_widges.brain_btn.grid(row=0, column=1, padx=10, sticky="w")
my_widges.prime_btn.grid(row=0, column=2, padx=10,sticky="w")
my_widges.fill_lb.grid(row=0, column=3, padx=10, sticky="w")
my_widges.reagent_list_cbox.grid(row=0, column=4, padx=10, sticky="w")
my_widges.reagent_amount.grid(row=0, column=5, padx=10, sticky="w")
my_widges.inchamber_path_cbox.grid(row=0, column=6, padx=10,sticky="w")
my_widges.fill_single_btn.grid(row=0, column=7, padx=10, sticky="w")

my_widges.start_sequence_btn.grid(row=0, column=0, padx=10, sticky="w")
my_widges.cancel_sequence_btn.grid(row=0, column=1, padx=10, sticky="w")
my_widges.wash_btn.grid(row=0, column=2, padx=10, sticky="w")

my_widges.canvas_focus.get_tk_widget().grid(row=1, column=0,padx=10,sticky="w")
my_widges.canvas_align.get_tk_widget().grid(row=1, column=1,padx=10,sticky="w")
my_widges.canvas_tile.get_tk_widget().grid(row=1, column=2,padx=10,sticky="w")

my_widges.focus_lb.grid(row=0, column=0,padx=5,pady=3)
my_widges.align_lb.grid(row=0, column=1,padx=5,pady=3)
my_widges.tile_lb.grid(row=0, column=2,padx=5,pady=3)

my_widges.note_lb.grid(row=0, column=0,padx=5,pady=3)
my_widges.note_stw.grid(row=0, column=1,padx=5,pady=3)
my_widges.note_btn.grid(row=0, column=2,padx=5,pady=3)
## manual tab area
my_widges.work_path_lb_manual.grid(row=3, column=0, padx=10,sticky="w")
my_widges.work_path_field_manual.grid(row=3, column=10, padx=10, sticky="w")
my_widges.section1_lbf_manual.grid(row=1, column=10,padx=10, sticky="w")
my_widges.browse_btn_manual.grid(row=3, column=15, padx=10, sticky="w")
my_widges.exp_btn_manual.grid(row=3, column=25, padx=10, sticky="w")

mainwindow.mainloop()