import tkinter as tk
from tkinter import ttk, filedialog
import serial
import tkinter.messagebox as messagebox
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from datetime import datetime
import threading
import time
import os
from PIL import Image, ImageTk
import sv_ttk  # Modern theme for tkinter

# Kelas untuk membuat tooltip pada elemen UI
class CreateToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     # miliseconds
        self.wraplength = 180   # pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = ttk.Label(self.tw, text=self.text, justify='left',
                         background="#ffffff", relief='solid', borderwidth=1,
                         wraplength=self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

class UTMInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Testing Machine Interface")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 768)
        
        # Apply modern theme
        sv_ttk.set_theme("dark")
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Segoe UI', 10))
        self.style.configure('TLabel', font=('Segoe UI', 10))
        self.style.configure('TLabelframe', font=('Segoe UI', 11, 'bold'))
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 11, 'bold'))
        
        # Define colors
        self.colors = {
            'primary': '#007bff',
            'success': '#28a745',
            'danger': '#dc3545',
            'warning': '#ffc107',
            'info': '#17a2b8',
            'light': '#f8f9fa',
            'dark': '#343a40',
            'graph1': '#007bff',
            'graph2': '#28a745',
            'graph3': '#dc3545'
        }
        
        # Tidak menggunakan ikon
        
        # Serial Communication
        self.serial_port = None
        self.is_collecting = False
        self.data = {
            'time': [],
            'mass': [],
            'displacement': [],
            'voltage': [],
            'resistance': [],
            'force': [],
            'stress': [],
            'strain': []
        }
        
        # Sample parameters
        self.sample_area = 100.0  # mm² (cross-sectional area)
        self.sample_length = 50.0  # mm (initial length)
        
        self.setup_gui()
        self.setup_plots()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("Serial port closed.")
        self.root.destroy()
        
    def setup_gui(self):
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=3)
        main_container.rowconfigure(0, weight=10)
        main_container.rowconfigure(1, weight=1)
        
        # Control Frame
        control_frame = ttk.LabelFrame(main_container, text="Control Panel", padding=10)
        control_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # Configure control frame grid
        for i in range(4):
            control_frame.columnconfigure(i, weight=1)
        for i in range(6):  # Increased to 6 for sample parameters frame
            control_frame.rowconfigure(i, weight=1)
        
        # Store references to buttons for state control
        self.control_buttons = {}
        
        # Connection Section
        conn_frame = ttk.LabelFrame(control_frame, text="Connection", padding=5)
        conn_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        # Port Selection
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=15)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.refresh_ports()
        
        # Connect Button
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection, width=10)
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Add refresh button next to port selection
        self.control_buttons['refresh_ports'] = ttk.Button(conn_frame, text="Refresh Ports", 
                                                           command=self.refresh_ports, width=12)
        self.control_buttons['refresh_ports'].grid(row=0, column=3, padx=5, pady=5)
        
        # Mode Selection
        mode_frame = ttk.LabelFrame(control_frame, text="Test Mode", padding=5)
        mode_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        mode_buttons_frame = ttk.Frame(mode_frame)
        mode_buttons_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        self.mode_var = tk.StringVar()
        self.control_buttons['compression_mode'] = ttk.Button(mode_buttons_frame, text="Compression", 
                                                             command=lambda: self.set_mode("Compression"), width=15)
        self.control_buttons['compression_mode'].pack(side=tk.LEFT, padx=10, expand=True)
        
        self.control_buttons['tension_mode'] = ttk.Button(mode_buttons_frame, text="Tension", 
                                                         command=lambda: self.set_mode("Tension"), width=15)
        self.control_buttons['tension_mode'].pack(side=tk.LEFT, padx=10, expand=True)
        
        # Sample Parameters Frame
        sample_frame = ttk.LabelFrame(control_frame, text="Sample Parameters", padding=5)
        sample_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        sample_content = ttk.Frame(sample_frame)
        sample_content.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        # Cross-sectional Area dengan tooltip penjelasan
        area_label = ttk.Label(sample_content, text="Cross-sectional Area (mm²):")
        area_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        CreateToolTip(area_label, "Luas penampang spesimen (mm²)\nUntuk spesimen berbentuk silinder: π × (diameter/2)²\nUntuk spesimen berbentuk persegi: panjang × lebar")
        
        self.area_var = tk.StringVar(value=str(self.sample_area))
        self.control_buttons['area_entry'] = ttk.Entry(sample_content, textvariable=self.area_var, width=10)
        self.control_buttons['area_entry'].grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # Initial Length dengan tooltip penjelasan
        length_label = ttk.Label(sample_content, text="Initial Length (mm):")
        length_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        CreateToolTip(length_label, "Panjang awal spesimen (mm)\nJarak antara dua titik pengukuran pada spesimen\nsebelum pengujian dimulai")
        
        self.length_var = tk.StringVar(value=str(self.sample_length))
        self.control_buttons['length_entry'] = ttk.Entry(sample_content, textvariable=self.length_var, width=10)
        self.control_buttons['length_entry'].grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        sample_buttons = ttk.Frame(sample_content)
        sample_buttons.grid(row=1, column=2, columnspan=2, padx=5, pady=5)
        
        self.control_buttons['update_sample'] = ttk.Button(sample_buttons, text="Update Parameters", 
                                                          command=self.update_sample_parameters, width=15)
        self.control_buttons['update_sample'].pack(side=tk.LEFT, padx=5)
        
        # Calibration Frame
        calib_frame = ttk.LabelFrame(control_frame, text="Calibration", padding=5)
        calib_frame.grid(row=3, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        calib_content = ttk.Frame(calib_frame)
        calib_content.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Label(calib_content, text="Known Weight (g):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.weight_var = tk.StringVar()
        self.control_buttons['weight_entry'] = ttk.Entry(calib_content, textvariable=self.weight_var, width=10)
        self.control_buttons['weight_entry'].grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        calib_buttons = ttk.Frame(calib_content)
        calib_buttons.grid(row=0, column=2, columnspan=2, padx=5, pady=5)
        
        self.control_buttons['calibrate'] = ttk.Button(calib_buttons, text="Calibrate", command=self.calibrate, width=10)
        self.control_buttons['calibrate'].pack(side=tk.LEFT, padx=5)
        
        self.control_buttons['tare'] = ttk.Button(calib_buttons, text="Tare", command=self.tare, width=10)
        self.control_buttons['tare'].pack(side=tk.LEFT, padx=5)
        
        # Test Control Frame
        test_control_frame = ttk.LabelFrame(control_frame, text="Test Controls", padding=5)
        test_control_frame.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        control_btns = ttk.Frame(test_control_frame)
        control_btns.pack(fill=tk.X, expand=True, padx=5, pady=10)
        
        self.control_buttons['start'] = ttk.Button(control_btns, text="Start Test", command=self.start_test, width=10)
        self.control_buttons['start'].pack(side=tk.LEFT, padx=5, expand=True)
        
        self.control_buttons['stop'] = ttk.Button(control_btns, text="Stop Test", command=self.stop_test, width=10)
        self.control_buttons['stop'].pack(side=tk.LEFT, padx=5, expand=True)
        
        self.control_buttons['reset'] = ttk.Button(control_btns, text="Reset Test", command=self.reset_test, width=10)
        self.control_buttons['reset'].pack(side=tk.LEFT, padx=5, expand=True)
        
        self.control_buttons['save'] = ttk.Button(control_btns, text="Save Data", command=self.save_data, width=10)
        self.control_buttons['save'].pack(side=tk.LEFT, padx=5, expand=True)
        
        # Data Display Frame
        data_frame = ttk.LabelFrame(control_frame, text="Current Data", padding=5)
        data_frame.grid(row=5, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        
        # Current values display
        self.current_values = {
            'force': tk.StringVar(value="0.00 N"),
            'displacement': tk.StringVar(value="0.00 mm"),
            'stress': tk.StringVar(value="0.00 MPa"),
            'strain': tk.StringVar(value="0.00")
        }
        
        ttk.Label(data_frame, text="Force:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Label(data_frame, textvariable=self.current_values['force']).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(data_frame, text="Displacement:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Label(data_frame, textvariable=self.current_values['displacement']).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        ttk.Label(data_frame, text="Stress:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Label(data_frame, textvariable=self.current_values['stress']).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(data_frame, text="Strain:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        ttk.Label(data_frame, textvariable=self.current_values['strain']).grid(row=1, column=3, padx=5, pady=5, sticky="w")
        
        self.toggle_buttons_state(False)
        
    def setup_plots(self):
        # Get the main container (parent of control_frame)
        main_container = self.root.winfo_children()[0]
        
        # Create plot frame
        plot_frame = ttk.LabelFrame(main_container, text="Test Results", padding=10)
        plot_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        
        # Create matplotlib figure with improved styling
        plt.style.use('ggplot')
        self.fig, (self.ax1, self.ax2, self.ax3) = plt.subplots(3, 1, figsize=(10, 10), dpi=100, facecolor='#2e2e2e')
        self.fig.tight_layout(pad=3.0)
        
        # Configure plots with better styling
        self.ax1.set_title('Force vs Displacement', color='white', fontsize=12, fontweight='bold')
        self.ax1.set_xlabel('Displacement (mm)', color='white', fontsize=10)
        self.ax1.set_ylabel('Force (N)', color='white', fontsize=10)
        self.ax1.tick_params(colors='white')
        self.ax1.grid(True, linestyle='--', alpha=0.7)
        
        self.ax2.set_title('Stress vs Strain', color='white', fontsize=12, fontweight='bold')
        self.ax2.set_xlabel('Strain (%)', color='white', fontsize=10)
        self.ax2.set_ylabel('Stress (Pa)', color='white', fontsize=10)
        self.ax2.tick_params(colors='white')
        self.ax2.grid(True, linestyle='--', alpha=0.7)
        
        self.ax3.set_title('Resistance vs Strain', color='white', fontsize=12, fontweight='bold')
        self.ax3.set_xlabel('Strain (%)', color='white', fontsize=10)
        self.ax3.set_ylabel('Resistance (Ω)', color='white', fontsize=10)
        self.ax3.tick_params(colors='white')
        self.ax3.grid(True, linestyle='--', alpha=0.7)
        
        # Set white edge color for all plots
        for ax in [self.ax1, self.ax2, self.ax3]:
            for spine in ax.spines.values():
                spine.set_edgecolor('white')
        
        # Create lines with better colors
        self.line1, = self.ax1.plot([], [], lw=2, color=self.colors['graph1'])
        self.line2, = self.ax2.plot([], [], lw=2, color=self.colors['graph3'])
        self.line3, = self.ax3.plot([], [], lw=2, color=self.colors['graph2'])
        
        # Add canvas to plot frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add status bar
        self.setup_status_bar(main_container)
        
    def refresh_ports(self):
        time.sleep(1)  # Tambah delay 1 detik
        ports = [port.device for port in serial.tools.list_ports.comports()]
        print("Available ports:")
        for port in serial.tools.list_ports.comports():
            print(f"Port: {port.device}, Desc: {port.description}, HW ID: {port.hwid}")
    
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
            
    def toggle_connection(self):
        if self.serial_port is None:
            try:
                self.serial_port = serial.Serial(
                    port=self.port_var.get(),
                    baudrate=9600,  # Match ESP32's baud rate
                    timeout=1,
                    write_timeout=1
                )
                self.connect_btn.config(text="Disconnect")
                self.toggle_buttons_state(True)
                self.status_vars['connection'].set("Connected")
                self.connection_label.configure(foreground=self.colors['success'])
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to connect to port: {str(e)}")
                self.status_vars['connection'].set("Connection Failed")
                self.connection_label.configure(foreground=self.colors['danger'])
        else:
            self.serial_port.close()
            self.serial_port = None
            self.connect_btn.config(text="Connect")
            self.toggle_buttons_state(False)
            self.status_vars['connection'].set("Not Connected")
            self.connection_label.configure(foreground="")  # Reset to default color
            
    def set_mode(self, mode):
        if self.serial_port:
            command = 'c' if mode == "Compression" else 'v'
            self.serial_port.write(f"{command}\n".encode())
            tk.messagebox.showinfo("Mode Set", f"Mode set to {mode}")
            self.test_mode = mode
            self.status_vars['mode'].set(mode)
            self.mode_label.configure(foreground=self.colors['info'])
            
    def calibrate(self):
        if self.serial_port:
            calibration_value_str = self.weight_var.get()
            if not calibration_value_str:
                tk.messagebox.showwarning("Warning", "Calibration input cannot be empty.")
                return
            try:
                value = float(calibration_value_str)
                command = f"w {value}\n"
                self.serial_port.write(command.encode())
                tk.messagebox.showinfo("Calibration", f"Sent calibration value: {value}")
                # Tidak menonaktifkan tombol mode
            except ValueError:
                tk.messagebox.showerror("Error", "Invalid calibration value. Please enter a number.")
            
    def tare(self):
        if self.serial_port:
            self.serial_port.write(b"t\n")
            # Tidak menonaktifkan tombol mode

            
    def start_test(self):
        if not hasattr(self, 'test_mode') or not self.test_mode:
            messagebox.showwarning("Test Mode Error", "Please select a test mode (Tension or Compression) before starting.")
            return
            
        if self.serial_port:
            self.is_collecting = True
            self.serial_port.write(b"1\n")
            # Disable other buttons during test
            self.toggle_buttons_state(False)
            # Enable stop and reset buttons when test starts
            if 'stop' in self.control_buttons:
                self.control_buttons['stop'].config(state=tk.NORMAL)
            if 'reset' in self.control_buttons:
                self.control_buttons['reset'].config(state=tk.NORMAL)
            
            # Update status
            self.status_vars['test_status'].set("Running")
            self.status_label.configure(foreground=self.colors['success'])
            
            threading.Thread(target=self.collect_data, daemon=True).start()
            
    def stop_test(self):
        if self.serial_port:
            self.is_collecting = False
            self.serial_port.write(b"0\n")
            # Re-enable buttons after test, but keep mode selection disabled
            self.toggle_buttons_state(True)
            # Keep reset button enabled after stopping the test
            if 'reset' in self.control_buttons:
                self.control_buttons['reset'].config(state=tk.NORMAL)
            if 'compression_mode' in self.control_buttons:
                self.control_buttons['compression_mode'].config(state=tk.DISABLED)
            if 'tension_mode' in self.control_buttons:
                self.control_buttons['tension_mode'].config(state=tk.DISABLED)
            if 'calibrate' in self.control_buttons:
                self.control_buttons['calibrate'].config(state=tk.DISABLED)
            if 'tare' in self.control_buttons:
                self.control_buttons['tare'].config(state=tk.DISABLED)
            if 'weight_entry' in self.control_buttons:
                self.control_buttons['weight_entry'].config(state=tk.DISABLED)
            
            # Update status
            self.status_vars['test_status'].set("Stopped")
            self.status_label.configure(foreground=self.colors['warning'])

            
    def toggle_buttons_state(self, enabled):
        """Enable/disable control buttons based on connection status"""
        for name, button in self.control_buttons.items():
            if name not in ['connect', 'refresh_ports']:
                button.config(state=tk.NORMAL if enabled else tk.DISABLED)
        
        # Special handling for connect and refresh_ports buttons
        self.connect_btn.config(state=tk.NORMAL)
        self.control_buttons['refresh_ports'].config(state=tk.NORMAL)
        
        # Always disable stop and reset buttons until test is started
        if 'stop' in self.control_buttons:
            self.control_buttons['stop'].config(state=tk.DISABLED)
        if 'reset' in self.control_buttons:
            self.control_buttons['reset'].config(state=tk.DISABLED)

        # Disable mode selection buttons if not enabled
        if not enabled:
            if 'compression_mode' in self.control_buttons:
                self.control_buttons['compression_mode'].config(state=tk.DISABLED)
            if 'tension_mode' in self.control_buttons:
                self.control_buttons['tension_mode'].config(state=tk.DISABLED)
                
    def reset_test(self):
        # Clear data for new test
        self.data = {
            'time': [],
            'mass': [],
            'displacement': [],
            'voltage': [],
            'resistance': [],
            'force': [],
            'stress': [],
            'strain': []
        }
        self.update_plots() # Update plots to clear them
        
        # Reset current values display
        self.current_values['force'].set("0.00 N")
        self.current_values['displacement'].set("0.00 mm")
        self.current_values['stress'].set("0.00 Pa")
        self.current_values['strain'].set("0.00 %")
        
        # Reset sample count
        self.status_vars['samples'].set("Samples: 0")

        # Re-enable mode selection buttons
        if 'compression_mode' in self.control_buttons:
            self.control_buttons['compression_mode'].config(state=tk.NORMAL)
        if 'tension_mode' in self.control_buttons:
            self.control_buttons['tension_mode'].config(state=tk.NORMAL)
        if 'calibrate' in self.control_buttons:
            self.control_buttons['calibrate'].config(state=tk.NORMAL)
        if 'tare' in self.control_buttons:
            self.control_buttons['tare'].config(state=tk.NORMAL)
        if 'weight_entry' in self.control_buttons:
            self.control_buttons['weight_entry'].config(state=tk.NORMAL)
            
        # Update status
        self.status_vars['test_status'].set("Ready")
        self.status_label.configure(foreground="")  # Reset to default color
            
    def setup_status_bar(self, parent):
        # Create status bar frame
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        # Status indicators
        self.status_vars = {
            'connection': tk.StringVar(value="Not Connected"),
            'mode': tk.StringVar(value="No Mode Selected"),
            'test_status': tk.StringVar(value="Ready"),
            'samples': tk.StringVar(value="Samples: 0")
        }
        
        # Create status indicators
        ttk.Label(status_frame, text="Connection:").pack(side=tk.LEFT, padx=(5, 0))
        self.connection_label = ttk.Label(status_frame, textvariable=self.status_vars['connection'])
        self.connection_label.pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(status_frame, text="Mode:").pack(side=tk.LEFT, padx=(5, 0))
        self.mode_label = ttk.Label(status_frame, textvariable=self.status_vars['mode'])
        self.mode_label.pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(5, 0))
        self.status_label = ttk.Label(status_frame, textvariable=self.status_vars['test_status'])
        self.status_label.pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(status_frame, textvariable=self.status_vars['samples']).pack(side=tk.RIGHT, padx=10)
    
    def collect_data(self):
        while self.is_collecting:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode().strip()
                if line.startswith(';'):
                    try:
                        _, mass, disp, volt, res = line.split(';')
                        
                        # Convert to float values
                        mass_val = float(mass)
                        disp_val = float(disp)
                        volt_val = float(volt)
                        res_val = float(res)
                        
                        # Calculate force (N), stress (Pa), and strain (%)
                        force_val = mass_val * 9.81  # Convert mass (g) to force (N)
                        stress_val = (force_val / self.sample_area) * 1000000  # Force (N) / Area (mm²) * 1000000 = Stress (Pa)
                        strain_val = (disp_val / self.sample_length) * 100  # (Displacement (mm) / Initial length (mm)) * 100 = Strain (%)
                        
                        # Store all data
                        self.data['time'].append(time.time())
                        self.data['mass'].append(mass_val)
                        self.data['displacement'].append(disp_val)
                        self.data['voltage'].append(volt_val)
                        self.data['resistance'].append(res_val)
                        self.data['force'].append(force_val)
                        self.data['stress'].append(stress_val)
                        self.data['strain'].append(strain_val)
                        
                        # Update current values display
                        self.current_values['force'].set(f"{force_val:.2f} N")
                        self.current_values['displacement'].set(f"{disp_val:.2f} mm")
                        self.current_values['stress'].set(f"{stress_val:.2f} Pa")
                        self.current_values['strain'].set(f"{strain_val:.2f} %")
                        
                        # Update sample count
                        self.status_vars['samples'].set(f"Samples: {len(self.data['time'])}")
                        
                        self.update_plots()
                    except Exception as e:
                        print(f"Error parsing data: {e}")
                        pass
                        
    def update_plots(self):
        # Update Force vs Displacement plot
        self.line1.set_data(self.data['displacement'], self.data['force'])
        self.ax1.relim()
        self.ax1.autoscale_view()
        
        # Update Stress vs Strain plot
        self.line2.set_data(self.data['strain'], self.data['stress'])
        self.ax2.relim()
        self.ax2.autoscale_view()
        
        # Update Resistance vs Strain plot
        self.line3.set_data(self.data['strain'], self.data['resistance'])
        self.ax3.relim()
        self.ax3.autoscale_view()
        
        self.canvas.draw()
        
    def update_sample_parameters(self):
        try:
            # Get values from entry fields
            new_area = float(self.area_var.get())
            new_length = float(self.length_var.get())
            
            # Update sample parameters
            self.sample_area = new_area
            self.sample_length = new_length
            
            # Recalculate stress and strain if data exists
            if len(self.data['time']) > 0:
                # Clear existing stress and strain data
                self.data['stress'] = []
                self.data['strain'] = []
                
                # Recalculate for each data point
                for i in range(len(self.data['time'])):
                    force = self.data['force'][i]
                    disp = self.data['displacement'][i]
                    
                    # Calculate new stress and strain values
                    stress = (force / self.sample_area) * 1000000  # Convert to Pa
                    strain = (disp / self.sample_length) * 100  # Convert to %
                    
                    # Add to data arrays
                    self.data['stress'].append(stress)
                    self.data['strain'].append(strain)
                
                # Update current values display if data exists
                if self.data['stress'] and self.data['strain']:
                    self.current_values['stress'].set(f"{self.data['stress'][-1]:.2f} Pa")
                    self.current_values['strain'].set(f"{self.data['strain'][-1]:.2f} %")
                
                # Update plots
                self.update_plots()
            
            messagebox.showinfo("Parameters Updated", "Sample parameters have been updated successfully.")
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for area and length.")
    
    def save_data(self):
        if len(self.data['time']) > 0:
            # Create DataFrame with all data including stress and strain
            df = pd.DataFrame({
                'Time': self.data['time'],
                'Mass (g)': self.data['mass'],
                'Displacement (mm)': self.data['displacement'],
                'Force (N)': self.data['force'],
                'Stress (Pa)': self.data['stress'],
                'Strain (%)': self.data['strain'],
                'Voltage (V)': self.data['voltage'],
                'Resistance (Ω)': self.data['resistance']
            })
            
            # Ask for save location and filename
            filename = tk.filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"utm_test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if filename:  # If user didn't cancel
                # Simpan data dengan setiap parameter dalam kolom terpisah
                df.to_csv(filename, index=False)
                tk.messagebox.showinfo("Success", f"Data saved to {filename}\n\nData disimpan dengan format kolom terpisah untuk setiap parameter (Mass, Displacement, Force, Stress, Strain, Voltage, Resistance).")

    # Fungsi ikon dihapus

    def update_sample_parameters(self):
        try:
            # Get values from entry fields
            new_area = float(self.area_var.get())
            new_length = float(self.length_var.get())
            
            # Update sample parameters
            self.sample_area = new_area
            self.sample_length = new_length
            
            # Show confirmation message
            tk.messagebox.showinfo("Parameters Updated", 
                                  f"Sample parameters updated:\n\nCross-sectional Area: {new_area} mm²\nInitial Length: {new_length} mm")
            
            # If there's data, recalculate stress and strain
            if len(self.data['force']) > 0:
                # Recalculate stress and strain with new parameters
                self.data['stress'] = [(force / self.sample_area) * 1000000 for force in self.data['force']]  # Convert to Pa
                self.data['strain'] = [(disp / self.sample_length) * 100 for disp in self.data['displacement']]  # Convert to %
                
                # Update plots with new calculations
                self.update_plots()
                tk.messagebox.showinfo("Recalculation Complete", "Stress and strain values have been recalculated with the new parameters.")
        except ValueError:
            tk.messagebox.showerror("Input Error", "Please enter valid numeric values for area and length.")

if __name__ == "__main__":
    # Check if sv_ttk is installed, if not, install it
    try:
        import sv_ttk
    except ImportError:
        import subprocess
        import sys
        print("Installing sv_ttk theme...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sv-ttk"])
        import sv_ttk
    
    # Check if PIL is installed, if not, install it
    try:
        from PIL import Image, ImageTk
    except ImportError:
        import subprocess
        import sys
        print("Installing Pillow...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image, ImageTk
    
    root = tk.Tk()
    app = UTMInterface(root)
    root.mainloop()