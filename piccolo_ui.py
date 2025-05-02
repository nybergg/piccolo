# Imports from the python standard library:
import math
import numpy as np
import sys
import threading
import time

# Third party imports, installable via pip:
# -> bokeh graphics and features etc
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource,
    Slider,
    Toggle,
    Label,
    Span,
    LinearColorMapper,
    Spinner,
    Div,
    )
from bokeh.models.callbacks import CustomJS
from bokeh.plotting import curdoc, figure
from bokeh.events import SelectionGeometry
# -> bokeh server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.server.server import Server

# Our code, one .py file per module, copy files to your local directory:
import concurrency_tools as ct  # github.com/AndrewGYork/tools
from piccolo_instrument_sim import InstrumentSim # github.com/nybergg/piccolo
from piccolo_instrument import Instrument # github.com/nybergg/piccolo

class UI:
    def __init__(self,
                 doc,
                 sys,
                 name='Piccolo_ui',
                 simulate=False,
                 verbose=True):
        self.doc = doc
        self.name = name
        self.verbose = verbose
        if self.verbose:
            print("%s: opening..."%self.name)
        # Detect if browser is closed:
        def _session_destroyed(session_context):
            if self.verbose:
                print("%s: session_destroyed = %s"%(
                    self.name, session_context.destroyed))
            sys.exit()
            return None
        self.doc.on_session_destroyed(_session_destroyed)
        # create launch buttons for hardware and sim:
        self.simulate = simulate
        if simulate:
            self._init_sim()
        else:  
            self._init_hw()
        
        if self.verbose:
            print("%s: -> open and ready."%self.name)

    def _init_sim(self):
        # Run CPU intensive InstrumentSim in subprocess:
        self.sim = ct.ObjectInSubprocess(InstrumentSim)
        self.sim_lock = threading.Lock()
        # Initialize UI components:
        with self.sim_lock:
            self.sipm_source = [self.sim.signal[0],
                                self.sim.signal[1]]
            self._setup_fpgaout_sources()
            self._setup_ui_components()
            # update ui every 150ms:
            self.timers = np.zeros(100)
            self.doc.add_periodic_callback(self._update_ui, 150)
        return None
    
    def _init_hw(self):
        if self.verbose:
            print("%s: initializing hardware"%self.name)
        
        # Launch piccolo instrument:
        self.instrument = Instrument()
        self.instrument_lock = threading.Lock()
        self.instrument.launch_piccolo_rp()
        time.sleep(10)  # Give time for the server to start
        self.instrument.start_clients()
        time.sleep(1)  # Give time for the clients to start

        # Launch simulation as well
        self.sim = ct.ObjectInSubprocess(InstrumentSim)
        self.sim_lock = threading.Lock()
        # Initialize UI components:
        
        if self.verbose:
            print("%s: -> hardware initialized"%self.name)

       # Setup data sources and UI components:
        with self.instrument_lock:
            with self.sim_lock:
                self.sipm_source = [self.instrument.stream_clients["adc"].adc1_data,
                                    self.instrument.stream_clients["adc"].adc2_data]
                self._setup_sipm_sources()
                self._setup_fpgaout_sources()
                self._setup_ui_components()
                # update ui every 150ms:
                self.timers = np.zeros(100)
                self.doc.add_periodic_callback(self._update_ui, 150)
        return None

    def _setup_sipm_sources(self):
        # Initialize data sources for the generated data (s to ms):
        time_ms = np.linspace(0, 50, 4096)
        self.sipm0 = ColumnDataSource(data={'x':time_ms,
                                            'y':self.sipm_source[0]})
        self.sipm1 = ColumnDataSource(data={'x':time_ms,
                                            'y':self.sipm_source[1]})
        return None

    def _setup_fpgaout_sources(self):
        # Initialize data sources for the generated data (s to ms):
        self.source_2d = ColumnDataSource(data=self.sim.data2d)
        self.rolling_source_2d = self.sim.data2d.copy()
        # Initialize data sources for the interactive callbacks:
        self.thresh = 0.05
        self.buffer_length = 5000
        self.boxselect = {"x0": [0], "y0": [0], "x1": [0], "y1": [0]}
        self.source_bx = ColumnDataSource(data=self.boxselect)
        return None

    def _setup_ui_components(self):
        # Setup update rate label, toggle, sliders, plot, and scatter plot:
        self.label = Label(x=10,
                           y=400,
                           text="Update Rate: 0 Hz",
                           text_font_size="20pt",
                           text_color="black")
        self._create_button()
        self._create_sliders()
        self._create_bufferspinner()
        self._create_custom_div()
        self._create_2d_scatter_plot()
        self._create_signal_plot()
        # Generate Layout:
        self.doc.add_root(
            column(
                self.button,
                row(
                    column(
                        self.sliders[0],
                        self.sliders[1],
                        self.sliders[2],
                        self.bufferspinner,
                        self.custom_div,
                        ),
                    self.plot2d,
                    ),
                self.plot,
                )
            )
        return None
    
    def _update_ui(self):
        # Pull data from subprocess and update the datasource and plot:
        with self.sim_lock:
            with self.instrument_lock:
                # Update sipm data:
                self.sipm0.data['y'] = self.instrument.stream_clients["adc"].adc1_data
                self.sipm1.data['y'] = self.instrument.stream_clients["adc"].adc2_data
                for key in self.rolling_source_2d:
                    self.rolling_source_2d[key].extend(self.sim.data2d[key])
                    if self.buffer_length == 0:
                        self.rolling_source_2d[key] = [np.nan]
                    elif len(self.rolling_source_2d[key]) > self.buffer_length:
                        self.rolling_source_2d[key] = (
                            self.rolling_source_2d[key][-self.buffer_length:])
                self.source_2d.data = self.rolling_source_2d
                # time update and display:
                self.timers = np.roll(self.timers, 1)
                self.timers[0] = time.perf_counter()
                s_per_update = np.mean(np.diff(self.timers)) * -1
                self.plot.title.text = (
                    f"Update Rate: {1/s_per_update:.01f} Hz"
                    f" ({s_per_update*1000:.00f} ms)")

    def _create_button(self):
        def _update_toggle(state):
            with self.sim_lock:
                if state:
                    self.button.label = "Stop"
                    self.button.button_type = "danger"
                    self.sim.start_generating()
                else:
                    self.button.label = "Start"
                    self.button.button_type = "success"
                    self.sim.stop_generating()        
        self.button = Toggle(label="Start", button_type="success")
        self.button.on_click(_update_toggle)
        return None

    def _create_sliders(self):
        def _gain0_changed(attr, old, new):
            with self.sim_lock:
                self.sim.set_sipm_gain(0, new)
            return None
        def _gain1_changed(attr, old, new):
            with self.sim_lock:
                self.sim.set_sipm_gain(1, new)
            return None
        def _threshold_changed(attr, old, new):
            with self.sim_lock:
                self.sim.set_threshold(new)
                self.thresh_line.location = self.sliders[2].value
            return None
        slider_margin = (10, 10, 20, 50)
        sliders_info = [
            {
                "start": 0.01,
                "end": 1,
                "value": 0.5,
                "step": 0.01,
                "title": "SiPM 0 Gain",
                "bar_color": "mediumseagreen",
                "callback": _gain0_changed,
            },
            {
                "start": 0.01,
                "end": 1,
                "value": 0.5,
                "step": 0.01,
                "title": "SiPM 1 Gain",
                "bar_color": "royalblue",
                "callback": _gain1_changed,
            },
            {
                "start": 0,
                "end": 2,
                "value": self.thresh,
                "step": 0.01,
                "title": "SiPM 0 Threshold",
                "bar_color": "mediumseagreen",
                "callback": _threshold_changed,
            },
            ]
        self.sliders = []
        for slider_info in sliders_info:
            slider = Slider(
                start=slider_info["start"],
                end=slider_info["end"],
                value=slider_info["value"],
                step=slider_info["step"],
                title=slider_info["title"],
                bar_color=slider_info["bar_color"],
                margin=slider_margin,
            )
            slider.on_change("value", slider_info["callback"])
            self.sliders.append(slider)
        return None

    def _create_bufferspinner(self):
        def _spinner_changed(attr, old, new):
            with self.sim_lock:
                self.buffer_length = self.bufferspinner.value
            return None
        self.bufferspinner = Spinner(
            title="Datapoint Count for Scatter Plot",
            low=0,
            high=10000,
            step=500,
            value=self.buffer_length,
            width=200,
            margin=(20, 0, 20, 50),
            )
        self.bufferspinner.on_change("value", _spinner_changed)
        return None

    def _create_custom_div(self):
        # Creating the Bokeh Div object with the HTML content:
        self.custom_div = Div(
            text=self._create_divhtml(),
            width=400,
            height=100,
            margin=(0, 0, 20, 40)
            )
        return None

    def _create_2d_scatter_plot(self):
        color_mapper = LinearColorMapper(palette="Viridis256")
        self.plot2d = figure(
            height=400,
            width=450,
            x_axis_label="Channel 1 AUC",
            y_axis_label="Channel 2 AUC",
            x_range=(1e3, 1e6),
            y_range=(1e3, 1e6),
            x_axis_type="log",
            y_axis_type="log",
            title="Density Scatter Plot",
            tools="box_select,reset",
            )
        glyph = self.plot2d.scatter(
            "x",
            "y",
            source=self.source_2d,
            size=2,
            color={"field": "density", "transform": color_mapper},
            line_color=None,
            fill_alpha=0.6,
            )
        # supress alpha change for nonselected indices bc refresh messes it up:
        glyph.nonselection_glyph = None
        # Custom javascript callback for box select tool:
        callback = CustomJS(
            args=dict(source_bx=self.source_bx),
            code="""
            // Store selected geometry in variables
            var geometry = cb_obj.geometry;
            var x0 = geometry.x0;
            var y0 = geometry.y0;
            var x1 = geometry.x1;
            var y1 = geometry.y1;
                            
            // Log the values in the JS console:
            console.log('Sorting Gate xmin: ', x0);
            console.log('Sorting Gate ymin: ', y0);
            console.log('Sorting Gate xmax: ', x1);
            console.log('Sorting Gate ymax: ', y1);
            console.log('Geometry: ', geometry);

            // source_bx.data = geometry;
            source_bx.data = {
                'x0': [x0],
                'y0': [y0],
                'x1': [x1],
                'y1': [y1]
            };
            source_bx.change.emit();
            """,
            )
        # Attach Javascript and callback to plot for 'selectiongeometry' event:
        self.plot2d.js_on_event(SelectionGeometry, callback)
        def _boxselect_pass(attr, old, new):
            with self.sim_lock:
                print("Box Select Callback Triggered")
                # Pass box values sim through the pipe to set gate values:
                self.sim.set_gate_limits(dict(new))
                # Store box values in ui box_select and update box select text:
                self.boxselect = new
                self.custom_div.text = self._create_divhtml()        
        self.source_bx.on_change("data", _boxselect_pass)
        return None

    def _create_signal_plot(self):
        self.plot = figure(
            height=300,
            width=900,
            title="Generated SiPM Data",
            x_axis_label="Time(ms)",
            y_axis_label="Voltage",
            toolbar_location=None,
            x_range=(0, 50),
            y_range=(0, 1.2),
            margin=(50, 0, 0, 10),
            )
        self.plot.line(
            "x",
            "y",
            source=self.sipm0,
            color="mediumseagreen",
            legend_label="SiPM0",
            )
        self.plot.line(
            "x",
            "y",
            source=self.sipm1,
            color="royalblue",
            legend_label="SiPM1"
            )
        # create threshold lines:
        self.thresh_line = Span(
            location=self.thresh,
            dimension="width",
            line_color="mediumseagreen",
            line_width=2,
            line_dash="dotted",
        )
        self.plot.add_layout(self.thresh_line)
        return None

    def _create_divhtml(self):
        # Extracting float values from the dictionary:
        float_values = [self.boxselect[key][0] for key in [
            "x0", "y0", "x1", "y1"]]
        # Convert float values to a string format of 10^x:
        def to_scientific_with_superscript(value):
            if value == 0:
                return "0"
            exponent = math.floor(math.log10(abs(value)))
            base = value / 10**exponent
            return f"{base:.1f} × 10<sup>{exponent}</sup>"
        formatted_values = [
            to_scientific_with_superscript(value) for value in float_values]
        # Labels for each box:
        labels = [
            "X<sub>min</sub>",
            "Y<sub>min</sub>",
            "X<sub>max</sub>",
            "Y<sub>max</sub>",
            ]
        # HTML template with embedded CSS for styling:
        html_content = f"""
        <div style="padding: 10px; background-color: white;">
            <div style="color: black; padding: 5px; background-color: white; text-align: left;"><b>Scatter Plot Gate Selection:</b></div>
            <div style="display: flex; justify-content: space-around; padding: 5px;">
                {''.join([f'<div style="width: 80px;"><div style="text-align: center; margin-bottom: 5px;">{label}</div><div style="background-color: #E8E8E8; color: black; padding: 10px; border-radius: 10px; text-align: center; margin-right: 2px; margin-left: 2px; ">{value}</div></div>' for label, value in zip(labels, formatted_values)])}
            </div>
        </div>
        """
        return html_content
    
    def _shutdown_hw(self):
        self.instrument.stop_clients()
        time.sleep(1)  # Give time for the clients to stop
        self.instrument.stop_servers()

# -> Edit args and kwargs here for test block:
def func(doc): # get instance of class WITH args and kwargs
    bk_doc = UI(doc, sys, simulate=False, verbose=True)
    return bk_doc

if __name__ == '__main__':
    bk_app = {'/': Application(FunctionHandler(func))} # doc created here
    server = Server(
        bk_app,
        port=5001, # default 5006
        # check session status sooner (.on_session_destroyed callback)
        check_unused_sessions_milliseconds=500,     # default 17000
        unused_session_lifetime_milliseconds=500)   # default 15000
    server.start()
    server.io_loop.add_callback(server.show, "/")
    server.io_loop.start()