"""
Piccolo UI layout — defines the Dash app layout.

All component definitions live here. No callbacks, no global state.
"""

import math

from dash import dcc, html
import dash_bootstrap_components as dbc


# Axis options for scatter plot dropdowns
AXIS_OPTIONS_LIST = [
    "cur_droplet_intensity[0]", "cur_droplet_intensity[1]", "cur_droplet_intensity[2]", "cur_droplet_intensity[3]",
    "cur_droplet_intensity_v[0]", "cur_droplet_intensity_v[1]", "cur_droplet_intensity_v[2]", "cur_droplet_intensity_v[3]",
    "cur_droplet_width_ms[0]", "cur_droplet_width_ms[1]", "cur_droplet_width_ms[2]", "cur_droplet_width_ms[3]",
    "cur_droplet_area_vms[0]", "cur_droplet_area_vms[1]", "cur_droplet_area_vms[2]", "cur_droplet_area_vms[3]",
]
AXIS_OPTIONS_DICT = [{'label': i, 'value': i} for i in AXIS_OPTIONS_LIST]

INITIAL_X_KEY = "cur_droplet_intensity_v[0]"
INITIAL_Y_KEY = "cur_droplet_intensity_v[1]"
INITIAL_X_KEY_2 = "cur_droplet_intensity_v[2]"
INITIAL_Y_KEY_2 = "cur_droplet_intensity_v[3]"


def build_layout(camera_available: bool, simulate: bool) -> dbc.Container:
    """Build the full Dash layout."""
    return dbc.Container([
        dcc.Store(id='timer-store', data=[]),
        dcc.Store(id='gate-selection-store', data={"x0": [0.0], "y0": [0.0], "x1": [0.0], "y1": [0.0]}),
        dcc.Store(id='axis-keys-store', data={'x1': INITIAL_X_KEY, 'y1': INITIAL_Y_KEY, 'x2': INITIAL_X_KEY_2, 'y2': INITIAL_Y_KEY_2}),
        dcc.Store(id='sorter-state-store', data=False),
        dcc.Interval(id='counter-interval-component', interval=1000, n_intervals=0),
        dcc.Interval(id='interval-component', interval=250, n_intervals=0),
        dbc.Alert("SIMULATION MODE", color="warning", className="text-center mb-0 py-1") if simulate else html.Span(),
        dbc.Row(html.Hr()),
        dbc.Row([
            _controls_column(),
            _data_column(),
            _camera_column(camera_available),
        ]),
    ], fluid=True)


def _controls_column():
    """Left column: instrument controls and FPGA registers."""
    return dbc.Col([
        html.H5("Instrument Controls"),
        dbc.Tabs([
            dbc.Tab(label="Settings", children=[
                html.Div([
                    # Detection and Sorting
                    html.H6("Detection and Sorting Controls", className="mt-3"),
                    dbc.Row([
                        dbc.Col(width=1),
                        dbc.Col([
                            dbc.Row(dbc.Button("Detection: OFF", id="detection-button", color="secondary", size="sm", className="w-100 mb-3")),
                            dbc.Row(dbc.Button("Sorting: OFF", id="sorter-button", color="secondary", size="sm", className="w-100 mb-3")),
                        ], width=4, align="center"),
                        dbc.Col(width=1),
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
                        ], align="start", width=5),
                    ]),
                    html.Hr(),
                    # Lasers
                    dbc.Row([
                        dbc.Col(html.H6("Laser Controls", className="mt-3"), width='auto'),
                        dbc.Col(html.Div(id='laser-status-indicator', className='status-indicator-off'), width='auto', align='center')
                    ], align='center'),
                    _laser_row('405', '405 nm'),
                    _laser_row('488', '488 nm'),
                    _laser_row('561', '561 nm'),
                    _laser_row('633', '633 nm'),
                    html.Hr(),
                    # Detection Threshold
                    html.H6("Droplet Detection Settings"),
                    html.Label("Enabled Detection Channels:"),
                    dbc.Row([
                        dbc.Col(width=1),
                        dbc.Col(
                            dbc.Checklist(
                                id='enabled-channels-checklist',
                                options=[
                                    {'label': '  Ch0', 'value': 0},
                                    {'label': '  Ch1', 'value': 1},
                                    {'label': '  Ch2', 'value': 2},
                                    {'label': '  Ch3', 'value': 3}
                                ],
                                value=[0, 1, 2, 3],
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
    ], md=3, style={'maxHeight': '90vh', 'overflowY': 'auto', 'paddingRight': '15px'})


def _laser_row(index, label):
    """Single laser control row with checkbox and power slider."""
    return dbc.Row([
        dbc.Col(dbc.Checklist(id={'type': 'laser-on-checklist', 'index': index}, options=[{'label': label, 'value': index}], value=[]), width=2),
        dbc.Col(dcc.Slider(id={'type': 'laser-power-slider', 'index': index}, min=0, max=50, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True}, disabled=False), width=10)
    ], className="mb-2")


def _data_column():
    """Middle column: scatter plots and signal viewer."""
    return dbc.Col([
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
        # Plot settings
        dbc.Row([
            _scatter_settings_col(1, INITIAL_X_KEY, INITIAL_Y_KEY),
            _scatter_settings_col(2, INITIAL_X_KEY_2, INITIAL_Y_KEY_2),
            dbc.Button('Clear Scatter', id='clear-scatter-button', n_clicks=0, color="secondary", className="w-100"),
        ]),
        html.Hr(className="my-2"),
        html.H6("SiPM Signals"),
        dcc.Graph(id='signal-plot', style={'height': '25vh'}),
        html.P(id='update-rate-label', children="Update Rate: ...", style={'textAlign': 'center', 'marginTop': '10px'})
    ], md=6)


def _scatter_settings_col(plot_num, initial_x, initial_y):
    """Settings column for one scatter plot (axis selectors, scale, range)."""
    return dbc.Col([
        html.Label("X-Axis:"),
        dcc.Dropdown(id=f'x-axis-dropdown-{plot_num}', options=AXIS_OPTIONS_DICT, value=initial_x, clearable=False, className="mb-2"),
        html.Label("Y-Axis:"),
        dcc.Dropdown(id=f'y-axis-dropdown-{plot_num}', options=AXIS_OPTIONS_DICT, value=initial_y, clearable=False, className="mb-2"),
        dbc.Row([
            dbc.Col(html.Label("X-Scale:"), width=4),
            dbc.Col(dcc.RadioItems(id=f'x-scale-radio-{plot_num}', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8),
        ], className="mb-1"),
        dbc.Row([
            dbc.Col(dbc.Input(id=f'x-min-input-{plot_num}', type='number', placeholder='X Min', value=0.1, size="sm", step="any"), width=6),
            dbc.Col(dbc.Input(id=f'x-max-input-{plot_num}', type='number', placeholder='X Max', value=3, size="sm", step="any"), width=6),
        ], className="mb-2"),
        dbc.Row([
            dbc.Col(html.Label("Y-Scale:"), width=4),
            dbc.Col(dcc.RadioItems(id=f'y-scale-radio-{plot_num}', options=[{'label': 'Log', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', inline=True, inputClassName="me-1"), width=8),
        ], className="mb-1"),
        dbc.Row([
            dbc.Col(dbc.Input(id=f'y-min-input-{plot_num}', type='number', placeholder='Y Min', value=0.1, size="sm", step="any"), width=6),
            dbc.Col(dbc.Input(id=f'y-max-input-{plot_num}', type='number', placeholder='Y Max', value=3, size="sm", step="any"), width=6),
        ], className="mb-3"),
    ])


def _camera_column(camera_available):
    """Right column: camera feed and controls."""
    return dbc.Col([
        html.H5("Camera Controls"),
        html.Img(
            src="/video_feed" if camera_available else "",
            id='camera-feed-img',
            style={
                'width': '100%',
                'border': '1px solid #555',
                'display': 'block' if camera_available else 'none',
                'minHeight': '240px',
                'backgroundColor': '#000' if camera_available else 'transparent',
                'aspectRatio': '4/3',
                'objectFit': 'contain',
                'maxHeight': '75vh'
            }
        ),
        html.P(
            "Camera disabled: pypylon or OpenCV not installed.",
            style={'textAlign': 'center', 'fontSize': 'small', 'display': 'block' if not camera_available else 'none'}
        ),
        html.Div([
            html.Hr(),
            dbc.Checkbox(
                id="camera-trigger-mode-checkbox",
                label="Enable Hardware Trigger",
                value=False,
                className="mb-2"
            ),
            html.Label("Exposure Time (us):"),
            dcc.Slider(id='camera-exposure-slider', min=28, max=200, step=1, value=28, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
            html.Label("Camera Trigger Delay (us):"),
            dcc.Slider(id='camera-trigger-delay-slider', min=0, max=5000, step=1, value=0, marks=None, tooltip={"placement": "bottom", "always_visible": True}),
            html.Div(id='camera-settings-status', className="mt-2")
        ], style={'display': 'block' if camera_available else 'none'}),
    ], md=3, style={'maxHeight': '90vh', 'overflowY': 'auto', 'paddingRight': '15px'})
