# master-thesis
Code for masterthesis on 4G LTE/5G NSA/5G SA mobile networks.

Run everything with sudo - root is needed for loopback.
Python3 + kivy framework downloaded, everything run in Linux Terminal - SCAT requirement.

1. Run controller.py to launch application.
<pre> 2. 
   a. Run SCAT to listen on loopback: ```scat -t qc -u -a BUS:Device i 0 ``` *(Make sure to replace `BUS:Device` with the correct values found via `lsusb`)* 
   b. Run SCAT using the Quectel modem: ```scat -t qc -s /dev/ttyUSB0 ``` 
   b2. Set up a screen for raw AT commands: ```screen /dev/ttyUSB2 115200 ``` 
   #### Quectel 520NG-L AT Commands (for RG520N, RG525F, RG5x0F, RM5x0N series): - Manual uploaded in repo.
   
   ```
   AT+COPS=2 # Deregister UE 
   AT+COPS=0 # Register 
   UE AT+QNWPREFCFG="mode_pref",NR5G # Prefer LTE 
   AT+QNWPREFCFG="mode_pref",LTE # Prefer 5G NR 
   AT+QENG="servingcell" # Check cell info 
   AT+QSIMDET=1,1 # Auto connect SIM after insert 
   AT+CPIN=XXXX # 
   Enter SIM PIN (if required) 
   ``` 
</pre>
  
4. Beneficial to also use Wireshark to analyze individual packets further. Listen on loopback. To listen on 5G packets use plugin https://github.com/fgsect/scat/blob/master/wireshark/scat.lua in wireshark.


Code currently captures        

def capture_identifiers(queue):
    debug_print("capture_identifiers started.")

    gsm_a_imeisv_cmd = [
        "tshark", "-i", "lo",
        "-Y", "gsm_a.imeisv and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "gsm_a.imeisv",
        "-E", "separator=,", "-l", "-Q"
    ]
    paging_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.PagingRecord_element and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.m_TMSI",
        "-e", "lte-rrc.IMSI_Digit",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.MCC_MNC_Digit",
        "-e", "lte-rrc.trackingAreaCode",
        "-e", "lte-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib5g_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T", "fields",
        "-e", "nr-rrc.MCC_MNC_Digit",
        "-e", "nr-rrc.trackingAreaCode",
        "-e", "nr-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    nas_eps_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nas-eps and not icmp",
        "-T", "fields",
        "-e", "nas-eps.emm.m_tmsi",
        "-e", "e212.imsi",
        "-e", "e212.assoc.imsi",
        "-e", "nas-eps.emm.mme_grp_id",
        "-e", "nas-eps.emm.mme_code",
        "-e", "nas-eps.nas_msg_emm_type",
        "-E", "separator=\t", "-l", "-Q"
    ]
    nas_5gs_cmd = [
        "tshark", "-i", "lo",
        "-Y", "(nas-5gs or nr-rrc.ng_5G_S_TMSI_Part1 or nr-rrc.ng_5G_S_TMSI_Part2 or nr-rrc.randomValue) and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nas-5gs.5g_tmsi",
        "-e", "nas-5gs.mm.suci.msin",
        "-e", "nas-5gs.mm.imeisv",
        "-e", "nas-5gs.mm.message_type",
        "-e", "nas-5gs.mm.5gs_reg_type",
        "-e", "nr-rrc.ng_5G_S_TMSI_Part1",
        "-e", "nr-rrc.ng_5G_S_TMSI_Part2",
        "-e", "nr-rrc.randomValue",
        "-E", "separator=\t", "-l", "-Q"
    ]
    sa_paging_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc.pagingRecordList and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nr-rrc.ng_5G_S_TMSI",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib5g_sa_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nr-rrc.MCC_MNC_Digit",
        "-e", "nr-rrc.trackingAreaCode",
        "-e", "nr-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    rrc_newueid_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.newUE_Identity and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.newUE_Identity",
        "-E", "separator=,", "-l", "-Q"
    ]
    # EXACT command that works for RRCConnectionRequest:
    rrc_connreq_merged_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.rrcConnectionRequest_element and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.randomValue",
        "-e", "lte-rrc.mmec",
        "-e", "lte-rrc.m_TMSI",
        "-E", "separator=,", "-l"
    ]


Pagings, SIBs, Attach requests, deattaches, accepts, registration, deregistration, identity responses, mme codes, mme group ids, cell identities, TACs, MNC, MCC and more...

Details tab currently tracks count, lifespan, CID, SIB, TAC, etc. Every table header can be sorted from high->low or low->high.
As SIB and cell information is not sent in the broadcasted paging messages. This information is taken from the connected ue.

Would advise to use show top 50 for ID's if tracking is being done - as the application may lag.
Running the code between two network cells or TA can also cause lag as this generates a lot of communication.
