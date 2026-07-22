#!/usr/bin/env python3
import tkinter as tk
import sqlite3
import os
import threading
import pystray
from PIL import Image, ImageTk
import tempfile

if os.environ.get("SNAP"):
    # --- SNAP STORE MODE ---
    # Read-only folder for the app icon
    ICON_PATH = os.path.join(os.environ["SNAP"], "bin", "skidadit-icon.png")
    
    # Writable folder for the database
    snap_data_dir = os.environ.get("SNAP_USER_DATA", os.path.expanduser("~"))
    db_path = os.path.join(snap_data_dir, "skidadit.db")
    
    os.environ["TMPDIR"] = snap_data_dir
    tempfile.tempdir = snap_data_dir
else:
    # --- LOCAL DEVELOPER MODE ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Everything lives together in your development folder
    ICON_PATH = os.path.join(BASE_DIR, "skidadit-icon.png")
    db_path = os.path.join(BASE_DIR, "skidadit.db")

# Connect to (or create) the local SQLite database in your Home folder
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create the table to hold tasks if it doesn't exist yet
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0
    )
''')
conn.commit()

def toggle_strike(cb, var, task_id):
    is_completed = var.get()
    
    if is_completed:
        cb.config(font=("Ubuntu", 11, "overstrike"), fg="#717C74")
    else:
        cb.config(font=("Ubuntu", 11, "normal"), fg="white")
        
    cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (is_completed, task_id))
    conn.commit()

def delete_task(row_frame, task_id):
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    row_frame.destroy()

def add_task_ui(task_id, task_text, is_completed):
    row_frame = tk.Frame(tasks_frame, bg="#2E3440")
    row_frame.pack(fill="x", pady=2)
    
    var = tk.IntVar(value=is_completed)
    current_font = ("Ubuntu", 11, "overstrike") if is_completed else ("Ubuntu", 11, "normal")
    current_fg = "#717C74" if is_completed else "white"
    
    cb = tk.Checkbutton(
        row_frame, text=task_text, variable=var,
        bg="#2E3440", fg=current_fg, selectcolor="#3B4252",
        activebackground="#2E3440", activeforeground="white",
        font=current_font, borderwidth=0, highlightthickness=0
    )
    cb.config(command=lambda c=cb, v=var, t_id=task_id: toggle_strike(c, v, t_id))
    cb.pack(side="left", anchor="w")
    
    delete_btn = tk.Button(
        row_frame, text="🗑", bg="#2E3440", fg="#BF616A", 
        activebackground="#2E3440", activeforeground="#BF616A",
        font=("Ubuntu", 12), borderwidth=0, highlightthickness=0,
        command=lambda r=row_frame, t_id=task_id: delete_task(r, t_id)
    )
    delete_btn.pack(side="right", padx=(0, 5))

def adjust_height(event=None):
    # Safely asks Tkinter how many visual lines the wrapped text is using
    task_entry.update_idletasks()
    try:
        lines = task_entry.count("1.0", "end-1c", "displaylines")
        line_count = lines[0] if lines else 1
    except Exception:
        # Failsafe fallback
        line_count = 1
        
    new_height = min(max(1, line_count), 5) 
    
    if int(task_entry.cget("height")) != new_height:
        task_entry.config(height=new_height)
        # Force the parent frame to recalculate layout so it expands properly
        entry_frame.update_idletasks()

def add_task_event(event=None):
    # Tkinter Text widgets read data differently than Entry widgets
    task_text = task_entry.get("1.0", "end-1c").strip()
    
    if task_text:
        cursor.execute("INSERT INTO tasks (task, completed) VALUES (?, 0)", (task_text,))
        conn.commit()
        task_id = cursor.lastrowid
        add_task_ui(task_id, task_text, 0)
        
        # Clear the box and shrink it back down
        task_entry.delete("1.0", tk.END)
        task_entry.config(height=1)
        
    # Prevents the Enter key from typing a new line in the box
    return "break"

def load_tasks():
    cursor.execute("SELECT id, task, completed FROM tasks")
    for row in cursor.fetchall():
        add_task_ui(row[0], row[1], row[2])

def toggle_pin():
    root.attributes('-topmost', pin_var.get())

# --- Window Hiding & Quitting Mechanics ---
def hide_window():
    root.withdraw()

def full_quit():
    if tray_icon:
        tray_icon.stop()
    root.destroy()

# --- System Tray Mechanics ---
def show_app(icon, item):
    root.after(0, root.deiconify)

def quit_app(icon, item):
    icon.stop()
    root.after(0, root.destroy)

tray_icon = None

def setup_tray():
    global tray_icon
    image = Image.open(ICON_PATH)
    menu = pystray.Menu(
        pystray.MenuItem('Show Skidadit', show_app, default=True),
        pystray.MenuItem('Quit', quit_app)
    )
    tray_icon = pystray.Icon("Skidadit", image, "Skidadit", menu)
    tray_icon.run()

# --- Main App UI Setup ---
# Ensure className is set for Wayland Dock matching
root = tk.Tk(className='skidadit')
root.title("Skidadit")
root.configure(bg="#2E3440", padx=10, pady=10)

# The +100+100 keeps auto-expansion alive.
root.geometry("+100+100") 
# We increase the min height to 350 to provide the empty starting gap.
root.minsize(300, 350)
root.maxsize(1200, 1000)

root.protocol('WM_DELETE_WINDOW', hide_window)

# --- Dock and Window Icon Setup ---
try:
    # 1. Use Pillow to open the image (more robust than tk.PhotoImage)
    app_icon = ImageTk.PhotoImage(Image.open(ICON_PATH))
    
    # 2. Anchor the image to root so the Garbage Collector doesn't delete it
    root.tk_icon_anchor = app_icon
    
    # 3. Apply the icon to the window
    root.iconphoto(True, app_icon)
except Exception as e:
    # Changed from 'pass' to print so we can see any hidden errors
    print(f"Could not load window icon: {e}")

# --- Top Controls ---
pin_var = tk.BooleanVar(value=False)
pin_cb = tk.Checkbutton(
    root, text="📌 Keep on top", variable=pin_var, command=toggle_pin,
    bg="#2E3440", fg="#88C0D0", selectcolor="#3B4252",
    activebackground="#2E3440", activeforeground="#88C0D0",
    font=("Ubuntu", 10, "bold"), borderwidth=0, highlightthickness=0
)
pin_cb.pack(side="top", anchor="w", pady=(0, 5))

entry_frame = tk.Frame(root, bg="#2E3440")
entry_frame.pack(fill="x", pady=(0, 10))

# Layout Fix: Pack the Add button FIRST so it claims the right side of the frame permanently
add_btn = tk.Button(entry_frame, text="Add", command=add_task_event, bg="#A3BE8C", fg="#2E3440", font=("Ubuntu", 10, "bold"), borderwidth=0)
add_btn.pack(side="right", fill="y") # fill="y" ensures it stays matched to the text box height

# Pack the text box SECOND so it only takes up the remaining space
task_entry = tk.Text(entry_frame, font=("Ubuntu", 11), bg="#3B4252", fg="white", insertbackground="white", borderwidth=0, height=1, width=1, wrap="word")
task_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=4)

task_entry.bind("<Return>", add_task_event) 
task_entry.bind("<KeyRelease>", adjust_height)

tasks_frame = tk.Frame(root, bg="#2E3440")
tasks_frame.pack(fill="both", expand=True)

# --- Bottom Controls ---
quit_btn = tk.Button(root, text="Quit Application", command=full_quit, bg="#BF616A", fg="white", borderwidth=0)
quit_btn.pack(side="bottom", fill="x", pady=(5, 0))

hide_btn = tk.Button(root, text="Hide to Taskbar", command=hide_window, bg="#4C566A", fg="white", borderwidth=0)
hide_btn.pack(side="bottom", fill="x", pady=(5, 0))

# Load tasks
load_tasks()

# Start the system tray in a background thread
tray_thread = threading.Thread(target=setup_tray, daemon=True)
tray_thread.start()

root.mainloop()
conn.close()
