--------------------------------------------------------------------------------
-- Company: FE
-- Engineer: A. Trost
--
-- Design Name: proc
-- Project Name: DIVS2021, Red Pitaya classic signal processing
-- Target Device: Red Pitaya
-- Tool versions: Vivado 2019
-- Description: waveform scaling ASG
-- Sys Registers: 4030_1000 ID; 1004 a, 1008 b
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.all;
use IEEE.NUMERIC_STD.all;

entity proc is
  port (
    clk_i   : in  std_logic;                      -- bus clock 
    rstn_i  : in  std_logic;                      -- bus reset - active low
    dat_a_i, dat_b_i  : in  std_logic_vector(13 downto 0);
	dat_a_o, dat_b_o  : out std_logic_vector(13 downto 0); -- output
	  
    sys_addr  : in  std_logic_vector(31 downto 0);  -- bus address
    sys_wdata : in  std_logic_vector(31 downto 0);  -- bus write data          
    sys_wen   : in  std_logic;                      -- bus write enable
    sys_ren   : in  std_logic;                      -- bus read enable
    sys_rdata : out std_logic_vector(31 downto 0);  -- bus read data
    sys_err   : out std_logic;                      -- bus error indicator
    sys_ack   : out std_logic                      -- bus acknowledge signal
    );
end proc;

architecture Behavioral of proc is
 signal a, b: std_logic_vector(7 downto 0); -- amplitude registers
 signal mul_a, mul_b: signed(22 downto 0);
begin

-- multiply signed inputs with 8-bit register, register values are unsigned 
mul_a <= signed(dat_a_i) * signed('0' & a);
mul_b <= signed(dat_b_i) * signed('0' & b);

-- divide by 16 (multiplication format 4.4), possible output overflow 
dat_a_o <= std_logic_vector(mul_a(17 downto 4)); 
dat_b_o <= std_logic_vector(mul_b(17 downto 4));

-- read data mux
with sys_addr(19 downto 0) select
   sys_rdata <= X"FE020210" when x"01000",   -- ID
                X"000000" & a when x"01004", -- 8-bit amplitude
                X"000000" & b when x"01008", -- 8-bit amplitude
                X"00000000" when others;

pbus: process(clk_i, rstn_i)
begin
 if rstn_i = '0' then
   a <= x"10";
   b <= x"10";
 elsif rising_edge(clk_i) then  
  -- write system bus
  if sys_wen='1' then
	if sys_addr(19 downto 0)=X"01004" then
		a <= sys_wdata(7 downto 0);
	elsif sys_addr(19 downto 0)=X"01008" then
		b <= sys_wdata(7 downto 0);
    end if;
  end if;  

  -- acknowledge transactions
  if (sys_wen or sys_ren)='1' then
    sys_ack <= '1';
  else
    sys_ack <= '0';
  end if;
  sys_err <= '0';
  
 end if;
end process;

end Behavioral;