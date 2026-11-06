import tkinter as tk
from tkinter import ttk

def show_dialog(parent):
    dialog = tk.Toplevel(parent)
    dialog.title("Setup Dialog")
    #dialog.transient(parent)  # Make dialog stay on top of parent
    dialog.grab_set()         # Grab all input to this window

    # Add your widgets here, e.g.:
    label = ttk.Label(dialog, text="Choose your options:")
    label.pack(padx=20, pady=20)

    # Example: a button to close the dialog
    def on_ok():
        # Store user choices here, e.g. in a class or global variable
        dialog.destroy()

    ok_button = ttk.Button(dialog, text="OK", command=on_ok)
    ok_button.pack(pady=10)

    # Wait for the dialog to be destroyed
    parent.wait_window(dialog)
    print('there')
    # After dialog is closed, return user choices
    return "user_choices"  # Replace with actual data

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the root window until dialog is done

    # Show the dialog and wait for it to close
    user_choices = show_dialog(root)

    # Now create your main window
    main_window = ttk.Frame(root, padding=20)
    main_window.pack()
    label = ttk.Label(main_window, text=f"Main window created with choices: {user_choices}")
    label.pack()
    print('af')
    root.deiconify()
    root.mainloop()

if __name__ == "__main__":
    main()