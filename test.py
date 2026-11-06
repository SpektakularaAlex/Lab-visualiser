import tkinter as tk
from tkinter import ttk

def show_dialog(root):
    dialog = tk.Toplevel(root)
    dialog.title("Setup Dialog")
    #dialog.transient(root)
    dialog.grab_set()

    label = ttk.Label(dialog, text="Choose your options:")
    label.pack(padx=20, pady=20)

    def on_ok():
        dialog.destroy()
        # Now create the main window
        main_window = ttk.Frame(root, padding=20)
        main_window.pack()
        ttk.Label(main_window, text="Main window is now shown!").pack()
        root.deiconify()

    ok_button = ttk.Button(dialog, text="OK", command=on_ok)
    ok_button.pack(pady=10)

    # This will block until the dialog is destroyed
    print('here')
    root.wait_window(dialog)

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    # Schedule the dialog to appear as soon as the event loop starts
    root.after(0, lambda: show_dialog(root))
    root.mainloop()

if __name__ == "__main__":
    main()