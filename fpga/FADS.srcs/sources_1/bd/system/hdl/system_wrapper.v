//Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2020.1 (win64) Build 2902540 Wed May 27 19:54:49 MDT 2020
//Date        : Tue Feb 11 15:22:18 2025
//Host        : E381-W10-2255 running 64-bit major release  (build 9200)
//Command     : generate_target system_wrapper.bd
//Design      : system_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module system_wrapper
   (CAN0_rx,
    CAN0_tx,
    CAN1_rx,
    CAN1_tx,
    DDR_addr,
    DDR_ba,
    DDR_cas_n,
    DDR_ck_n,
    DDR_ck_p,
    DDR_cke,
    DDR_cs_n,
    DDR_dm,
    DDR_dq,
    DDR_dqs_n,
    DDR_dqs_p,
    DDR_odt,
    DDR_ras_n,
    DDR_reset_n,
    DDR_we_n,
    FCLK_CLK0,
    FCLK_CLK1,
    FCLK_CLK2,
    FCLK_CLK3,
    FCLK_RESET0_N,
    FCLK_RESET1_N,
    FCLK_RESET2_N,
    FCLK_RESET3_N,
    FIXED_IO_ddr_vrn,
    FIXED_IO_ddr_vrp,
    FIXED_IO_mio,
    FIXED_IO_ps_clk,
    FIXED_IO_ps_porb,
    FIXED_IO_ps_srstb,
    GPIO_tri_io,
    M_AXI_GP0_ACLK,
    M_AXI_GP0_araddr,
    M_AXI_GP0_arburst,
    M_AXI_GP0_arcache,
    M_AXI_GP0_arid,
    M_AXI_GP0_arlen,
    M_AXI_GP0_arlock,
    M_AXI_GP0_arprot,
    M_AXI_GP0_arqos,
    M_AXI_GP0_arready,
    M_AXI_GP0_arsize,
    M_AXI_GP0_arvalid,
    M_AXI_GP0_awaddr,
    M_AXI_GP0_awburst,
    M_AXI_GP0_awcache,
    M_AXI_GP0_awid,
    M_AXI_GP0_awlen,
    M_AXI_GP0_awlock,
    M_AXI_GP0_awprot,
    M_AXI_GP0_awqos,
    M_AXI_GP0_awready,
    M_AXI_GP0_awsize,
    M_AXI_GP0_awvalid,
    M_AXI_GP0_bid,
    M_AXI_GP0_bready,
    M_AXI_GP0_bresp,
    M_AXI_GP0_bvalid,
    M_AXI_GP0_rdata,
    M_AXI_GP0_rid,
    M_AXI_GP0_rlast,
    M_AXI_GP0_rready,
    M_AXI_GP0_rresp,
    M_AXI_GP0_rvalid,
    M_AXI_GP0_wdata,
    M_AXI_GP0_wid,
    M_AXI_GP0_wlast,
    M_AXI_GP0_wready,
    M_AXI_GP0_wstrb,
    M_AXI_GP0_wvalid,
    SPI0_io0_io,
    SPI0_io1_io,
    SPI0_sck_io,
    SPI0_ss1_o,
    SPI0_ss2_o,
    SPI0_ss_io,
    S_AXI_HP0_aclk,
    S_AXI_HP0_araddr,
    S_AXI_HP0_arburst,
    S_AXI_HP0_arcache,
    S_AXI_HP0_arid,
    S_AXI_HP0_arlen,
    S_AXI_HP0_arlock,
    S_AXI_HP0_arprot,
    S_AXI_HP0_arqos,
    S_AXI_HP0_arready,
    S_AXI_HP0_arsize,
    S_AXI_HP0_arvalid,
    S_AXI_HP0_awaddr,
    S_AXI_HP0_awburst,
    S_AXI_HP0_awcache,
    S_AXI_HP0_awid,
    S_AXI_HP0_awlen,
    S_AXI_HP0_awlock,
    S_AXI_HP0_awprot,
    S_AXI_HP0_awqos,
    S_AXI_HP0_awready,
    S_AXI_HP0_awsize,
    S_AXI_HP0_awvalid,
    S_AXI_HP0_bid,
    S_AXI_HP0_bready,
    S_AXI_HP0_bresp,
    S_AXI_HP0_bvalid,
    S_AXI_HP0_rdata,
    S_AXI_HP0_rid,
    S_AXI_HP0_rlast,
    S_AXI_HP0_rready,
    S_AXI_HP0_rresp,
    S_AXI_HP0_rvalid,
    S_AXI_HP0_wdata,
    S_AXI_HP0_wid,
    S_AXI_HP0_wlast,
    S_AXI_HP0_wready,
    S_AXI_HP0_wstrb,
    S_AXI_HP0_wvalid,
    S_AXI_HP1_aclk,
    S_AXI_HP1_araddr,
    S_AXI_HP1_arburst,
    S_AXI_HP1_arcache,
    S_AXI_HP1_arid,
    S_AXI_HP1_arlen,
    S_AXI_HP1_arlock,
    S_AXI_HP1_arprot,
    S_AXI_HP1_arqos,
    S_AXI_HP1_arready,
    S_AXI_HP1_arsize,
    S_AXI_HP1_arvalid,
    S_AXI_HP1_awaddr,
    S_AXI_HP1_awburst,
    S_AXI_HP1_awcache,
    S_AXI_HP1_awid,
    S_AXI_HP1_awlen,
    S_AXI_HP1_awlock,
    S_AXI_HP1_awprot,
    S_AXI_HP1_awqos,
    S_AXI_HP1_awready,
    S_AXI_HP1_awsize,
    S_AXI_HP1_awvalid,
    S_AXI_HP1_bid,
    S_AXI_HP1_bready,
    S_AXI_HP1_bresp,
    S_AXI_HP1_bvalid,
    S_AXI_HP1_rdata,
    S_AXI_HP1_rid,
    S_AXI_HP1_rlast,
    S_AXI_HP1_rready,
    S_AXI_HP1_rresp,
    S_AXI_HP1_rvalid,
    S_AXI_HP1_wdata,
    S_AXI_HP1_wid,
    S_AXI_HP1_wlast,
    S_AXI_HP1_wready,
    S_AXI_HP1_wstrb,
    S_AXI_HP1_wvalid,
    S_AXI_HP2_aclk,
    S_AXI_HP2_araddr,
    S_AXI_HP2_arburst,
    S_AXI_HP2_arcache,
    S_AXI_HP2_arid,
    S_AXI_HP2_arlen,
    S_AXI_HP2_arlock,
    S_AXI_HP2_arprot,
    S_AXI_HP2_arqos,
    S_AXI_HP2_arready,
    S_AXI_HP2_arsize,
    S_AXI_HP2_arvalid,
    S_AXI_HP2_awaddr,
    S_AXI_HP2_awburst,
    S_AXI_HP2_awcache,
    S_AXI_HP2_awid,
    S_AXI_HP2_awlen,
    S_AXI_HP2_awlock,
    S_AXI_HP2_awprot,
    S_AXI_HP2_awqos,
    S_AXI_HP2_awready,
    S_AXI_HP2_awsize,
    S_AXI_HP2_awvalid,
    S_AXI_HP2_bid,
    S_AXI_HP2_bready,
    S_AXI_HP2_bresp,
    S_AXI_HP2_bvalid,
    S_AXI_HP2_rdata,
    S_AXI_HP2_rid,
    S_AXI_HP2_rlast,
    S_AXI_HP2_rready,
    S_AXI_HP2_rresp,
    S_AXI_HP2_rvalid,
    S_AXI_HP2_wdata,
    S_AXI_HP2_wid,
    S_AXI_HP2_wlast,
    S_AXI_HP2_wready,
    S_AXI_HP2_wstrb,
    S_AXI_HP2_wvalid,
    S_AXI_HP3_aclk,
    S_AXI_HP3_araddr,
    S_AXI_HP3_arburst,
    S_AXI_HP3_arcache,
    S_AXI_HP3_arid,
    S_AXI_HP3_arlen,
    S_AXI_HP3_arlock,
    S_AXI_HP3_arprot,
    S_AXI_HP3_arqos,
    S_AXI_HP3_arready,
    S_AXI_HP3_arsize,
    S_AXI_HP3_arvalid,
    S_AXI_HP3_awaddr,
    S_AXI_HP3_awburst,
    S_AXI_HP3_awcache,
    S_AXI_HP3_awid,
    S_AXI_HP3_awlen,
    S_AXI_HP3_awlock,
    S_AXI_HP3_awprot,
    S_AXI_HP3_awqos,
    S_AXI_HP3_awready,
    S_AXI_HP3_awsize,
    S_AXI_HP3_awvalid,
    S_AXI_HP3_bid,
    S_AXI_HP3_bready,
    S_AXI_HP3_bresp,
    S_AXI_HP3_bvalid,
    S_AXI_HP3_rdata,
    S_AXI_HP3_rid,
    S_AXI_HP3_rlast,
    S_AXI_HP3_rready,
    S_AXI_HP3_rresp,
    S_AXI_HP3_rvalid,
    S_AXI_HP3_wdata,
    S_AXI_HP3_wid,
    S_AXI_HP3_wlast,
    S_AXI_HP3_wready,
    S_AXI_HP3_wstrb,
    S_AXI_HP3_wvalid,
    Vaux0_v_n,
    Vaux0_v_p,
    Vaux1_v_n,
    Vaux1_v_p,
    Vaux8_v_n,
    Vaux8_v_p,
    Vaux9_v_n,
    Vaux9_v_p,
    Vp_Vn_v_n,
    Vp_Vn_v_p);
  input CAN0_rx;
  output CAN0_tx;
  input CAN1_rx;
  output CAN1_tx;
  inout [14:0]DDR_addr;
  inout [2:0]DDR_ba;
  inout DDR_cas_n;
  inout DDR_ck_n;
  inout DDR_ck_p;
  inout DDR_cke;
  inout DDR_cs_n;
  inout [3:0]DDR_dm;
  inout [31:0]DDR_dq;
  inout [3:0]DDR_dqs_n;
  inout [3:0]DDR_dqs_p;
  inout DDR_odt;
  inout DDR_ras_n;
  inout DDR_reset_n;
  inout DDR_we_n;
  output FCLK_CLK0;
  output FCLK_CLK1;
  output FCLK_CLK2;
  output FCLK_CLK3;
  output FCLK_RESET0_N;
  output FCLK_RESET1_N;
  output FCLK_RESET2_N;
  output FCLK_RESET3_N;
  inout FIXED_IO_ddr_vrn;
  inout FIXED_IO_ddr_vrp;
  inout [53:0]FIXED_IO_mio;
  inout FIXED_IO_ps_clk;
  inout FIXED_IO_ps_porb;
  inout FIXED_IO_ps_srstb;
  inout [23:0]GPIO_tri_io;
  input M_AXI_GP0_ACLK;
  output [31:0]M_AXI_GP0_araddr;
  output [1:0]M_AXI_GP0_arburst;
  output [3:0]M_AXI_GP0_arcache;
  output [11:0]M_AXI_GP0_arid;
  output [3:0]M_AXI_GP0_arlen;
  output [1:0]M_AXI_GP0_arlock;
  output [2:0]M_AXI_GP0_arprot;
  output [3:0]M_AXI_GP0_arqos;
  input M_AXI_GP0_arready;
  output [2:0]M_AXI_GP0_arsize;
  output M_AXI_GP0_arvalid;
  output [31:0]M_AXI_GP0_awaddr;
  output [1:0]M_AXI_GP0_awburst;
  output [3:0]M_AXI_GP0_awcache;
  output [11:0]M_AXI_GP0_awid;
  output [3:0]M_AXI_GP0_awlen;
  output [1:0]M_AXI_GP0_awlock;
  output [2:0]M_AXI_GP0_awprot;
  output [3:0]M_AXI_GP0_awqos;
  input M_AXI_GP0_awready;
  output [2:0]M_AXI_GP0_awsize;
  output M_AXI_GP0_awvalid;
  input [11:0]M_AXI_GP0_bid;
  output M_AXI_GP0_bready;
  input [1:0]M_AXI_GP0_bresp;
  input M_AXI_GP0_bvalid;
  input [31:0]M_AXI_GP0_rdata;
  input [11:0]M_AXI_GP0_rid;
  input M_AXI_GP0_rlast;
  output M_AXI_GP0_rready;
  input [1:0]M_AXI_GP0_rresp;
  input M_AXI_GP0_rvalid;
  output [31:0]M_AXI_GP0_wdata;
  output [11:0]M_AXI_GP0_wid;
  output M_AXI_GP0_wlast;
  input M_AXI_GP0_wready;
  output [3:0]M_AXI_GP0_wstrb;
  output M_AXI_GP0_wvalid;
  inout SPI0_io0_io;
  inout SPI0_io1_io;
  inout SPI0_sck_io;
  output SPI0_ss1_o;
  output SPI0_ss2_o;
  inout SPI0_ss_io;
  input S_AXI_HP0_aclk;
  input [31:0]S_AXI_HP0_araddr;
  input [1:0]S_AXI_HP0_arburst;
  input [3:0]S_AXI_HP0_arcache;
  input [3:0]S_AXI_HP0_arid;
  input [3:0]S_AXI_HP0_arlen;
  input [1:0]S_AXI_HP0_arlock;
  input [2:0]S_AXI_HP0_arprot;
  input [3:0]S_AXI_HP0_arqos;
  output S_AXI_HP0_arready;
  input [2:0]S_AXI_HP0_arsize;
  input S_AXI_HP0_arvalid;
  input [31:0]S_AXI_HP0_awaddr;
  input [1:0]S_AXI_HP0_awburst;
  input [3:0]S_AXI_HP0_awcache;
  input [3:0]S_AXI_HP0_awid;
  input [3:0]S_AXI_HP0_awlen;
  input [1:0]S_AXI_HP0_awlock;
  input [2:0]S_AXI_HP0_awprot;
  input [3:0]S_AXI_HP0_awqos;
  output S_AXI_HP0_awready;
  input [2:0]S_AXI_HP0_awsize;
  input S_AXI_HP0_awvalid;
  output [3:0]S_AXI_HP0_bid;
  input S_AXI_HP0_bready;
  output [1:0]S_AXI_HP0_bresp;
  output S_AXI_HP0_bvalid;
  output [63:0]S_AXI_HP0_rdata;
  output [3:0]S_AXI_HP0_rid;
  output S_AXI_HP0_rlast;
  input S_AXI_HP0_rready;
  output [1:0]S_AXI_HP0_rresp;
  output S_AXI_HP0_rvalid;
  input [63:0]S_AXI_HP0_wdata;
  input [3:0]S_AXI_HP0_wid;
  input S_AXI_HP0_wlast;
  output S_AXI_HP0_wready;
  input [7:0]S_AXI_HP0_wstrb;
  input S_AXI_HP0_wvalid;
  input S_AXI_HP1_aclk;
  input [31:0]S_AXI_HP1_araddr;
  input [1:0]S_AXI_HP1_arburst;
  input [3:0]S_AXI_HP1_arcache;
  input [3:0]S_AXI_HP1_arid;
  input [3:0]S_AXI_HP1_arlen;
  input [1:0]S_AXI_HP1_arlock;
  input [2:0]S_AXI_HP1_arprot;
  input [3:0]S_AXI_HP1_arqos;
  output S_AXI_HP1_arready;
  input [2:0]S_AXI_HP1_arsize;
  input S_AXI_HP1_arvalid;
  input [31:0]S_AXI_HP1_awaddr;
  input [1:0]S_AXI_HP1_awburst;
  input [3:0]S_AXI_HP1_awcache;
  input [3:0]S_AXI_HP1_awid;
  input [3:0]S_AXI_HP1_awlen;
  input [1:0]S_AXI_HP1_awlock;
  input [2:0]S_AXI_HP1_awprot;
  input [3:0]S_AXI_HP1_awqos;
  output S_AXI_HP1_awready;
  input [2:0]S_AXI_HP1_awsize;
  input S_AXI_HP1_awvalid;
  output [3:0]S_AXI_HP1_bid;
  input S_AXI_HP1_bready;
  output [1:0]S_AXI_HP1_bresp;
  output S_AXI_HP1_bvalid;
  output [63:0]S_AXI_HP1_rdata;
  output [3:0]S_AXI_HP1_rid;
  output S_AXI_HP1_rlast;
  input S_AXI_HP1_rready;
  output [1:0]S_AXI_HP1_rresp;
  output S_AXI_HP1_rvalid;
  input [63:0]S_AXI_HP1_wdata;
  input [3:0]S_AXI_HP1_wid;
  input S_AXI_HP1_wlast;
  output S_AXI_HP1_wready;
  input [7:0]S_AXI_HP1_wstrb;
  input S_AXI_HP1_wvalid;
  input S_AXI_HP2_aclk;
  input [31:0]S_AXI_HP2_araddr;
  input [1:0]S_AXI_HP2_arburst;
  input [3:0]S_AXI_HP2_arcache;
  input [3:0]S_AXI_HP2_arid;
  input [3:0]S_AXI_HP2_arlen;
  input [1:0]S_AXI_HP2_arlock;
  input [2:0]S_AXI_HP2_arprot;
  input [3:0]S_AXI_HP2_arqos;
  output S_AXI_HP2_arready;
  input [2:0]S_AXI_HP2_arsize;
  input S_AXI_HP2_arvalid;
  input [31:0]S_AXI_HP2_awaddr;
  input [1:0]S_AXI_HP2_awburst;
  input [3:0]S_AXI_HP2_awcache;
  input [3:0]S_AXI_HP2_awid;
  input [3:0]S_AXI_HP2_awlen;
  input [1:0]S_AXI_HP2_awlock;
  input [2:0]S_AXI_HP2_awprot;
  input [3:0]S_AXI_HP2_awqos;
  output S_AXI_HP2_awready;
  input [2:0]S_AXI_HP2_awsize;
  input S_AXI_HP2_awvalid;
  output [3:0]S_AXI_HP2_bid;
  input S_AXI_HP2_bready;
  output [1:0]S_AXI_HP2_bresp;
  output S_AXI_HP2_bvalid;
  output [63:0]S_AXI_HP2_rdata;
  output [3:0]S_AXI_HP2_rid;
  output S_AXI_HP2_rlast;
  input S_AXI_HP2_rready;
  output [1:0]S_AXI_HP2_rresp;
  output S_AXI_HP2_rvalid;
  input [63:0]S_AXI_HP2_wdata;
  input [3:0]S_AXI_HP2_wid;
  input S_AXI_HP2_wlast;
  output S_AXI_HP2_wready;
  input [7:0]S_AXI_HP2_wstrb;
  input S_AXI_HP2_wvalid;
  input S_AXI_HP3_aclk;
  input [31:0]S_AXI_HP3_araddr;
  input [1:0]S_AXI_HP3_arburst;
  input [3:0]S_AXI_HP3_arcache;
  input [3:0]S_AXI_HP3_arid;
  input [3:0]S_AXI_HP3_arlen;
  input [1:0]S_AXI_HP3_arlock;
  input [2:0]S_AXI_HP3_arprot;
  input [3:0]S_AXI_HP3_arqos;
  output S_AXI_HP3_arready;
  input [2:0]S_AXI_HP3_arsize;
  input S_AXI_HP3_arvalid;
  input [31:0]S_AXI_HP3_awaddr;
  input [1:0]S_AXI_HP3_awburst;
  input [3:0]S_AXI_HP3_awcache;
  input [3:0]S_AXI_HP3_awid;
  input [3:0]S_AXI_HP3_awlen;
  input [1:0]S_AXI_HP3_awlock;
  input [2:0]S_AXI_HP3_awprot;
  input [3:0]S_AXI_HP3_awqos;
  output S_AXI_HP3_awready;
  input [2:0]S_AXI_HP3_awsize;
  input S_AXI_HP3_awvalid;
  output [3:0]S_AXI_HP3_bid;
  input S_AXI_HP3_bready;
  output [1:0]S_AXI_HP3_bresp;
  output S_AXI_HP3_bvalid;
  output [63:0]S_AXI_HP3_rdata;
  output [3:0]S_AXI_HP3_rid;
  output S_AXI_HP3_rlast;
  input S_AXI_HP3_rready;
  output [1:0]S_AXI_HP3_rresp;
  output S_AXI_HP3_rvalid;
  input [63:0]S_AXI_HP3_wdata;
  input [3:0]S_AXI_HP3_wid;
  input S_AXI_HP3_wlast;
  output S_AXI_HP3_wready;
  input [7:0]S_AXI_HP3_wstrb;
  input S_AXI_HP3_wvalid;
  input Vaux0_v_n;
  input Vaux0_v_p;
  input Vaux1_v_n;
  input Vaux1_v_p;
  input Vaux8_v_n;
  input Vaux8_v_p;
  input Vaux9_v_n;
  input Vaux9_v_p;
  input Vp_Vn_v_n;
  input Vp_Vn_v_p;

  wire CAN0_rx;
  wire CAN0_tx;
  wire CAN1_rx;
  wire CAN1_tx;
  wire [14:0]DDR_addr;
  wire [2:0]DDR_ba;
  wire DDR_cas_n;
  wire DDR_ck_n;
  wire DDR_ck_p;
  wire DDR_cke;
  wire DDR_cs_n;
  wire [3:0]DDR_dm;
  wire [31:0]DDR_dq;
  wire [3:0]DDR_dqs_n;
  wire [3:0]DDR_dqs_p;
  wire DDR_odt;
  wire DDR_ras_n;
  wire DDR_reset_n;
  wire DDR_we_n;
  wire FCLK_CLK0;
  wire FCLK_CLK1;
  wire FCLK_CLK2;
  wire FCLK_CLK3;
  wire FCLK_RESET0_N;
  wire FCLK_RESET1_N;
  wire FCLK_RESET2_N;
  wire FCLK_RESET3_N;
  wire FIXED_IO_ddr_vrn;
  wire FIXED_IO_ddr_vrp;
  wire [53:0]FIXED_IO_mio;
  wire FIXED_IO_ps_clk;
  wire FIXED_IO_ps_porb;
  wire FIXED_IO_ps_srstb;
  wire [0:0]GPIO_tri_i_0;
  wire [1:1]GPIO_tri_i_1;
  wire [10:10]GPIO_tri_i_10;
  wire [11:11]GPIO_tri_i_11;
  wire [12:12]GPIO_tri_i_12;
  wire [13:13]GPIO_tri_i_13;
  wire [14:14]GPIO_tri_i_14;
  wire [15:15]GPIO_tri_i_15;
  wire [16:16]GPIO_tri_i_16;
  wire [17:17]GPIO_tri_i_17;
  wire [18:18]GPIO_tri_i_18;
  wire [19:19]GPIO_tri_i_19;
  wire [2:2]GPIO_tri_i_2;
  wire [20:20]GPIO_tri_i_20;
  wire [21:21]GPIO_tri_i_21;
  wire [22:22]GPIO_tri_i_22;
  wire [23:23]GPIO_tri_i_23;
  wire [3:3]GPIO_tri_i_3;
  wire [4:4]GPIO_tri_i_4;
  wire [5:5]GPIO_tri_i_5;
  wire [6:6]GPIO_tri_i_6;
  wire [7:7]GPIO_tri_i_7;
  wire [8:8]GPIO_tri_i_8;
  wire [9:9]GPIO_tri_i_9;
  wire [0:0]GPIO_tri_io_0;
  wire [1:1]GPIO_tri_io_1;
  wire [10:10]GPIO_tri_io_10;
  wire [11:11]GPIO_tri_io_11;
  wire [12:12]GPIO_tri_io_12;
  wire [13:13]GPIO_tri_io_13;
  wire [14:14]GPIO_tri_io_14;
  wire [15:15]GPIO_tri_io_15;
  wire [16:16]GPIO_tri_io_16;
  wire [17:17]GPIO_tri_io_17;
  wire [18:18]GPIO_tri_io_18;
  wire [19:19]GPIO_tri_io_19;
  wire [2:2]GPIO_tri_io_2;
  wire [20:20]GPIO_tri_io_20;
  wire [21:21]GPIO_tri_io_21;
  wire [22:22]GPIO_tri_io_22;
  wire [23:23]GPIO_tri_io_23;
  wire [3:3]GPIO_tri_io_3;
  wire [4:4]GPIO_tri_io_4;
  wire [5:5]GPIO_tri_io_5;
  wire [6:6]GPIO_tri_io_6;
  wire [7:7]GPIO_tri_io_7;
  wire [8:8]GPIO_tri_io_8;
  wire [9:9]GPIO_tri_io_9;
  wire [0:0]GPIO_tri_o_0;
  wire [1:1]GPIO_tri_o_1;
  wire [10:10]GPIO_tri_o_10;
  wire [11:11]GPIO_tri_o_11;
  wire [12:12]GPIO_tri_o_12;
  wire [13:13]GPIO_tri_o_13;
  wire [14:14]GPIO_tri_o_14;
  wire [15:15]GPIO_tri_o_15;
  wire [16:16]GPIO_tri_o_16;
  wire [17:17]GPIO_tri_o_17;
  wire [18:18]GPIO_tri_o_18;
  wire [19:19]GPIO_tri_o_19;
  wire [2:2]GPIO_tri_o_2;
  wire [20:20]GPIO_tri_o_20;
  wire [21:21]GPIO_tri_o_21;
  wire [22:22]GPIO_tri_o_22;
  wire [23:23]GPIO_tri_o_23;
  wire [3:3]GPIO_tri_o_3;
  wire [4:4]GPIO_tri_o_4;
  wire [5:5]GPIO_tri_o_5;
  wire [6:6]GPIO_tri_o_6;
  wire [7:7]GPIO_tri_o_7;
  wire [8:8]GPIO_tri_o_8;
  wire [9:9]GPIO_tri_o_9;
  wire [0:0]GPIO_tri_t_0;
  wire [1:1]GPIO_tri_t_1;
  wire [10:10]GPIO_tri_t_10;
  wire [11:11]GPIO_tri_t_11;
  wire [12:12]GPIO_tri_t_12;
  wire [13:13]GPIO_tri_t_13;
  wire [14:14]GPIO_tri_t_14;
  wire [15:15]GPIO_tri_t_15;
  wire [16:16]GPIO_tri_t_16;
  wire [17:17]GPIO_tri_t_17;
  wire [18:18]GPIO_tri_t_18;
  wire [19:19]GPIO_tri_t_19;
  wire [2:2]GPIO_tri_t_2;
  wire [20:20]GPIO_tri_t_20;
  wire [21:21]GPIO_tri_t_21;
  wire [22:22]GPIO_tri_t_22;
  wire [23:23]GPIO_tri_t_23;
  wire [3:3]GPIO_tri_t_3;
  wire [4:4]GPIO_tri_t_4;
  wire [5:5]GPIO_tri_t_5;
  wire [6:6]GPIO_tri_t_6;
  wire [7:7]GPIO_tri_t_7;
  wire [8:8]GPIO_tri_t_8;
  wire [9:9]GPIO_tri_t_9;
  wire M_AXI_GP0_ACLK;
  wire [31:0]M_AXI_GP0_araddr;
  wire [1:0]M_AXI_GP0_arburst;
  wire [3:0]M_AXI_GP0_arcache;
  wire [11:0]M_AXI_GP0_arid;
  wire [3:0]M_AXI_GP0_arlen;
  wire [1:0]M_AXI_GP0_arlock;
  wire [2:0]M_AXI_GP0_arprot;
  wire [3:0]M_AXI_GP0_arqos;
  wire M_AXI_GP0_arready;
  wire [2:0]M_AXI_GP0_arsize;
  wire M_AXI_GP0_arvalid;
  wire [31:0]M_AXI_GP0_awaddr;
  wire [1:0]M_AXI_GP0_awburst;
  wire [3:0]M_AXI_GP0_awcache;
  wire [11:0]M_AXI_GP0_awid;
  wire [3:0]M_AXI_GP0_awlen;
  wire [1:0]M_AXI_GP0_awlock;
  wire [2:0]M_AXI_GP0_awprot;
  wire [3:0]M_AXI_GP0_awqos;
  wire M_AXI_GP0_awready;
  wire [2:0]M_AXI_GP0_awsize;
  wire M_AXI_GP0_awvalid;
  wire [11:0]M_AXI_GP0_bid;
  wire M_AXI_GP0_bready;
  wire [1:0]M_AXI_GP0_bresp;
  wire M_AXI_GP0_bvalid;
  wire [31:0]M_AXI_GP0_rdata;
  wire [11:0]M_AXI_GP0_rid;
  wire M_AXI_GP0_rlast;
  wire M_AXI_GP0_rready;
  wire [1:0]M_AXI_GP0_rresp;
  wire M_AXI_GP0_rvalid;
  wire [31:0]M_AXI_GP0_wdata;
  wire [11:0]M_AXI_GP0_wid;
  wire M_AXI_GP0_wlast;
  wire M_AXI_GP0_wready;
  wire [3:0]M_AXI_GP0_wstrb;
  wire M_AXI_GP0_wvalid;
  wire SPI0_io0_i;
  wire SPI0_io0_io;
  wire SPI0_io0_o;
  wire SPI0_io0_t;
  wire SPI0_io1_i;
  wire SPI0_io1_io;
  wire SPI0_io1_o;
  wire SPI0_io1_t;
  wire SPI0_sck_i;
  wire SPI0_sck_io;
  wire SPI0_sck_o;
  wire SPI0_sck_t;
  wire SPI0_ss1_o;
  wire SPI0_ss2_o;
  wire SPI0_ss_i;
  wire SPI0_ss_io;
  wire SPI0_ss_o;
  wire SPI0_ss_t;
  wire S_AXI_HP0_aclk;
  wire [31:0]S_AXI_HP0_araddr;
  wire [1:0]S_AXI_HP0_arburst;
  wire [3:0]S_AXI_HP0_arcache;
  wire [3:0]S_AXI_HP0_arid;
  wire [3:0]S_AXI_HP0_arlen;
  wire [1:0]S_AXI_HP0_arlock;
  wire [2:0]S_AXI_HP0_arprot;
  wire [3:0]S_AXI_HP0_arqos;
  wire S_AXI_HP0_arready;
  wire [2:0]S_AXI_HP0_arsize;
  wire S_AXI_HP0_arvalid;
  wire [31:0]S_AXI_HP0_awaddr;
  wire [1:0]S_AXI_HP0_awburst;
  wire [3:0]S_AXI_HP0_awcache;
  wire [3:0]S_AXI_HP0_awid;
  wire [3:0]S_AXI_HP0_awlen;
  wire [1:0]S_AXI_HP0_awlock;
  wire [2:0]S_AXI_HP0_awprot;
  wire [3:0]S_AXI_HP0_awqos;
  wire S_AXI_HP0_awready;
  wire [2:0]S_AXI_HP0_awsize;
  wire S_AXI_HP0_awvalid;
  wire [3:0]S_AXI_HP0_bid;
  wire S_AXI_HP0_bready;
  wire [1:0]S_AXI_HP0_bresp;
  wire S_AXI_HP0_bvalid;
  wire [63:0]S_AXI_HP0_rdata;
  wire [3:0]S_AXI_HP0_rid;
  wire S_AXI_HP0_rlast;
  wire S_AXI_HP0_rready;
  wire [1:0]S_AXI_HP0_rresp;
  wire S_AXI_HP0_rvalid;
  wire [63:0]S_AXI_HP0_wdata;
  wire [3:0]S_AXI_HP0_wid;
  wire S_AXI_HP0_wlast;
  wire S_AXI_HP0_wready;
  wire [7:0]S_AXI_HP0_wstrb;
  wire S_AXI_HP0_wvalid;
  wire S_AXI_HP1_aclk;
  wire [31:0]S_AXI_HP1_araddr;
  wire [1:0]S_AXI_HP1_arburst;
  wire [3:0]S_AXI_HP1_arcache;
  wire [3:0]S_AXI_HP1_arid;
  wire [3:0]S_AXI_HP1_arlen;
  wire [1:0]S_AXI_HP1_arlock;
  wire [2:0]S_AXI_HP1_arprot;
  wire [3:0]S_AXI_HP1_arqos;
  wire S_AXI_HP1_arready;
  wire [2:0]S_AXI_HP1_arsize;
  wire S_AXI_HP1_arvalid;
  wire [31:0]S_AXI_HP1_awaddr;
  wire [1:0]S_AXI_HP1_awburst;
  wire [3:0]S_AXI_HP1_awcache;
  wire [3:0]S_AXI_HP1_awid;
  wire [3:0]S_AXI_HP1_awlen;
  wire [1:0]S_AXI_HP1_awlock;
  wire [2:0]S_AXI_HP1_awprot;
  wire [3:0]S_AXI_HP1_awqos;
  wire S_AXI_HP1_awready;
  wire [2:0]S_AXI_HP1_awsize;
  wire S_AXI_HP1_awvalid;
  wire [3:0]S_AXI_HP1_bid;
  wire S_AXI_HP1_bready;
  wire [1:0]S_AXI_HP1_bresp;
  wire S_AXI_HP1_bvalid;
  wire [63:0]S_AXI_HP1_rdata;
  wire [3:0]S_AXI_HP1_rid;
  wire S_AXI_HP1_rlast;
  wire S_AXI_HP1_rready;
  wire [1:0]S_AXI_HP1_rresp;
  wire S_AXI_HP1_rvalid;
  wire [63:0]S_AXI_HP1_wdata;
  wire [3:0]S_AXI_HP1_wid;
  wire S_AXI_HP1_wlast;
  wire S_AXI_HP1_wready;
  wire [7:0]S_AXI_HP1_wstrb;
  wire S_AXI_HP1_wvalid;
  wire S_AXI_HP2_aclk;
  wire [31:0]S_AXI_HP2_araddr;
  wire [1:0]S_AXI_HP2_arburst;
  wire [3:0]S_AXI_HP2_arcache;
  wire [3:0]S_AXI_HP2_arid;
  wire [3:0]S_AXI_HP2_arlen;
  wire [1:0]S_AXI_HP2_arlock;
  wire [2:0]S_AXI_HP2_arprot;
  wire [3:0]S_AXI_HP2_arqos;
  wire S_AXI_HP2_arready;
  wire [2:0]S_AXI_HP2_arsize;
  wire S_AXI_HP2_arvalid;
  wire [31:0]S_AXI_HP2_awaddr;
  wire [1:0]S_AXI_HP2_awburst;
  wire [3:0]S_AXI_HP2_awcache;
  wire [3:0]S_AXI_HP2_awid;
  wire [3:0]S_AXI_HP2_awlen;
  wire [1:0]S_AXI_HP2_awlock;
  wire [2:0]S_AXI_HP2_awprot;
  wire [3:0]S_AXI_HP2_awqos;
  wire S_AXI_HP2_awready;
  wire [2:0]S_AXI_HP2_awsize;
  wire S_AXI_HP2_awvalid;
  wire [3:0]S_AXI_HP2_bid;
  wire S_AXI_HP2_bready;
  wire [1:0]S_AXI_HP2_bresp;
  wire S_AXI_HP2_bvalid;
  wire [63:0]S_AXI_HP2_rdata;
  wire [3:0]S_AXI_HP2_rid;
  wire S_AXI_HP2_rlast;
  wire S_AXI_HP2_rready;
  wire [1:0]S_AXI_HP2_rresp;
  wire S_AXI_HP2_rvalid;
  wire [63:0]S_AXI_HP2_wdata;
  wire [3:0]S_AXI_HP2_wid;
  wire S_AXI_HP2_wlast;
  wire S_AXI_HP2_wready;
  wire [7:0]S_AXI_HP2_wstrb;
  wire S_AXI_HP2_wvalid;
  wire S_AXI_HP3_aclk;
  wire [31:0]S_AXI_HP3_araddr;
  wire [1:0]S_AXI_HP3_arburst;
  wire [3:0]S_AXI_HP3_arcache;
  wire [3:0]S_AXI_HP3_arid;
  wire [3:0]S_AXI_HP3_arlen;
  wire [1:0]S_AXI_HP3_arlock;
  wire [2:0]S_AXI_HP3_arprot;
  wire [3:0]S_AXI_HP3_arqos;
  wire S_AXI_HP3_arready;
  wire [2:0]S_AXI_HP3_arsize;
  wire S_AXI_HP3_arvalid;
  wire [31:0]S_AXI_HP3_awaddr;
  wire [1:0]S_AXI_HP3_awburst;
  wire [3:0]S_AXI_HP3_awcache;
  wire [3:0]S_AXI_HP3_awid;
  wire [3:0]S_AXI_HP3_awlen;
  wire [1:0]S_AXI_HP3_awlock;
  wire [2:0]S_AXI_HP3_awprot;
  wire [3:0]S_AXI_HP3_awqos;
  wire S_AXI_HP3_awready;
  wire [2:0]S_AXI_HP3_awsize;
  wire S_AXI_HP3_awvalid;
  wire [3:0]S_AXI_HP3_bid;
  wire S_AXI_HP3_bready;
  wire [1:0]S_AXI_HP3_bresp;
  wire S_AXI_HP3_bvalid;
  wire [63:0]S_AXI_HP3_rdata;
  wire [3:0]S_AXI_HP3_rid;
  wire S_AXI_HP3_rlast;
  wire S_AXI_HP3_rready;
  wire [1:0]S_AXI_HP3_rresp;
  wire S_AXI_HP3_rvalid;
  wire [63:0]S_AXI_HP3_wdata;
  wire [3:0]S_AXI_HP3_wid;
  wire S_AXI_HP3_wlast;
  wire S_AXI_HP3_wready;
  wire [7:0]S_AXI_HP3_wstrb;
  wire S_AXI_HP3_wvalid;
  wire Vaux0_v_n;
  wire Vaux0_v_p;
  wire Vaux1_v_n;
  wire Vaux1_v_p;
  wire Vaux8_v_n;
  wire Vaux8_v_p;
  wire Vaux9_v_n;
  wire Vaux9_v_p;
  wire Vp_Vn_v_n;
  wire Vp_Vn_v_p;

  IOBUF GPIO_tri_iobuf_0
       (.I(GPIO_tri_o_0),
        .IO(GPIO_tri_io[0]),
        .O(GPIO_tri_i_0),
        .T(GPIO_tri_t_0));
  IOBUF GPIO_tri_iobuf_1
       (.I(GPIO_tri_o_1),
        .IO(GPIO_tri_io[1]),
        .O(GPIO_tri_i_1),
        .T(GPIO_tri_t_1));
  IOBUF GPIO_tri_iobuf_10
       (.I(GPIO_tri_o_10),
        .IO(GPIO_tri_io[10]),
        .O(GPIO_tri_i_10),
        .T(GPIO_tri_t_10));
  IOBUF GPIO_tri_iobuf_11
       (.I(GPIO_tri_o_11),
        .IO(GPIO_tri_io[11]),
        .O(GPIO_tri_i_11),
        .T(GPIO_tri_t_11));
  IOBUF GPIO_tri_iobuf_12
       (.I(GPIO_tri_o_12),
        .IO(GPIO_tri_io[12]),
        .O(GPIO_tri_i_12),
        .T(GPIO_tri_t_12));
  IOBUF GPIO_tri_iobuf_13
       (.I(GPIO_tri_o_13),
        .IO(GPIO_tri_io[13]),
        .O(GPIO_tri_i_13),
        .T(GPIO_tri_t_13));
  IOBUF GPIO_tri_iobuf_14
       (.I(GPIO_tri_o_14),
        .IO(GPIO_tri_io[14]),
        .O(GPIO_tri_i_14),
        .T(GPIO_tri_t_14));
  IOBUF GPIO_tri_iobuf_15
       (.I(GPIO_tri_o_15),
        .IO(GPIO_tri_io[15]),
        .O(GPIO_tri_i_15),
        .T(GPIO_tri_t_15));
  IOBUF GPIO_tri_iobuf_16
       (.I(GPIO_tri_o_16),
        .IO(GPIO_tri_io[16]),
        .O(GPIO_tri_i_16),
        .T(GPIO_tri_t_16));
  IOBUF GPIO_tri_iobuf_17
       (.I(GPIO_tri_o_17),
        .IO(GPIO_tri_io[17]),
        .O(GPIO_tri_i_17),
        .T(GPIO_tri_t_17));
  IOBUF GPIO_tri_iobuf_18
       (.I(GPIO_tri_o_18),
        .IO(GPIO_tri_io[18]),
        .O(GPIO_tri_i_18),
        .T(GPIO_tri_t_18));
  IOBUF GPIO_tri_iobuf_19
       (.I(GPIO_tri_o_19),
        .IO(GPIO_tri_io[19]),
        .O(GPIO_tri_i_19),
        .T(GPIO_tri_t_19));
  IOBUF GPIO_tri_iobuf_2
       (.I(GPIO_tri_o_2),
        .IO(GPIO_tri_io[2]),
        .O(GPIO_tri_i_2),
        .T(GPIO_tri_t_2));
  IOBUF GPIO_tri_iobuf_20
       (.I(GPIO_tri_o_20),
        .IO(GPIO_tri_io[20]),
        .O(GPIO_tri_i_20),
        .T(GPIO_tri_t_20));
  IOBUF GPIO_tri_iobuf_21
       (.I(GPIO_tri_o_21),
        .IO(GPIO_tri_io[21]),
        .O(GPIO_tri_i_21),
        .T(GPIO_tri_t_21));
  IOBUF GPIO_tri_iobuf_22
       (.I(GPIO_tri_o_22),
        .IO(GPIO_tri_io[22]),
        .O(GPIO_tri_i_22),
        .T(GPIO_tri_t_22));
  IOBUF GPIO_tri_iobuf_23
       (.I(GPIO_tri_o_23),
        .IO(GPIO_tri_io[23]),
        .O(GPIO_tri_i_23),
        .T(GPIO_tri_t_23));
  IOBUF GPIO_tri_iobuf_3
       (.I(GPIO_tri_o_3),
        .IO(GPIO_tri_io[3]),
        .O(GPIO_tri_i_3),
        .T(GPIO_tri_t_3));
  IOBUF GPIO_tri_iobuf_4
       (.I(GPIO_tri_o_4),
        .IO(GPIO_tri_io[4]),
        .O(GPIO_tri_i_4),
        .T(GPIO_tri_t_4));
  IOBUF GPIO_tri_iobuf_5
       (.I(GPIO_tri_o_5),
        .IO(GPIO_tri_io[5]),
        .O(GPIO_tri_i_5),
        .T(GPIO_tri_t_5));
  IOBUF GPIO_tri_iobuf_6
       (.I(GPIO_tri_o_6),
        .IO(GPIO_tri_io[6]),
        .O(GPIO_tri_i_6),
        .T(GPIO_tri_t_6));
  IOBUF GPIO_tri_iobuf_7
       (.I(GPIO_tri_o_7),
        .IO(GPIO_tri_io[7]),
        .O(GPIO_tri_i_7),
        .T(GPIO_tri_t_7));
  IOBUF GPIO_tri_iobuf_8
       (.I(GPIO_tri_o_8),
        .IO(GPIO_tri_io[8]),
        .O(GPIO_tri_i_8),
        .T(GPIO_tri_t_8));
  IOBUF GPIO_tri_iobuf_9
       (.I(GPIO_tri_o_9),
        .IO(GPIO_tri_io[9]),
        .O(GPIO_tri_i_9),
        .T(GPIO_tri_t_9));
  IOBUF SPI0_io0_iobuf
       (.I(SPI0_io0_o),
        .IO(SPI0_io0_io),
        .O(SPI0_io0_i),
        .T(SPI0_io0_t));
  IOBUF SPI0_io1_iobuf
       (.I(SPI0_io1_o),
        .IO(SPI0_io1_io),
        .O(SPI0_io1_i),
        .T(SPI0_io1_t));
  IOBUF SPI0_sck_iobuf
       (.I(SPI0_sck_o),
        .IO(SPI0_sck_io),
        .O(SPI0_sck_i),
        .T(SPI0_sck_t));
  IOBUF SPI0_ss_iobuf
       (.I(SPI0_ss_o),
        .IO(SPI0_ss_io),
        .O(SPI0_ss_i),
        .T(SPI0_ss_t));
  system system_i
       (.CAN0_rx(CAN0_rx),
        .CAN0_tx(CAN0_tx),
        .CAN1_rx(CAN1_rx),
        .CAN1_tx(CAN1_tx),
        .DDR_addr(DDR_addr),
        .DDR_ba(DDR_ba),
        .DDR_cas_n(DDR_cas_n),
        .DDR_ck_n(DDR_ck_n),
        .DDR_ck_p(DDR_ck_p),
        .DDR_cke(DDR_cke),
        .DDR_cs_n(DDR_cs_n),
        .DDR_dm(DDR_dm),
        .DDR_dq(DDR_dq),
        .DDR_dqs_n(DDR_dqs_n),
        .DDR_dqs_p(DDR_dqs_p),
        .DDR_odt(DDR_odt),
        .DDR_ras_n(DDR_ras_n),
        .DDR_reset_n(DDR_reset_n),
        .DDR_we_n(DDR_we_n),
        .FCLK_CLK0(FCLK_CLK0),
        .FCLK_CLK1(FCLK_CLK1),
        .FCLK_CLK2(FCLK_CLK2),
        .FCLK_CLK3(FCLK_CLK3),
        .FCLK_RESET0_N(FCLK_RESET0_N),
        .FCLK_RESET1_N(FCLK_RESET1_N),
        .FCLK_RESET2_N(FCLK_RESET2_N),
        .FCLK_RESET3_N(FCLK_RESET3_N),
        .FIXED_IO_ddr_vrn(FIXED_IO_ddr_vrn),
        .FIXED_IO_ddr_vrp(FIXED_IO_ddr_vrp),
        .FIXED_IO_mio(FIXED_IO_mio),
        .FIXED_IO_ps_clk(FIXED_IO_ps_clk),
        .FIXED_IO_ps_porb(FIXED_IO_ps_porb),
        .FIXED_IO_ps_srstb(FIXED_IO_ps_srstb),
        .GPIO_tri_i({GPIO_tri_i_23,GPIO_tri_i_22,GPIO_tri_i_21,GPIO_tri_i_20,GPIO_tri_i_19,GPIO_tri_i_18,GPIO_tri_i_17,GPIO_tri_i_16,GPIO_tri_i_15,GPIO_tri_i_14,GPIO_tri_i_13,GPIO_tri_i_12,GPIO_tri_i_11,GPIO_tri_i_10,GPIO_tri_i_9,GPIO_tri_i_8,GPIO_tri_i_7,GPIO_tri_i_6,GPIO_tri_i_5,GPIO_tri_i_4,GPIO_tri_i_3,GPIO_tri_i_2,GPIO_tri_i_1,GPIO_tri_i_0}),
        .GPIO_tri_o({GPIO_tri_o_23,GPIO_tri_o_22,GPIO_tri_o_21,GPIO_tri_o_20,GPIO_tri_o_19,GPIO_tri_o_18,GPIO_tri_o_17,GPIO_tri_o_16,GPIO_tri_o_15,GPIO_tri_o_14,GPIO_tri_o_13,GPIO_tri_o_12,GPIO_tri_o_11,GPIO_tri_o_10,GPIO_tri_o_9,GPIO_tri_o_8,GPIO_tri_o_7,GPIO_tri_o_6,GPIO_tri_o_5,GPIO_tri_o_4,GPIO_tri_o_3,GPIO_tri_o_2,GPIO_tri_o_1,GPIO_tri_o_0}),
        .GPIO_tri_t({GPIO_tri_t_23,GPIO_tri_t_22,GPIO_tri_t_21,GPIO_tri_t_20,GPIO_tri_t_19,GPIO_tri_t_18,GPIO_tri_t_17,GPIO_tri_t_16,GPIO_tri_t_15,GPIO_tri_t_14,GPIO_tri_t_13,GPIO_tri_t_12,GPIO_tri_t_11,GPIO_tri_t_10,GPIO_tri_t_9,GPIO_tri_t_8,GPIO_tri_t_7,GPIO_tri_t_6,GPIO_tri_t_5,GPIO_tri_t_4,GPIO_tri_t_3,GPIO_tri_t_2,GPIO_tri_t_1,GPIO_tri_t_0}),
        .M_AXI_GP0_ACLK(M_AXI_GP0_ACLK),
        .M_AXI_GP0_araddr(M_AXI_GP0_araddr),
        .M_AXI_GP0_arburst(M_AXI_GP0_arburst),
        .M_AXI_GP0_arcache(M_AXI_GP0_arcache),
        .M_AXI_GP0_arid(M_AXI_GP0_arid),
        .M_AXI_GP0_arlen(M_AXI_GP0_arlen),
        .M_AXI_GP0_arlock(M_AXI_GP0_arlock),
        .M_AXI_GP0_arprot(M_AXI_GP0_arprot),
        .M_AXI_GP0_arqos(M_AXI_GP0_arqos),
        .M_AXI_GP0_arready(M_AXI_GP0_arready),
        .M_AXI_GP0_arsize(M_AXI_GP0_arsize),
        .M_AXI_GP0_arvalid(M_AXI_GP0_arvalid),
        .M_AXI_GP0_awaddr(M_AXI_GP0_awaddr),
        .M_AXI_GP0_awburst(M_AXI_GP0_awburst),
        .M_AXI_GP0_awcache(M_AXI_GP0_awcache),
        .M_AXI_GP0_awid(M_AXI_GP0_awid),
        .M_AXI_GP0_awlen(M_AXI_GP0_awlen),
        .M_AXI_GP0_awlock(M_AXI_GP0_awlock),
        .M_AXI_GP0_awprot(M_AXI_GP0_awprot),
        .M_AXI_GP0_awqos(M_AXI_GP0_awqos),
        .M_AXI_GP0_awready(M_AXI_GP0_awready),
        .M_AXI_GP0_awsize(M_AXI_GP0_awsize),
        .M_AXI_GP0_awvalid(M_AXI_GP0_awvalid),
        .M_AXI_GP0_bid(M_AXI_GP0_bid),
        .M_AXI_GP0_bready(M_AXI_GP0_bready),
        .M_AXI_GP0_bresp(M_AXI_GP0_bresp),
        .M_AXI_GP0_bvalid(M_AXI_GP0_bvalid),
        .M_AXI_GP0_rdata(M_AXI_GP0_rdata),
        .M_AXI_GP0_rid(M_AXI_GP0_rid),
        .M_AXI_GP0_rlast(M_AXI_GP0_rlast),
        .M_AXI_GP0_rready(M_AXI_GP0_rready),
        .M_AXI_GP0_rresp(M_AXI_GP0_rresp),
        .M_AXI_GP0_rvalid(M_AXI_GP0_rvalid),
        .M_AXI_GP0_wdata(M_AXI_GP0_wdata),
        .M_AXI_GP0_wid(M_AXI_GP0_wid),
        .M_AXI_GP0_wlast(M_AXI_GP0_wlast),
        .M_AXI_GP0_wready(M_AXI_GP0_wready),
        .M_AXI_GP0_wstrb(M_AXI_GP0_wstrb),
        .M_AXI_GP0_wvalid(M_AXI_GP0_wvalid),
        .SPI0_io0_i(SPI0_io0_i),
        .SPI0_io0_o(SPI0_io0_o),
        .SPI0_io0_t(SPI0_io0_t),
        .SPI0_io1_i(SPI0_io1_i),
        .SPI0_io1_o(SPI0_io1_o),
        .SPI0_io1_t(SPI0_io1_t),
        .SPI0_sck_i(SPI0_sck_i),
        .SPI0_sck_o(SPI0_sck_o),
        .SPI0_sck_t(SPI0_sck_t),
        .SPI0_ss1_o(SPI0_ss1_o),
        .SPI0_ss2_o(SPI0_ss2_o),
        .SPI0_ss_i(SPI0_ss_i),
        .SPI0_ss_o(SPI0_ss_o),
        .SPI0_ss_t(SPI0_ss_t),
        .S_AXI_HP0_aclk(S_AXI_HP0_aclk),
        .S_AXI_HP0_araddr(S_AXI_HP0_araddr),
        .S_AXI_HP0_arburst(S_AXI_HP0_arburst),
        .S_AXI_HP0_arcache(S_AXI_HP0_arcache),
        .S_AXI_HP0_arid(S_AXI_HP0_arid),
        .S_AXI_HP0_arlen(S_AXI_HP0_arlen),
        .S_AXI_HP0_arlock(S_AXI_HP0_arlock),
        .S_AXI_HP0_arprot(S_AXI_HP0_arprot),
        .S_AXI_HP0_arqos(S_AXI_HP0_arqos),
        .S_AXI_HP0_arready(S_AXI_HP0_arready),
        .S_AXI_HP0_arsize(S_AXI_HP0_arsize),
        .S_AXI_HP0_arvalid(S_AXI_HP0_arvalid),
        .S_AXI_HP0_awaddr(S_AXI_HP0_awaddr),
        .S_AXI_HP0_awburst(S_AXI_HP0_awburst),
        .S_AXI_HP0_awcache(S_AXI_HP0_awcache),
        .S_AXI_HP0_awid(S_AXI_HP0_awid),
        .S_AXI_HP0_awlen(S_AXI_HP0_awlen),
        .S_AXI_HP0_awlock(S_AXI_HP0_awlock),
        .S_AXI_HP0_awprot(S_AXI_HP0_awprot),
        .S_AXI_HP0_awqos(S_AXI_HP0_awqos),
        .S_AXI_HP0_awready(S_AXI_HP0_awready),
        .S_AXI_HP0_awsize(S_AXI_HP0_awsize),
        .S_AXI_HP0_awvalid(S_AXI_HP0_awvalid),
        .S_AXI_HP0_bid(S_AXI_HP0_bid),
        .S_AXI_HP0_bready(S_AXI_HP0_bready),
        .S_AXI_HP0_bresp(S_AXI_HP0_bresp),
        .S_AXI_HP0_bvalid(S_AXI_HP0_bvalid),
        .S_AXI_HP0_rdata(S_AXI_HP0_rdata),
        .S_AXI_HP0_rid(S_AXI_HP0_rid),
        .S_AXI_HP0_rlast(S_AXI_HP0_rlast),
        .S_AXI_HP0_rready(S_AXI_HP0_rready),
        .S_AXI_HP0_rresp(S_AXI_HP0_rresp),
        .S_AXI_HP0_rvalid(S_AXI_HP0_rvalid),
        .S_AXI_HP0_wdata(S_AXI_HP0_wdata),
        .S_AXI_HP0_wid(S_AXI_HP0_wid),
        .S_AXI_HP0_wlast(S_AXI_HP0_wlast),
        .S_AXI_HP0_wready(S_AXI_HP0_wready),
        .S_AXI_HP0_wstrb(S_AXI_HP0_wstrb),
        .S_AXI_HP0_wvalid(S_AXI_HP0_wvalid),
        .S_AXI_HP1_aclk(S_AXI_HP1_aclk),
        .S_AXI_HP1_araddr(S_AXI_HP1_araddr),
        .S_AXI_HP1_arburst(S_AXI_HP1_arburst),
        .S_AXI_HP1_arcache(S_AXI_HP1_arcache),
        .S_AXI_HP1_arid(S_AXI_HP1_arid),
        .S_AXI_HP1_arlen(S_AXI_HP1_arlen),
        .S_AXI_HP1_arlock(S_AXI_HP1_arlock),
        .S_AXI_HP1_arprot(S_AXI_HP1_arprot),
        .S_AXI_HP1_arqos(S_AXI_HP1_arqos),
        .S_AXI_HP1_arready(S_AXI_HP1_arready),
        .S_AXI_HP1_arsize(S_AXI_HP1_arsize),
        .S_AXI_HP1_arvalid(S_AXI_HP1_arvalid),
        .S_AXI_HP1_awaddr(S_AXI_HP1_awaddr),
        .S_AXI_HP1_awburst(S_AXI_HP1_awburst),
        .S_AXI_HP1_awcache(S_AXI_HP1_awcache),
        .S_AXI_HP1_awid(S_AXI_HP1_awid),
        .S_AXI_HP1_awlen(S_AXI_HP1_awlen),
        .S_AXI_HP1_awlock(S_AXI_HP1_awlock),
        .S_AXI_HP1_awprot(S_AXI_HP1_awprot),
        .S_AXI_HP1_awqos(S_AXI_HP1_awqos),
        .S_AXI_HP1_awready(S_AXI_HP1_awready),
        .S_AXI_HP1_awsize(S_AXI_HP1_awsize),
        .S_AXI_HP1_awvalid(S_AXI_HP1_awvalid),
        .S_AXI_HP1_bid(S_AXI_HP1_bid),
        .S_AXI_HP1_bready(S_AXI_HP1_bready),
        .S_AXI_HP1_bresp(S_AXI_HP1_bresp),
        .S_AXI_HP1_bvalid(S_AXI_HP1_bvalid),
        .S_AXI_HP1_rdata(S_AXI_HP1_rdata),
        .S_AXI_HP1_rid(S_AXI_HP1_rid),
        .S_AXI_HP1_rlast(S_AXI_HP1_rlast),
        .S_AXI_HP1_rready(S_AXI_HP1_rready),
        .S_AXI_HP1_rresp(S_AXI_HP1_rresp),
        .S_AXI_HP1_rvalid(S_AXI_HP1_rvalid),
        .S_AXI_HP1_wdata(S_AXI_HP1_wdata),
        .S_AXI_HP1_wid(S_AXI_HP1_wid),
        .S_AXI_HP1_wlast(S_AXI_HP1_wlast),
        .S_AXI_HP1_wready(S_AXI_HP1_wready),
        .S_AXI_HP1_wstrb(S_AXI_HP1_wstrb),
        .S_AXI_HP1_wvalid(S_AXI_HP1_wvalid),
        .S_AXI_HP2_aclk(S_AXI_HP2_aclk),
        .S_AXI_HP2_araddr(S_AXI_HP2_araddr),
        .S_AXI_HP2_arburst(S_AXI_HP2_arburst),
        .S_AXI_HP2_arcache(S_AXI_HP2_arcache),
        .S_AXI_HP2_arid(S_AXI_HP2_arid),
        .S_AXI_HP2_arlen(S_AXI_HP2_arlen),
        .S_AXI_HP2_arlock(S_AXI_HP2_arlock),
        .S_AXI_HP2_arprot(S_AXI_HP2_arprot),
        .S_AXI_HP2_arqos(S_AXI_HP2_arqos),
        .S_AXI_HP2_arready(S_AXI_HP2_arready),
        .S_AXI_HP2_arsize(S_AXI_HP2_arsize),
        .S_AXI_HP2_arvalid(S_AXI_HP2_arvalid),
        .S_AXI_HP2_awaddr(S_AXI_HP2_awaddr),
        .S_AXI_HP2_awburst(S_AXI_HP2_awburst),
        .S_AXI_HP2_awcache(S_AXI_HP2_awcache),
        .S_AXI_HP2_awid(S_AXI_HP2_awid),
        .S_AXI_HP2_awlen(S_AXI_HP2_awlen),
        .S_AXI_HP2_awlock(S_AXI_HP2_awlock),
        .S_AXI_HP2_awprot(S_AXI_HP2_awprot),
        .S_AXI_HP2_awqos(S_AXI_HP2_awqos),
        .S_AXI_HP2_awready(S_AXI_HP2_awready),
        .S_AXI_HP2_awsize(S_AXI_HP2_awsize),
        .S_AXI_HP2_awvalid(S_AXI_HP2_awvalid),
        .S_AXI_HP2_bid(S_AXI_HP2_bid),
        .S_AXI_HP2_bready(S_AXI_HP2_bready),
        .S_AXI_HP2_bresp(S_AXI_HP2_bresp),
        .S_AXI_HP2_bvalid(S_AXI_HP2_bvalid),
        .S_AXI_HP2_rdata(S_AXI_HP2_rdata),
        .S_AXI_HP2_rid(S_AXI_HP2_rid),
        .S_AXI_HP2_rlast(S_AXI_HP2_rlast),
        .S_AXI_HP2_rready(S_AXI_HP2_rready),
        .S_AXI_HP2_rresp(S_AXI_HP2_rresp),
        .S_AXI_HP2_rvalid(S_AXI_HP2_rvalid),
        .S_AXI_HP2_wdata(S_AXI_HP2_wdata),
        .S_AXI_HP2_wid(S_AXI_HP2_wid),
        .S_AXI_HP2_wlast(S_AXI_HP2_wlast),
        .S_AXI_HP2_wready(S_AXI_HP2_wready),
        .S_AXI_HP2_wstrb(S_AXI_HP2_wstrb),
        .S_AXI_HP2_wvalid(S_AXI_HP2_wvalid),
        .S_AXI_HP3_aclk(S_AXI_HP3_aclk),
        .S_AXI_HP3_araddr(S_AXI_HP3_araddr),
        .S_AXI_HP3_arburst(S_AXI_HP3_arburst),
        .S_AXI_HP3_arcache(S_AXI_HP3_arcache),
        .S_AXI_HP3_arid(S_AXI_HP3_arid),
        .S_AXI_HP3_arlen(S_AXI_HP3_arlen),
        .S_AXI_HP3_arlock(S_AXI_HP3_arlock),
        .S_AXI_HP3_arprot(S_AXI_HP3_arprot),
        .S_AXI_HP3_arqos(S_AXI_HP3_arqos),
        .S_AXI_HP3_arready(S_AXI_HP3_arready),
        .S_AXI_HP3_arsize(S_AXI_HP3_arsize),
        .S_AXI_HP3_arvalid(S_AXI_HP3_arvalid),
        .S_AXI_HP3_awaddr(S_AXI_HP3_awaddr),
        .S_AXI_HP3_awburst(S_AXI_HP3_awburst),
        .S_AXI_HP3_awcache(S_AXI_HP3_awcache),
        .S_AXI_HP3_awid(S_AXI_HP3_awid),
        .S_AXI_HP3_awlen(S_AXI_HP3_awlen),
        .S_AXI_HP3_awlock(S_AXI_HP3_awlock),
        .S_AXI_HP3_awprot(S_AXI_HP3_awprot),
        .S_AXI_HP3_awqos(S_AXI_HP3_awqos),
        .S_AXI_HP3_awready(S_AXI_HP3_awready),
        .S_AXI_HP3_awsize(S_AXI_HP3_awsize),
        .S_AXI_HP3_awvalid(S_AXI_HP3_awvalid),
        .S_AXI_HP3_bid(S_AXI_HP3_bid),
        .S_AXI_HP3_bready(S_AXI_HP3_bready),
        .S_AXI_HP3_bresp(S_AXI_HP3_bresp),
        .S_AXI_HP3_bvalid(S_AXI_HP3_bvalid),
        .S_AXI_HP3_rdata(S_AXI_HP3_rdata),
        .S_AXI_HP3_rid(S_AXI_HP3_rid),
        .S_AXI_HP3_rlast(S_AXI_HP3_rlast),
        .S_AXI_HP3_rready(S_AXI_HP3_rready),
        .S_AXI_HP3_rresp(S_AXI_HP3_rresp),
        .S_AXI_HP3_rvalid(S_AXI_HP3_rvalid),
        .S_AXI_HP3_wdata(S_AXI_HP3_wdata),
        .S_AXI_HP3_wid(S_AXI_HP3_wid),
        .S_AXI_HP3_wlast(S_AXI_HP3_wlast),
        .S_AXI_HP3_wready(S_AXI_HP3_wready),
        .S_AXI_HP3_wstrb(S_AXI_HP3_wstrb),
        .S_AXI_HP3_wvalid(S_AXI_HP3_wvalid),
        .Vaux0_v_n(Vaux0_v_n),
        .Vaux0_v_p(Vaux0_v_p),
        .Vaux1_v_n(Vaux1_v_n),
        .Vaux1_v_p(Vaux1_v_p),
        .Vaux8_v_n(Vaux8_v_n),
        .Vaux8_v_p(Vaux8_v_p),
        .Vaux9_v_n(Vaux9_v_n),
        .Vaux9_v_p(Vaux9_v_p),
        .Vp_Vn_v_n(Vp_Vn_v_n),
        .Vp_Vn_v_p(Vp_Vn_v_p));
endmodule
