# Building the Piccolo FPGA bitstream

How to rebuild `firmware/fpga/piccolo.bit.bin` from the RTL in `firmware/fpga/rtl/`
after changing the FADS logic. The Piccolo RTL is built inside the **Red Pitaya FPGA
project** (v0.94, Vivado 2020.1); `red_pitaya_fads.sv` is imported into that project as
instance `i_fads` in `red_pitaya_top_4ADC.sv`.

## Prerequisites

- Xilinx Vivado 2020.1 (matches the Red Pitaya v0.94 project / `xc7z020-clg400`).
- The Red Pitaya FPGA project (the `RedPitaya-FPGA` tree with `redpitaya.xpr`).
- The FADS sources here (`firmware/fpga/rtl/red_pitaya_fads.sv`,
  `red_pitaya_top_4ADC.sv`) imported into that project. If you edit the RTL here,
  re-import or point the project at these files so the change is picked up.

## Build steps (Vivado GUI + Tcl Console)

1. **Open the project** and make sure the FADS sources are current.
2. **Run Synthesis**, then **Run Implementation**.
3. **Optimization step (required to close timing):** run post-route physical
   optimization. In the Tcl Console, with the implemented design open:
   ```tcl
   phys_opt_design
   report_timing_summary
   ```
   Confirm **`WNS >= 0`** and "All user specified timing constraints are met."
   (Or set the implementation strategy to `Performance_ExplorePostRoutePhysOpt`
   so physopt runs automatically each build.)

   > Timing note: the design closes at ~0 ns slack, and the binding path is the
   > PS7 -> `i_fads/sys_rdata` register-read mux (not the droplet datapath, which is
   > pipelined). `phys_opt_design` is what closes it. There is little headroom, so
   > re-check timing whenever you add FADS logic. See `TIMING_NOTES.md` (local) for
   > the full analysis and the headroom plan for the future peak-count feature.

4. **Write the raw `.bin`** the Red Pitaya loads (via `-bin_file`), in the Tcl Console
   with the (physopt'd) design open:
   ```tcl
   write_bitstream -force -bin_file {C:/Users/automation/Github/piccolo/firmware/fpga/piccolo.bit}
   ```
   This produces `piccolo.bit` (has a header — not what the RP wants) and
   `piccolo.bin` (raw configuration data) in `firmware/fpga/`.

5. **Rename the raw bin** to the tracked filename and drop the `.bit`:
   ```tcl
   file rename -force {C:/Users/automation/Github/piccolo/firmware/fpga/piccolo.bin} \
                      {C:/Users/automation/Github/piccolo/firmware/fpga/piccolo.bit.bin}
   file delete       {C:/Users/automation/Github/piccolo/firmware/fpga/piccolo.bit}
   ```

6. **Sanity check** the size — it should be ~**4,045,564 bytes** for the `xc7z020`.
   If it is ~120 bytes larger (~4,045,678) you saved the `.bit` (with header) by
   mistake; redo step 4 using the `-bin_file` output.

## How it gets onto the hardware

`HardwareController.launch()` (host/src/piccolo/controllers/hardware_controller.py)
SCPs `firmware/fpga/piccolo.bit.bin` to the Red Pitaya, then loads it with:
```
/opt/redpitaya/sbin/overlay.sh v0.49        # reset overlay to a known state
/opt/redpitaya/bin/fpgautil -b <rp>/piccolo.bit.bin
```
`fpgautil` accepts the raw `.bit.bin` directly — no byte-swapping needed.
