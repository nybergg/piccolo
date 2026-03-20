"""
Piccolo UI callbacks — all Dash callback registrations.

Callbacks are registered via register_callbacks(), which receives the app
instance and the controller. No module-level globals.
"""

import math
import json
import re
import time
import threading

import numpy as np
import dash
from dash import dcc, html, Input, Output, State, exceptions
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from piccolo.conversion import convert_display_to_raw


def register_callbacks(app, controller, camera_manager=None):
    """Register all Dash callbacks against the given app and controller."""

    lock = threading.Lock()

    # ------------------------------------------------------------------
    # Axis store
    # ------------------------------------------------------------------
    @app.callback(
        Output('axis-keys-store', 'data'),
        Input('x-axis-dropdown-1', 'value'),
        Input('y-axis-dropdown-1', 'value'),
        Input('x-axis-dropdown-2', 'value'),
        Input('y-axis-dropdown-2', 'value')
    )
    def update_axis_store(x1, y1, x2, y2):
        return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

    # ------------------------------------------------------------------
    # Main graph update
    # ------------------------------------------------------------------
    @app.callback(
        [Output('scatter-plot-1', 'figure'),
         Output('scatter-plot-2', 'figure'),
         Output('signal-plot', 'figure'),
         Output('update-rate-label', 'children'),
         Output('timer-store', 'data')],
        [Input('interval-component', 'n_intervals'),
         Input('x-axis-dropdown-1', 'value'),
         Input('y-axis-dropdown-1', 'value'),
         Input('x-scale-radio-1', 'value'),
         Input('y-scale-radio-1', 'value'),
         Input('x-min-input-1', 'value'),
         Input('x-max-input-1', 'value'),
         Input('y-min-input-1', 'value'),
         Input('y-max-input-1', 'value'),
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
        current_time = time.perf_counter()
        timers.append(current_time)
        timers = timers[-100:]
        s_per_update = 0
        if len(timers) > 1:
            s_per_update = np.mean(np.diff(timers))

        with lock:
            adc1 = controller.adc1_data
            adc2 = controller.adc2_data
            adc3 = controller.adc3_data
            adc4 = controller.adc4_data
            df = controller.droplet_data
            sort_gates = controller.get_sort_gates()

        time_axis = np.linspace(0, 50, 4096)

        signal_fig = go.Figure()
        signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc1, mode='lines', name='CH0', line=dict(color="#3fe4fa")))
        signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc2, mode='lines', name='CH1', line=dict(color="#71f445")))
        signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc3, mode='lines', name='CH2', line=dict(color="#ddfd25")))
        signal_fig.add_trace(go.Scattergl(x=time_axis, y=adc4, mode='lines', name='CH3', line=dict(color="#b83671")))
        signal_fig.add_hline(y=threshold_value, line_dash="dot", line_color="mediumseagreen", annotation_text="Threshold")
        signal_fig.update_layout(xaxis_title="Time (ms)", yaxis_title="Voltage", yaxis_range=[0, 1.2], legend_title="Signals", uirevision='signal_layout')
        update_text = f"Update Rate: {1 / s_per_update:.01f} Hz ({s_per_update * 1000:.00f} ms)" if s_per_update > 0 else "Calculating..."

        def make_scatter(plot_num, x_key, y_key, x_scale, y_scale, x_min, x_max, y_min, y_max, gates):
            if x_key not in df.columns or y_key not in df.columns:
                missing_key = x_key if x_key not in df.columns else y_key
                return go.Figure().update_layout(title=f"Error: Axis '{missing_key}' not found")

            x = df[x_key].values
            y = df[y_key].values
            density = []
            if len(x) > 0 and len(y) > 0:
                try:
                    bins = 25
                    H, xedges, yedges = np.histogram2d(x, y, bins=bins)
                    ix = np.searchsorted(xedges, x, side='right') - 1
                    iy = np.searchsorted(yedges, y, side='right') - 1
                    ix = np.clip(ix, 0, bins - 1)
                    iy = np.clip(iy, 0, bins - 1)
                    density = H[ix, iy]
                except Exception as e:
                    print(f"Density/Hist error: {e}")
                    density = []

            fig = go.Figure(data=go.Scattergl(
                x=x, y=y, mode='markers',
                marker=dict(color=density if len(density) > 0 else 'lightblue', colorscale='Viridis', opacity=0.6, size=4,
                            showscale=True if len(density) > 0 else False, colorbar=dict(title="Density") if len(density) > 0 else None)
            ))

            x_axis_config = {'title': x_key, 'type': x_scale, 'autorange': False}
            y_axis_config = {'title': y_key, 'type': y_scale, 'autorange': False}

            if x_min is not None and x_max is not None and x_max > x_min:
                if x_scale == 'log':
                    if x_min > 0 and x_max > 0:
                        x_axis_config['range'] = [math.log10(x_min), math.log10(x_max)]
                else:
                    x_axis_config['range'] = [x_min, x_max]

            if y_min is not None and y_max is not None and y_max > y_min:
                if y_scale == 'log':
                    if y_min > 0 and y_max > 0:
                        y_axis_config['range'] = [math.log10(y_min), math.log10(y_max)]
                else:
                    y_axis_config['range'] = [y_min, y_max]

            fig.update_layout(xaxis=x_axis_config, yaxis=y_axis_config,
                              dragmode='select', uirevision=f'scatter{plot_num}')

            # Draw gate lines
            if gates:
                converted_regs = controller.get_fpga_registers_converted()
                for gate_key, raw_val in gates.items():
                    param_match = re.match(r'(low|high)_(intensity|width|area)_thresh\[(\d)\]', gate_key)
                    if not param_match:
                        continue

                    limit_type, param_type, ch_str = param_match.groups()
                    ch = int(ch_str)

                    display_key_suffix = "_v" if param_type == 'intensity' else "_ms" if param_type == 'width' else "_vms"
                    display_key = f"cur_droplet_{param_type}{display_key_suffix}[{ch}]"

                    converted_val, unit = converted_regs.get(gate_key, (None, None))
                    if converted_val is None:
                        continue

                    line_style = dict(color="cyan", width=1, dash="dot")

                    if x_key == display_key:
                        fig.add_vline(x=converted_val, line=line_style)
                    if y_key == display_key:
                        fig.add_hline(y=converted_val, line=line_style)

            return fig

        scatter_fig_1 = make_scatter(1, x_key_1, y_key_1, x_scale_1, y_scale_1, x_min_1, x_max_1, y_min_1, y_max_1, sort_gates)
        scatter_fig_2 = make_scatter(2, x_key_2, y_key_2, x_scale_2, y_scale_2, x_min_2, x_max_2, y_min_2, y_max_2, sort_gates)

        return scatter_fig_1, scatter_fig_2, signal_fig, update_text, timers

    # ------------------------------------------------------------------
    # Laser callbacks
    # ------------------------------------------------------------------
    @app.callback(
        Output({'type': 'laser-on-checklist', 'index': dash.MATCH}, 'id'),
        [Input({'type': 'laser-on-checklist', 'index': dash.MATCH}, 'value'),
         Input({'type': 'laser-power-slider', 'index': dash.MATCH}, 'value')],
        [State({'type': 'laser-power-slider', 'index': dash.MATCH}, 'id')],
        prevent_initial_call=True
    )
    def update_laser_state(checklist_value, power_mw, slider_id):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise exceptions.PreventUpdate

        laser_name = str(slider_id['index'])
        is_checked = bool(checklist_value)

        with lock:
            controller.set_laser_on_state(laser_name, is_checked)
            if is_checked:
                controller.set_laser_power(laser_name, power_mw)

        return slider_id

    @app.callback(
        Output('laser-status-indicator', 'className'),
        Input({'type': 'laser-on-checklist', 'index': dash.ALL}, 'value')
    )
    def update_laser_status_indicator(checklist_values):
        any_laser_on = any(checklist_values)
        return 'status-indicator-on' if any_laser_on else 'status-indicator-off'

    # ------------------------------------------------------------------
    # Channel / detection / sorting callbacks
    # ------------------------------------------------------------------
    @app.callback(
        Output('fpga-set-status', 'children', allow_duplicate=True),
        Input('enabled-channels-checklist', 'value'),
        prevent_initial_call=True
    )
    def set_enabled_channels(selected_channels):
        if selected_channels is None:
            selected_channels = []

        bitmask = 0
        for ch_index in selected_channels:
            bitmask |= (1 << ch_index)

        final_value = int(bitmask)

        with lock:
            try:
                controller.set_memory_variable("enabled_channels", final_value)
                msg = f"Success: Enabled channels updated to bitmask {final_value}."
                print(msg)
                return dbc.Alert(msg, color="success", dismissable=True, duration=4000)
            except Exception as e:
                msg = f"Error setting enabled channels: {e}"
                print(msg)
                return dbc.Alert(msg, color="danger", dismissable=True, duration=4000)

    @app.callback(
        Output('threshold-slider', 'className'),
        [Input('threshold-slider', 'value')],
        [State('threshold-channel-dropdown', 'value')],
        prevent_initial_call=True
    )
    def update_detection_threshold(threshold_volts, channel):
        with lock:
            controller.set_detection_threshold(thresh=threshold_volts, ch=channel)
        return ""

    @app.callback(
        Output('sort-delay-slider', 'className'),
        Input('sort-delay-slider', 'value'),
        prevent_initial_call=True
    )
    def update_sort_delay(delay_ms):
        if delay_ms is not None:
            delay_us = int(delay_ms * 1000)
            with lock:
                controller.set_memory_variable("sort_delay", delay_us)
        return ""

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
            try:
                controller.set_memory_variable("detection_channel", channel)
                msg = f"Success: Detection channel updated to {channel}."
                print(msg)
                alert_msg = dbc.Alert(msg, color="success", dismissable=True, duration=4000)

                converted_regs = controller.get_fpga_registers_converted()
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

    # ------------------------------------------------------------------
    # Camera callbacks
    # ------------------------------------------------------------------
    @app.callback(
        Output('camera-settings-status', 'children', allow_duplicate=True),
        Input('camera-trigger-mode-checkbox', 'value'),
        prevent_initial_call=True
    )
    def manage_camera_trigger_mode(hw_trigger_enabled):
        if camera_manager is None:
            raise exceptions.PreventUpdate

        camera_manager.restart(hw_trigger=hw_trigger_enabled)
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
        if camera_manager is None:
            return dash.no_update

        msgs = []
        triggered_ids = [p['prop_id'].split('.')[0] for p in dash.callback_context.triggered]

        try:
            if 'camera-exposure-slider' in triggered_ids:
                camera_manager.set_exposure(float(exposure_us))
                msgs.append(f"Exposure: {exposure_us} us.")

            if 'camera-trigger-delay-slider' in triggered_ids:
                camera_manager.set_trigger_delay(float(delay_us))
                msgs.append(f"Delay: {delay_us} us.")

        except Exception as e:
            msg = f"Error setting camera parameter: {e}"
            print(msg)
            return dbc.Alert(msg, color="danger", duration=4000)

        if msgs:
            return dbc.Alert(" ".join(msgs), color="success", duration=2000)
        return dash.no_update

    # ------------------------------------------------------------------
    # Detection / sorter toggle
    # ------------------------------------------------------------------
    @app.callback(
        [Output('detection-button', 'children'),
         Output('detection-button', 'color'),
         Output('detection-button', 'data'),
         Output('sorter-button', 'disabled')],
        [Input('detection-button', 'n_clicks')],
        [State('detection-button', 'data')],
        prevent_initial_call=True
    )
    def toggle_detection(n_clicks, is_on):
        if n_clicks is None:
            raise exceptions.PreventUpdate
        new_state = not is_on
        with lock:
            controller.enable_detection(new_state)

        sorter_disabled = not new_state

        if new_state:
            return "Detection: ON", "success", new_state, sorter_disabled
        else:
            return "Detection: OFF", "secondary", new_state, sorter_disabled

    @app.callback(
        [Output('sorter-button', 'children'),
         Output('sorter-button', 'color'),
         Output('sorter-state-store', 'data')],
        [Input('sorter-button', 'n_clicks'),
         Input('detection-button', 'n_clicks')],
        [State('sorter-state-store', 'data'),
         State('detection-button', 'data')],
        prevent_initial_call=True
    )
    def toggle_sorter(n_clicks, n_detection_clicks, sorter_is_on, detection_is_on):
        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id == 'sorter-button':
            if not detection_is_on:
                raise exceptions.PreventUpdate

            new_state = not sorter_is_on
            with lock:
                controller.enable_sorter(new_state)

            if new_state:
                return "Sorting: ON", "success", new_state
            else:
                return "Sorting: OFF", "secondary", new_state

        raise exceptions.PreventUpdate

    # ------------------------------------------------------------------
    # Gate selection
    # ------------------------------------------------------------------
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
            else:
                current_sort_keys = [axis_keys['x2'], axis_keys['y2']]

            new_box = {"x0": [x_range[0]], "y0": [y_range[0]], "x1": [x_range[1]], "y1": [y_range[1]],
                       "x_key": current_sort_keys[0], "y_key": current_sort_keys[1]}

            print(f"New selection. Keys={current_sort_keys}. Box={new_box}")
            with lock:
                controller.set_gate_limits(sort_keys=current_sort_keys, limits=new_box)
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
            if v == 0:
                return ["0"]
            try:
                if not isinstance(v, (int, float)) or math.isinf(v) or math.isnan(v) or v == 0:
                    if v == 0:
                        return ["0"]
                    return ["N/A"]
                log_v = math.log10(abs(v))
                exp = math.floor(log_v)
                base = v / (10**exp)
                return [f"{base:.1f} x 10", html.Sup(exp)]
            except (ValueError, TypeError, OverflowError):
                return ["N/A"]

        return [
            html.B("Gate Selection:", style={'display': 'block', 'marginBottom': '5px'}),
            html.Span(["Xmin: "] + to_sci(box['x0'][0]) + [" | Ymin: "] + to_sci(box['y0'][0]), style={'display': 'block'}),
            html.Span(["Xmax: "] + to_sci(box['x1'][0]) + [" | Ymax: "] + to_sci(box['y1'][0]), style={'display': 'block'}),
        ]

    # ------------------------------------------------------------------
    # Data logging
    # ------------------------------------------------------------------
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
                    if not scatter_file.endswith(".csv"):
                        scatter_file += ".csv"
                    controller.save_droplet_data_log(filename=scatter_file)
                    msg = f"Scatter data saved to {scatter_file}"
                    color = "success"
                elif button_id == 'save-signal-button':
                    if not signal_file.endswith(".csv"):
                        signal_file += ".csv"
                    controller.save_adc_log(filename=signal_file)
                    msg = f"Signal data saved to {signal_file}"
                elif button_id == 'clear-scatter-button':
                    controller.clear_droplet_data()
                    msg = "Scatter plot data cleared."
                    color = "warning"
            except Exception as e:
                msg = f"Error performing action: {e}"
                color = "danger"
        print(msg)
        return dbc.Alert(msg, color=color, dismissable=True, duration=4000)

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------
    @app.callback(
        [Output('droplet-count-div', 'children'),
         Output('sorted-droplet-count-div', 'children'),
         Output('droplet-frequency-div', 'children')],
        Input('counter-interval-component', 'n_intervals')
    )
    def update_counters(n):
        count_str, sorted_str, freq_str = "...", "...", "... Hz"

        with lock:
            try:
                converted_registers = controller.get_fpga_registers_converted()

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

    # ------------------------------------------------------------------
    # FPGA register display + set
    # ------------------------------------------------------------------
    @app.callback(
        Output('fpga-register-div', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_fpga_register_display(n):
        if n % 20 != 0:
            return dash.no_update

        with lock:
            raw_registers = controller.get_fpga_registers()
            converted_registers = controller.get_fpga_registers_converted()

        if not raw_registers:
            return dbc.Alert("FPGA registers not available yet.", color="warning")

        header = dbc.Row([
            dbc.Col(html.B("Register Name"), width=3),
            dbc.Col(html.B("Converted Value"), width=3),
            dbc.Col(html.B("Raw Value"), width=2),
            dbc.Col(html.B("New Value"), width=2),
            dbc.Col(width=2),
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
                value_to_set = float(value_to_set_str)

                with lock:
                    final_value_int = convert_display_to_raw(
                        register_name, value_to_set, controller.calibration_values
                    )
                    controller.set_memory_variable(register_name, final_value_int)
                    msg = f"Success: Set {register_name} to {value_to_set_str} (raw: {final_value_int})"
                    print(msg)
                    return dbc.Alert(msg, color="success", dismissable=True, duration=4000)

            except (ValueError, TypeError) as e:
                msg = f"Error: Invalid value for {register_name}: '{value_to_set_str}'. Must be a number. ({e})"
                print(msg)
                return dbc.Alert(msg, color="danger", dismissable=True, duration=4000)

        return dash.no_update
