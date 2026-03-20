# Imports from the python standard library
import math
import numpy as np
import sys
import threading
import time
import signal
import webbrowser
import re
import json
from threading import Timer
import logging

# Third party imports
import dash
from dash import dcc, html, Input, Output, State, exceptions
import plotly.graph_objects as go
import plotly.io as pio
import dash_bootstrap_components as dbc
from flask import Response # For MJPEG streaming
from pypylon import pylon
import cv2

# Piccolo imports
from piccolo_instrument_sim import InstrumentSim
from piccolo_instrument import Instrument
print("Successfully imported all modules.")


################ Configuration ################

SIMULATE = False       # True = use simulated instrument, False = connect to real hardware
LAUNCH_RP = True       # True = deploy code and load bitstream on startup (ignored in sim mode)
CAMERA_AVAILABLE = True
SERVER_URL = "http://127.0.0.1:8050/"

################ Global Variables ################

lock = threading.Lock()
instrument = None

if SIMULATE:
    instrument = InstrumentSim()
    instrument.start_generating()
else:
    instrument = Instrument(rp_dir="piccolo_testing", verbose=True)
    if LAUNCH_RP:
        print("Launching Piccolo RP... please wait.")
        instrument.launch_piccolo_rp()
        time.sleep(10)
    instrument.start_clients()
    time.sleep(1)

# Initiate Camera Variables
latest_frame_jpeg = None
frame_lock = threading.Lock() # Separate lock for camera frame
camera_lock = threading.Lock() # Lock for camera object access
camera_running = False
cam_thread = None
camera = None # Global pypylon camera object
camera_config = {'hw_trigger': False} # Global config for camera thread

# Create an initial placeholder image for the camera feed
if CAMERA_AVAILABLE:
    placeholder_img = np.zeros((240, 320, 3), dtype=np.uint8) # Small placeholder
    cv2.putText(placeholder_img, "Waiting for Camera...", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
    ret_init, jpeg_init = cv2.imencode('.jpg', placeholder_img)
    if ret_init:
        latest_frame_jpeg = jpeg_init.tobytes()

# Camera Thread Function
def camera_thread_func():
    global latest_frame_jpeg, camera_running, camera, camera_lock, camera_config
    if not CAMERA_AVAILABLE:
        print("Camera thread not starting: pypylon or OpenCV missing.")
        return

    print("Camera thread started.")
    cam_instance = None
    try:
        cam_instance = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        cam_instance.Open()

        # --- Disable Auto-Features ---
        # It's good practice to disable auto functions before setting manual values.
        cam_instance.ExposureAuto.SetValue("Off")
        cam_instance.GainAuto.SetValue("Off")

        # Configure non-UI camera parameters
        cam_instance.Width.SetValue(2048)
        cam_instance.Height.SetValue(2048)
        cam_instance.PixelFormat.SetValue("Mono12p")

        # --- Trigger Configuration ---
        # The trigger mode is now set based on a global config dict.
        # This allows the mode to be changed by restarting the thread.
        hw_trigger_enabled = camera_config.get('hw_trigger', False)
        mode = "On" if hw_trigger_enabled else "Off"
        cam_instance.TriggerSelector.SetValue("FrameStart")
        cam_instance.TriggerMode.SetValue(mode)
        cam_instance.TriggerSource.SetValue("Line1") # Assumes trigger is on Line 1
        print(f"Camera thread configured with TriggerMode: {mode}")

        # Set initial values for UI-controlled parameters
        cam_instance.ExposureTime.SetValue(28.0) # Default exposure time in microseconds
        cam_instance.TriggerDelay.SetValue(0.0)   # Default trigger delay in microseconds

        # Make camera object globally available for UI control
        with camera_lock:
            camera = cam_instance

        cam_instance.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed # OpenCV uses BGR
        
        while cam_instance.IsGrabbing() and camera_running:
            try:
                grabResult = cam_instance.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                if grabResult.GrabSucceeded():
                    image = converter.Convert(grabResult)
                    img_array = image.GetArray()

                    # Resize for web display to reduce bandwidth
                    target_width = 640
                    aspect_ratio = img_array.shape[0] / img_array.shape[1]
                    target_height = int(target_width * aspect_ratio)
                    img_resized = cv2.resize(img_array, (target_width, target_height))
                    ret, jpeg = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 75]) # Quality 0-100
                    if ret:
                        with frame_lock:
                            latest_frame_jpeg = jpeg.tobytes()
                grabResult.Release()
            except pylon.GenericException as e:
                print(f"Pylon grab error: {e}")
                time.sleep(0.1) # Wait a bit before retrying
            except Exception as e_cv:
                print(f"OpenCV processing error: {e_cv}")
                time.sleep(0.1)

    except pylon.GenericException as e:
        print(f"Pylon camera initialization error: {e}")
        # Fallback to error image
        error_img = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(error_img, "Camera Error", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        ret, jpeg = cv2.imencode('.jpg', error_img)
        if ret:
            with frame_lock:
                latest_frame_jpeg = jpeg.tobytes()
    except Exception as e_outer:
        print(f"Outer camera thread error: {e_outer}")
    finally:
        with camera_lock:
            camera = None # Invalidate global camera object
        if cam_instance:
            if cam_instance.IsGrabbing():
                cam_instance.StopGrabbing()
            if cam_instance.IsOpen():
                cam_instance.Close()
            print("Camera stopped and closed.")
        print("Camera thread finished.")


################ Dash App Setup ################

# Dark Theme Setup
pio.templates.default = "plotly_dark"
external_stylesheets = [dbc.themes.CYBORG, dbc.icons.BOOTSTRAP, '/assets/custom.css']

# Dash App Initialization
app = dash.Dash(__name__,
                title="Piccolo UI",
                external_stylesheets=external_stylesheets,
                update_title=None)

# MJPEG Streaming Route
def generate_camera_frames():
    global latest_frame_jpeg
    while True:
        time.sleep(1/30)  # Aim for ~30 FPS, adjust as needed for performance
        with frame_lock:
            frame_bytes_to_send = latest_frame_jpeg
        
        if frame_bytes_to_send:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes_to_send + b'\r\n')
        else: # If no frame, send the placeholder again or a very small blank JPEG
            placeholder_img_yield = np.zeros((50, 50, 3), dtype=np.uint8)
            cv2.putText(placeholder_img_yield, "NC", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,100,100),1)
            ret_yield, jpeg_yield = cv2.imencode('.jpg', placeholder_img_yield)
            if ret_yield:
                 yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_yield.tobytes() + b'\r\n')


@app.server.route('/video_feed')
def video_feed():
    if not CAMERA_AVAILABLE:
        return "Camera support is not available (missing pypylon or OpenCV).", 503
    return Response(generate_camera_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# Define Axis Options
axis_options_list = [
    "cur_droplet_intensity[0]", "cur_droplet_intensity[1]", "cur_droplet_intensity[2]", "cur_droplet_intensity[3]",
    "cur_droplet_intensity_v[0]", "cur_droplet_intensity_v[1]", "cur_droplet_intensity_v[2]", "cur_droplet_intensity_v[3]",
    "cur_droplet_width_ms[0]", "cur_droplet_width_ms[1]", "cur_droplet_width_ms[2]", "cur_droplet_width_ms[3]",
    "cur_droplet_area_vms[0]", "cur_droplet_area_vms[1]", "cur_droplet_area_vms[2]", "cur_droplet_area_vms[3]",
]
axis_options_dict = [{'label': i, 'value': i} for i in axis_options_list]
initial_x_key = "cur_droplet_intensity_v[0]"
initial_y_key = "cur_droplet_intensity_v[1]"
initial_x_key_2 = "cur_droplet_intensity_v[2]"
initial_y_key_2 = "cur_droplet_intensity_v[3]"

# Dash App Layout
app.layout = dbc.Container([
    dcc.Store(id='timer-store', data=[]),
    dcc.Store(id='gate-selection-store', data={"x0": [0.0], "y0": [0.0], "x1": [0.0], "y1": [0.0]}),
    dcc.Store(id='axis-keys-store', data={'x1': initial_x_key, 'y1': initial_y_key, 'x2': initial_x_key_2, 'y2': initial_y_key_2}),
    dcc.Store(id='sorter-state-store', data=False), # Sorter is OFF by default
    dcc.Interval(id='counter-interval-component', interval=1000, n_intervals=0),
    dcc.Interval(id='interval-component', interval=250, n_intervals=0),
    dbc.Row(html.Hr()),
    dbc.Row([
        # Controls Column (Left)
        dbc.Col([
            html.H5("Instrument Controls"),
            dbc.Tabs([
                dbc.Tab(label="Settings", children=[
                    html.Div([
                        # Detection and Sorting
                        html.H6("Detection and Sorting Controls", className="mt-3"),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col([
                                dbc.Row(dbc.Button("Detection: OFF", id="detection-button", color="secondary", size="sm", className="w-100 mb-3")),
                                dbc.Row(dbc.Button("Sorting: OFF", id="sorter-button", color="secondary", size="sm", className="w-100 mb-3")),
                            ], width=4, align="center"),
                            dbc.Col(width=1), # Spacer column
                            dbc.Col([
                                dbc.Row([
                                    dbc.Col(html.Div("Total:", style={'fontWeight': 'bold'})),
                                    dbc.Col(html.Div("...", id='droplet-count-div')),
                                ], align="center"),
                                dbc.Row([
                                    dbc.Col(html.Div("Sorted:", style={'fontWeight': 'bold'})),
                                    dbc.Col(html.Div("...", id='sorted-droplet-count-div')),
                                ], align="center"),
                                dbc.Row([
                                    dbc.Col(html.Div("Frequency:", style={'fontWeight': 'bold'})),
                                    dbc.Col(html.Div("... Hz", id='droplet-frequency-div')),
                                ], align="center"),
                            ], align="start", width = 5),
                        ]),
                        html.Hr(),
                        # Lasers
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(html.H6("Laser Controls", className="mt-3"), width='auto'),
                            dbc.Col(html.Div(id='laser-status-indicator', className='status-indicator-off'), width='auto', align='center')
                        ], align='center'),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(dbc.Checklist(id={'type': 'laser-on-checklist', 'index': '405'}, options=[{'label': '405 nm', 'value': '405'}], value=[]), width=2),
                            dbc.Col(dcc.Slider(id={'type': 'laser-power-slider', 'index': '405'}, min=0, max=50, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True}, disabled=False), width=9)
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(dbc.Checklist(id={'type': 'laser-on-checklist', 'index': '488'}, options=[{'label': '488 nm', 'value': '488'}], value=[]), width=2),
                            dbc.Col(dcc.Slider(id={'type': 'laser-power-slider', 'index': '488'}, min=0, max=50, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True}, disabled=False), width=9)
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(dbc.Checklist(id={'type': 'laser-on-checklist', 'index': '561'}, options=[{'label': '561 nm', 'value': '561'}], value=[]), width=2),
                            dbc.Col(dcc.Slider(id={'type': 'laser-power-slider', 'index': '561'}, min=0, max=50, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True}, disabled=False), width=9)
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(dbc.Checklist(id={'type': 'laser-on-checklist', 'index': '633'}, options=[{'label': '633 nm', 'value': '633'}], value=[]), width=2),
                            dbc.Col(dcc.Slider(id={'type': 'laser-power-slider', 'index': '633'}, min=0, max=50, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True}, disabled=False), width=9)
                        ], className="mb-2"),
                        html.Hr(),
                        # Detection Threshold
                        html.H6("Droplet Detection Settings"),
                        html.Label("Enabled Detection Channels:"),
                        dbc.Row([
                            dbc.Col(width=1), # Spacer column
                            dbc.Col(
                                dbc.Checklist(
                                    id='enabled-channels-checklist',
                                    options=[
                                        {'label': '  Ch0', 'value': 0},
                                        {'label': '  Ch1', 'value': 1},
                                        {'label': '  Ch2', 'value': 2},
                                        {'label': '  Ch3', 'value': 3}
                                    ],
                                    value=[0, 1, 2, 3],  # Default value: all channels enabled
                                    inline=False,
                                    className="mb-2"
                                ),
                            ),
                            dbc.Col(width=1)
                        ]),
                        html.Label("Detection Threshold Channel:"),
                        dcc.Dropdown(id='threshold-channel-dropdown',
                                    options=[{'label': f'Channel {i}', 'value': i} for i in range(4)],
                                    value=0, clearable=False, className="mb-2"),
                        html.Label("Detection Threshold (V):"),
                        dcc.Slider(id='threshold-slider', min=0, max=2, step=0.01, value=0.05, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
                        html.Label("Sort Trigger Delay (ms):"),
                        dcc.Slider(id='sort-delay-slider', min=0, max=0.5, step=0.02, value=0.1, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
                        html.Label("Datapoint Count:"),
                        dcc.Input(id='buffer-spinner', type='number', min=0, max=10000, step=500, value=10000, className="mb-2"),
                        html.Div(id='box-select-div', style={'border': '1px solid #555', 'padding': '10px', 'borderRadius': '5px'}, className="mb-3"),
                        html.Hr(),
                        html.H6("Log Files"),
                        html.Label("Scatter Log Filename:"),
                        dbc.Input(id='scatter-filename-input', type='text', value="droplet_log.csv", className="mb-1"),
                        dbc.Button('Save Scatter', id='save-scatter-button', n_clicks=0, color="success", className="w-100"),
                        html.Label("Signal Log Filename:"),
                        dbc.Input(id='signal-filename-input', type='text', value="signal_log.csv", className="mb-1"),
                        dbc.Button('Save Signal Log', id='save-signal-button', n_clicks=0, color="primary", className="w-100 mb-3"),
                        html.Div(id='save-status-div', style={'marginTop': '10px', 'fontWeight': 'bold'}),
                    ], style={'padding': '10px'})
                ]),
                dbc.Tab(label="FPGA Registers", children=[
                    html.Div([
                        html.P("Values are updated every 5 seconds. Enter a new value and press 'Set' to update a register on the FPGA.", className="mt-3"),
                        html.Div(id='fpga-set-status', className="mb-2"),
                        html.Div(id='fpga-register-div'),
                    ], style={'padding': '10px'})
                ]),
            ])
        ], md=3, style={'maxHeight': '90vh', 'overflowY': 'auto', 'paddingRight': '15px'}),
        

        # Instrument Data Column (Middle)
        dbc.Col([
            html.H5("Instrument Data"),
            dbc.Row([
                dbc.Col(dcc.Graph(
                    id='scatter-plot-1',
                    style={'height': '45vh'},
                    figure={'layout': {'xaxis': {'type': 'log', 'range': [math.log10(0.1), math.log10(3)]},
                                      'yaxis': {'type': 'log', 'range': [math.log10(0.1), math.log10(3)]}}}
                ), width=6),
                dbc.Col(dcc.Graph(
                    id='scatter-plot-2',
                    style={'height': '45vh'},
                    figure={'layout': {'xaxis': {'type': 'log', 'range': [math.log10(0.1), math.log10(3)]},
                                      'yaxis': {'type': 'log', 'range': [math.log10(0.1), math.log10(3)]}}}
                ), width=6),
            ]),
            # --- Plot 1 Settings ---
            dbc.Row([
                dbc.Col([
                        html.Label("X-Axis:"),
                        dcc.Dropdown(id='x-axis-dropdown-1', options=axis_options_dict, value=initial_x_key, clearable=False, className="mb-2"),
                        html.Label("Y-Axis:"),
                        dcc.Dropdown(id='y-axis-dropdown-1', options=axis_options_dict, value=initial_y_key, clearable=False, className="mb-2"),
                        dbc.Row([ dbc.Col(html.Label("X-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='x-scale-radio-1', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
                        dbc.Row([
                            dbc.Col(dbc.Input(id='x-min-input-1', type='number', placeholder='X Min', value=0.1, size="sm", step="any"), width=6),
                            dbc.Col(dbc.Input(id='x-max-input-1', type='number', placeholder='X Max', value=3, size="sm", step="any"), width=6),
                        ], className="mb-2"),
                        dbc.Row([ dbc.Col(html.Label("Y-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='y-scale-radio-1', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
                        dbc.Row([
                            dbc.Col(dbc.Input(id='y-min-input-1', type='number', placeholder='Y Min', value=0.1, size="sm", step="any"), width=6),
                            dbc.Col(dbc.Input(id='y-max-input-1', type='number', placeholder='Y Max', value=3, size="sm", step="any"), width=6),
                        ], className="mb-3")]),
                dbc.Col([
                        html.Label("X-Axis:"),
                        dcc.Dropdown(id='x-axis-dropdown-2', options=axis_options_dict, value=initial_x_key_2, clearable=False, className="mb-2"),
                        html.Label("Y-Axis:"),
                        dcc.Dropdown(id='y-axis-dropdown-2', options=axis_options_dict, value=initial_y_key_2, clearable=False, className="mb-2"),
                        dbc.Row([ dbc.Col(html.Label("X-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='x-scale-radio-2', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
                        dbc.Row([
                            dbc.Col(dbc.Input(id='x-min-input-2', type='number', placeholder='X Min', value=0.1, size="sm", step="any"), width=6),
                            dbc.Col(dbc.Input(id='x-max-input-2', type='number', placeholder='X Max', value=3, size="sm", step="any"), width=6),
                        ], className="mb-2"),
                        dbc.Row([ dbc.Col(html.Label("Y-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='y-scale-radio-2', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
                        dbc.Row([
                            dbc.Col(dbc.Input(id='y-min-input-2', type='number', placeholder='Y Min', value=0.1, size="sm", step="any"), width=6),
                            dbc.Col(dbc.Input(id='y-max-input-2', type='number', placeholder='Y Max', value=3, size="sm", step="any"), width=6),
                        ], className="mb-3")]),
                dbc.Button('Clear Scatter', id='clear-scatter-button', n_clicks=0, color="secondary", className="w-100"),
            ]),
            html.Hr(className="my-2"),
            html.H6("SiPM Signals"),
            dcc.Graph(id='signal-plot', style={'height': '25vh'}), # Adjusted height
            html.P(id='update-rate-label', children="Update Rate: ...", style={'textAlign': 'center', 'marginTop': '10px'})
        ], md=6),

        # Camera Column (Right)
        dbc.Col([
            html.H5("Camera Controls"),
            html.Img(
                src="/video_feed" if CAMERA_AVAILABLE else "",
                id='camera-feed-img',
                style={
                    'width': '100%',
                    'border': '1px solid #555',
                    'display': 'block' if CAMERA_AVAILABLE else 'none',
                    'minHeight': '240px', # Set a minimum height
                    'backgroundColor': '#000' if CAMERA_AVAILABLE else 'transparent', # Black background while loading/if small
                    'aspectRatio': '4/3', # Try to maintain aspect ratio
                    'objectFit': 'contain', # Scale image to fit within bounds, maintaining aspect ratio
                    'maxHeight': '75vh' # Constrain camera height
                }
            ),
            html.P(
                "Camera disabled: pypylon or OpenCV not installed.",
                style={'textAlign': 'center', 'fontSize': 'small', 'display': 'block' if not CAMERA_AVAILABLE else 'none'}
            ),
            html.Div([
                html.Hr(),
                dbc.Checkbox(
                    id="camera-trigger-mode-checkbox",
                    label="Enable Hardware Trigger",
                    value=False, # Default to Freerun
                    className="mb-2"
                ),
                html.Label("Exposure Time (µs):"),
                dcc.Slider(id='camera-exposure-slider', min=28, max=200, step=1, value=28, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
                html.Label("Camera Trigger Delay (µs):"),
                dcc.Slider(id='camera-trigger-delay-slider', min=0, max=1000, step=1, value=0, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
                html.Div(id='camera-settings-status', className="mt-2")
            ], style={'display': 'block' if CAMERA_AVAILABLE else 'none'}),
        ], md=3, style={'maxHeight': '90vh', 'overflowY': 'auto', 'paddingRight': '15px'})
    ]),
], fluid=True)


################ Dash Callbacks ################

@app.callback(
    Output('axis-keys-store', 'data'),
    Input('x-axis-dropdown-1', 'value'),
    Input('y-axis-dropdown-1', 'value'),
    Input('x-axis-dropdown-2', 'value'),
    Input('y-axis-dropdown-2', 'value')
)
def update_axis_store(x1, y1, x2, y2):
    return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

@app.callback(
    [Output('scatter-plot-1', 'figure'),
     Output('scatter-plot-2', 'figure'),
     Output('signal-plot', 'figure'),
     Output('update-rate-label', 'children'),
     Output('timer-store', 'data')],
    [Input('interval-component', 'n_intervals'),
     # Plot 1 Inputs
     Input('x-axis-dropdown-1', 'value'),
     Input('y-axis-dropdown-1', 'value'),
     Input('x-scale-radio-1', 'value'),
     Input('y-scale-radio-1', 'value'),
     Input('x-min-input-1', 'value'),
     Input('x-max-input-1', 'value'),
     Input('y-min-input-1', 'value'),
     Input('y-max-input-1', 'value'),
     # Plot 2 Inputs
     Input('x-axis-dropdown-2', 'value'),
     Input('y-axis-dropdown-2', 'value'),
     Input('x-scale-radio-2', 'value'),
     Input('y-scale-radio-2', 'value'),
     Input('x-min-input-2', 'value'),
     Input('x-max-input-2', 'value'),
     Input('y-min-input-2', 'value'),
     Input('y-max-input-2', 'value')],
    [State('threshold-slider', 'value'),
     State('timer-store', 'data'),
     State('gate-selection-store', 'data'),
     State('axis-keys-store', 'data')],
    prevent_initial_call=True
)
def update_graphs(n, x_key_1, y_key_1, x_scale_1, y_scale_1, x_min_1, x_max_1, y_min_1, y_max_1,
                  x_key_2, y_key_2, x_scale_2, y_scale_2, x_min_2, x_max_2, y_min_2, y_max_2,
                  threshold_value, timers, box_data, axis_keys):
    current_time = time.perf_counter(); timers.append(current_time); timers = timers[-100:]
    s_per_update = 0
    if len(timers) > 1: s_per_update = np.mean(np.diff(timers))

    with lock:
        adc1 = instrument.adc1_data
        adc2 = instrument.adc2_data
        adc3 = instrument.adc3_data
        adc4 = instrument.adc4_data
        df = instrument.droplet_data
        sort_gates = instrument.get_sort_gates()

    time_axis = np.linspace(0, 50, 4096)

    signal_fig = go.Figure()
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc1, mode='lines', name='CH0', line=dict(color="#3fe4fa")))
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc2, mode='lines', name='CH1', line=dict(color="#71f445")))
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc3, mode='lines', name='CH2', line=dict(color="#ddfd25")))
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc4, mode='lines', name='CH3', line=dict(color="#b83671")))
    signal_fig.add_hline(y=threshold_value, line_dash="dot", line_color="mediumseagreen", annotation_text="Threshold")
    signal_fig.update_layout(xaxis_title="Time (ms)", yaxis_title="Voltage", yaxis_range=[0, 1.2], legend_title="Signals", uirevision='signal_layout')
    update_text = f"Update Rate: {1 / s_per_update:.01f} Hz ({s_per_update * 1000:.00f} ms)" if s_per_update > 0 else "Calculating..."

    # --- Helper function to generate a scatter plot ---
    def make_scatter(plot_num, x_key, y_key, x_scale, y_scale, x_min, x_max, y_min, y_max, gates):
        if x_key not in df.columns or y_key not in df.columns:
            missing_key = x_key if x_key not in df.columns else y_key
            return go.Figure().update_layout(title=f"Error: Axis '{missing_key}' not found")

        x = df[x_key].values; y = df[y_key].values; density = []
        if len(x) > 0 and len(y) > 0:
            try:
                bins = 25; H, xedges, yedges = np.histogram2d(x, y, bins=bins)
                ix = np.searchsorted(xedges, x, side='right') - 1; iy = np.searchsorted(yedges, y, side='right') - 1
                ix = np.clip(ix, 0, bins - 1); iy = np.clip(iy, 0, bins - 1)
                density = H[ix, iy]
            except Exception as e: print(f"Density/Hist error: {e}"); density = []

        fig = go.Figure(data=go.Scattergl(
            x=x, y=y, mode='markers',
            marker=dict(color=density if len(density) > 0 else 'lightblue', colorscale='Viridis', opacity=0.6, size=4,
                        showscale=True if len(density) > 0 else False, colorbar=dict(title="Density") if len(density) > 0 else None)
        ))

        x_axis_config = {'title': x_key, 'type': x_scale, 'autorange': False}
        y_axis_config = {'title': y_key, 'type': y_scale, 'autorange': False}

        if x_min is not None and x_max is not None and x_max > x_min:
            if x_scale == 'log':
                if x_min > 0 and x_max > 0: x_axis_config['range'] = [math.log10(x_min), math.log10(x_max)]
            else: x_axis_config['range'] = [x_min, x_max]
        
        if y_min is not None and y_max is not None and y_max > y_min:
            if y_scale == 'log':
                if y_min > 0 and y_max > 0: y_axis_config['range'] = [math.log10(y_min), math.log10(y_max)]
            else: y_axis_config['range'] = [y_min, y_max]

        fig.update_layout(xaxis=x_axis_config, yaxis=y_axis_config,
                                  dragmode='select', uirevision=f'scatter{plot_num}')

        # --- Draw Gate Lines ---
        if gates:
            converted_regs = instrument.get_fpga_registers_converted()
            for gate_key, raw_val in gates.items():
                param_match = re.match(r'(low|high)_(intensity|width|area)_thresh\[(\d)\]', gate_key)
                if not param_match: continue
                
                limit_type, param_type, ch_str = param_match.groups()
                ch = int(ch_str)

                # Find the corresponding display key (e.g., 'cur_droplet_intensity_v[0]')
                display_key_suffix = "_v" if param_type == 'intensity' else "_ms" if param_type == 'width' else "_vms"
                display_key = f"cur_droplet_{param_type}{display_key_suffix}[{ch}]"

                # Get the converted value from the instrument's state
                converted_val, unit = converted_regs.get(gate_key, (None, None))
                if converted_val is None: continue

                line_style = dict(color="cyan", width=1, dash="dot")

                # If the plot's X-axis matches the gated parameter, draw vertical lines
                if x_key == display_key:
                    fig.add_vline(x=converted_val, line=line_style)

                # If the plot's Y-axis matches the gated parameter, draw horizontal lines
                if y_key == display_key:
                    fig.add_hline(y=converted_val, line=line_style)
        
        return fig

    # --- Generate both scatter plots ---
    scatter_fig_1 = make_scatter(1, x_key_1, y_key_1, x_scale_1, y_scale_1, x_min_1, x_max_1, y_min_1, y_max_1, sort_gates)
    scatter_fig_2 = make_scatter(2, x_key_2, y_key_2, x_scale_2, y_scale_2, x_min_2, x_max_2, y_min_2, y_max_2, sort_gates)

    return scatter_fig_1, scatter_fig_2, signal_fig, update_text, timers


@app.callback(
    Output({'type': 'laser-on-checklist', 'index': dash.MATCH}, 'id'), # Dummy output
    [Input({'type': 'laser-on-checklist', 'index': dash.MATCH}, 'value'),
     Input({'type': 'laser-power-slider', 'index': dash.MATCH}, 'value')],
    [State({'type': 'laser-power-slider', 'index': dash.MATCH}, 'id')],
    prevent_initial_call=True
)
def update_laser_state(checklist_value, power_mw, slider_id):
    """
    This single callback handles all laser state changes.
    - The checklist turns the laser emission on or off.
    - The slider sets the power level.
    - If the laser is on, changing the slider value updates the power immediately.
    - If the laser is off, changing the slider value does nothing to the hardware.
    - Toggling the checklist on will apply the slider's current power value.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        raise exceptions.PreventUpdate

    laser_name = str(slider_id['index'])
    is_checked = bool(checklist_value)

    with lock:
        if instrument:
            # The checklist is the master control for emission.
            instrument.set_laser_on_state(laser_name, is_checked)

            # If the laser is supposed to be on, set its power.
            # If it's being turned off, set_laser_on_state(False) handles setting power to 0.
            if is_checked:
                instrument.set_laser_power(laser_name, power_mw)

    return slider_id  # No actual change to the dummy output

@app.callback(
    Output('laser-status-indicator', 'className'),
    Input({'type': 'laser-on-checklist', 'index': dash.ALL}, 'value')
)
def update_laser_status_indicator(checklist_values):
    """
    Updates the blinking status indicator for the laser panel.
    Blinks red if any laser is checked on.
    """
    # checklist_values is a list of lists, e.g., [[], ['488'], [], []]
    # any() on this list of lists is True if any sublist is not empty.
    any_laser_on = any(checklist_values)
    return 'status-indicator-on' if any_laser_on else 'status-indicator-off'


@app.callback(
    Output('fpga-set-status', 'children', allow_duplicate=True), # Re-use the status message div
    Input('enabled-channels-checklist', 'value'),
    prevent_initial_call=True
)
def set_enabled_channels(selected_channels):
    """
    Converts the list of selected channels into a bitmask and sends it to the FPGA.
    """
    if selected_channels is None:
        selected_channels = []

    # Create the bitmask from the selected channels.
    # e.g., if [0, 1] is selected, the bitmask is (1 << 0) | (1 << 1) = 1 | 2 = 3.
    bitmask = 0
    for ch_index in selected_channels:
        bitmask |= (1 << ch_index)

    # The FPGA expects a 32-bit integer, so the bitmask should be an integer.
    final_value = int(bitmask)

    with lock:
        if instrument:
            try:
                instrument.set_memory_variable("enabled_channels", final_value)
                msg = f"Success: Enabled channels updated to bitmask {final_value}."
                print(msg)
                return dbc.Alert(msg, color="success", dismissable=True, duration=4000)
            except Exception as e:
                msg = f"Error setting enabled channels: {e}"
                print(msg)
                return dbc.Alert(msg, color="danger", dismissable=True, duration=4000)
    
    raise exceptions.PreventUpdate

@app.callback(
    Output('threshold-slider', 'className'), 
    [Input('threshold-slider', 'value')],
    [State('threshold-channel-dropdown', 'value')],
    prevent_initial_call=True
)
def update_detection_threshold(threshold_volts, channel):
    with lock:
        if instrument:
            instrument.set_detection_threshold(thresh=threshold_volts, ch=channel)
    return "" # No actual class change needed

@app.callback(
    Output('sort-delay-slider', 'className'), # Dummy output to hang the callback on
    Input('sort-delay-slider', 'value'),
    prevent_initial_call=True
)
def update_sort_delay(delay_ms):
    if delay_ms is not None:
        # Convert from ms to us for the FPGA
        delay_us = int(delay_ms * 1000)
        with lock:
            if instrument:
                instrument.set_memory_variable("sort_delay", delay_us)
    return "" # No class change needed


@app.callback(
    [Output('fpga-set-status', 'children', allow_duplicate=True),
     Output('threshold-slider', 'value')],
    Input('threshold-channel-dropdown', 'value'),
    prevent_initial_call=True
)
def update_detection_channel(channel):
    alert_msg = dash.no_update
    new_slider_value = dash.no_update

    with lock:
        if instrument:
            try:
                # 1. Set the detection channel on the FPGA
                instrument.set_memory_variable("detection_channel", channel)
                msg = f"Success: Detection channel updated to {channel}."
                print(msg)
                alert_msg = dbc.Alert(msg, color="success", dismissable=True, duration=4000)

                # 2. Get the threshold for the new channel to update the slider
                converted_regs = instrument.get_fpga_registers_converted()
                thresh_key = f"min_intensity_thresh[{channel}]"
                
                if thresh_key in converted_regs:
                    new_slider_value = converted_regs[thresh_key][0]
                else:
                    print(f"Warning: Could not find {thresh_key} in converted registers to update slider.")

            except Exception as e:
                msg = f"Error updating detection channel: {e}"
                print(msg)
                alert_msg = dbc.Alert(msg, color="danger", dismissable=True, duration=4000)
    
    return alert_msg, new_slider_value

@app.callback(
    Output('camera-settings-status', 'children', allow_duplicate=True),
    Input('camera-trigger-mode-checkbox', 'value'),
    prevent_initial_call=True
)
def manage_camera_thread_for_trigger_mode(hw_trigger_enabled):
    global cam_thread, camera_running, camera_config

    # Update the global config that the thread will use on startup
    camera_config['hw_trigger'] = hw_trigger_enabled

    # Stop the existing camera thread
    if cam_thread and cam_thread.is_alive():
        print("Stopping camera thread for mode change...")
        camera_running = False
        cam_thread.join(timeout=7)
        if cam_thread.is_alive():
            msg = "Error: Camera thread did not stop in time. Mode not changed."
            print(msg)
            return dbc.Alert(msg, color="danger", duration=5000)
        print("Camera thread stopped.")

    # Start a new camera thread which will use the new config
    print(f"Starting new camera thread...")
    camera_running = True
    cam_thread = threading.Thread(target=camera_thread_func, daemon=True)
    cam_thread.start()

    status_str = "Hardware Trigger" if hw_trigger_enabled else "Freerun"
    msg = f"Camera restarting in {status_str} mode."
    return dbc.Alert(msg, color="info", duration=4000)

@app.callback(
    Output('camera-settings-status', 'children'),
    Input('camera-exposure-slider', 'value'),
    Input('camera-trigger-delay-slider', 'value'),
    prevent_initial_call=True
)
def update_camera_settings(exposure_us, delay_us):
    global camera, camera_lock
    
    msgs = []
    triggered_ids = [p['prop_id'].split('.')[0] for p in dash.callback_context.triggered]

    with camera_lock:
        if not (camera and camera.IsOpen()):
            # Don't show an error to the user if the camera is just not ready yet.
            return dash.no_update
        
        try:
            if 'camera-exposure-slider' in triggered_ids:
                camera.ExposureTime.SetValue(float(exposure_us))
                msgs.append(f"Exposure: {exposure_us} µs.")
            
            if 'camera-trigger-delay-slider' in triggered_ids:
                camera.TriggerDelay.SetValue(float(delay_us))
                msgs.append(f"Delay: {delay_us} µs.")

        except pylon.GenericException as e:
            msg = f"Error setting camera parameter: {e}"
            print(msg)
            return dbc.Alert(msg, color="danger", duration=4000)
        except Exception as e:
            msg = f"An unexpected error occurred: {e}"
            print(msg)
            return dbc.Alert(msg, color="danger", duration=4000)

    if msgs:
        return dbc.Alert(" ".join(msgs), color="success", duration=2000)

    return dash.no_update

@app.callback(
    [Output('detection-button', 'children'),
     Output('detection-button', 'color'),
     Output('detection-button', 'data'),
     Output('sorter-button', 'disabled')],  # Add this output
    [Input('detection-button', 'n_clicks')],
    [State('detection-button', 'data')],
    prevent_initial_call=True
)
def toggle_detection(n_clicks, is_on):
    if n_clicks is None:
        raise exceptions.PreventUpdate
    new_state = not is_on
    with lock:
        if instrument:
            instrument.enable_detection(new_state)
    
    # Determine the disabled state for the sorter button
    sorter_disabled = not new_state # Sorter is disabled if detection is OFF
    
    if new_state:
        # Detection is ON, enable the sorter button
        return "Detection: ON", "success", new_state, sorter_disabled
    else:
        # Detection is OFF, disable the sorter button
        return "Detection: OFF", "secondary", new_state, sorter_disabled

@app.callback(
    [Output('sorter-button', 'children'),
     Output('sorter-button', 'color'),
     Output('sorter-state-store', 'data')],
    [Input('sorter-button', 'n_clicks'),
     Input('detection-button', 'n_clicks')], # Listen to the detection button
    [State('sorter-state-store', 'data'),
     State('detection-button', 'data')],     # Get detection button state
    prevent_initial_call=True
)
def toggle_sorter(n_clicks, n_detection_clicks, sorter_is_on, detection_is_on):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Handle the case when the Sorter button is clicked
    if triggered_id == 'sorter-button':
        # Don't toggle if detection is currently off
        if not detection_is_on:
            raise exceptions.PreventUpdate
        
        # Toggle the sorter state
        new_state = not sorter_is_on
        with lock:
            if instrument:
                instrument.enable_sorter(new_state)
        
        if new_state:
            return "Sorting: ON", "success", new_state
        else:
            return "Sorting: OFF", "secondary", new_state

    raise exceptions.PreventUpdate

@app.callback(
    Output('gate-selection-store', 'data'),
    [Input('scatter-plot-1', 'selectedData'),
     Input('scatter-plot-2', 'selectedData')],
    State('axis-keys-store', 'data'),
    prevent_initial_call=True
)
def store_box_select(selectedData1, selectedData2, axis_keys):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    selectedData = selectedData1 if triggered_id == 'scatter-plot-1' else selectedData2
    
    if selectedData and 'range' in selectedData:
        x_range = selectedData['range']['x']
        y_range = selectedData['range']['y']

        if triggered_id == 'scatter-plot-1':
            current_sort_keys = [axis_keys['x1'], axis_keys['y1']]
        else: # triggered by scatter-plot-2
            current_sort_keys = [axis_keys['x2'], axis_keys['y2']]

        # Store coordinates AND the keys they correspond to
        new_box = {"x0": [x_range[0]], "y0": [y_range[0]], "x1": [x_range[1]], "y1": [y_range[1]],
                   "x_key": current_sort_keys[0], "y_key": current_sort_keys[1]}

        print(f"New selection. Keys={current_sort_keys}. Box={new_box}") # Keep for debugging if needed
        with lock:
            instrument.set_gate_limits(sort_keys=current_sort_keys, limits=new_box)
        return new_box
    
    raise exceptions.PreventUpdate

@app.callback(
    Output('box-select-div', 'children'),
    Input('gate-selection-store', 'data')
)
def display_box_select(box_data):
    if not box_data or not isinstance(box_data.get("x0"), list):
         box = {"x0": [0.0], "y0": [0.0], "x1": [0.0], "y1": [0.0]}
    else:
        box = box_data
    def to_sci(v):
        if v == 0: return ["0"]
        try:
            if not isinstance(v, (int, float)) or math.isinf(v) or math.isnan(v) or v == 0:
                if v == 0: return ["0"]
                return ["N/A"]
            log_v = math.log10(abs(v))
            exp = math.floor(log_v)
            base = v / (10**exp)
            return [f"{base:.1f} × 10", html.Sup(exp)]
        except (ValueError, TypeError, OverflowError): return ["N/A"]
    return [
        html.B("Gate Selection:", style={'display': 'block', 'marginBottom': '5px'}),
        html.Span(["Xmin: "] + to_sci(box['x0'][0]) + [" | Ymin: "] + to_sci(box['y0'][0]), style={'display': 'block'}),
        html.Span(["Xmax: "] + to_sci(box['x1'][0]) + [" | Ymax: "] + to_sci(box['y1'][0]), style={'display': 'block'}),
    ]

@app.callback(
        Output('save-status-div', 'children'), 
        [Input('save-scatter-button', 'n_clicks'),
         Input('save-signal-button', 'n_clicks'),
         Input('clear-scatter-button', 'n_clicks')],
        [State('scatter-filename-input', 'value'), 
         State('signal-filename-input', 'value')], 
         prevent_initial_call=True
)
def data_actions(n_scatter, n_signal, n_clear, scatter_file, signal_file):
    ctx = dash.callback_context
    if not ctx.triggered or not ctx.triggered[0]['value']:
        raise exceptions.PreventUpdate
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    msg = ""
    color = "info"
    with lock:
        try:
            if button_id == 'save-scatter-button':
                if not scatter_file.endswith(".csv"): scatter_file += ".csv"
                instrument.save_droplet_data_log(filename=scatter_file)
                msg = f"Scatter data saved to {scatter_file}"
                color = "success"
            elif button_id == 'save-signal-button':
                if not signal_file.endswith(".csv"): signal_file += ".csv"
                instrument.save_adc_log(filename=signal_file)
                msg = f"Signal data saved to {signal_file}"
            elif button_id == 'clear-scatter-button':
                instrument.clear_droplet_data()
                msg = "Scatter plot data cleared."
                color = "warning"
        except Exception as e:
            msg = f"Error performing action: {e}"
            color = "danger"
    print(msg)
    return dbc.Alert(msg, color=color, dismissable=True, duration=4000)

@app.callback(
    [Output('droplet-count-div', 'children'),
     Output('sorted-droplet-count-div', 'children'),
     Output('droplet-frequency-div', 'children')],
    Input('counter-interval-component', 'n_intervals')
)
def update_counters(n):
    # Default values
    count_str, sorted_str, freq_str = "...", "...", "... Hz"

    # Note: This polls all registers every second, which may have a performance impact.
    # A more optimized instrument class could fetch these specific registers 
    # more efficiently in its background data acquisition thread.
    with lock:
        if instrument:
            try:
                # This reads ALL registers via the instrument object, which handles both simulation and real hardware.
                # Assumes these registers exist on the FPGA and are part of the conversion map.
                converted_registers = instrument.get_fpga_registers_converted()

                droplet_count = converted_registers.get('droplet_counter', ("N/A", ""))[0]
                sorted_droplet_count = converted_registers.get('sorted_droplet_counter', ("N/A", ""))[0]
                droplet_freq = converted_registers.get('droplet_frequency', ("N/A", ""))[0]

                count_str = f"{droplet_count:,}" if isinstance(droplet_count, int) else str(droplet_count)
                sorted_str = f"{sorted_droplet_count:,}" if isinstance(sorted_droplet_count, int) else str(sorted_droplet_count)
                freq_str = f"{droplet_freq:,} Hz" if isinstance(droplet_freq, (int, float)) else str(droplet_freq)
            except Exception as e:
                print(f"Could not update counters from FPGA: {e}")
                count_str, sorted_str, freq_str = "Error", "Error", "Error"
    
    return count_str, sorted_str, freq_str

@app.callback(
    Output('fpga-register-div', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_fpga_register_display(n):
    if n % 20 != 0: # Update every 5 seconds (20 * 250ms)
        return dash.no_update

    with lock:
        if instrument:
            raw_registers = instrument.get_fpga_registers()
            converted_registers = instrument.get_fpga_registers_converted()
        else:
            raw_registers = {}
            converted_registers = {}

    if not raw_registers:
        return dbc.Alert("FPGA registers not available yet.", color="warning")

    header = dbc.Row([
        dbc.Col(html.B("Register Name"), width=3),
        dbc.Col(html.B("Converted Value"), width=3),
        dbc.Col(html.B("Raw Value"), width=2),
        dbc.Col(html.B("New Value"), width=2),
        dbc.Col(width=2), # for button
    ], className="mb-2")

    rows = [header, html.Hr()]
    for name, raw_value in sorted(raw_registers.items()):
        converted_value, unit = converted_registers.get(name, (raw_value, ""))

        if isinstance(converted_value, float):
            display_text = f"{converted_value:.3f} {unit}"
            placeholder_text = f"{converted_value:.3f}"
        else:
            display_text = f"{converted_value} {unit}"
            placeholder_text = f"{converted_value}"

        # For inputs that are not numbers (e.g. binary strings), use text input
        is_numeric = isinstance(converted_value, (int, float))
        input_type = 'number' if is_numeric else 'text'

        row = dbc.Row([
            dbc.Col(html.Label(name), width=3, style={'word-wrap': 'break-word'}),
            dbc.Col(html.Div(display_text), width=3),
            dbc.Col(html.Div(f"{raw_value}"), width=2),
            dbc.Col(dbc.Input(id={'type': 'fpga-input', 'index': name}, type=input_type, placeholder=placeholder_text, step="any")),
            dbc.Col(dbc.Button("Set", id={'type': 'fpga-set-button', 'index': name}, size="sm", className="w-100"), width=2),
        ], className="mb-2", align="center")
        rows.append(row)

    return html.Div(rows)

@app.callback(
    Output('fpga-set-status', 'children'),
    Input({'type': 'fpga-set-button', 'index': dash.ALL}, 'n_clicks'),
    [State({'type': 'fpga-input', 'index': dash.ALL}, 'value'),
     State({'type': 'fpga-input', 'index': dash.ALL}, 'id')],
    prevent_initial_call=True
)
def set_fpga_register(n_clicks, values, ids):
    ctx = dash.callback_context
    triggered = ctx.triggered[0]
    if not triggered or not triggered['value']:
        raise exceptions.PreventUpdate

    triggered_id = json.loads(triggered['prop_id'].split('.')[0])
    register_name = triggered_id['index']

    value_to_set_str = next((val for i, val in enumerate(values) if ids[i]['index'] == register_name), None)

    if value_to_set_str is not None:
        try:
            # User inputs the converted value, which should be a number
            value_to_set = float(value_to_set_str)

            # This will be converted back to a raw integer for the FPGA
            final_value = value_to_set

            # Reverse conversion logic
            ch_match = re.search(r'\[(\d)\]', register_name)
            ch = int(ch_match.group(1)) if ch_match else None

            with lock:
                if instrument:
                    if ch is not None:
                        if 'intensity_thresh' in register_name:
                            final_value = instrument.convert_volts_to_raw(value_to_set, ch)
                        elif 'area_thresh' in register_name:
                            # User enters V·ms, convert to V, then to raw
                            volts = value_to_set * 1000.0
                            final_value = instrument.convert_volts_to_raw(volts, ch)
                        elif 'width_thresh' in register_name:
                            # User enters ms, convert to us for raw value
                            final_value = value_to_set * 1000.0
                    elif 'sort_delay' in register_name or 'sort_duration' in register_name or 'camera_trig_delay' in register_name or 'camera_trig_duration' in register_name:
                        # User enters ms, convert to us for raw value
                        final_value = value_to_set * 1000.0

                    # For non-converted values, final_value remains value_to_set
                    final_value_int = int(final_value)
                    instrument.set_memory_variable(register_name, final_value_int)
                    msg = f"Success: Set {register_name} to {value_to_set_str} (raw: {final_value_int})"
                    print(msg)
                    return dbc.Alert(msg, color="success", dismissable=True, duration=4000)

        except (ValueError, TypeError) as e:
            msg = f"Error: Invalid value for {register_name}: '{value_to_set_str}'. Must be a number. ({e})"
            print(msg)
            return dbc.Alert(msg, color="danger", dismissable=True, duration=4000)

    return dash.no_update



################ Cleanup and Signal Handling ################

def cleanup():
    global camera_running, cam_thread
    print("\nInitiating shutdown sequence...")
    # Stop camera thread first
    if CAMERA_AVAILABLE and cam_thread:
        print("Stopping camera thread...")
        camera_running = False
        cam_thread.join(timeout=7) # Wait for camera thread to finish
        if cam_thread.is_alive():
            print("Warning: Camera thread did not stop in time.")
        else:
            print("Camera thread stopped.")
    
    # Then instrument
    print("Shutting down instrument...")
    with lock:
        if instrument:
            try:
                instrument.stop()
                print("Instrument stop called.")
            except Exception as e:
                print(f"Error during instrument stop: {e}")
    print("Cleanup finished.")


def handle_signal(sig, frame):
    print(f"Received signal {sig}, initiating shutdown...")
    cleanup(); time.sleep(0.5); sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
try: signal.signal(signal.SIGTERM, handle_signal)
except AttributeError: print("SIGTERM not available.")

def open_browser():
    try: webbrowser.open_new_tab(SERVER_URL)
    except Exception as e: print(f"Could not open browser automatically: {e}")


################ Run App ################
if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print("Werkzeug (HTTP Server) logging is set to ERROR level.")

    if CAMERA_AVAILABLE:
        print("Starting camera thread...")
        camera_running = True
        cam_thread = threading.Thread(target=camera_thread_func, daemon=True)
        cam_thread.start()
    else:
        print("Camera functionality disabled.")
    
    # Check if laser is available and handle it
    if instrument and instrument.laser_box:
        print("Laser control is available.")
    else:
        print("Laser control is DISABLED.")

    print(f"Starting Dash server on {SERVER_URL} ... Press Ctrl+C to stop.")
    Timer(1.5, open_browser).start()
    app.run(debug=False, port=8050)
    print("Server has been shut down.") # This might not be reached due to sys.exit in signal_handler
    cleanup() # Final attempt at cleanup
