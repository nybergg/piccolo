# Imports from the python standard library:
import math
import numpy as np
import sys
import threading
import time
import pandas as pd
import signal
import webbrowser
from threading import Timer
import logging

# Third party imports: Dash and Plotly
import dash
from dash import dcc, html, Input, Output, State, exceptions
import plotly.graph_objects as go
import plotly.io as pio
import dash_bootstrap_components as dbc
from flask import Response # For MJPEG streaming

# Camera related imports
from pypylon import pylon
import cv2
camera_available = True

# --- Import Actual Instrument/Sim Modules ---
import concurrency_tools as ct
from piccolo_instrument_sim import InstrumentSim
from piccolo_instrument import Instrument
print("Successfully imported all modules.")
# --- End Imports ---

# --- Global Instrument/Sim and Lock ---
simulate = False
launch_rp = True
lock = threading.Lock() # For instrument data
instrument = None
SERVER_URL = "http://127.0.0.1:8050/"

if simulate:
    instrument = ct.ObjectInSubprocess(InstrumentSim)
    instrument.start_generating()
else:
    instrument = Instrument(rp_dir="piccolo_testing", verbose=True)
    if launch_rp:
        print("Launching Piccolo RP... please wait.")
        instrument.launch_piccolo_rp()
        time.sleep(10)
    instrument.start_clients()
    time.sleep(1)

# --- Camera Globals ---
latest_frame_jpeg = None
frame_lock = threading.Lock() # Separate lock for camera frame
camera_running = False
cam_thread = None

# Create an initial placeholder image for the camera feed
if camera_available:
    placeholder_img = np.zeros((240, 320, 3), dtype=np.uint8) # Small placeholder
    cv2.putText(placeholder_img, "Waiting for Camera...", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
    ret_init, jpeg_init = cv2.imencode('.jpg', placeholder_img)
    if ret_init:
        latest_frame_jpeg = jpeg_init.tobytes()

# --- Camera Thread Function ---
def camera_thread_func():
    global latest_frame_jpeg, camera_running
    if not camera_available:
        print("Camera thread not starting: pypylon or OpenCV missing.")
        return

    print("Camera thread started.")
    try:
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        camera.Open()
        # Optional: Configure camera parameters (e.g., resolution, exposure, gain)
        # camera.Width.SetValue(640)
        # camera.Height.SetValue(480)
        # camera.PixelFormat.SetValue("BGR8Packed") # Or Mono8, ensure it's a format OpenCV understands
        # camera.ExposureTime.SetValue(10000) # Example: 10ms

        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed # OpenCV uses BGR
        
        while camera.IsGrabbing() and camera_running:
            try:
                grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                if grabResult.GrabSucceeded():
                    image = converter.Convert(grabResult)
                    img_array = image.GetArray()

                    # Optional: Resize for web display to reduce bandwidth
                    # target_width = 640
                    # aspect_ratio = img_array.shape[0] / img_array.shape[1]
                    # target_height = int(target_width * aspect_ratio)
                    # img_resized = cv2.resize(img_array, (target_width, target_height))
                    # ret, jpeg = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 70])

                    ret, jpeg = cv2.imencode('.jpg', img_array, [cv2.IMWRITE_JPEG_QUALITY, 75]) # Quality 0-100
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


        camera.StopGrabbing()
        camera.Close()
        print("Camera stopped and closed.")
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
        print("Camera thread finished.")


# --- Dark Theme Setup ---
pio.templates.default = "plotly_dark"
external_stylesheets = [dbc.themes.CYBORG]

# --- Dash App Initialization ---
app = dash.Dash(__name__,
                title="Piccolo UI (Dash)",
                external_stylesheets=external_stylesheets,
                update_title=None)

# --- MJPEG Streaming Route ---
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
    if not camera_available:
        return "Camera support is not available (missing pypylon or OpenCV).", 503
    return Response(generate_camera_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# --- Define Axis Options ---
axis_options_list = [
    "cur_droplet_intensity[0]", "cur_droplet_intensity[1]",
    "cur_droplet_intensity_v[0]", "cur_droplet_intensity_v[1]",
    "cur_droplet_width[0]", "cur_droplet_width[1]",
    "cur_droplet_width_ms[0]", "cur_droplet_width_ms[1]",
    "cur_droplet_area[0]", "cur_droplet_area[1]",
    "cur_droplet_area_vms[0]", "cur_droplet_area_vms[1]",
]
axis_options_dict = [{'label': i, 'value': i} for i in axis_options_list]
initial_x_key = "cur_droplet_intensity_v[0]"
initial_y_key = "cur_droplet_intensity_v[1]"

# --- Dash App Layout ---
app.layout = dbc.Container([
    dcc.Store(id='timer-store', data=[]),
    dcc.Store(id='gate-selection-store', data={"x0": [0.0], "y0": [0.0], "x1": [0.0], "y1": [0.0]}),
    dcc.Store(id='axis-keys-store', data={'x': initial_x_key, 'y': initial_y_key}),
    dcc.Interval(id='interval-component', interval=250, n_intervals=0),
    html.H3("Piccolo", style={'textAlign': 'center', 'marginBottom': '20px'}), # Centered main title

    dbc.Row([
        # --- Controls Column (Left) ---
        dbc.Col([
            html.H5("Controls"),
            html.Hr(),
            html.Label("488nm Laser Power:"),
            dcc.Slider(id='laser0-slider', min=0, max=25, step=1, value=0, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
            html.Label("520nm Laser Power:"),
            dcc.Slider(id='laser1-slider', min=0, max=25, step=1, value=0, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
            html.Label("SiPM 0 Threshold:"),
            dcc.Slider(id='threshold-slider', min=0, max=2, step=0.01, value=0.05, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
            html.Label("Datapoint Count:"),
            dcc.Input(id='buffer-spinner', type='number', min=0, max=10000, step=500, value=10000, className="mb-2"),
            html.Hr(),
            html.H6("Scatter Plot Settings"),
            html.Label("X-Axis Data:"),
            dcc.Dropdown(id='x-axis-dropdown', options=axis_options_dict, value=initial_x_key, clearable=False, className="mb-2"),
            html.Label("Y-Axis Data:"),
            dcc.Dropdown(id='y-axis-dropdown', options=axis_options_dict, value=initial_y_key, clearable=False, className="mb-2"),
            dbc.Row([ dbc.Col(html.Label("X-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='x-scale-radio', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
            dbc.Row([ dbc.Col(dbc.Input(id='x-min-input', type='number', placeholder='X Min', size="sm", step="any"), width=6), dbc.Col(dbc.Input(id='x-max-input', type='number', placeholder='X Max', size="sm", step="any"), width=6), ], className="mb-2"),
            dbc.Row([ dbc.Col(html.Label("Y-Scale:"), width=4), dbc.Col(dcc.RadioItems(id='y-scale-radio', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8), ], className="mb-1"),
            dbc.Row([ dbc.Col(dbc.Input(id='y-min-input', type='number', placeholder='Y Min', size="sm", step="any"), width=6), dbc.Col(dbc.Input(id='y-max-input', type='number', placeholder='Y Max', size="sm", step="any"), width=6), ], className="mb-3"),
            html.Hr(),
            html.Div(id='box-select-div', style={'border': '1px solid #555', 'padding': '10px', 'borderRadius': '5px'}, className="mb-3"),
            html.Hr(),
            html.H6("Log Files"),
            html.Label("Scatter Log Filename:"),
            dbc.Input(id='scatter-filename-input', type='text', value="droplet_log.csv", className="mb-1"),
            dbc.Button('Save Scatter Log', id='save-scatter-button', n_clicks=0, color="success", className="w-100 mb-3"),
            html.Label("Signal Log Filename:"),
            dbc.Input(id='signal-filename-input', type='text', value="signal_log.csv", className="mb-1"),
            dbc.Button('Save Signal Log', id='save-signal-button', n_clicks=0, color="primary", className="w-100 mb-3"),
            html.Div(id='save-status-div', style={'marginTop': '10px', 'fontWeight': 'bold'}),
        ], md=3, style={'maxHeight': '90vh', 'overflowY': 'auto', 'paddingRight': '15px'}),

        # --- Plots Column (Middle) ---
        dbc.Col([
            html.H6("Droplet Data"),
            dcc.Graph(id='scatter-plot', style={'height': '45vh'}), # Adjusted height
            html.Hr(className="my-2"),
            html.H6("SiPM Signals"),
            dcc.Graph(id='signal-plot', style={'height': '28vh'}), # Adjusted height
            html.P(id='update-rate-label', children="Update Rate: ...", style={'textAlign': 'center', 'marginTop': '10px'})
        ], md=6),

        # --- Camera Column (Right) ---
        dbc.Col([
            html.H6("Basler Camera Live View"),
            html.Img(
                src="/video_feed" if camera_available else "",
                id='camera-feed-img',
                style={
                    'width': '100%',
                    'border': '1px solid #555',
                    'display': 'block' if camera_available else 'none',
                    'minHeight': '240px', # Set a minimum height
                    'backgroundColor': '#000' if camera_available else 'transparent', # Black background while loading/if small
                    'aspectRatio': '4/3', # Try to maintain aspect ratio
                    'objectFit': 'contain', # Scale image to fit within bounds, maintaining aspect ratio
                    'maxHeight': '75vh' # Constrain camera height
                }
            ),
            html.P(
                "Camera disabled: pypylon or OpenCV not installed.",
                style={'textAlign': 'center', 'fontSize': 'small', 'display': 'block' if not camera_available else 'none'}
            )
        ], md=3)
    ]),
], fluid=True)


# --- Dash Callbacks ---

@app.callback(
    Output('axis-keys-store', 'data'),
    Input('x-axis-dropdown', 'value'),
    Input('y-axis-dropdown', 'value')
)
def update_axis_store(x_axis, y_axis):
    return {'x': x_axis, 'y': y_axis}

@app.callback(
    [Output('scatter-plot', 'figure'),
     Output('signal-plot', 'figure'),
     Output('update-rate-label', 'children'),
     Output('timer-store', 'data')],
    [Input('interval-component', 'n_intervals'),
     Input('x-axis-dropdown', 'value'),
     Input('y-axis-dropdown', 'value'),
     Input('x-scale-radio', 'value'),
     Input('y-scale-radio', 'value'),
     Input('x-min-input', 'value'),
     Input('x-max-input', 'value'),
     Input('y-min-input', 'value'),
     Input('y-max-input', 'value')],
    [State('threshold-slider', 'value'),
     State('timer-store', 'data'),
     State('gate-selection-store', 'data'),
     State('axis-keys-store', 'data')]
)
def update_graphs(n, x_key_in, y_key_in, x_scale, y_scale,
                  x_min_user, x_max_user, y_min_user, y_max_user,
                  threshold_value, timers, box_data, axis_keys):
    current_time = time.perf_counter(); timers.append(current_time); timers = timers[-100:]
    s_per_update = 0
    if len(timers) > 1: s_per_update = np.mean(np.diff(timers))

    with lock:
        if simulate:
            adc1 = instrument.signal[0]; adc2 = instrument.signal[1]; df = instrument.droplet_data
        else:
            adc1 = instrument.adc1_data; adc2 = instrument.adc2_data; df = instrument.droplet_data

    x_key = axis_keys['x']
    y_key = axis_keys['y']
    time_axis = np.linspace(0, 50, 4096)

    signal_fig = go.Figure()
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc1, mode='lines', name='SiPM0', line=dict(color='mediumseagreen')))
    signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc2, mode='lines', name='SiPM1', line=dict(color='royalblue')))
    signal_fig.add_hline(y=threshold_value, line_dash="dot", line_color="mediumseagreen", annotation_text="Threshold")
    signal_fig.update_layout(title="SiPM Data", xaxis_title="Time (ms)", yaxis_title="Voltage", yaxis_range=[0, 1.2], legend_title="Signals", uirevision='signal_layout')
    update_text = f"Update Rate: {1 / s_per_update:.01f} Hz ({s_per_update * 1000:.00f} ms)" if s_per_update > 0 else "Calculating..."

    if x_key not in df.columns or y_key not in df.columns:
        missing_key = x_key if x_key not in df.columns else y_key
        empty_scatter = go.Figure().update_layout(title=f"Error: Axis '{missing_key}' not found in data")
        return empty_scatter, signal_fig, update_text, timers

    x = df[x_key].values; y = df[y_key].values; density = []
    if len(x) > 0 and len(y) > 0:
        try:
            bins = 25; H, xedges, yedges = np.histogram2d(x, y, bins=bins)
            ix = np.searchsorted(xedges, x, side='right') - 1; iy = np.searchsorted(yedges, y, side='right') - 1
            ix = np.clip(ix, 0, bins - 1); iy = np.clip(iy, 0, bins - 1)
            density = H[ix, iy]
        except Exception as e: print(f"Density/Hist error: {e}"); density = []

    scatter_fig = go.Figure(data=go.Scattergl(
        x=x, y=y, mode='markers',
        marker=dict(color=density if len(density) > 0 else 'lightblue', colorscale='Viridis', opacity=0.6, size=4,
                    showscale=True if len(density) > 0 else False, colorbar=dict(title="Density") if len(density) > 0 else None)
    ))

    x_axis_config = {'title': x_key, 'type': x_scale}
    y_axis_config = {'title': y_key, 'type': y_scale}

    if x_min_user is not None and x_max_user is not None:
        if x_max_user > x_min_user:
            if x_scale == 'log':
                if x_min_user > 0 and x_max_user > 0: x_axis_config['range'] = [math.log10(x_min_user), math.log10(x_max_user)]
                else: print(f"Warning: Log X-range values ({x_min_user}, {x_max_user}) must be > 0.")
            else: x_axis_config['range'] = [x_min_user, x_max_user]
        else: print(f"Warning: X-max ({x_max_user}) must be > X-min ({x_min_user}).")
    if y_min_user is not None and y_max_user is not None:
        if y_max_user > y_min_user:
            if y_scale == 'log':
                if y_min_user > 0 and y_max_user > 0: y_axis_config['range'] = [math.log10(y_min_user), math.log10(y_max_user)]
                else: print(f"Warning: Log Y-range values ({y_min_user}, {y_max_user}) must be > 0.")
            else: y_axis_config['range'] = [y_min_user, y_max_user]
        else: print(f"Warning: Y-max ({y_max_user}) must be > Y-min ({y_min_user}).")

    scatter_fig.update_layout(title='Density Scatter Plot', xaxis=x_axis_config, yaxis=y_axis_config,
                              dragmode='select', uirevision=x_key + y_key + x_scale + y_scale + str(x_min_user) + str(x_max_user) + str(y_min_user) + str(y_max_user))

    if box_data and box_data.get("x0") and box_data["x0"][0] != 0.0:
        try:
            scatter_fig.add_shape( type="rect", x0=box_data["x0"][0], y0=box_data["y0"][0],
                x1=box_data["x1"][0], y1=box_data["y1"][0], line=dict(color="RoyalBlue", width=2, dash="dot"),
                fillcolor="LightSkyBlue", opacity=0.3, layer="below" )
        except Exception as e: print(f"Error adding shape: {e}")

    return scatter_fig, signal_fig, update_text, timers


@app.callback( Output('laser0-slider', 'value'), [Input('laser0-slider', 'value'), Input('laser1-slider', 'value'), Input('threshold-slider', 'value')], prevent_initial_call=True)
def update_sliders(g0, g1, thresh):
    ctx = dash.callback_context; trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    with lock:
            if simulate:
                if trigger_id == 'laser0-slider': instrument.set_sipm_gain(0, g0)
                elif trigger_id == 'laser1-slider': instrument.set_sipm_gain(1, g1)
                elif trigger_id == 'threshold-slider': instrument.set_threshold(thresh)
            else:
                if trigger_id == 'threshold-slider': instrument.set_detection_threshold(thresh=thresh, thresh_key="min_intensity_thresh[0]")
    return g0

@app.callback( Output('buffer-spinner', 'className'), [Input('buffer-spinner', 'value')], prevent_initial_call=True)
def update_buffer(value):
    if value is not None:
        with lock:
            if simulate: instrument.buffer_length = value
    return "mb-2"

@app.callback(
    Output('gate-selection-store', 'data'),
    Input('scatter-plot', 'selectedData'),
    State('axis-keys-store', 'data'),
    prevent_initial_call=True
)
def store_box_select(selectedData, axis_keys):
    if selectedData and 'range' in selectedData:
        x_range = selectedData['range']['x']
        y_range = selectedData['range']['y']
        new_box = {"x0": [x_range[0]], "y0": [y_range[0]], "x1": [x_range[1]], "y1": [y_range[1]]}
        current_sort_keys = [axis_keys['x'], axis_keys['y']]
        # print(f"New selection. Keys={current_sort_keys}. Box={new_box}") # Keep for debugging if needed
        with lock:
            instrument.set_gate_limits(sort_keys=current_sort_keys, limits=new_box)
        return new_box
    else:
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

@app.callback( Output('save-status-div', 'children'), [Input('save-scatter-button', 'n_clicks'), Input('save-signal-button', 'n_clicks')], [State('scatter-filename-input', 'value'), State('signal-filename-input', 'value')], prevent_initial_call=True)
def save_data(n_scatter, n_signal, scatter_file, signal_file):
    ctx = dash.callback_context; button_id = ctx.triggered[0]['prop_id'].split('.')[0]; msg = ""
    with lock:
        try:
            if button_id == 'save-scatter-button':
                if not scatter_file.endswith(".csv"): scatter_file += ".csv"
                instrument.save_droplet_data_log(filename=scatter_file)
                msg = f"Scatter data saved to {scatter_file}"
            elif button_id == 'save-signal-button':
                if not signal_file.endswith(".csv"): signal_file += ".csv"
                instrument.save_adc_log(filename=signal_file)
                msg = f"Signal data saved to {signal_file}"
        except Exception as e: msg = f"Error saving data: {e}"
    print(msg)
    return msg

# --- Cleanup and Signal Handling ---
def cleanup():
    global camera_running, cam_thread
    print("\nInitiating shutdown sequence...")
    # Stop camera thread first
    if camera_available and cam_thread:
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
        if instrument and hasattr(instrument, 'stop') and callable(instrument.stop):
            try: instrument.stop(); print("Instrument stop called.")
            except Exception as e: print(f"Error during instrument stop: {e}")
        else: print("Instrument has no 'stop' method or is not initialized.")
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

# --- Run App ---
if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print("Werkzeug (HTTP Server) logging is set to ERROR level.")

    if camera_available:
        print("Starting camera thread...")
        camera_running = True
        cam_thread = threading.Thread(target=camera_thread_func, daemon=True)
        cam_thread.start()
    else:
        print("Camera functionality disabled.")

    print(f"Starting Dash server on {SERVER_URL} ... Press Ctrl+C to stop.")
    Timer(1.5, open_browser).start()
    app.run(debug=False, port=8050)
    print("Server has been shut down.") # This might not be reached due to sys.exit in signal_handler
    cleanup() # Final attempt at cleanup
