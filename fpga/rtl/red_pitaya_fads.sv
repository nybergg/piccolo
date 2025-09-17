`timescale 10ns / 1ns //for simulation
/*
  RedPitaya FADS module for dual ADC inputs.
*/
module red_pitaya_fads #(
    parameter RSZ = 14,
    parameter DWT = 14,
    parameter MEM = 32,
    parameter CHNL = 4,      // Now four channels
    parameter ALIG = 4'h4,
    parameter MAVG_WINDOW_SIZE = 128, // Window size for the filter. MUST be a power of 2. 128 cc ~ 1us
    parameter MAVG_SHIFT_BITS = 7    // log2(MAVG_WINDOW_SIZE). This is the bit-shift amount for division.
)(
    // ADC inputs – now two independent channels
    input                   clk_i,          // ADC Clock
    input                   rstn_i,         // ADC Reset - active low
    input signed [14-1:0]   dat_a_i,        // ADC Channel A (0)
    input signed [14-1:0]   dat_b_i,        // ADC Channel B (1)
    input signed [14-1:0]   dat_c_i,        // ADC Channel C (2)
    input signed [14-1:0]   dat_d_i,        // ADC Channel D (3)
    output reg              sort_trig,      // Trigger for sorting
    output reg              camera_trig,
    output reg  [8-1:0]     debug,          // At the moment the current state of the state machine
    
    // System bus 
    input      [32-1:0]     sys_addr,
    input      [32-1:0]     sys_wdata,
    input                   sys_wen,
    input                   sys_ren,
    output reg [32-1:0]     sys_rdata,
    output reg              sys_err,
    output reg              sys_ack
);

////////////////////////////////////////////////////////////////////////////////
// ADC Data and Droplet Parameter Registers
////////////////////////////////////////////////////////////////////////////////

// Registers for timers
reg [MEM -1:0] general_timer_us = 32'd0; // General timer in microseconds
reg [8   -1:0] general_timer_counter = 8'd0; // Counter for general timer

// Output registers
reg         [MEM -1:0] droplet_id               = 32'd0;      // unique ID of the last fully evaluated droplet signal, stays stable until overwritten with the next event when its evaluation has finished
reg         [MEM -1:0] cur_time_us              = 32'd0;      // output of time - changes rapidly
reg signed  [MEM -1:0] cur_droplet_intensity    [CHNL-1:0];   // intensity peak value
reg         [MEM -1:0] cur_droplet_width        [CHNL-1:0];   // peak width - full width at half maximum (fwhm)
reg signed  [MEM -1:0] cur_droplet_area         [CHNL-1:0];   // area under the curve (auc)

// Eval
wire            droplet_positive; // Indicates if the droplet is positive
wire            droplet_negative; // Indicates if the droplet is negative
reg [16 -1:0]   droplet_classification; // Classification of the droplet

// Maintenance
reg             droplet_acquisition_enable  = 1'b1;     // Enable droplet acquisition
reg             sort_enable                 = 1'b1;     // Enable sorting
reg [MEM -1:0]  sort_end_us                 = 32'd0;    // End time for sorting in microseconds
reg [MEM -1:0]  sort_delay_end_us           = 32'd0;    // End time for sorting delay in microseconds
reg [MEM -1:0]  sort_duration               = 32'd50;   // Duration of sorting in microseconds
reg [MEM -1:0]  sort_delay                  = 32'd100;  // Delay before sorting in microseconds
reg             fads_reset                  = 1'b0;     // Reset signal for FADS

// Multi Channel registers and wires
reg  [CHNL-1:0] active_channels_o;
wire [CHNL-1:0] droplet_sensing_channel;                // Channel for droplet sensing
reg  [3-1:0]    droplet_sensing_addr;                   // Address for droplet sensing
reg  [CHNL-1:0] enabled_channels;                       // Enabled channels, one bit per channel
assign          droplet_sensing_channel     = (1 << droplet_sensing_addr); // one-hot encode the sensing channel
assign          active_channels_o           = '1; // All channels are active outputs

// Intensity (result of droplet classification) for all channels
wire [CHNL-1:0]      min_intensity;
wire [CHNL-1:0]      low_intensity;
wire [CHNL-1:0] positive_intensity;
wire [CHNL-1:0]     high_intensity;

// Width (result of droplet classification)
wire [CHNL-1:0]      min_width;
wire [CHNL-1:0]      low_width;
wire [CHNL-1:0] positive_width;
wire [CHNL-1:0]     high_width;

// Area (result of droplet classification)
wire [CHNL-1:0]      min_area;
wire [CHNL-1:0]      low_area;
wire [CHNL-1:0] positive_area;
wire [CHNL-1:0]     high_area;

// Intensity thresholds
reg signed  [DWT-1:0]   min_intensity_threshold [CHNL-1:0]; // noise cutoff threshold - from here on we evaluate and record
reg signed  [DWT-1:0]   low_intensity_threshold [CHNL-1:0]; // min sorting threshold - below this value droplets are not sorted
reg signed  [DWT-1:0]  high_intensity_threshold [CHNL-1:0]; // max sorting threshold - above this value droplets are not sorted

// Width thresholds
reg         [MEM-1:0]       min_width_threshold [CHNL-1:0]; // noise cutoff threshold
reg         [MEM-1:0]       low_width_threshold [CHNL-1:0]; // min sorting threshold
reg         [MEM-1:0]      high_width_threshold [CHNL-1:0]; // max sorting threshold

// Area thresholds
reg         [MEM-1:0]        min_area_threshold [CHNL-1:0]; // noise cutoff threshold
reg         [MEM-1:0]        low_area_threshold [CHNL-1:0]; // min sorting threshold
reg         [MEM-1:0]       high_area_threshold [CHNL-1:0]; // max sorting threshold

// Signal parameters 
reg         [MEM-1:0]              signal_width [CHNL-1:0]; // Signal width for each channel
reg signed  [MEM-1:0]               signal_area [CHNL-1:0]; // Signal area for each channel
reg signed  [DWT-1:0]                signal_max [CHNL-1:0]; // Signal max intensity for each channel

// Registers to store average-filtered ADC values for each channel
reg signed [DWT-1:0]                 adc_values [CHNL-1:0]; // 

// Counter registers
reg [MEM-1:0] droplet_counter = 32'd0;
reg [MEM-1:0] sorted_droplet_counter = 32'd0;
reg [MEM-1:0] frequency_counter = 32'd0;
reg [MEM-1:0] frequency_timer_us = 32'd0;
reg [MEM-1:0] droplet_frequency = 32'd0;


////////////////////////////////////////////////////////////////////////////////
// Assigning Variables
////////////////////////////////////////////////////////////////////////////////

genvar i;
generate
    for (i = 0; i < CHNL; i = i + 1) begin
        // since min_intensity uses the current adc value, it is not something to be used in droplet evaluation (state >= 3)
        // Assign intensity thresholds
        assign      min_intensity[i] = (adc_values[i] >=   min_intensity_threshold[i]);
        assign      low_intensity[i] = (signal_max[i] >=   min_intensity_threshold[i]) && (signal_max[i] < low_intensity_threshold[i]);
        assign positive_intensity[i] = (signal_max[i] >=   low_intensity_threshold[i]) && (signal_max[i] < high_intensity_threshold[i]);
        assign     high_intensity[i] =  signal_max[i] >=  high_intensity_threshold[i];

        // Assign area thresholds
        assign      min_area[i] =  signal_area[i] >=  min_area_threshold[i];
        assign      low_area[i] = (signal_area[i] >=  min_area_threshold[i]) && (signal_area[i] <  low_area_threshold[i]);
        assign positive_area[i] = (signal_area[i] >=  low_area_threshold[i]) && (signal_area[i] < high_area_threshold[i]) && min_area[i];
        assign     high_area[i] = (signal_area[i] >= high_area_threshold[i]) && min_area[i];

        // Assign width thresholds
        assign      min_width[i] =  signal_width[i] >=  min_width_threshold[i];
        assign      low_width[i] = (signal_width[i] >=  min_width_threshold[i]) && (signal_width[i] <  low_width_threshold[i]);
        assign positive_width[i] = (signal_width[i] >=  low_width_threshold[i]) && (signal_width[i] < high_width_threshold[i]) && min_width[i];
        assign     high_width[i] = (signal_width[i] >= high_width_threshold[i]) && min_width[i];
    end
endgenerate

// Final droplet sorting decision logic
assign droplet_positive = &positive_intensity && &positive_width && &positive_area;
assign droplet_negative = (|low_intensity || |high_intensity || |positive_intensity) && (|low_width || |high_width || |positive_width) && (|low_area || |high_area || |positive_area) && (~(&positive_intensity && &positive_width && &positive_area));


////////////////////////////////////////////////////////////////////////////////
// MOVING AVERAGE FILTERS
////////////////////////////////////////////////////////////////////////////////

wire signed [DWT-1:0] filtered_adc_values [CHNL-1:0]; // Wires to hold the output of each filter

genvar ch;
generate
    for (ch = 0; ch < CHNL; ch = ch + 1) begin : MAVG_FILTERS
        // A wider register to hold the sum of all samples in the window.
        // Its width is calculated to prevent overflow.
        reg signed [DWT+MAVG_SHIFT_BITS:0] mavg_sum;

        // The shift register that holds the window of the last N samples.
        reg signed [DWT-1:0] mavg_window [MAVG_WINDOW_SIZE-1:0];

        // Wire for the current raw ADC input for this channel
        wire signed [DWT-1:0] current_dat_i;
        if (ch == 0) assign current_dat_i = dat_a_i;
        else if (ch == 1) assign current_dat_i = dat_b_i;
        else if (ch == 2) assign current_dat_i = dat_c_i;
        else if (ch == 3) assign current_dat_i = dat_d_i;

        // The main filter logic
        always @(posedge clk_i) begin
            if (!rstn_i) begin
                // Reset the sum and clear the entire window on reset
                mavg_sum <= 0;
                for (integer j = 0; j < MAVG_WINDOW_SIZE; j = j + 1) begin
                    mavg_window[j] <= 0;
                end
            end else begin
                // Efficient "running sum" calculation:
                // new_sum = old_sum - oldest_sample + newest_sample
                mavg_sum <= mavg_sum - mavg_window[MAVG_WINDOW_SIZE-1] + current_dat_i;

                // Shift the window registers to make room for the new sample
                for (integer j = MAVG_WINDOW_SIZE-1; j > 0; j = j - 1) begin
                    mavg_window[j] <= mavg_window[j-1];
                end
                // Add the new sample to the front of the window
                mavg_window[0] <= current_dat_i;
            end
        end

        // Calculate the average by dividing the sum by the window size.
        // Since window size is a power of 2, this is just a fast bit-shift.
        assign filtered_adc_values[ch] = mavg_sum >>> MAVG_SHIFT_BITS;

    end
endgenerate


////////////////////////////////////////////////////////////////////////////////
// ADC Sampling
////////////////////////////////////////////////////////////////////////////////

always @(posedge clk_i) begin
  if (!rstn_i) begin
    for (integer i = 0; i < CHNL; i = i + 1) begin
        adc_values[i] <= 0;
    end
  end else begin
    for (integer i = 0; i < CHNL; i = i + 1) begin
        adc_values[i] <= filtered_adc_values[i];
    end
  end
end


////////////////////////////////////////////////////////////////////////////////
// General Timer
////////////////////////////////////////////////////////////////////////////////

always @(posedge clk_i) begin
    if (fads_reset) begin
        general_timer_counter <= 8'd0;
        general_timer_us <= 32'd0;
    end else begin
        general_timer_counter <= general_timer_counter + 8'd1;
        if (general_timer_counter >= 8'd125) begin
            general_timer_us <= general_timer_us + 32'd1;
            general_timer_counter <= 8'd0;
        end
    end
end


////////////////////////////////////////////////////////////////////////////////
// Droplet Frequency Calculation
////////////////////////////////////////////////////////////////////////////////
always @(posedge clk_i) begin
    if (fads_reset) begin
        frequency_timer_us <= 32'd0;
        frequency_counter <= 32'd0;
        droplet_frequency <= 32'd0;
    end else begin
        if (general_timer_counter >= 8'd125) begin
            frequency_timer_us <= frequency_timer_us + 32'd1;
            if (frequency_timer_us == 32'd1000000) begin
                droplet_frequency <= frequency_counter;
                frequency_counter <= 32'd0;
                frequency_timer_us <= 32'd0;
            end
        end
    end
end

////////////////////////////////////////////////////////////////////////////////
// Droplet State Machine
////////////////////////////////////////////////////////////////////////////////

reg [3-1:0] state = 3'd0;  // state encoding

always @(posedge clk_i) begin
    integer i;
    debug[6] <= droplet_negative;
    debug[7] <= droplet_positive;
    
    // Debug
    case (state)
        // Base state | 0
        3'd0: begin
            debug <= 8'b00000001;
            if (fads_reset || !rstn_i) begin
                state <= 3'd0;                
                sort_trig <= 1'b1;
                camera_trig <= 1'b0;
                
                droplet_id              <= 32'd0;
                droplet_counter <= 32'd0;
                sorted_droplet_counter <= 32'd0;
                frequency_counter <= 32'd0;
                frequency_timer_us <= 32'd0;
                droplet_frequency <= 32'd0;

                cur_droplet_intensity   <= '{default:0};
                cur_droplet_width       <= '{default:0};
                cur_droplet_area        <= '{default:0};
                droplet_classification  <=  8'd0;

                signal_width <= '{default:0};
                signal_area  <= '{default:0};
                signal_max   <= '{default:-14'sd8192};
                
            end else if (droplet_acquisition_enable) begin
                state <= 3'd1;
            end
        end

        //  Wait for Droplet | 1
        3'd1: begin
            debug <= 8'b00000010;
            if (fads_reset || !rstn_i)
                state <= 3'd0;
            else if (adc_values[droplet_sensing_addr] >= min_intensity_threshold[droplet_sensing_addr]) begin
                signal_width <= '{default:0};
                signal_area  <= '{default:0};
                signal_max   <= '{default:-14'sd8192};
                        
                // Reset and start droplet evaluation for the sensing channel
                signal_width[droplet_sensing_addr] <= 32'd1;
                signal_area[droplet_sensing_addr]  <= adc_values[droplet_sensing_addr];
                signal_max[droplet_sensing_addr]   <= adc_values[droplet_sensing_addr];
                state <= 3'd2;
            end
            
        end

        // Acquiring Droplet | 2
        3'd2: begin
            debug <= 8'b00000100;
            sort_trig <= 1'b1;
            if (fads_reset || !rstn_i)
                state <= 3'd0;  
            else begin
                // Intensity updates for all channels
                for (i = 0; i < CHNL; i = i + 1) begin
                    if (adc_values[i] > signal_max[i])
                        signal_max[i] <= adc_values[i];
                end

                // Based on the droplet-sensing channel signal: increment width and accumulate area for all channels.
                if (adc_values[droplet_sensing_addr] >= min_intensity_threshold[droplet_sensing_addr]) begin
                    for (i = 0; i < CHNL; i = i + 1) begin
                        signal_width[i] <= signal_width[i] + 32'd1;
                        signal_area[i]  <= signal_area[i] + adc_values[i];
                    end
                end else begin
                    state <= 3'd3;
                end
            end
        end

        // Evaluating Droplet | 3
        3'd3: begin
            if (fads_reset || !rstn_i)
                state <= 3'd0;  
            else begin
                debug <= 8'b00001000;
                // Only update droplet outputs if the droplet meets all the threshold requirements:
                if ((signal_width[droplet_sensing_addr] >= min_width_threshold[droplet_sensing_addr]) &&
                    (signal_max[droplet_sensing_addr]  >= min_intensity_threshold[droplet_sensing_addr]) &&
                    (signal_area[droplet_sensing_addr] >= min_area_threshold[droplet_sensing_addr]) &&
                    (droplet_positive || droplet_negative)) begin
                    droplet_id <= droplet_id + 32'd1;
                    droplet_counter <= droplet_counter + 32'd1;
                    frequency_counter <= frequency_counter + 32'd1;
                    
                    for (i = 0; i < CHNL; i = i + 1) begin
                        cur_droplet_width[i]     <= signal_width[i];
                        cur_droplet_intensity[i] <= signal_max[i];
                        cur_droplet_area[i]      <= signal_area[i];
                    end
                    cur_time_us <= general_timer_us;
            
                    droplet_classification[ 0] <= | low_intensity;
                    droplet_classification[ 1] <= & positive_intensity;
                    droplet_classification[ 2] <= | high_intensity;
            
                    droplet_classification[ 3] <= | low_width;
                    droplet_classification[ 4] <= & positive_width;
                    droplet_classification[ 5] <= | high_width;
            
                    droplet_classification[ 6] <= | low_area;
                    droplet_classification[ 7] <= & positive_area;
                    droplet_classification[ 8] <= | high_area;
            
                    droplet_classification[ 9]  <= 1'b0;
                    droplet_classification[10]  <= 1'b0;
                    droplet_classification[11]  <= 1'b0;
                    droplet_classification[12]  <= 1'b0;
                    droplet_classification[13]  <= 1'b0;
            
                    droplet_classification[14]  <= sort_trig;
                    droplet_classification[15]  <= droplet_positive;
                end
                
                // Continue with state transition (sorting if enabled and droplet is positive)
                if (sort_enable && droplet_positive) begin
                    sorted_droplet_counter <= sorted_droplet_counter + 32'd1;
                    sort_delay_end_us <= general_timer_us + sort_delay;
                    state <= 3'd4;
                end else begin
                    state <= 3'd1;
                end
            end
        end
        
        // Sorting Delay | 4
        3'd4 : begin
            if (fads_reset || !rstn_i)
                state <= 3'd0;  
            else if (general_timer_us >= sort_delay_end_us) begin
                debug <= 8'b00010000;
                sort_end_us <= general_timer_us + sort_duration;
                state <= 3'd5;
            end
        end

        // Sorting | 5
        3'd5 : begin
            if (fads_reset || !rstn_i)
                state <= 3'd0;  
            else begin 
                debug <= 8'b00100000;
                if (general_timer_us < sort_end_us) begin
                    debug <= 8'b11100000;
                    camera_trig <= 1'b1;
                end else begin
                    camera_trig <= 1'b0;
                    debug <= 8'b10000000;
                    state <= 3'd1;
                end
            end
        end
    endcase
end

////////////////////////////////////////////////////////////////////////////////
// System Bus Interface - Read and Write
////////////////////////////////////////////////////////////////////////////////

// Setting up necessary wires
wire sys_en;
assign sys_en = sys_wen | sys_ren;

// Reading from system bus
always @(posedge clk_i)
    // Necessary handling of reset signal
    if (rstn_i == 1'b0) begin
        // Resetting to default values
        min_intensity_threshold  <= '{default:-14'sd175}; // Should roughly correspond to -0.5V
        low_intensity_threshold  <= '{default:-14'sd150}; // On the specific RedPitaya I'm testing on
        high_intensity_threshold  <= '{default: 14'sd900};

        min_width_threshold  <= '{default:32'h000004E2}; // 1,250 clock cycles = 10 us
        low_width_threshold  <= '{default:32'h000030D4}; // 12,500 clock cycles = 100 us
        high_width_threshold  <= '{default:32'hccddeeff};

        min_area_threshold  <= '{default:32'h00000001};
        low_area_threshold  <= '{default:32'h000000ff};
        high_area_threshold  <= '{default:32'hccddeeff};
               
        enabled_channels <= '1;
        droplet_sensing_addr <= 3'h0;

    end else if (sys_wen) begin
        // Writing to system bus
        if (sys_addr[19:0]==20'h00020)                    fads_reset    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h00024)                    sort_delay    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h00028)                 sort_duration    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h0002C)                   sort_enable    <= sys_wdata[0:0];
        if (sys_addr[19:0]==20'h00300)              enabled_channels    <= sys_wdata[CHNL-1:0];
        if (sys_addr[19:0]==20'h00304)          droplet_sensing_addr    <= sys_wdata[   3-1:0];

        if (sys_addr[19:0]==20'h01000)    min_intensity_threshold[0]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01004)    min_intensity_threshold[1]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01008)    min_intensity_threshold[2]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h0100C)    min_intensity_threshold[3]    <= sys_wdata[DWT-1:0];

        if (sys_addr[19:0]==20'h01020)    low_intensity_threshold[0]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01024)    low_intensity_threshold[1]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01028)    low_intensity_threshold[2]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h0102C)    low_intensity_threshold[3]    <= sys_wdata[DWT-1:0];

        if (sys_addr[19:0]==20'h01040)   high_intensity_threshold[0]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01044)   high_intensity_threshold[1]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h01048)   high_intensity_threshold[2]    <= sys_wdata[DWT-1:0];
        if (sys_addr[19:0]==20'h0104C)   high_intensity_threshold[3]    <= sys_wdata[DWT-1:0];

        if (sys_addr[19:0]==20'h01060)        min_width_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01064)        min_width_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01068)        min_width_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h0106C)        min_width_threshold[3]    <= sys_wdata[MEM-1:0];

        if (sys_addr[19:0]==20'h01080)        low_width_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01084)        low_width_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01088)        low_width_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h0108C)        low_width_threshold[3]    <= sys_wdata[MEM-1:0];

        if (sys_addr[19:0]==20'h010a0)       high_width_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010a4)       high_width_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010a8)       high_width_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010aC)       high_width_threshold[3]    <= sys_wdata[MEM-1:0];

        if (sys_addr[19:0]==20'h010c0)         min_area_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010c4)         min_area_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010c8)         min_area_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010cC)         min_area_threshold[3]    <= sys_wdata[MEM-1:0];

        if (sys_addr[19:0]==20'h010e0)         low_area_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010e4)         low_area_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010e8)         low_area_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h010eC)         low_area_threshold[3]    <= sys_wdata[MEM-1:0];

        if (sys_addr[19:0]==20'h01100)        high_area_threshold[0]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01104)        high_area_threshold[1]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h01108)        high_area_threshold[2]    <= sys_wdata[MEM-1:0];
        if (sys_addr[19:0]==20'h0110C)        high_area_threshold[3]    <= sys_wdata[MEM-1:0];
    end

// Writing to system bus
always @(posedge clk_i)
    // Necessary handling of reset signal
    if (rstn_i == 1'b0) begin
        sys_err <= 1'b0;
        sys_ack <= 1'b0;
    end else begin
        sys_err <= 1'b0;
        casez (sys_addr[19:0])
        //   Address  |       handling bus signals        | creating 32 bit wide word containing the data
            20'h01000: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  min_intensity_threshold[0]}  ; end // these inputs are written back to the system bus as standard procedure in FPGA development
            20'h01004: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  min_intensity_threshold[1]}  ; end
            20'h01008: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  min_intensity_threshold[2]}  ; end
            20'h0100C: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  min_intensity_threshold[3]}  ; end

            20'h01020: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  low_intensity_threshold[0]}  ; end
            20'h01024: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  low_intensity_threshold[1]}  ; end
            20'h01028: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  low_intensity_threshold[2]}  ; end
            20'h0102C: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},  low_intensity_threshold[3]}  ; end

            20'h01040: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}}, high_intensity_threshold[0]}  ; end
            20'h01044: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}}, high_intensity_threshold[1]}  ; end
            20'h01048: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}}, high_intensity_threshold[2]}  ; end
            20'h0104C: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}}, high_intensity_threshold[3]}  ; end

            20'h01060: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      min_width_threshold[0]}  ; end
            20'h01064: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      min_width_threshold[1]}  ; end
            20'h01068: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      min_width_threshold[2]}  ; end
            20'h0106C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      min_width_threshold[3]}  ; end

            20'h01080: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      low_width_threshold[0]}  ; end
            20'h01084: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      low_width_threshold[1]}  ; end
            20'h01088: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      low_width_threshold[2]}  ; end
            20'h0108C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      low_width_threshold[3]}  ; end

            20'h010a0: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},     high_width_threshold[0]}  ; end
            20'h010a4: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},     high_width_threshold[1]}  ; end
            20'h010a8: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},     high_width_threshold[2]}  ; end
            20'h010aC: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},     high_width_threshold[3]}  ; end

            20'h010c0: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       min_area_threshold[0]}  ; end
            20'h010c4: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       min_area_threshold[1]}  ; end
            20'h010c8: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       min_area_threshold[2]}  ; end
            20'h010cC: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       min_area_threshold[3]}  ; end

            20'h010e0: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       low_area_threshold[0]}  ; end
            20'h010e4: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       low_area_threshold[1]}  ; end
            20'h010e8: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       low_area_threshold[2]}  ; end
            20'h010eC: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},       low_area_threshold[3]}  ; end

            20'h01100: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      high_area_threshold[0]}  ; end
            20'h01104: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      high_area_threshold[1]}  ; end
            20'h01108: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      high_area_threshold[2]}  ; end
            20'h0110C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},      high_area_threshold[3]}  ; end

            20'h00020: begin sys_ack <= sys_en;  sys_rdata <= {{32-   1{1'b0}},               fads_reset}     ; end // used for trouble shooting and in the interface to reset sorter and values including droplet id
            20'h00024: begin sys_ack <= sys_en;  sys_rdata <= {{32-   1{1'b0}},               sort_delay}     ; end
            20'h00028: begin sys_ack <= sys_en;  sys_rdata <= {{32-   1{1'b0}},            sort_duration}     ; end
            20'h0002C: begin sys_ack <= sys_en;  sys_rdata <= {{32-   1{1'b0}},              sort_enable}     ; end

            20'h00200: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},               droplet_id}     ; end // unique droplet identifier of the last fully analysed droplet
            
            20'h00204: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},    cur_droplet_intensity[0]} ; end // output of the droplet sorter for each channel
            20'h00208: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},    cur_droplet_intensity[1]} ; end
            20'h0020C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},    cur_droplet_intensity[2]} ; end
            20'h00210: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},    cur_droplet_intensity[3]} ; end

            20'h0021C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},        cur_droplet_width[0]} ; end
            20'h00220: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},        cur_droplet_width[1]} ; end
            20'h00224: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},        cur_droplet_width[2]} ; end
            20'h00228: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},        cur_droplet_width[3]} ; end

            20'h00234: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},          cur_droplet_area[0]} ; end
            20'h00238: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},          cur_droplet_area[1]} ; end
            20'h0023C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},          cur_droplet_area[2]} ; end
            20'h00240: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},          cur_droplet_area[3]} ; end

            20'h0024C: begin sys_ack <= sys_en;  sys_rdata <= {{32-  16{1'b0}},   droplet_classification}     ; end // results of the state machine droplet classification
            20'h00250: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},              cur_time_us}     ; end // real time value fast changing

            20'h00254: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},          droplet_counter}     ; end // number of fully analysed droplets
            20'h00258: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},   sorted_droplet_counter}     ; end // number of sorted droplets
            20'h0025C: begin sys_ack <= sys_en;  sys_rdata <= {{32- MEM{1'b0}},        droplet_frequency}     ; end // time averaged frequency of droplets across ~1 sec

            20'h00300: begin sys_ack <= sys_en;  sys_rdata <= {{32-CHNL{1'b0}},         enabled_channels}     ; end // boolean, starting with channel one as the digit (0/1) on the right
            20'h00304: begin sys_ack <= sys_en;  sys_rdata <= {{32-   3{1'b0}},     droplet_sensing_addr}     ; end // number 0-3, indicates the master channel for droplet detection

            20'h0030C: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},            adc_values[0]}     ; end // ADC value for each channel seperately (only one active at a time during multiplexing)
            20'h00310: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},            adc_values[1]}     ; end
            20'h00314: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},            adc_values[2]}     ; end
            20'h00318: begin sys_ack <= sys_en;  sys_rdata <= {{32- DWT{1'b0}},            adc_values[3]}     ; end

            default:   begin sys_ack <= sys_en;  sys_rdata <= 32'h0                                 ; end
        endcase
    end


endmodule
